"""
Git Repository API endpoints for Archon

Handles:
- Repository initialization (linking existing repos to projects)
- Commit history browsing
- File tree navigation at specific commits
- File content retrieval with syntax highlighting support
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel

from ..config.logfire_config import get_logger, logfire
from ..services.git.git_repository_service import (
    GitBranchNotFoundError,
    GitCommitNotFoundError,
    GitError,
    GitFileNotFoundError,
    GitRepositoryNotFoundError,
    GitRepositoryService,
)
from ..utils import get_supabase_client

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["git"])


class InitializeRepositoryRequest(BaseModel):
    repo_path: str
    branch_name: str | None = None
    config: dict | None = None


class SyncCommitsRequest(BaseModel):
    branch_name: str | None = None
    max_commits: int | None = None


def _check_for_submodules(repo_path: str) -> bool:
    """
    Check if repository contains Git submodules.

    Args:
        repo_path: Path to repository

    Returns:
        True if .gitmodules file exists, False otherwise
    """
    gitmodules_path = Path(repo_path) / ".gitmodules"
    return gitmodules_path.exists()


@router.post("/projects/{project_id}/repository")
async def initialize_repository(project_id: str, request: InitializeRepositoryRequest):
    """
    Initialize a git repository for a project.

    Links an existing local git repository to an Archon project.
    Creates a source entry and repository metadata.

    Args:
        project_id: UUID of project
        request: Repository initialization parameters

    Returns:
        Repository metadata with repo_id, repo_name, default_branch, current_head_sha

    Raises:
        HTTPException 400: If repository contains submodules or is invalid
        HTTPException 404: If project not found
        HTTPException 500: If database operation fails
    """
    try:
        logfire.info(f"Initializing git repository for project {project_id} | path={request.repo_path}")

        # Check for submodules (explicitly not supported)
        if _check_for_submodules(request.repo_path):
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Git submodules are not supported",
                    "message": (
                        "Git submodules are not supported. "
                        "Please use a monorepo structure or create separate Archon projects instead."
                    ),
                    "alternatives": [
                        "Monorepo: Keep all code in a single repository",
                        "Separate Projects: Create multiple Archon projects and link via 'Related Projects'",
                    ],
                },
            )

        supabase_client = get_supabase_client()

        # Verify project exists
        project_response = supabase_client.table("archon_projects").select("id").eq("id", project_id).execute()

        if not project_response.data:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Project not found: {project_id}",
            )

        # Check if repository already exists for this project
        existing_repo_response = (
            supabase_client.table("archon_git_repositories").select("id").eq("source_id", project_id).execute()
        )

        if existing_repo_response.data:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Repository already initialized for this project. Delete existing repository first.",
            )

        # Create source entry for repository
        repo_name = Path(request.repo_path).name
        source_data = {
            "source_type": "git_repository",
            "source_url": request.repo_path,
            "source_display_name": repo_name,
            "title": repo_name,
            "status": "pending",
        }

        source_response = supabase_client.table("archon_sources").insert(source_data).execute()

        if not source_response.data:
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create source entry",
            )

        source_record = source_response.data[0]
        source_id = str(source_record["id"])

        # Register repository using GitRepositoryService
        git_service = GitRepositoryService(supabase_client)
        success, result = git_service.register_repository(
            repo_path=request.repo_path,
            source_id=source_id,
            config=request.config,
        )

        if not success:
            # Cleanup source entry if registration failed
            supabase_client.table("archon_sources").delete().eq("id", source_id).execute()
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to register repository"),
            )

        logger.info(f"Successfully initialized repository for project {project_id} | repo_id={result['repo_id']}")

        return {
            "repo_id": result["repo_id"],
            "repo_name": result["repo_name"],
            "default_branch": result["default_branch"],
            "current_head_sha": result["current_head_sha"],
        }

    except HTTPException:
        raise
    except GitRepositoryNotFoundError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=e.to_dict(),
        ) from e
    except GitError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=e.to_dict(),
        ) from e
    except Exception as e:
        logger.error(f"Error initializing repository: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        ) from e


@router.get("/projects/{project_id}/repository")
async def get_repository(project_id: str):
    """
    Get repository metadata for a project.

    Args:
        project_id: UUID of project

    Returns:
        Repository metadata or null if no repository linked

    Raises:
        HTTPException 500: If database query fails
    """
    try:
        logfire.debug(f"Getting repository metadata for project {project_id}")

        supabase_client = get_supabase_client()

        # Get repository by source_id (which links to project)
        repo_response = (
            supabase_client.table("archon_git_repositories").select("*").eq("source_id", project_id).execute()
        )

        if not repo_response.data:
            return None

        return repo_response.data[0]

    except Exception as e:
        logger.error(f"Error getting repository: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        ) from e


@router.delete("/projects/{project_id}/repository")
async def delete_repository(project_id: str):
    """
    Delete repository and all associated commits/files.

    Cascading delete removes:
    - Repository record
    - All commit records
    - All file records
    - Source entry

    Args:
        project_id: UUID of project

    Returns:
        Success message

    Raises:
        HTTPException 404: If repository not found
        HTTPException 500: If database operation fails
    """
    try:
        logfire.info(f"Deleting repository for project {project_id}")

        supabase_client = get_supabase_client()

        # Get repository
        repo_response = (
            supabase_client.table("archon_git_repositories")
            .select("id, source_id")
            .eq("source_id", project_id)
            .execute()
        )

        if not repo_response.data:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Repository not found for this project",
            )

        repo_record = repo_response.data[0]
        repo_id = str(repo_record["id"])
        source_id = str(repo_record["source_id"])

        # Delete repository (cascade deletes commits and files via DB constraints)
        supabase_client.table("archon_git_repositories").delete().eq("id", repo_id).execute()

        # Delete source entry
        supabase_client.table("archon_sources").delete().eq("id", source_id).execute()

        logger.info(f"Successfully deleted repository {repo_id} for project {project_id}")

        return {"message": "Repository deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting repository: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        ) from e


@router.get("/projects/{project_id}/repository/commits")
async def get_commits(
    project_id: str,
    branch_name: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    """
    Get commit history for repository.

    Args:
        project_id: UUID of project
        branch_name: Optional branch name to filter by
        limit: Maximum number of commits to return (default 100)
        offset: Number of commits to skip for pagination (default 0)

    Returns:
        List of commits with pagination metadata

    Raises:
        HTTPException 404: If repository not found
        HTTPException 500: If database query fails
    """
    try:
        logfire.debug(
            f"Getting commits for project {project_id} | branch={branch_name}, limit={limit}, offset={offset}"
        )

        supabase_client = get_supabase_client()

        # Get repository
        repo_response = (
            supabase_client.table("archon_git_repositories")
            .select("id, default_branch")
            .eq("source_id", project_id)
            .execute()
        )

        if not repo_response.data:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Repository not found for this project",
            )

        repo_id = repo_response.data[0]["id"]
        default_branch = repo_response.data[0]["default_branch"]

        # Use default branch if none specified
        if branch_name is None:
            branch_name = default_branch

        # Query commits
        query = supabase_client.table("archon_git_commits").select("*").eq("repo_id", repo_id)

        # Filter by branch if specified
        if branch_name:
            query = query.contains("branches", [branch_name])

        # Apply pagination and ordering
        commits_response = query.order("commit_date", desc=True).range(offset, offset + limit - 1).execute()

        # Get total count (for pagination metadata)
        count_query = supabase_client.table("archon_git_commits").select("id", count="exact").eq("repo_id", repo_id)

        if branch_name:
            count_query = count_query.contains("branches", [branch_name])

        count_response = count_query.execute()
        total_count = count_response.count if hasattr(count_response, "count") else 0

        return {
            "commits": commits_response.data or [],
            "pagination": {
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": (offset + limit) < total_count,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting commits: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        ) from e


@router.post("/projects/{project_id}/repository/sync")
async def sync_commits(project_id: str, request: SyncCommitsRequest | None = None):
    """
    Sync commits from git repository to database.

    Reads git log and populates archon_git_commits table.

    Args:
        project_id: UUID of project
        request: Optional sync parameters (branch_name, max_commits)

    Returns:
        Sync result with commit_count and branch

    Raises:
        HTTPException 404: If repository not found
        HTTPException 400: If branch not found
        HTTPException 500: If sync operation fails
    """
    try:
        # Default to empty request if none provided
        if request is None:
            request = SyncCommitsRequest()

        logfire.info(
            f"Syncing commits for project {project_id} | branch={request.branch_name}, max_commits={request.max_commits}"
        )

        supabase_client = get_supabase_client()

        # Get repository
        repo_response = (
            supabase_client.table("archon_git_repositories")
            .select("id, default_branch")
            .eq("source_id", project_id)
            .execute()
        )

        if not repo_response.data:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Repository not found for this project",
            )

        repo_id = repo_response.data[0]["id"]
        default_branch = repo_response.data[0]["default_branch"]

        # Use default branch if none specified
        branch_name = request.branch_name or default_branch

        # Sync commits using GitRepositoryService
        git_service = GitRepositoryService(supabase_client)
        success, result = git_service.sync_commits(
            repo_id=repo_id,
            branch_name=branch_name,
            max_commits=request.max_commits,
        )

        if not success:
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to sync commits"),
            )

        logger.info(f"Successfully synced {result['commit_count']} commits for project {project_id}")

        return result

    except HTTPException:
        raise
    except GitBranchNotFoundError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=e.to_dict(),
        ) from e
    except GitError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=e.to_dict(),
        ) from e
    except Exception as e:
        logger.error(f"Error syncing commits: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        ) from e


@router.get("/projects/{project_id}/repository/tree")
async def get_file_tree(
    project_id: str,
    commit_sha: str,
    path_prefix: str = "",
):
    """
    Get file tree at a specific commit.

    Args:
        project_id: UUID of project
        commit_sha: Commit SHA to read from (use "HEAD" for latest)
        path_prefix: Optional path prefix to filter results

    Returns:
        File tree with metadata (files list, file_count, commit_sha)

    Raises:
        HTTPException 404: If repository or commit not found
        HTTPException 500: If tree retrieval fails
    """
    try:
        logfire.debug(f"Getting file tree for project {project_id} | commit={commit_sha}, path_prefix={path_prefix}")

        supabase_client = get_supabase_client()

        # Get repository
        repo_response = (
            supabase_client.table("archon_git_repositories")
            .select("id, current_head_sha")
            .eq("source_id", project_id)
            .execute()
        )

        if not repo_response.data:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Repository not found for this project",
            )

        repo_id = repo_response.data[0]["id"]
        current_head_sha = repo_response.data[0]["current_head_sha"]

        # Resolve "HEAD" to actual SHA
        if commit_sha.upper() == "HEAD":
            commit_sha = current_head_sha

        # Get file tree using GitRepositoryService
        git_service = GitRepositoryService(supabase_client)
        success, result = git_service.get_file_tree(
            repo_id=repo_id,
            commit_sha=commit_sha,
            path_prefix=path_prefix,
        )

        if not success:
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to get file tree"),
            )

        return result

    except HTTPException:
        raise
    except GitCommitNotFoundError as e:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=e.to_dict(),
        ) from e
    except GitError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=e.to_dict(),
        ) from e
    except Exception as e:
        logger.error(f"Error getting file tree: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        ) from e


@router.get("/projects/{project_id}/repository/file")
async def get_file_content(
    project_id: str,
    commit_sha: str,
    file_path: str,
):
    """
    Get file content at a specific commit.

    Args:
        project_id: UUID of project
        commit_sha: Commit SHA to read from (use "HEAD" for latest)
        file_path: Path to file within repository

    Returns:
        File content with metadata (content, file_path, file_size, blob_sha, language, commit_sha)

    Raises:
        HTTPException 404: If repository, commit, or file not found
        HTTPException 400: If file is binary
        HTTPException 500: If content retrieval fails
    """
    try:
        logfire.debug(f"Getting file content for project {project_id} | commit={commit_sha}, file_path={file_path}")

        supabase_client = get_supabase_client()

        # Get repository
        repo_response = (
            supabase_client.table("archon_git_repositories")
            .select("id, current_head_sha")
            .eq("source_id", project_id)
            .execute()
        )

        if not repo_response.data:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Repository not found for this project",
            )

        repo_id = repo_response.data[0]["id"]
        current_head_sha = repo_response.data[0]["current_head_sha"]

        # Resolve "HEAD" to actual SHA
        if commit_sha.upper() == "HEAD":
            commit_sha = current_head_sha

        # Get file content using GitRepositoryService
        git_service = GitRepositoryService(supabase_client)
        success, result = git_service.get_file_content(
            repo_id=repo_id,
            commit_sha=commit_sha,
            file_path=file_path,
        )

        if not success:
            error_detail = result.get("error", "Failed to get file content")
            if result.get("is_binary"):
                raise HTTPException(
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                    detail=error_detail,
                )
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_detail,
            )

        return result

    except HTTPException:
        raise
    except GitCommitNotFoundError as e:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=e.to_dict(),
        ) from e
    except GitFileNotFoundError as e:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=e.to_dict(),
        ) from e
    except GitError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=e.to_dict(),
        ) from e
    except Exception as e:
        logger.error(f"Error getting file content: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        ) from e
