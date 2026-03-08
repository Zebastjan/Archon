"""
Git Embedding API Routes

Endpoints for generating and managing embeddings for git commits.

Routes:
- POST /api/projects/{project_id}/repository/commits/embed - Embed specific commits
- POST /api/projects/{project_id}/repository/commits/embed-all - Embed all commits
- GET /api/projects/{project_id}/repository/commits/{commit_sha}/embedding - Get embedding status
"""

from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ..services.git.git_embedding_service import get_git_embedding_service
from ..services.git.git_repository_service import get_git_repository_service

router = APIRouter()


class EmbedCommitsRequest(BaseModel):
    """Request to embed specific commits."""

    commit_shas: list[str] = Field(
        ...,
        description="List of commit SHAs to embed",
        min_length=1,
    )
    source: Literal["message", "diff", "combined"] = Field(
        default="message",
        description="What to embed: message, diff summary, or combined",
    )


class EmbedAllCommitsRequest(BaseModel):
    """Request to embed all commits in repository."""

    source: Literal["message", "diff", "combined"] = Field(
        default="message",
        description="What to embed: message, diff summary, or combined",
    )
    batch_size: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Number of commits to process per batch",
    )


class EmbeddingStatus(BaseModel):
    """Embedding status for a commit."""

    commit_sha: str
    has_embedding: bool
    embedding_dimension: int | None = None
    embedding_source: str | None = None
    embedding_model: str | None = None
    embedding_timestamp: str | None = None


class EmbedCommitsResponse(BaseModel):
    """Response from commit embedding operation."""

    total: int
    successes: int
    failures: int
    results: list[dict]  # List of CommitEmbeddingResult dicts


@router.post(
    "/api/projects/{project_id}/repository/commits/embed",
    response_model=EmbedCommitsResponse,
    status_code=status.HTTP_200_OK,
)
async def embed_commits(
    project_id: str,
    request: EmbedCommitsRequest,
):
    """
    Generate embeddings for specific commits.

    This endpoint takes a list of commit SHAs and generates embeddings for them,
    enabling semantic search across commit history.

    Args:
        project_id: Project ID containing the repository
        request: Request with commit SHAs and embedding source

    Returns:
        EmbedCommitsResponse with results

    Raises:
        404: Repository not found
        400: Invalid request or embedding failed

    Example:
        ```python
        POST /api/projects/proj-123/repository/commits/embed
        {
            "commit_shas": ["abc123", "def456"],
            "source": "message"
        }
        ```

        Response:
        ```json
        {
            "total": 2,
            "successes": 2,
            "failures": 0,
            "results": [
                {
                    "commit_sha": "abc123",
                    "success": true,
                    "embedding_dimension": 1536
                },
                ...
            ]
        }
        ```
    """
    # Get repository ID from project
    git_service = get_git_repository_service()
    repo = git_service.get_repository_by_project_id(project_id)

    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository not found for project {project_id}",
        )

    # Embed commits
    embedding_service = get_git_embedding_service()
    results = await embedding_service.embed_commits_batch(
        repo_id=repo["id"],
        commit_shas=request.commit_shas,
        source=request.source,
    )

    # Convert results to dicts
    results_dicts = [
        {
            "commit_id": r.commit_id,
            "commit_sha": r.commit_sha,
            "success": r.success,
            "embedding_dimension": r.embedding_dimension,
            "error": r.error,
        }
        for r in results
    ]

    successes = sum(1 for r in results if r.success)
    failures = sum(1 for r in results if not r.success)

    return EmbedCommitsResponse(
        total=len(results),
        successes=successes,
        failures=failures,
        results=results_dicts,
    )


@router.post(
    "/api/projects/{project_id}/repository/commits/embed-all",
    response_model=EmbedCommitsResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def embed_all_commits(
    project_id: str,
    request: EmbedAllCommitsRequest,
):
    """
    Generate embeddings for all commits in the repository.

    This is a long-running operation that processes all commits in batches.
    Use this to initially populate embeddings or re-embed after changing models.

    Args:
        project_id: Project ID containing the repository
        request: Request with embedding source and batch size

    Returns:
        EmbedCommitsResponse with results (202 Accepted for async processing)

    Raises:
        404: Repository not found
        400: Invalid request or embedding failed

    Example:
        ```python
        POST /api/projects/proj-123/repository/commits/embed-all
        {
            "source": "message",
            "batch_size": 50
        }
        ```

        Response (after completion):
        ```json
        {
            "total": 150,
            "successes": 148,
            "failures": 2,
            "results": [...]
        }
        ```

    Note:
        This endpoint returns 202 Accepted immediately and processes asynchronously.
        For large repositories (1000+ commits), this may take several minutes.
    """
    # Get repository ID from project
    git_service = get_git_repository_service()
    repo = git_service.get_repository_by_project_id(project_id)

    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository not found for project {project_id}",
        )

    # Embed all commits (pass None for commit_shas = embed all)
    embedding_service = get_git_embedding_service()
    results = await embedding_service.embed_commits_batch(
        repo_id=repo["id"],
        commit_shas=None,  # None = all commits
        source=request.source,
        batch_size=request.batch_size,
    )

    # Convert results to dicts
    results_dicts = [
        {
            "commit_id": r.commit_id,
            "commit_sha": r.commit_sha,
            "success": r.success,
            "embedding_dimension": r.embedding_dimension,
            "error": r.error,
        }
        for r in results
    ]

    successes = sum(1 for r in results if r.success)
    failures = sum(1 for r in results if not r.success)

    return EmbedCommitsResponse(
        total=len(results),
        successes=successes,
        failures=failures,
        results=results_dicts,
    )


@router.get(
    "/api/projects/{project_id}/repository/commits/{commit_sha}/embedding",
    response_model=EmbeddingStatus,
    status_code=status.HTTP_200_OK,
)
async def get_commit_embedding_status(
    project_id: str,
    commit_sha: str,
):
    """
    Get embedding status for a specific commit.

    Returns whether the commit has been embedded, what dimension, and when.

    Args:
        project_id: Project ID containing the repository
        commit_sha: Commit SHA to check

    Returns:
        EmbeddingStatus with embedding information

    Raises:
        404: Repository or commit not found

    Example:
        ```python
        GET /api/projects/proj-123/repository/commits/abc123/embedding
        ```

        Response:
        ```json
        {
            "commit_sha": "abc123",
            "has_embedding": true,
            "embedding_dimension": 1536,
            "embedding_source": "message",
            "embedding_model": "text-embedding-3-small",
            "embedding_timestamp": "2024-01-15T10:30:00Z"
        }
        ```
    """
    # Get repository ID from project
    git_service = get_git_repository_service()
    repo = git_service.get_repository_by_project_id(project_id)

    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository not found for project {project_id}",
        )

    # Get commit embedding status
    embedding_service = get_git_embedding_service()
    result = (
        embedding_service.supabase.table("archon_git_commits")
        .select(
            "commit_sha, embedding_384, embedding_768, embedding_1024, "
            "embedding_1536, embedding_3072, embedding_source, "
            "embedding_model, embedding_timestamp"
        )
        .eq("repo_id", repo["id"])
        .eq("commit_sha", commit_sha)
        .execute()
    )

    if not result.data or len(result.data) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Commit not found: {commit_sha}",
        )

    commit = result.data[0]

    # Determine if commit has embedding and what dimension
    has_embedding = False
    embedding_dimension = None

    for dim in [384, 768, 1024, 1536, 3072]:
        if commit.get(f"embedding_{dim}") is not None:
            has_embedding = True
            embedding_dimension = dim
            break

    return EmbeddingStatus(
        commit_sha=commit["commit_sha"],
        has_embedding=has_embedding,
        embedding_dimension=embedding_dimension,
        embedding_source=commit.get("embedding_source"),
        embedding_model=commit.get("embedding_model"),
        embedding_timestamp=commit.get("embedding_timestamp"),
    )
