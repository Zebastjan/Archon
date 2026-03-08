"""
Git-Aware RAG API

Endpoints for integrating Git commit context into RAG queries.

Features:
- Combined document + Git commit search
- File history queries
- Commit context retrieval for RAG
- Semantic commit search with filters
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..config.logfire_config import get_logger
from ..services.search.rag_service import RAGService
from ..utils import get_supabase_client

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["git-rag"])


class GitAwareSearchRequest(BaseModel):
    """Request for combined document + Git search."""

    query: str = Field(..., description="Search query")
    source: str | None = Field(None, description="Optional source filter for documents")
    match_count: int = Field(5, ge=1, le=50, description="Number of document results")
    include_git_commits: bool = Field(True, description="Include Git commit results")
    git_match_count: int = Field(3, ge=0, le=20, description="Number of Git commits to include")
    repo_id: str | None = Field(None, description="Filter commits by repository")
    branch: str | None = Field(None, description="Filter commits by branch")


class FileHistoryRequest(BaseModel):
    """Request for file commit history."""

    file_path: str = Field(..., description="Path to the file")
    repo_id: str = Field(..., description="Repository ID")
    match_count: int = Field(10, ge=1, le=50, description="Number of commits to return")
    branch: str | None = Field(None, description="Optional branch filter")


@router.post("/rag/search/git-aware")
async def search_with_git_context(request: GitAwareSearchRequest) -> dict[str, Any]:
    """
    Enhanced RAG search that includes Git commit context.

    Combines regular document/code search with Git commit history for
    richer context in code-related queries.

    Example queries:
    - "How does authentication work?" (with recent auth-related commits)
    - "Explain the database layer" (with DB-related commits)
    - "Show performance optimizations" (with performance commits)

    Returns:
        Combined results with both document matches and relevant commits
    """
    try:
        rag_service = RAGService(get_supabase_client())

        success, result = await rag_service.search_with_git_context(
            query=request.query,
            source=request.source,
            match_count=request.match_count,
            include_git_commits=request.include_git_commits,
            git_match_count=request.git_match_count,
            repo_id=request.repo_id,
            branch=request.branch,
        )

        if not success:
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Search failed"),
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Git-aware search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rag/git/file-history")
async def get_file_history(request: FileHistoryRequest) -> dict[str, Any]:
    """
    Get commit history for a specific file.

    Useful for understanding how a file has evolved over time,
    what changes were made, and by whom.

    Returns:
        List of commits that modified the file
    """
    try:
        rag_service = RAGService(get_supabase_client())

        success, result = await rag_service.get_file_history_context(
            file_path=request.file_path,
            repo_id=request.repo_id,
            match_count=request.match_count,
            branch=request.branch,
        )

        if not success:
            raise HTTPException(
                status_code=404 if "not found" in result.get("error", "").lower() else 500,
                detail=result.get("error", "File history lookup failed"),
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File history lookup failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rag/git/commit/{commit_sha}")
async def get_commit_context(
    commit_sha: str,
    repo_id: str = Query(..., description="Repository ID"),
) -> dict[str, Any]:
    """
    Get detailed context for a specific commit.

    Retrieves full commit information including:
    - Commit message and metadata
    - Classification (intent, risk level, etc.)
    - Files changed
    - Parent commits

    Useful for RAG queries like:
    - "What did commit abc123 change?"
    - "Explain the changes in commit xyz789"

    Returns:
        Detailed commit context
    """
    try:
        rag_service = RAGService(get_supabase_client())

        success, result = await rag_service.get_commit_context_for_rag(
            commit_sha=commit_sha,
            repo_id=repo_id,
        )

        if not success:
            raise HTTPException(
                status_code=404,
                detail=result.get("error", "Commit not found"),
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Commit context lookup failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rag/git/search")
async def search_commits(
    query: str = Query(..., description="Search query", min_length=1),
    match_count: int = Query(5, ge=1, le=50, description="Number of results"),
    repo_id: str | None = Query(None, description="Filter by repository"),
    branch: str | None = Query(None, description="Filter by branch"),
    since: str | None = Query(None, description="Filter commits after date (ISO format)"),
    until: str | None = Query(None, description="Filter commits before date (ISO format)"),
    intent: list[str] | None = Query(None, description="Filter by intent (feature, bugfix, etc.)"),
    risk: list[str] | None = Query(None, description="Filter by risk level (high, medium, low)"),
    author: str | None = Query(None, description="Filter by author"),
    breaking_only: bool = Query(False, description="Only breaking changes"),
    security_only: bool = Query(False, description="Only security-related commits"),
) -> dict[str, Any]:
    """
    Semantic search across Git commits.

    Enables natural language queries like:
    - "performance improvements"
    - "authentication changes"
    - "bug fixes in the API layer"

    Supports rich filtering by branch, date, classification, etc.

    Returns:
        List of matching commits with similarity scores
    """
    try:
        rag_service = RAGService(get_supabase_client())

        success, result = await rag_service.search_git_commits(
            query=query,
            match_count=match_count,
            repo_id=repo_id,
            branch=branch,
            since=since,
            until=until,
            intent_filter=intent,
            risk_filter=risk,
            author=author,
            breaking_only=breaking_only,
            security_only=security_only,
        )

        if not success:
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Commit search failed"),
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Commit search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
