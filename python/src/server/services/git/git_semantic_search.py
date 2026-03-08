"""
Git Semantic Search Service

Enables vector-based semantic search across Git commits using pgvector.

Features:
- Vector similarity search with cosine distance
- Multi-dimensional embedding support (384D-3072D)
- Rich filtering: branch, date, classification, author, repo
- Ranked results with similarity scores
- Pagination support

Use cases:
- "Find all performance optimizations in the last 6 months"
- "Show commits that introduced authentication changes"
- "What security fixes affected the API layer?"
- "Find commits similar to this one"
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from supabase import Client as SupabaseClient

from ...config.logfire_config import safe_span, search_logger
from ...db_connector import get_db_client
from ..embeddings.embedding_service import create_embedding


@dataclass
class CommitSearchResult:
    """A single commit search result with similarity score."""

    commit_id: str
    commit_sha: str
    repo_id: str
    message: str
    author_name: str | None
    author_email: str | None
    commit_date: datetime | None
    branches: list[str]
    classification: dict[str, Any] | None
    similarity_score: float
    embedding_dimension: int
    diff_summary: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "commit_id": self.commit_id,
            "commit_sha": self.commit_sha,
            "repo_id": self.repo_id,
            "message": self.message,
            "author_name": self.author_name,
            "author_email": self.author_email,
            "commit_date": self.commit_date.isoformat() if self.commit_date else None,
            "branches": self.branches,
            "classification": self.classification,
            "similarity_score": self.similarity_score,
            "embedding_dimension": self.embedding_dimension,
            "diff_summary": self.diff_summary,
        }


@dataclass
class SearchFilters:
    """Filters for commit search queries."""

    repo_id: str | None = None
    branch: str | None = None
    since: datetime | None = None
    until: datetime | None = None
    intent_filter: list[str] | None = None  # e.g., ["feature", "bugfix"]
    risk_filter: list[str] | None = None  # e.g., ["high", "medium"]
    author: str | None = None
    breaking_only: bool = False
    security_only: bool = False


class GitSemanticSearch:
    """
    Service for semantic search across Git commits.

    Uses pgvector for fast approximate nearest neighbor search with cosine similarity.
    """

    def __init__(self, supabase_client: SupabaseClient | None = None):
        """
        Initialize Git Semantic Search.

        Args:
            supabase_client: Supabase client for database operations
        """
        self.supabase = supabase_client or get_db_client()

    async def search_commits(
        self,
        query: str,
        filters: SearchFilters | None = None,
        limit: int = 10,
        min_similarity: float = 0.0,
    ) -> list[CommitSearchResult]:
        """
        Search commits using semantic similarity.

        Args:
            query: Natural language query (e.g., "authentication changes")
            filters: Optional filters to narrow results
            limit: Maximum number of results (default 10, max 100)
            min_similarity: Minimum similarity score (0.0-1.0)

        Returns:
            List of CommitSearchResult ordered by similarity (highest first)

        Examples:
            >>> results = await search.search_commits(
            ...     query="performance optimizations",
            ...     filters=SearchFilters(
            ...         intent_filter=["performance"],
            ...         since=datetime(2024, 1, 1)
            ...     ),
            ...     limit=10
            ... )
            >>> for result in results:
            ...     print(f"{result.commit_sha[:7]}: {result.message} ({result.similarity_score:.2f})")
        """
        with safe_span("git_semantic_search.search_commits"):
            search_logger.info(
                "Searching commits",
                query=query[:100],
                filters=filters,
                limit=limit,
            )

            # Generate query embedding
            try:
                query_embedding = await create_embedding(query)
            except Exception as e:
                search_logger.error(f"Failed to generate query embedding: {e}")
                raise ValueError(f"Could not embed query: {e}")

            dimension = len(query_embedding)
            search_logger.info(f"Query embedding dimension: {dimension}")

            # Build SQL query with filters
            sql_query = self._build_search_query(
                dimension=dimension,
                filters=filters or SearchFilters(),
                limit=min(limit, 100),  # Cap at 100
                min_similarity=min_similarity,
            )

            # Execute search
            try:
                # Use RPC for vector similarity search
                result = self.supabase.rpc(
                    "search_git_commits_vector",
                    {
                        "query_embedding": query_embedding,
                        "match_count": limit,
                        "filter_repo_id": filters.repo_id if filters else None,
                        "filter_branch": filters.branch if filters else None,
                        "filter_since": filters.since.isoformat() if filters and filters.since else None,
                        "filter_until": filters.until.isoformat() if filters and filters.until else None,
                        "min_similarity": min_similarity,
                    },
                ).execute()

                if not result.data:
                    search_logger.info("No commits found matching query")
                    return []

                # Parse results
                commits = self._parse_search_results(result.data, dimension)

                # Apply classification filters (post-processing)
                if filters:
                    commits = self._apply_classification_filters(commits, filters)

                search_logger.info(
                    f"Found {len(commits)} commits",
                    top_score=commits[0].similarity_score if commits else 0.0,
                )

                return commits[:limit]

            except Exception as e:
                search_logger.error(f"Search query failed: {e}")
                # Fallback to direct query if RPC not available
                return await self._fallback_search(
                    query_embedding=query_embedding,
                    dimension=dimension,
                    filters=filters or SearchFilters(),
                    limit=limit,
                    min_similarity=min_similarity,
                )

    async def find_similar_commits(
        self,
        commit_sha: str,
        repo_id: str,
        limit: int = 10,
        min_similarity: float = 0.5,
    ) -> list[CommitSearchResult]:
        """
        Find commits similar to a given commit.

        Args:
            commit_sha: Reference commit SHA
            repo_id: Repository ID
            limit: Maximum number of results
            min_similarity: Minimum similarity threshold (0.5 = 50% similar)

        Returns:
            List of similar commits (excluding the reference commit itself)

        Examples:
            >>> similar = await search.find_similar_commits(
            ...     commit_sha="abc123",
            ...     repo_id="repo-456",
            ...     limit=5
            ... )
        """
        with safe_span("git_semantic_search.find_similar_commits"):
            search_logger.info(
                "Finding similar commits",
                commit_sha=commit_sha[:7],
                repo_id=repo_id,
            )

            # Fetch reference commit embedding
            result = (
                self.supabase.table("archon_git_commits")
                .select(
                    "id, embedding_384, embedding_768, embedding_1024, "
                    "embedding_1536, embedding_3072"
                )
                .eq("repo_id", repo_id)
                .eq("commit_sha", commit_sha)
                .execute()
            )

            if not result.data or len(result.data) == 0:
                raise ValueError(f"Commit not found: {commit_sha}")

            commit_data = result.data[0]

            # Determine which embedding dimension is available
            query_embedding = None
            dimension = None

            for dim in [1536, 1024, 768, 384, 3072]:  # Prioritize 1536 (default)
                embedding_col = f"embedding_{dim}"
                if commit_data.get(embedding_col):
                    query_embedding = commit_data[embedding_col]
                    dimension = dim
                    break

            if not query_embedding:
                raise ValueError(f"Commit {commit_sha} has no embeddings")

            search_logger.info(f"Using {dimension}D embedding for similarity search")

            # Search for similar commits
            try:
                result = self.supabase.rpc(
                    "search_git_commits_vector",
                    {
                        "query_embedding": query_embedding,
                        "match_count": limit + 1,  # +1 to exclude self
                        "filter_repo_id": repo_id,
                        "min_similarity": min_similarity,
                    },
                ).execute()

                if not result.data:
                    return []

                # Parse and filter out the reference commit
                commits = self._parse_search_results(result.data, dimension)
                commits = [c for c in commits if c.commit_sha != commit_sha]

                return commits[:limit]

            except Exception as e:
                search_logger.error(f"Similar commit search failed: {e}")
                # Fallback
                return await self._fallback_similar_search(
                    query_embedding=query_embedding,
                    dimension=dimension,
                    repo_id=repo_id,
                    exclude_sha=commit_sha,
                    limit=limit,
                    min_similarity=min_similarity,
                )

    async def _fallback_search(
        self,
        query_embedding: list[float],
        dimension: int,
        filters: SearchFilters,
        limit: int,
        min_similarity: float,
    ) -> list[CommitSearchResult]:
        """
        Fallback search using direct SQL query (when RPC not available).

        This is slower but works without custom database functions.
        """
        search_logger.warning("Using fallback search (RPC not available)")

        embedding_col = f"embedding_{dimension}"

        # Build base query
        query = self.supabase.table("archon_git_commits").select(
            "id, commit_sha, repo_id, message, author_name, author_email, "
            "commit_date, branches, metadata"
        )

        # Apply filters
        if filters.repo_id:
            query = query.eq("repo_id", filters.repo_id)

        if filters.branch:
            query = query.contains("branches", [filters.branch])

        if filters.since:
            query = query.gte("commit_date", filters.since.isoformat())

        if filters.until:
            query = query.lte("commit_date", filters.until.isoformat())

        if filters.author:
            query = query.or_(
                f"author_name.ilike.%{filters.author}%,"
                f"author_email.ilike.%{filters.author}%"
            )

        # Only fetch commits with embeddings
        query = query.not_.is_(embedding_col, "null")

        # Execute query
        result = query.limit(1000).execute()  # Fetch top 1000, then filter

        if not result.data:
            return []

        # Calculate cosine similarity for each result
        commits_with_scores = []

        for commit in result.data:
            embedding = commit.get(embedding_col)
            if not embedding:
                continue

            # Calculate cosine similarity (1 - cosine distance)
            similarity = self._cosine_similarity(query_embedding, embedding)

            if similarity < min_similarity:
                continue

            commits_with_scores.append((commit, similarity))

        # Sort by similarity (descending)
        commits_with_scores.sort(key=lambda x: x[1], reverse=True)

        # Take top N
        top_commits = commits_with_scores[:limit]

        # Parse into result objects
        results = []
        for commit, score in top_commits:
            result_obj = self._parse_commit_result(commit, score, dimension)
            results.append(result_obj)

        return results

    async def _fallback_similar_search(
        self,
        query_embedding: list[float],
        dimension: int,
        repo_id: str,
        exclude_sha: str,
        limit: int,
        min_similarity: float,
    ) -> list[CommitSearchResult]:
        """Fallback similar search using direct query."""
        return await self._fallback_search(
            query_embedding=query_embedding,
            dimension=dimension,
            filters=SearchFilters(repo_id=repo_id),
            limit=limit + 1,  # +1 to account for exclusion
            min_similarity=min_similarity,
        )

    def _build_search_query(
        self,
        dimension: int,
        filters: SearchFilters,
        limit: int,
        min_similarity: float,
    ) -> str:
        """Build SQL query with filters (for documentation/reference)."""
        # This is used for logging/debugging - actual query uses RPC
        embedding_col = f"embedding_{dimension}"

        conditions = []
        if filters.repo_id:
            conditions.append(f"repo_id = '{filters.repo_id}'")
        if filters.branch:
            conditions.append(f"'{filters.branch}' = ANY(branches)")
        if filters.since:
            conditions.append(f"commit_date >= '{filters.since.isoformat()}'")
        if filters.until:
            conditions.append(f"commit_date <= '{filters.until.isoformat()}'")
        if filters.author:
            conditions.append(
                f"(author_name ILIKE '%{filters.author}%' OR "
                f"author_email ILIKE '%{filters.author}%')"
            )

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        return f"""
        SELECT id, commit_sha, repo_id, message, author_name, author_email,
               commit_date, branches, metadata,
               (1 - ({embedding_col} <=> query_embedding)) as similarity
        FROM archon_git_commits
        WHERE {where_clause}
          AND {embedding_col} IS NOT NULL
          AND (1 - ({embedding_col} <=> query_embedding)) >= {min_similarity}
        ORDER BY similarity DESC
        LIMIT {limit}
        """

    def _parse_search_results(
        self, data: list[dict], dimension: int
    ) -> list[CommitSearchResult]:
        """Parse raw search results into CommitSearchResult objects."""
        results = []

        for row in data:
            result = self._parse_commit_result(
                row, row.get("similarity", 0.0), dimension
            )
            results.append(result)

        return results

    def _parse_commit_result(
        self, commit: dict, similarity: float, dimension: int
    ) -> CommitSearchResult:
        """Parse a single commit row into CommitSearchResult."""
        commit_date = None
        if commit.get("commit_date"):
            try:
                commit_date = datetime.fromisoformat(
                    str(commit["commit_date"]).replace("Z", "+00:00")
                )
            except Exception:
                pass

        return CommitSearchResult(
            commit_id=str(commit.get("id", "")),
            commit_sha=str(commit.get("commit_sha", "")),
            repo_id=str(commit.get("repo_id", "")),
            message=str(commit.get("message", "")),
            author_name=str(commit.get("author_name")) if commit.get("author_name") else None,
            author_email=str(commit.get("author_email")) if commit.get("author_email") else None,
            commit_date=commit_date,
            branches=commit.get("branches", []),
            classification=commit.get("metadata") if isinstance(commit.get("metadata"), dict) else None,
            similarity_score=float(similarity),
            embedding_dimension=dimension,
        )

    def _apply_classification_filters(
        self, commits: list[CommitSearchResult], filters: SearchFilters
    ) -> list[CommitSearchResult]:
        """Apply classification-based filters to results."""
        filtered = commits

        if filters.intent_filter:
            filtered = [
                c
                for c in filtered
                if c.classification
                and c.classification.get("intent") in filters.intent_filter
            ]

        if filters.risk_filter:
            filtered = [
                c
                for c in filtered
                if c.classification
                and c.classification.get("risk_level") in filters.risk_filter
            ]

        if filters.breaking_only:
            filtered = [
                c
                for c in filtered
                if c.classification and c.classification.get("api_breaking") is True
            ]

        if filters.security_only:
            filtered = [
                c
                for c in filtered
                if c.classification
                and c.classification.get("security_relevant") is True
            ]

        return filtered

    def _cosine_similarity(
        self, vec1: list[float], vec2: list[float]
    ) -> float:
        """
        Calculate cosine similarity between two vectors.

        Returns:
            Similarity score (0.0 = completely different, 1.0 = identical)
        """
        if len(vec1) != len(vec2):
            raise ValueError("Vectors must have same dimension")

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)


# Singleton instance
_git_semantic_search: GitSemanticSearch | None = None


def get_git_semantic_search() -> GitSemanticSearch:
    """Get singleton GitSemanticSearch instance."""
    global _git_semantic_search
    if _git_semantic_search is None:
        _git_semantic_search = GitSemanticSearch()
    return _git_semantic_search
