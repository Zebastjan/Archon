"""Working Tree Search Service.

Provides semantic search over working_tree chunks with embeddings.
Enables agents to search the current working state, not just committed state.
"""

import json
from typing import Any

from src.server.config.logfire_config import get_logger
from src.server.services.database import get_database_connector
from src.server.services.embeddings.unified_embedding_service import get_unified_embedding_service

logger = get_logger(__name__)


async def search_working_tree_chunks(
    query: str,
    repo_id: str,
    top_k: int = 10,
    file_path_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Search working_tree chunks by semantic similarity.

    Args:
        query: Search query text
        repo_id: Repository UUID to search within
        top_k: Number of results to return
        file_path_filter: Optional file path filter (LIKE pattern)

    Returns:
        List of matching chunks with similarity scores
    """
    try:
        # Generate query embedding
        embedding_service = get_unified_embedding_service()
        query_embedding = await embedding_service.generate(query, use_cache=True)

        db = get_database_connector()

        # Convert embedding to string for pgvector
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        # Search working_tree chunks with embeddings
        # This query joins archon_chunks with archon_embeddings
        results = await db.fetch(
            """
            SELECT
                c.id,
                c.file_path,
                c.chunk_index,
                c.content,
                c.token_count,
                1 - (e.vector <=> $1::vector) AS similarity
            FROM archon_chunks c
            JOIN archon_embeddings e ON e.item_id = c.id::text AND e.item_type = 'chunk'
            WHERE c.repo_id = $2
              AND c.source = 'working_tree'
              AND ($3::text IS NULL OR c.file_path LIKE $3)
            ORDER BY e.vector <=> $1::vector
            LIMIT $4
            """,
            embedding_str,
            repo_id,
            file_path_filter,
            top_k,
        )

        return [
            {
                "chunk_id": str(r["id"]),
                "file_path": r["file_path"],
                "chunk_index": r["chunk_index"],
                "content": r["content"],
                "token_count": r["token_count"],
                "similarity": float(r["similarity"]),
                "source": "working_tree",
            }
            for r in results
        ]

    except Exception as e:
        logger.error(f"Working tree search failed: {e}")
        return []


async def search_all_chunks(
    query: str,
    repo_id: str,
    top_k: int = 10,
    include_working_tree: bool = True,
    include_committed: bool = True,
    file_path_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Search all chunks (both working_tree and committed) by semantic similarity.

    Args:
        query: Search query text
        repo_id: Repository UUID to search within
        top_k: Number of results to return
        include_working_tree: Include working_tree chunks
        include_committed: Include committed chunks
        file_path_filter: Optional file path filter (LIKE pattern)

    Returns:
        List of matching chunks with similarity scores
    """
    try:
        # Generate query embedding
        embedding_service = get_unified_embedding_service()
        query_embedding = await embedding_service.generate(query, use_cache=True)

        db = get_database_connector()

        # Convert embedding to string for pgvector
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        # Build source filter
        source_conditions = []
        if include_working_tree:
            source_conditions.append("'working_tree'")
        if include_committed:
            source_conditions.append("'committed'")

        if not source_conditions:
            return []

        source_filter = ",".join(source_conditions)

        # Search chunks with embeddings
        results = await db.fetch(
            f"""
            SELECT
                c.id,
                c.file_path,
                c.chunk_index,
                c.content,
                c.token_count,
                c.source,
                c.commit_sha,
                1 - (e.vector <=> $1::vector) AS similarity
            FROM archon_chunks c
            JOIN archon_embeddings e ON e.item_id = c.id::text AND e.item_type = 'chunk'
            WHERE c.repo_id = $2
              AND c.source IN ({source_filter})
              AND ($3::text IS NULL OR c.file_path LIKE $3)
            ORDER BY e.vector <=> $1::vector
            LIMIT $4
            """,
            embedding_str,
            repo_id,
            file_path_filter,
            top_k,
        )

        return [
            {
                "chunk_id": str(r["id"]),
                "file_path": r["file_path"],
                "chunk_index": r["chunk_index"],
                "content": r["content"],
                "token_count": r["token_count"],
                "source": r["source"],
                "commit_sha": r.get("commit_sha"),
                "similarity": float(r["similarity"]),
            }
            for r in results
        ]

    except Exception as e:
        logger.error(f"All chunks search failed: {e}")
        return []


async def get_working_tree_stats(repo_id: str) -> dict[str, Any]:
    """Get statistics about working_tree chunks for a repository.

    Args:
        repo_id: Repository UUID

    Returns:
        Dictionary with statistics
    """
    try:
        db = get_database_connector()

        # Count chunks by source
        chunk_counts = await db.fetch(
            """
            SELECT source, COUNT(*) as count
            FROM archon_chunks
            WHERE repo_id = $1
            GROUP BY source
            """,
            repo_id,
        )

        # Count files with working_tree chunks
        file_counts = await db.fetch(
            """
            SELECT file_path, COUNT(*) as chunk_count
            FROM archon_chunks
            WHERE repo_id = $1 AND source = 'working_tree'
            GROUP BY file_path
            """,
            repo_id,
        )

        # Count embeddings for working_tree chunks
        embedding_count = await db.fetchval(
            """
            SELECT COUNT(*)
            FROM archon_chunks c
            JOIN archon_embeddings e ON e.item_id = c.id::text AND e.item_type = 'chunk'
            WHERE c.repo_id = $1 AND c.source = 'working_tree'
            """,
            repo_id,
        )

        return {
            "success": True,
            "repo_id": repo_id,
            "chunks_by_source": {r["source"]: r["count"] for r in chunk_counts},
            "files_with_working_tree": [
                {"file_path": r["file_path"], "chunk_count": r["chunk_count"]} for r in file_counts
            ],
            "working_tree_embeddings": embedding_count or 0,
        }

    except Exception as e:
        logger.error(f"Failed to get working tree stats: {e}")
        return {
            "success": False,
            "error": str(e),
        }
