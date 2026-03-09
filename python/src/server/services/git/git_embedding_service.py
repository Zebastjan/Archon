"""
Git Embedding Service

Handles embedding generation for git commits, enabling semantic search across
commit messages and diff summaries.

Architecture:
- Formats commit data (message + metadata) into embeddable text
- Delegates to EmbeddingService for actual embedding generation
- Stores embeddings in appropriate dimension columns
- Supports batch processing with graceful failure handling

Use cases:
- "Find all performance optimizations in the last 6 months"
- "Show commits that introduced authentication changes"
- "What security fixes affected the API layer?"
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from supabase import Client as SupabaseClient

from ...config.logfire_config import safe_span, search_logger
from ..client_manager import get_supabase_client
from ..embeddings.embedding_service import (
    EmbeddingBatchResult,
    create_embeddings_batch,
)


@dataclass
class CommitEmbeddingResult:
    """Result of embedding a single commit."""

    commit_id: str
    commit_sha: str
    success: bool
    embedding_dimension: int | None = None
    error: str | None = None


class GitEmbeddingService:
    """
    Service for generating and storing embeddings for git commits.

    Supports multiple embedding sources:
    - message: Embed commit message only
    - diff: Embed diff summary only (not full diff - too large)
    - combined: Embed both message and diff summary

    Uses multi-dimensional storage to support different embedding models.
    """

    def __init__(
        self,
        supabase_client: SupabaseClient | None = None,
    ):
        """
        Initialize Git Embedding Service.

        Args:
            supabase_client: Supabase client for database operations
        """
        self.supabase = supabase_client or get_supabase_client()

    def format_commit_for_embedding(
        self,
        commit_sha: str,
        message: str,
        author_name: str | None = None,
        metadata: dict[str, Any] | None = None,
        diff_summary: str | None = None,
        source: str = "message",
    ) -> str:
        """
        Format commit data into embeddable text.

        Includes commit metadata (intent, risk level, etc.) to improve semantic search.

        Args:
            commit_sha: Commit SHA (for reference)
            message: Commit message
            author_name: Commit author
            metadata: Classification metadata (intent, risk_level, etc.)
            diff_summary: Summary of changes (not full diff)
            source: What to embed - "message", "diff", or "combined"

        Returns:
            Formatted text for embedding

        Examples:
            >>> format_commit_for_embedding(
            ...     commit_sha="abc123",
            ...     message="Add user authentication",
            ...     metadata={"intent": "feature", "risk_level": "medium"},
            ...     source="message"
            ... )
            "Intent: feature\nRisk: medium\n\nAdd user authentication"
        """
        parts = []

        # Add classification metadata if available (improves semantic search)
        if metadata:
            if "intent" in metadata:
                parts.append(f"Intent: {metadata['intent']}")
            if "risk_level" in metadata:
                parts.append(f"Risk: {metadata['risk_level']}")
            if metadata.get("api_breaking"):
                parts.append("Breaking change")
            if metadata.get("security_relevant"):
                parts.append("Security-related")

        # Add main content based on source
        if source in ("message", "combined"):
            if message:
                parts.append(f"\n{message.strip()}")

        if source in ("diff", "combined") and diff_summary:
            parts.append(f"\nChanges:\n{diff_summary.strip()}")

        # Fallback if no content
        if not parts:
            parts.append(f"Commit {commit_sha[:7]}")

        return "\n".join(parts)

    async def embed_commit(
        self,
        repo_id: str,
        commit_sha: str,
        source: str = "message",
        diff_summary: str | None = None,
    ) -> CommitEmbeddingResult:
        """
        Generate and store embedding for a single commit.

        Args:
            repo_id: Repository ID
            commit_sha: Commit SHA to embed
            source: What to embed - "message", "diff", or "combined"
            diff_summary: Optional diff summary (required if source includes "diff")

        Returns:
            CommitEmbeddingResult with success status

        Raises:
            ValueError: If commit not found or diff_summary missing when needed
        """
        with safe_span("git_embedding_service.embed_commit"):
            search_logger.info(
                "Embedding commit",
                repo_id=repo_id,
                commit_sha=commit_sha[:7],
                source=source,
            )

            try:
                # Fetch commit from database
                result = (
                    self.supabase.table("archon_git_commits")
                    .select("id, commit_sha, message, author_name, metadata")
                    .eq("repo_id", repo_id)
                    .eq("commit_sha", commit_sha)
                    .execute()
                )

                if not result.data or len(result.data) == 0:
                    raise ValueError(f"Commit not found: {commit_sha}")

                commit = result.data[0]

                # Validate diff_summary requirement
                if source in ("diff", "combined") and not diff_summary:
                    raise ValueError(
                        f"diff_summary required for source={source}"
                    )

                # Format commit for embedding
                embeddable_text = self.format_commit_for_embedding(
                    commit_sha=commit["commit_sha"],
                    message=commit.get("message", ""),
                    author_name=commit.get("author_name"),
                    metadata=commit.get("metadata", {}),
                    diff_summary=diff_summary,
                    source=source,
                )

                # Generate embedding using function-based API
                embedding_result = await create_embeddings_batch(
                    texts=[embeddable_text],
                )

                if embedding_result.has_failures:
                    error_msg = embedding_result.failed_items[0]["error"]
                    return CommitEmbeddingResult(
                        commit_id=commit["id"],
                        commit_sha=commit_sha,
                        success=False,
                        error=error_msg,
                    )

                # Store embedding in appropriate dimension column
                embedding = embedding_result.embeddings[0]
                dimension = len(embedding)
                column_name = f"embedding_{dimension}"

                # Get model name from settings or config
                # TODO: Get from embedding service config
                model_name = "text-embedding-3-small"  # Default

                # Update commit with embedding
                self.supabase.table("archon_git_commits").update(
                    {
                        column_name: embedding,
                        "embedding_source": source,
                        "embedding_model": model_name,
                        "embedding_timestamp": datetime.utcnow().isoformat(),
                    }
                ).eq("id", commit["id"]).execute()

                search_logger.info(
                    "Commit embedding stored",
                    commit_sha=commit_sha[:7],
                    dimension=dimension,
                    source=source,
                )

                return CommitEmbeddingResult(
                    commit_id=commit["id"],
                    commit_sha=commit_sha,
                    success=True,
                    embedding_dimension=dimension,
                )

            except Exception as e:
                search_logger.error(
                    "Failed to embed commit %s: %s",
                    commit_sha[:7],
                    str(e),
                )
                return CommitEmbeddingResult(
                    commit_id="",
                    commit_sha=commit_sha,
                    success=False,
                    error=str(e),
                )

    async def embed_commits_batch(
        self,
        repo_id: str,
        commit_shas: list[str] | None = None,
        source: str = "message",
        batch_size: int = 50,
    ) -> list[CommitEmbeddingResult]:
        """
        Batch process multiple commits for embedding.

        Handles rate limiting, quota exhaustion, and partial failures gracefully.

        Args:
            repo_id: Repository ID
            commit_shas: List of commit SHAs to embed (None = all commits in repo)
            source: What to embed - "message", "diff", or "combined"
            batch_size: Number of commits to process per batch

        Returns:
            List of CommitEmbeddingResult with success/failure status

        Examples:
            >>> results = await service.embed_commits_batch(
            ...     repo_id="repo-123",
            ...     commit_shas=["abc123", "def456"],
            ...     source="message"
            ... )
            >>> successes = [r for r in results if r.success]
            >>> failures = [r for r in results if not r.success]
        """
        with safe_span("git_embedding_service.embed_commits_batch"):
            search_logger.info(
                "Starting batch commit embedding",
                repo_id=repo_id,
                source=source,
                batch_size=batch_size,
            )

            # Fetch commits to embed
            query = (
                self.supabase.table("archon_git_commits")
                .select("id, commit_sha, message, author_name, metadata")
                .eq("repo_id", repo_id)
            )

            # Filter by specific commits if provided
            if commit_shas:
                query = query.in_("commit_sha", commit_shas)

            result = query.execute()

            if not result.data:
                search_logger.warning(
                    "No commits found for embedding in repo %s", repo_id
                )
                return []

            commits = result.data
            total_commits = len(commits)

            search_logger.info(
                "Found %s commits to embed in repo %s",
                total_commits,
                repo_id,
            )

            # Process in batches
            results: list[CommitEmbeddingResult] = []

            for i in range(0, total_commits, batch_size):
                batch = commits[i : i + batch_size]
                batch_num = i // batch_size + 1
                total_batches = (total_commits + batch_size - 1) // batch_size

                search_logger.info(
                    "Processing batch %s/%s with %s commits",
                    batch_num,
                    total_batches,
                    len(batch),
                )

                # Format commits for embedding
                embeddable_texts = []
                batch_metadata = []

                for commit in batch:
                    text = self.format_commit_for_embedding(
                        commit_sha=commit["commit_sha"],
                        message=commit.get("message", ""),
                        author_name=commit.get("author_name"),
                        metadata=commit.get("metadata", {}),
                        source=source,
                    )
                    embeddable_texts.append(text)
                    batch_metadata.append(
                        {
                            "commit_id": commit["id"],
                            "commit_sha": commit["commit_sha"],
                            "source": source,
                        }
                    )

                # Generate embeddings using function-based API
                try:
                    embedding_result = await create_embeddings_batch(
                        texts=embeddable_texts,
                    )

                    # Get model name (TODO: from config/settings)
                    model_name = "text-embedding-3-small"  # Default

                    # Process successful embeddings
                    for idx, embedding in enumerate(embedding_result.embeddings):
                        commit = batch[idx]
                        dimension = len(embedding)
                        column_name = f"embedding_{dimension}"

                        try:
                            # Store embedding
                            self.supabase.table("archon_git_commits").update(
                                {
                                    column_name: embedding,
                                    "embedding_source": source,
                                    "embedding_model": model_name,
                                    "embedding_timestamp": datetime.utcnow().isoformat(),
                                }
                            ).eq("id", commit["id"]).execute()

                            results.append(
                                CommitEmbeddingResult(
                                    commit_id=commit["id"],
                                    commit_sha=commit["commit_sha"],
                                    success=True,
                                    embedding_dimension=dimension,
                                )
                            )

                        except Exception as e:
                            search_logger.error(
                                "Failed to store embedding for %s: %s",
                                commit["commit_sha"][:7],
                                str(e),
                            )
                            results.append(
                                CommitEmbeddingResult(
                                    commit_id=commit["id"],
                                    commit_sha=commit["commit_sha"],
                                    success=False,
                                    error=f"Storage error: {str(e)}",
                                )
                            )

                    # Process failures
                    for failure in embedding_result.failed_items:
                        batch_index = failure.get("batch_index")
                        if batch_index is not None and batch_index < len(batch):
                            commit = batch[batch_index]
                            results.append(
                                CommitEmbeddingResult(
                                    commit_id=commit["id"],
                                    commit_sha=commit["commit_sha"],
                                    success=False,
                                    error=failure.get("error", "Unknown error"),
                                )
                            )

                except Exception as e:
                    search_logger.error(
                        "Batch embedding failed for batch %s: %s",
                        batch_num,
                        str(e),
                    )
                    # Mark entire batch as failed
                    for commit in batch:
                        results.append(
                            CommitEmbeddingResult(
                                commit_id=commit["id"],
                                commit_sha=commit["commit_sha"],
                                success=False,
                                error=f"Batch error: {str(e)}",
                            )
                        )

                # Brief pause between batches to avoid rate limits
                if i + batch_size < total_commits:
                    await asyncio.sleep(0.5)

            # Log summary
            successes = sum(1 for r in results if r.success)
            failures = sum(1 for r in results if not r.success)

            search_logger.info(
                "Batch embedding complete: %s total, %s successes, %s failures in repo %s",
                len(results),
                successes,
                failures,
                repo_id,
            )

            return results


# Singleton instance
_git_embedding_service: GitEmbeddingService | None = None


def get_git_embedding_service() -> GitEmbeddingService:
    """Get singleton GitEmbeddingService instance."""
    global _git_embedding_service
    if _git_embedding_service is None:
        _git_embedding_service = GitEmbeddingService()
    return _git_embedding_service
