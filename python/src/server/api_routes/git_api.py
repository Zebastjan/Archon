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
from ..services.database import get_database_connector
from ..services.git.git_commit_classifier import GitCommitClassifier
from ..services.git.git_diff_service import GitDiffService
from ..services.git.git_repository_service import (
    GitBranchNotFoundError,
    GitCommitNotFoundError,
    GitError,
    GitFileNotFoundError,
    GitRepositoryNotFoundError,
    GitRepositoryService,
)


class ExtractCodeEntitiesRequest(BaseModel):
    commit_sha: str | None = None
    file_paths: list[str] | None = None
    batch_size: int = 50


class SyncCommitsWithEntitiesRequest(BaseModel):
    branch_name: str | None = None
    max_commits: int | None = None
    extract_entities: bool = True
    entity_batch_size: int = 50

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

        db = get_database_connector()

        # Verify project exists
        project_response = await db.fetch(
            "SELECT id FROM archon_projects WHERE id = $1",
            project_id
        )

        if not project_response:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Project not found: {project_id}",
            )

        # Check if repository already exists for this project
        existing_repo_response = await db.fetch(
            "SELECT id FROM archon_git_repositories WHERE source_id = $1",
            project_id
        )

        if existing_repo_response:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Repository already initialized for this project. Delete existing repository first.",
            )

        # Create source entry for repository
        repo_name = Path(request.repo_path).name

        source_response = await db.fetch(
            """
            INSERT INTO archon_sources
            (source_type, source_url, source_display_name, title, status)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
            """,
            "git_repository",
            request.repo_path,
            repo_name,
            repo_name,
            "pending"
        )

        if not source_response:
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create source entry",
            )

        source_record = source_response[0]
        source_id = str(source_record["id"])

        # Register repository using GitRepositoryService
        git_service = GitRepositoryService()
        success, result = await git_service.register_repository(
            repo_path=request.repo_path,
            source_id=source_id,
            config=request.config,
        )

        if not success:
            # Cleanup source entry if registration failed
            await db.execute(
                "DELETE FROM archon_sources WHERE id = $1",
                source_id
            )
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

        db = get_database_connector()

        # Get repository by source_id (which links to project)
        repo_response = await db.fetch(
            "SELECT * FROM archon_git_repositories WHERE source_id = $1",
            project_id
        )

        if not repo_response:
            return None

        return repo_response[0]

    except Exception as e:
        logger.error(f"Error getting repository: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        ) from e


@router.get("/projects/{project_id}/repository/branches")
async def list_repository_branches(project_id: str):
    """
    List all branches in a repository.

    Args:
        project_id: UUID of project

    Returns:
        List of branch names with default branch marked

    Raises:
        HTTPException 404: If project or repository not found
        HTTPException 500: If operation fails
    """
    try:
        logfire.info(f"Listing branches for project {project_id}")

        db = get_database_connector()

        # Get repository for project
        repo_response = await db.fetch(
            "SELECT id, repo_url, default_branch, source_id FROM archon_git_repositories WHERE source_id = $1",
            project_id
        )

        if not repo_response or len(repo_response) == 0:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Repository not found for project",
            )

        repo_record = repo_response[0]
        repo_path = str(repo_record["repo_url"])
        default_branch = str(repo_record["default_branch"])

        # List branches using service
        service = GitRepositoryService()
        branches = service.list_branches(repo_path)

        return {
            "branches": branches,
            "default_branch": default_branch,
        }

    except HTTPException:
        raise
    except GitRepositoryNotFoundError as e:
        logger.error(f"Repository not found: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Repository path is invalid or not a git repository",
        ) from e
    except Exception as e:
        logger.error(f"Failed to list branches: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list branches: {str(e)}",
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

        db = get_database_connector()

        # Get repository
        repo_response = await db.fetch(
            "SELECT id, source_id FROM archon_git_repositories WHERE source_id = $1",
            project_id
        )

        if not repo_response:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Repository not found for this project",
            )

        repo_record = repo_response[0]
        repo_id = str(repo_record["id"])
        source_id = str(repo_record["source_id"])

        # Delete repository (cascade deletes commits and files via DB constraints)
        await db.execute(
            "DELETE FROM archon_git_repositories WHERE id = $1",
            repo_id
        )

        # Delete source entry
        await db.execute(
            "DELETE FROM archon_sources WHERE id = $1",
            source_id
        )

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

        db = get_database_connector()

        # Get repository
        repo_response = await db.fetch(
            "SELECT id, default_branch FROM archon_git_repositories WHERE source_id = $1",
            project_id
        )

        if not repo_response:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Repository not found for this project",
            )

        repo_id = repo_response[0]["id"]
        default_branch = repo_response[0]["default_branch"]

        # Use default branch if none specified
        if branch_name is None:
            branch_name = default_branch

        # Query commits with optional branch filter
        import json
        if branch_name:
            commits_response = await db.fetch(
                """
                SELECT * FROM archon_git_commits
                WHERE repo_id = $1 AND branches @> $2
                ORDER BY commit_date DESC
                LIMIT $3 OFFSET $4
                """,
                repo_id,
                json.dumps([branch_name]),
                limit,
                offset
            )

            # Get total count
            count_response = await db.fetch(
                "SELECT COUNT(*) as count FROM archon_git_commits WHERE repo_id = $1 AND branches @> $2",
                repo_id,
                json.dumps([branch_name])
            )
        else:
            commits_response = await db.fetch(
                """
                SELECT * FROM archon_git_commits
                WHERE repo_id = $1
                ORDER BY commit_date DESC
                LIMIT $2 OFFSET $3
                """,
                repo_id,
                limit,
                offset
            )

            # Get total count
            count_response = await db.fetch(
                "SELECT COUNT(*) as count FROM archon_git_commits WHERE repo_id = $1",
                repo_id
            )

        total_count = count_response[0]["count"] if count_response else 0

        return {
            "commits": commits_response or [],
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

        db = get_database_connector()

        # Get repository
        repo_response = await db.fetch(
            "SELECT id, default_branch FROM archon_git_repositories WHERE source_id = $1",
            project_id
        )

        if not repo_response:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Repository not found for this project",
            )

        repo_id = repo_response[0]["id"]
        default_branch = repo_response[0]["default_branch"]

        # Use default branch if none specified
        branch_name = request.branch_name or default_branch

        # Sync commits using GitRepositoryService
        git_service = GitRepositoryService()
        success, result = await git_service.sync_commits(
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

        db = get_database_connector()

        # Get repository
        repo_response = await db.fetch(
            "SELECT id, current_head_sha FROM archon_git_repositories WHERE source_id = $1",
            project_id
        )

        if not repo_response:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Repository not found for this project",
            )

        repo_id = repo_response[0]["id"]
        current_head_sha = repo_response[0]["current_head_sha"]

        # Resolve "HEAD" to actual SHA
        if commit_sha.upper() == "HEAD":
            commit_sha = current_head_sha

        # Get file tree using GitRepositoryService
        git_service = GitRepositoryService()
        success, result = await git_service.get_file_tree(
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

        db = get_database_connector()

        # Get repository
        repo_response = await db.fetch(
            "SELECT id, current_head_sha FROM archon_git_repositories WHERE source_id = $1",
            project_id
        )

        if not repo_response:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Repository not found for this project",
            )

        repo_id = repo_response[0]["id"]
        current_head_sha = repo_response[0]["current_head_sha"]

        # Resolve "HEAD" to actual SHA
        if commit_sha.upper() == "HEAD":
            commit_sha = current_head_sha

        # Get file content using GitRepositoryService
        git_service = GitRepositoryService()
        success, result = await git_service.get_file_content(
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


@router.get("/projects/{project_id}/repository/diff")
async def get_diff(
    project_id: str,
    from_commit: str,
    to_commit: str,
    file_path: str | None = None,
):
    """
    Get structured diff between two commits.

    Args:
        project_id: UUID of project
        from_commit: Starting commit SHA
        to_commit: Ending commit SHA
        file_path: Optional file path to filter diff

    Returns:
        Structured diff with file-level and hunk-level details:
        {
            "from_commit": "abc123",
            "to_commit": "def456",
            "files_changed": 3,
            "additions": 45,
            "deletions": 12,
            "files": [
                {
                    "path": "src/main.py",
                    "old_path": null,
                    "status": "modified",
                    "language": "python",
                    "additions": 15,
                    "deletions": 8,
                    "is_binary": false,
                    "hunks": [
                        {
                            "old_start": 10,
                            "old_lines": 5,
                            "new_start": 10,
                            "new_lines": 12,
                            "context": "def main()",
                            "diff_text": "@@ -10,5 +10,12 @@ def main()...",
                            "additions": 7,
                            "deletions": 0
                        }
                    ]
                }
            ]
        }

    Raises:
        404: Repository, commits, or file not found
        400: Invalid commit SHA or diff generation failed
        500: Internal server error
    """
    try:
        db = get_database_connector()

        # Get project's source_id
        project_response = await db.fetch(
            "SELECT * FROM archon_projects WHERE id = $1",
            project_id
        )

        if not project_response:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Project not found: {project_id}",
            )

        project = project_response[0]
        source_id = project.get("source_id")

        if not source_id:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Project does not have an associated Git repository",
            )

        # Get repository by source_id
        repo_response = await db.fetch(
            "SELECT * FROM archon_git_repositories WHERE source_id = $1",
            source_id
        )

        if not repo_response:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Git repository not found for project: {project_id}",
            )

        repo_record = repo_response[0]
        repo_path = repo_record["repo_url"]

        # Generate diff using GitDiffService
        git_service = GitRepositoryService()
        diff_service = GitDiffService(git_service)

        structured_diff = diff_service.get_diff(
            repo_path=repo_path,
            from_sha=from_commit,
            to_sha=to_commit,
            file_path=file_path,
        )

        # Convert dataclasses to dicts for JSON response
        return {
            "from_commit": structured_diff.from_commit,
            "to_commit": structured_diff.to_commit,
            "files_changed": structured_diff.files_changed,
            "additions": structured_diff.additions,
            "deletions": structured_diff.deletions,
            "files": [
                {
                    "path": f.path,
                    "old_path": f.old_path,
                    "status": f.status,
                    "language": f.language,
                    "additions": f.additions,
                    "deletions": f.deletions,
                    "is_binary": f.is_binary,
                    "hunks": [
                        {
                            "old_start": h.old_start,
                            "old_lines": h.old_lines,
                            "new_start": h.new_start,
                            "new_lines": h.new_lines,
                            "context": h.context,
                            "diff_text": h.diff_text,
                            "additions": h.additions,
                            "deletions": h.deletions,
                        }
                        for h in f.hunks
                    ],
                }
                for f in structured_diff.files
            ],
        }

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
        logger.error(f"Error generating diff: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        ) from e


@router.post("/projects/{project_id}/repository/extract-entities")
async def extract_code_entities(project_id: str, request: ExtractCodeEntitiesRequest):
    """
    Extract code entities and relationships from source files.

    Uses Tree-sitter parsers to analyze source code structure (functions, classes,
    methods, imports, calls) and store them for querying.

    Args:
        project_id: UUID of project
        request: Extraction parameters (commit_sha, file_paths, batch_size)

    Returns:
        Extraction results with counts of entities and relationships created

    Raises:
        HTTPException 404: If repository not found
        HTTPException 400: If commit not found
        HTTPException 500: If extraction fails
    """
    try:
        logfire.info(f"Extracting code entities for project {project_id} | commit={request.commit_sha}")

        db = get_database_connector()

        # Get repository
        repo_response = await db.fetch(
            "SELECT id, current_head_sha FROM archon_git_repositories WHERE source_id = $1",
            project_id
        )

        if not repo_response:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Repository not found for this project",
            )

        repo_id = repo_response[0]["id"]
        current_head_sha = repo_response[0]["current_head_sha"]

        # Use HEAD if no commit SHA specified
        commit_sha = request.commit_sha or current_head_sha

        # Extract entities using GitRepositoryService
        git_service = GitRepositoryService()
        result = await git_service.extract_code_entities(
            repo_id=repo_id,
            commit_sha=commit_sha,
            file_paths=request.file_paths,
            batch_size=request.batch_size,
        )

        logger.info(
            f"Entity extraction complete for project {project_id}: "
            f"{result['processed']} files, {result['entities_created']} entities"
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
        logger.error(f"Error extracting code entities: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        ) from e


@router.post("/projects/{project_id}/repository/sync-with-entities")
async def sync_commits_with_entities(project_id: str, request: SyncCommitsWithEntitiesRequest):
    """
    Sync commits and extract code entities in one operation.

    Combines commit synchronization with code entity extraction for convenience.

    Args:
        project_id: UUID of project
        request: Sync parameters including entity extraction options

    Returns:
        Combined sync and extraction results

    Raises:
        HTTPException 404: If repository not found
        HTTPException 400: If branch not found
        HTTPException 500: If operation fails
    """
    try:
        logfire.info(
            f"Syncing commits with entity extraction for project {project_id} | "
            f"branch={request.branch_name}, extract={request.extract_entities}"
        )

        db = get_database_connector()

        # Get repository
        repo_response = await db.fetch(
            "SELECT id, default_branch FROM archon_git_repositories WHERE source_id = $1",
            project_id
        )

        if not repo_response:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Repository not found for this project",
            )

        repo_id = repo_response[0]["id"]
        default_branch = repo_response[0]["default_branch"]
        branch_name = request.branch_name or default_branch

        # Sync commits with entity extraction
        git_service = GitRepositoryService()
        success, result = await git_service.sync_commits_with_code_entities(
            repo_id=repo_id,
            branch_name=branch_name,
            max_commits=request.max_commits,
            extract_entities=request.extract_entities,
            entity_batch_size=request.entity_batch_size,
        )

        if not success:
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("sync_result", {}).get("error", "Failed to sync commits"),
            )

        logger.info(
            f"Sync with entities complete for project {project_id}: "
            f"{result['sync_result'].get('commit_count', 0)} commits, "
            f"entities={result.get('entity_result', {})}"
        )

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
        logger.error(f"Error syncing commits with entities: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        ) from e
