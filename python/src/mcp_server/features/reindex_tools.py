"""Reindex MCP tools for incremental file re-indexing (ADR-016).

Provides tools for manually triggering re-indexing of specific files
or all modified files in the working tree.
"""

import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from src.server.config.logfire_config import get_logger
from src.server.services.file_watcher_service import (
    FileWatcherService,
    WatcherConfig,
    reindex_single_file,
    IndexStatus,
)
from src.server.services.file_watcher_config import get_watcher_config
from src.server.services.database import get_database_connector
from src.server.services.search.working_tree_search_service import (
    search_working_tree_chunks,
    search_all_chunks,
    get_working_tree_stats,
)

logger = get_logger(__name__)

# Check if we're in test mode
_TEST_MODE = os.environ.get("TEST_MODE", "false").lower() == "true"

# Global watcher service instance
_watcher_service: FileWatcherService | None = None


def get_watcher_service() -> FileWatcherService:
    """Get or create the global FileWatcherService instance."""
    global _watcher_service
    if _watcher_service is None:
        config = get_watcher_config()
        _watcher_service = FileWatcherService(config)
        logger.info(f"Created FileWatcherService (enabled={config.enabled})")
    return _watcher_service


def register_reindex_tools(mcp: FastMCP) -> None:
    """Register reindex MCP tools."""
    logger.info("registering_reindex_tools")

    @mcp.tool()
    async def reindex_file(
        repo_id: str,
        filepath: str,
    ) -> dict[str, Any]:
        """
        Manually trigger re-indexing of a specific file.

        Use when:
        - File watcher is not running
        - You want to force re-index after bulk edits
        - You need to confirm current state is indexed before a search

        Args:
            repo_id: Repository UUID
            filepath: Path relative to repo root

        Returns:
            Dict with reindex result:
            - status: "reindexed" | "unchanged" | "skipped"
            - chunks_updated: Number of chunks updated
            - embedding_ms: Time taken in milliseconds
            - error: Error message if any

        Example:
            >>> await reindex_file(
            ...     repo_id="uuid",
            ...     filepath="src/auth.py"
            ... )
        """
        try:
            from src.mcp_server import worktree_context

            repo_root = worktree_context.get_repo_root() or os.getcwd()

            result = await reindex_single_file(
                repo_id=repo_id,
                filepath=filepath,
                repo_root=repo_root,
            )

            return {
                "success": True,
                "status": result.status.value,
                "filepath": filepath,
                "chunks_updated": result.chunks_updated,
                "embedding_ms": result.embedding_ms,
                "error": result.error,
            }

        except Exception as e:
            logger.exception("reindex_file_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
                "filepath": filepath,
                "status": "skipped",
            }

    @mcp.tool()
    async def reindex_working_tree(
        repo_id: str,
        paths: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Re-index all modified files in the working tree.

        Compares current file state against last indexed SHA.
        Only re-embeds files that have actually changed.

        Args:
            repo_id: Repository UUID
            paths: Optional list of specific paths to check (None = all watched files)

        Returns:
            Dict with reindex results:
            - total_files: Number of files processed
            - reindexed: Number of files re-indexed
            - unchanged: Number of files unchanged
            - skipped: Number of files skipped
            - results: List of individual results

        Example:
            >>> await reindex_working_tree(repo_id="uuid")
            >>> await reindex_working_tree(repo_id="uuid", paths=["src/auth.py"])
        """
        try:
            from src.mcp_server import worktree_context

            repo_root = worktree_context.get_repo_root() or os.getcwd()

            service = get_watcher_service()
            results = await service.reindex_all_modified(
                repo_id=repo_id,
                repo_root=repo_root,
                paths=paths,
            )

            summary = {
                "total_files": len(results),
                "reindexed": sum(1 for r in results if r.status == IndexStatus.REINDEXED),
                "unchanged": sum(1 for r in results if r.status == IndexStatus.UNCHANGED),
                "skipped": sum(1 for r in results if r.status == IndexStatus.SKIPPED),
            }

            return {
                "success": True,
                **summary,
                "results": [
                    {
                        "status": r.status.value,
                        "filepath": r.filepath,
                        "chunks_updated": r.chunks_updated,
                        "error": r.error,
                    }
                    for r in results
                ],
            }

        except Exception as e:
            logger.exception("reindex_working_tree_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
            }

    @mcp.tool()
    async def replace_working_tree_chunks_on_commit(
        repo_id: str,
        commit_sha: str,
    ) -> dict[str, Any]:
        """
        Replace working_tree chunks with committed chunks.

        Called automatically after commit_with_review() to ensure
        working_tree chunks are promoted to committed state.

        Args:
            repo_id: Repository UUID
            commit_sha: The commit SHA to associate with the chunks

        Returns:
            Dict with replacement results

        Example:
            >>> await replace_working_tree_chunks_on_commit(
            ...     repo_id="uuid",
            ...     commit_sha="abc1234"
            ... )
        """
        try:
            db = get_database_connector()

            # Get all working_tree chunks for this repo
            chunks = await db.fetch(
                """
                SELECT id, file_path, chunk_index, content, token_count
                FROM archon_chunks
                WHERE repo_id = $1 AND source = 'working_tree'
                """,
                repo_id,
            )

            if not chunks:
                return {
                    "success": True,
                    "message": "No working_tree chunks to replace",
                    "replaced_count": 0,
                }

            # Update working_tree chunks to committed
            count = await db.fetchval(
                """
                UPDATE archon_chunks
                SET source = 'committed', commit_sha = $2
                WHERE repo_id = $1 AND source = 'working_tree'
                RETURNING COUNT(*)
                """,
                repo_id,
                commit_sha,
            )

            return {
                "success": True,
                "replaced_count": count or 0,
                "commit_sha": commit_sha[:8],
            }

        except Exception as e:
            logger.exception("replace_working_tree_chunks_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
            }

    @mcp.tool()
    async def search_working_tree(
        repo_id: str,
        query: str,
        top_k: int = 10,
        file_path_filter: str | None = None,
    ) -> dict[str, Any]:
        """
        Search working tree chunks by semantic similarity.

        Searches only the current working state, not committed state.
        Requires embeddings to be generated via reindex_file() or reindex_working_tree() first.

        Args:
            repo_id: Repository UUID
            query: Natural language search query
            top_k: Number of results to return (default 10)
            file_path_filter: Optional file path filter (LIKE pattern, e.g., "src/%.py")

        Returns:
            Dict with search results:
            - results: List of matching chunks with similarity scores
            - count: Number of results returned

        Example:
            >>> await search_working_tree(
            ...     repo_id="uuid",
            ...     query="authentication logic",
            ...     file_path_filter="src/auth/%"
            ... )
        """
        try:
            results = await search_working_tree_chunks(
                query=query,
                repo_id=repo_id,
                top_k=top_k,
                file_path_filter=file_path_filter,
            )

            return {
                "success": True,
                "results": results,
                "count": len(results),
            }

        except Exception as e:
            logger.exception("search_working_tree_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
                "results": [],
                "count": 0,
            }

    @mcp.tool()
    async def search_all_states(
        repo_id: str,
        query: str,
        top_k: int = 10,
        include_working_tree: bool = True,
        include_committed: bool = True,
        file_path_filter: str | None = None,
    ) -> dict[str, Any]:
        """
        Search both working tree and committed chunks by semantic similarity.

        Returns results from both states, allowing agents to see current
        working state alongside committed state.

        Args:
            repo_id: Repository UUID
            query: Natural language search query
            top_k: Number of results to return (default 10)
            include_working_tree: Include working_tree chunks (default True)
            include_committed: Include committed chunks (default True)
            file_path_filter: Optional file path filter (LIKE pattern)

        Returns:
            Dict with search results from both states

        Example:
            >>> await search_all_states(
            ...     repo_id="uuid",
            ...     query="database connection",
            ...     include_working_tree=True,
            ...     include_committed=True
            ... )
        """
        try:
            results = await search_all_chunks(
                query=query,
                repo_id=repo_id,
                top_k=top_k,
                include_working_tree=include_working_tree,
                include_committed=include_committed,
                file_path_filter=file_path_filter,
            )

            working_tree_count = sum(1 for r in results if r["source"] == "working_tree")
            committed_count = sum(1 for r in results if r["source"] == "committed")

            return {
                "success": True,
                "results": results,
                "count": len(results),
                "working_tree_count": working_tree_count,
                "committed_count": committed_count,
            }

        except Exception as e:
            logger.exception("search_all_states_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
                "results": [],
                "count": 0,
            }

    @mcp.tool()
    async def working_tree_stats(
        repo_id: str,
    ) -> dict[str, Any]:
        """
        Get statistics about working tree chunks.

        Returns counts of chunks by source (working_tree vs committed),
        files with working_tree chunks, and embedding status.

        Args:
            repo_id: Repository UUID

        Returns:
            Dict with working tree statistics

        Example:
            >>> await working_tree_stats(repo_id="uuid")
        """
        try:
            stats = await get_working_tree_stats(repo_id)
            return stats

        except Exception as e:
            logger.exception("working_tree_stats_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
            }

    logger.info("reindex_tools_registered")
