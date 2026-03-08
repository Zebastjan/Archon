"""
Git Semantic Search API Routes

Endpoints for searching commits using vector similarity and natural language queries.

Routes:
- GET /api/projects/{project_id}/repository/commits/search - Semantic search
- POST /api/projects/{project_id}/repository/commits/search - Advanced search with filters
- GET /api/projects/{project_id}/repository/commits/{commit_sha}/similar - Find similar commits
"""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..services.git.git_repository_service import get_git_repository_service
from ..services.git.git_semantic_search import (
    SearchFilters,
    get_git_semantic_search,
)

router = APIRouter()


class CommitSearchRequest(BaseModel):
    """Request for advanced commit search with filters."""

    query: str = Field(
        ...,
        description="Natural language search query",
        min_length=1,
        max_length=500,
    )
    repo_id: str | None = Field(
        default=None,
        description="Filter by repository ID (None = search all repos in project)",
    )
    branch: str | None = Field(
        default=None,
        description="Filter by branch name (e.g., 'main', 'develop')",
    )
    since: datetime | None = Field(
        default=None,
        description="Filter commits after this date (ISO 8601 format)",
    )
    until: datetime | None = Field(
        default=None,
        description="Filter commits before this date (ISO 8601 format)",
    )
    intent_filter: list[str] | None = Field(
        default=None,
        description="Filter by commit intent (e.g., ['feature', 'bugfix', 'security-fix'])",
    )
    risk_filter: list[str] | None = Field(
        default=None,
        description="Filter by risk level (e.g., ['high', 'medium'])",
    )
    author: str | None = Field(
        default=None,
        description="Filter by author name or email (partial match)",
    )
    breaking_only: bool = Field(
        default=False,
        description="Only return breaking changes",
    )
    security_only: bool = Field(
        default=False,
        description="Only return security-relevant commits",
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of results (1-100)",
    )
    min_similarity: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score (0.0-1.0)",
    )


class CommitSearchResult(BaseModel):
    """A single commit search result."""

    commit_id: str
    commit_sha: str
    repo_id: str
    message: str
    author_name: str | None
    author_email: str | None
    commit_date: datetime | None
    branches: list[str]
    classification: dict | None
    similarity_score: float = Field(
        ...,
        description="Similarity score (0.0-1.0, higher = better match)",
    )
    embedding_dimension: int


class CommitSearchResponse(BaseModel):
    """Response from commit search."""

    query: str
    total: int
    results: list[CommitSearchResult]
    filters_applied: dict


@router.get(
    "/api/projects/{project_id}/repository/commits/search",
    response_model=CommitSearchResponse,
    status_code=status.HTTP_200_OK,
)
async def search_commits_simple(
    project_id: str,
    q: str = Query(
        ...,
        description="Search query",
        min_length=1,
        max_length=500,
    ),
    branch: str | None = Query(
        default=None,
        description="Filter by branch",
    ),
    limit: int = Query(
        default=10,
        ge=1,
        le=100,
        description="Number of results",
    ),
):
    """
    Simple semantic search for commits (GET endpoint).

    Quick search interface for finding commits by natural language query.

    Args:
        project_id: Project ID
        q: Search query (e.g., "authentication changes")
        branch: Optional branch filter
        limit: Number of results (1-100)

    Returns:
        CommitSearchResponse with matching commits

    Example:
        ```
        GET /api/projects/proj-123/repository/commits/search?q=performance+improvements&limit=5
        ```

        Response:
        ```json
        {
            "query": "performance improvements",
            "total": 5,
            "results": [
                {
                    "commit_sha": "abc123...",
                    "message": "Optimize database queries",
                    "similarity_score": 0.87,
                    ...
                }
            ]
        }
        ```
    """
    # Get repository
    git_service = get_git_repository_service()
    repo = git_service.get_repository_by_project_id(project_id)

    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository not found for project {project_id}",
        )

    # Build filters
    filters = SearchFilters(
        repo_id=repo["id"],
        branch=branch,
    )

    # Execute search
    search_service = get_git_semantic_search()
    results = await search_service.search_commits(
        query=q,
        filters=filters,
        limit=limit,
    )

    # Convert to response format
    result_models = [
        CommitSearchResult(
            commit_id=r.commit_id,
            commit_sha=r.commit_sha,
            repo_id=r.repo_id,
            message=r.message,
            author_name=r.author_name,
            author_email=r.author_email,
            commit_date=r.commit_date,
            branches=r.branches,
            classification=r.classification,
            similarity_score=r.similarity_score,
            embedding_dimension=r.embedding_dimension,
        )
        for r in results
    ]

    return CommitSearchResponse(
        query=q,
        total=len(result_models),
        results=result_models,
        filters_applied={"branch": branch, "repo_id": repo["id"]},
    )


@router.post(
    "/api/projects/{project_id}/repository/commits/search",
    response_model=CommitSearchResponse,
    status_code=status.HTTP_200_OK,
)
async def search_commits_advanced(
    project_id: str,
    request: CommitSearchRequest,
):
    """
    Advanced semantic search with comprehensive filters (POST endpoint).

    Supports filtering by date range, classification, author, and more.

    Args:
        project_id: Project ID
        request: Search request with query and filters

    Returns:
        CommitSearchResponse with matching commits

    Example:
        ```python
        POST /api/projects/proj-123/repository/commits/search
        {
            "query": "authentication improvements",
            "branch": "main",
            "since": "2024-01-01T00:00:00Z",
            "intent_filter": ["feature", "security-fix"],
            "limit": 20,
            "min_similarity": 0.5
        }
        ```

        Response:
        ```json
        {
            "query": "authentication improvements",
            "total": 15,
            "results": [...],
            "filters_applied": {
                "branch": "main",
                "since": "2024-01-01T00:00:00Z",
                "intent_filter": ["feature", "security-fix"]
            }
        }
        ```
    """
    # Get repository
    git_service = get_git_repository_service()
    repo = git_service.get_repository_by_project_id(project_id)

    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository not found for project {project_id}",
        )

    # Build filters
    filters = SearchFilters(
        repo_id=request.repo_id or repo["id"],
        branch=request.branch,
        since=request.since,
        until=request.until,
        intent_filter=request.intent_filter,
        risk_filter=request.risk_filter,
        author=request.author,
        breaking_only=request.breaking_only,
        security_only=request.security_only,
    )

    # Execute search
    search_service = get_git_semantic_search()
    results = await search_service.search_commits(
        query=request.query,
        filters=filters,
        limit=request.limit,
        min_similarity=request.min_similarity,
    )

    # Convert to response format
    result_models = [
        CommitSearchResult(
            commit_id=r.commit_id,
            commit_sha=r.commit_sha,
            repo_id=r.repo_id,
            message=r.message,
            author_name=r.author_name,
            author_email=r.author_email,
            commit_date=r.commit_date,
            branches=r.branches,
            classification=r.classification,
            similarity_score=r.similarity_score,
            embedding_dimension=r.embedding_dimension,
        )
        for r in results
    ]

    return CommitSearchResponse(
        query=request.query,
        total=len(result_models),
        results=result_models,
        filters_applied={
            "repo_id": filters.repo_id,
            "branch": filters.branch,
            "since": filters.since.isoformat() if filters.since else None,
            "until": filters.until.isoformat() if filters.until else None,
            "intent_filter": filters.intent_filter,
            "risk_filter": filters.risk_filter,
            "author": filters.author,
            "breaking_only": filters.breaking_only,
            "security_only": filters.security_only,
        },
    )


@router.get(
    "/api/projects/{project_id}/repository/commits/{commit_sha}/similar",
    response_model=CommitSearchResponse,
    status_code=status.HTTP_200_OK,
)
async def find_similar_commits(
    project_id: str,
    commit_sha: str,
    limit: int = Query(
        default=10,
        ge=1,
        le=100,
        description="Number of similar commits to return",
    ),
    min_similarity: float = Query(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum similarity threshold",
    ),
):
    """
    Find commits similar to a given commit.

    Uses vector similarity to find commits with similar changes or context.

    Args:
        project_id: Project ID
        commit_sha: Reference commit SHA
        limit: Number of results (1-100)
        min_similarity: Minimum similarity (0.0-1.0, default 0.5 = 50%)

    Returns:
        CommitSearchResponse with similar commits

    Example:
        ```
        GET /api/projects/proj-123/repository/commits/abc123.../similar?limit=5
        ```

        Response:
        ```json
        {
            "query": "Similar to abc123...",
            "total": 5,
            "results": [
                {
                    "commit_sha": "def456...",
                    "message": "Update authentication module",
                    "similarity_score": 0.82,
                    ...
                }
            ]
        }
        ```

    Use Cases:
        - "Find commits that made similar changes"
        - "Show related work on this feature"
        - "Discover potential duplicates or conflicts"
    """
    # Get repository
    git_service = get_git_repository_service()
    repo = git_service.get_repository_by_project_id(project_id)

    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository not found for project {project_id}",
        )

    # Find similar commits
    search_service = get_git_semantic_search()
    try:
        results = await search_service.find_similar_commits(
            commit_sha=commit_sha,
            repo_id=repo["id"],
            limit=limit,
            min_similarity=min_similarity,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    # Convert to response format
    result_models = [
        CommitSearchResult(
            commit_id=r.commit_id,
            commit_sha=r.commit_sha,
            repo_id=r.repo_id,
            message=r.message,
            author_name=r.author_name,
            author_email=r.author_email,
            commit_date=r.commit_date,
            branches=r.branches,
            classification=r.classification,
            similarity_score=r.similarity_score,
            embedding_dimension=r.embedding_dimension,
        )
        for r in results
    ]

    return CommitSearchResponse(
        query=f"Similar to {commit_sha[:7]}",
        total=len(result_models),
        results=result_models,
        filters_applied={
            "reference_commit": commit_sha,
            "repo_id": repo["id"],
            "min_similarity": min_similarity,
        },
    )
