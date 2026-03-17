"""
Code Repositories API

Provides endpoints for creating and indexing code repositories.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Any
import asyncio
import logging

from ..services.git_repo_manager import get_repo_manager
from ..services.database.db_connector import get_database_connector

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/code_repos", tags=["code_repos"])


class CreateRepoRequest(BaseModel):
    """Request to create and index a code repository."""
    name: str = Field(..., description="Repository display name")
    local_path: str = Field(..., description="Absolute path to local git repository")
    github_url: str | None = Field(None, description="Optional GitHub URL")
    reindex: bool = Field(False, description="Force re-indexing if repo already exists")


class CreateRepoResponse(BaseModel):
    """Response from create and index operation."""
    success: bool
    repo_id: str | None = None
    name: str | None = None
    status: str = "unknown"  # queued, indexing, ready, error
    error_message: str | None = None
    entities_count: int = 0
    existing: bool = False


@router.post("/create-and-index", response_model=CreateRepoResponse)
async def create_and_index_repo(
    request: CreateRepoRequest,
    background_tasks: BackgroundTasks,
) -> CreateRepoResponse:
    """
    Create a code repository entry and trigger indexing.
    
    This endpoint:
    1. Validates the local path is a git repository
    2. Creates or updates the repo entry in archon_code_repos
    3. Triggers background indexing of the repository
    4. Returns immediately with status (does not wait for indexing to complete)
    
    Idempotent: If repo already exists by local_path, returns existing repo_id.
    """
    try:
        manager = get_repo_manager()
        
        # Check if repo already exists
        existing_repos = await manager.get_registered_repos()
        existing = next(
            (r for r in existing_repos if r["local_path"] == request.local_path),
            None
        )
        
        if existing and not request.reindex:
            # Return existing repo without reindexing
            db = get_database_connector()
            await db.initialize()
            
            # Get entity count
            count_result = await db.fetch(
                "SELECT COUNT(*) as cnt FROM archon_code_entities WHERE repo_id = $1",
                existing["repo_id"]
            )
            entities_count = count_result[0]["cnt"] if count_result else 0
            
            # Determine status based on last_synced
            status = "ready" if existing.get("last_synced") else "created"
            
            return CreateRepoResponse(
                success=True,
                repo_id=existing["repo_id"],
                name=existing["name"],
                status=status,
                entities_count=entities_count,
                existing=True,
            )
        
        if existing and request.reindex:
            # Reindex existing repo
            repo_id = existing["repo_id"]
            
            # Trigger reindexing in background
            background_tasks.add_task(_run_reindex, manager, repo_id)
            
            return CreateRepoResponse(
                success=True,
                repo_id=repo_id,
                name=existing["name"],
                status="indexing",
                existing=True,
            )
        
        # Create new repo
        try:
            config = await manager.register_local_repo(
                local_path=request.local_path,
                name=request.name,
                github_url=request.github_url,
            )
            
            # Trigger full ingestion in background
            background_tasks.add_task(_run_full_ingest, manager, config.repo_id)
            
            return CreateRepoResponse(
                success=True,
                repo_id=config.repo_id,
                name=request.name,
                status="queued",
                existing=False,
            )
            
        except ValueError as e:
            return CreateRepoResponse(
                success=False,
                name=request.name,
                status="error",
                error_message=str(e),
            )
            
    except Exception as e:
        logger.exception("Failed to create and index repo")
        return CreateRepoResponse(
            success=False,
            name=request.name,
            status="error",
            error_message=f"Unexpected error: {str(e)}",
        )


async def _run_full_ingest(manager, repo_id: str):
    """Run full reingestion in background."""
    try:
        logger.info(f"Starting full ingestion for repo {repo_id}")
        await manager.full_reingest(repo_id)
        logger.info(f"Full ingestion complete for repo {repo_id}")
    except Exception as e:
        logger.exception(f"Full ingestion failed for repo {repo_id}: {e}")


async def _run_reindex(manager, repo_id: str):
    """Run reindexing in background."""
    try:
        logger.info(f"Starting reindex for repo {repo_id}")
        await manager.full_reingest(repo_id)
        logger.info(f"Reindex complete for repo {repo_id}")
    except Exception as e:
        logger.exception(f"Reindex failed for repo {repo_id}: {e}")


@router.get("/{repo_id}/status")
async def get_repo_status(repo_id: str) -> dict[str, Any]:
    """
    Get the current status of a repository.
    
    Returns:
        - repo_id: Repository UUID
        - status: created, indexing, ready, error
        - entities_count: Number of indexed entities
        - last_synced: Timestamp of last successful sync
        - error_message: Error details if status is error
    """
    try:
        db = get_database_connector()
        await db.initialize()
        
        # Get repo info
        repo_result = await db.fetchrow(
            """
            SELECT id, name, local_path, last_synced, last_commit_sha, created_at
            FROM archon_code_repos
            WHERE id = $1
            """,
            repo_id
        )
        
        if not repo_result:
            raise HTTPException(status_code=404, detail=f"Repository {repo_id} not found")
        
        # Get entity count
        count_result = await db.fetch(
            "SELECT COUNT(*) as cnt FROM archon_code_entities WHERE repo_id = $1",
            repo_id
        )
        entities_count = count_result[0]["cnt"] if count_result else 0
        
        # Determine status
        if repo_result["last_synced"]:
            status = "ready"
        elif entities_count > 0:
            status = "indexing"  # Has entities but no last_synced yet
        else:
            status = "created"  # No entities, not yet indexed
        
        return {
            "repo_id": str(repo_result["id"]),
            "name": repo_result["name"],
            "status": status,
            "entities_count": entities_count,
            "last_synced": repo_result["last_synced"].isoformat() if repo_result["last_synced"] else None,
            "last_commit": repo_result["last_commit_sha"],
            "created_at": repo_result["created_at"].isoformat() if repo_result["created_at"] else None,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get repo status for {repo_id}")
        raise HTTPException(status_code=500, detail=f"Error getting repo status: {str(e)}")


@router.get("")
async def list_repos() -> list[dict[str, Any]]:
    """
    List all registered code repositories.
    
    Returns list of repos with their current status.
    """
    try:
        manager = get_repo_manager()
        repos = await manager.get_registered_repos()
        
        # Enrich with entity counts
        db = get_database_connector()
        await db.initialize()
        
        for repo in repos:
            count_result = await db.fetch(
                "SELECT COUNT(*) as cnt FROM archon_code_entities WHERE repo_id = $1",
                repo["repo_id"]
            )
            repo["entities_count"] = count_result[0]["cnt"] if count_result else 0
            repo["status"] = "ready" if repo.get("last_synced") else "created"
        
        return repos
        
    except Exception as e:
        logger.exception("Failed to list repos")
        raise HTTPException(status_code=500, detail=f"Error listing repos: {str(e)}")
