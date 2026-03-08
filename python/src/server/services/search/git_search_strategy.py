"""
Git Search Strategy

Integrates Git commit semantic search into the RAG pipeline.
Enables queries like:
- "What changed in authentication code at commit abc123?"
- "Find performance improvements in the last 6 months"
- "Show security fixes affecting the API layer"
"""

from datetime import datetime
from typing import Any

from supabase import Client

from ...config.logfire_config import get_logger, safe_span
from ..git.git_semantic_search import GitSemanticSearch, SearchFilters

logger = get_logger(__name__)


class GitSearchStrategy:
    """
    Strategy for integrating Git commit search into RAG queries.

    This strategy extends the RAG service to include Git commit context
    in search results, enabling code history-aware queries.
    """

    def __init__(self, supabase_client: Client):
        """
        Initialize Git search strategy.

        Args:
            supabase_client: Supabase client for database operations
        """
        self.supabase_client = supabase_client
        self.git_search = GitSemanticSearch(supabase_client)

    async def search_commits(
        self,
        query: str,
        match_count: int = 5,
        repo_id: str | None = None,
        branch: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        intent_filter: list[str] | None = None,
        risk_filter: list[str] | None = None,
        author: str | None = None,
        breaking_only: bool = False,
        security_only: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Search Git commits semantically using the query.

        Args:
            query: Search query (e.g., "performance improvements")
            match_count: Number of results to return
            repo_id: Filter by repository ID
            branch: Filter by branch name
            since: Filter commits after this date
            until: Filter commits before this date
            intent_filter: Filter by commit intent (e.g., ["feature", "bugfix"])
            risk_filter: Filter by risk level (e.g., ["high", "medium"])
            author: Filter by author name/email
            breaking_only: Only return breaking changes
            security_only: Only return security-related commits

        Returns:
            List of matching commits with similarity scores
        """
        with safe_span(
            "git_search_commits",
            query_length=len(query),
            match_count=match_count,
            repo_id=repo_id,
            branch=branch,
        ) as span:
            try:
                # Build filters
                filters = SearchFilters(
                    repo_id=repo_id,
                    branch=branch,
                    since=since,
                    until=until,
                    intent_filter=intent_filter,
                    risk_filter=risk_filter,
                    author=author,
                    breaking_only=breaking_only,
                    security_only=security_only,
                )

                # Perform semantic search
                results = await self.git_search.search_commits(
                    query=query,
                    filters=filters,
                    limit=match_count,
                )

                # Format results for RAG pipeline
                formatted_results = [
                    {
                        "type": "git_commit",
                        "commit_sha": r.commit_sha,
                        "commit_id": r.commit_id,
                        "repo_id": r.repo_id,
                        "message": r.message,
                        "author": r.author_name,
                        "author_email": r.author_email,
                        "commit_date": r.commit_date.isoformat() if r.commit_date else None,
                        "branches": r.branches,
                        "classification": r.classification,
                        "similarity_score": r.similarity_score,
                        "embedding_dimension": r.embedding_dimension,
                        "diff_summary": r.diff_summary,
                        # Make content searchable in standard RAG format
                        "content": self._format_commit_content(r),
                        "metadata": {
                            "type": "git_commit",
                            "repo_id": r.repo_id,
                            "commit_sha": r.commit_sha,
                            "branches": r.branches,
                            "classification": r.classification,
                        },
                    }
                    for r in results
                ]

                span.set_attribute("results_found", len(formatted_results))
                return formatted_results

            except Exception as e:
                logger.error(f"Git commit search failed: {e}")
                span.set_attribute("error", str(e))
                return []

    def _format_commit_content(self, result) -> str:
        """
        Format commit information as searchable text content.

        This makes Git commits compatible with standard RAG result formatting.

        Args:
            result: CommitSearchResult object

        Returns:
            Formatted text content for the commit
        """
        parts = [f"Commit: {result.commit_sha[:8]}"]

        if result.message:
            parts.append(f"Message: {result.message}")

        if result.classification:
            intent = result.classification.get("intent", "unknown")
            risk = result.classification.get("risk_level", "unknown")
            parts.append(f"Type: {intent} (risk: {risk})")

        if result.author_name:
            parts.append(f"Author: {result.author_name}")

        if result.commit_date:
            parts.append(f"Date: {result.commit_date.strftime('%Y-%m-%d')}")

        if result.branches:
            parts.append(f"Branches: {', '.join(result.branches[:3])}")

        if result.diff_summary:
            parts.append(f"Changes: {result.diff_summary[:200]}")

        return " | ".join(parts)

    async def search_commits_for_file(
        self,
        file_path: str,
        repo_id: str,
        match_count: int = 10,
        branch: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Find commits that modified a specific file.

        This uses direct database queries rather than semantic search
        since we're looking for exact file path matches.

        Args:
            file_path: Path to the file (e.g., "src/server/main.py")
            repo_id: Repository ID
            match_count: Number of commits to return
            branch: Optional branch filter

        Returns:
            List of commits that modified the file
        """
        with safe_span(
            "git_search_commits_for_file",
            file_path=file_path,
            repo_id=repo_id,
            branch=branch,
        ) as span:
            try:
                # Query commits that have this file in their file tree
                # This uses the archon_git_files table which links commits to files
                query = (
                    self.supabase_client.table("archon_git_files")
                    .select(
                        """
                        commit_id,
                        file_path,
                        archon_git_commits!inner(
                            id,
                            commit_sha,
                            message,
                            author_name,
                            author_email,
                            commit_date,
                            branches,
                            metadata,
                            repo_id
                        )
                        """
                    )
                    .eq("file_path", file_path)
                    .eq("archon_git_commits.repo_id", repo_id)
                )

                if branch:
                    query = query.contains("archon_git_commits.branches", [branch])

                query = query.order("archon_git_commits.commit_date", desc=True).limit(match_count)

                response = query.execute()

                # Format results
                formatted_results = []
                if response.data:
                    for item in response.data:
                        commit = item.get("archon_git_commits", {})
                        if commit:
                            formatted_results.append({
                                "type": "git_commit_file_change",
                                "commit_sha": commit.get("commit_sha"),
                                "commit_id": commit.get("id"),
                                "repo_id": commit.get("repo_id"),
                                "message": commit.get("message"),
                                "author": commit.get("author_name"),
                                "author_email": commit.get("author_email"),
                                "commit_date": commit.get("commit_date"),
                                "branches": commit.get("branches", []),
                                "classification": commit.get("metadata"),
                                "file_path": item.get("file_path"),
                                "content": f"Modified {file_path} in commit {commit.get('commit_sha', '')[:8]}: {commit.get('message', '')}",
                                "metadata": {
                                    "type": "git_commit_file_change",
                                    "file_path": file_path,
                                    "commit_sha": commit.get("commit_sha"),
                                },
                            })

                span.set_attribute("commits_found", len(formatted_results))
                return formatted_results

            except Exception as e:
                logger.error(f"File history search failed: {e}")
                span.set_attribute("error", str(e))
                return []

    async def get_commit_context(
        self,
        commit_sha: str,
        repo_id: str,
    ) -> dict[str, Any] | None:
        """
        Get detailed context for a specific commit.

        This retrieves the full commit information including:
        - Commit metadata (message, author, date)
        - Classification (intent, risk, etc.)
        - File changes
        - Diff summary

        Args:
            commit_sha: The commit SHA to look up
            repo_id: Repository ID

        Returns:
            Commit context dict or None if not found
        """
        with safe_span("git_get_commit_context", commit_sha=commit_sha, repo_id=repo_id) as span:
            try:
                # Query commit with related files
                response = (
                    self.supabase_client.table("archon_git_commits")
                    .select(
                        """
                        id,
                        commit_sha,
                        message,
                        author_name,
                        author_email,
                        commit_date,
                        branches,
                        metadata,
                        parent_shas,
                        repo_id
                        """
                    )
                    .eq("commit_sha", commit_sha)
                    .eq("repo_id", repo_id)
                    .maybe_single()
                    .execute()
                )

                if not response.data:
                    span.set_attribute("found", False)
                    return None

                commit = response.data

                # Get files modified in this commit
                files_response = (
                    self.supabase_client.table("archon_git_files")
                    .select("file_path, is_binary")
                    .eq("commit_id", commit["id"])
                    .execute()
                )

                files = files_response.data if files_response.data else []

                # Format context
                context = {
                    "commit_sha": commit["commit_sha"],
                    "message": commit["message"],
                    "author": commit["author_name"],
                    "author_email": commit["author_email"],
                    "commit_date": commit["commit_date"],
                    "branches": commit["branches"],
                    "classification": commit.get("metadata"),
                    "parent_shas": commit.get("parent_shas", []),
                    "files_changed": len(files),
                    "files": [
                        {"path": f["file_path"], "is_binary": f.get("is_binary", False)}
                        for f in files[:20]  # Limit to first 20 files
                    ],
                }

                span.set_attribute("found", True)
                span.set_attribute("files_count", len(files))
                return context

            except Exception as e:
                logger.error(f"Failed to get commit context: {e}")
                span.set_attribute("error", str(e))
                return None
