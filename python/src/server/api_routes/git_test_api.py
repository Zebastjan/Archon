"""
Git Test Fixtures API endpoints for Archon

Handles:
- Initializing test fixtures as project repositories
- Cleanup of test fixtures
"""

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config.logfire_config import get_logger, logfire
from ..services.git.git_repository_service import GitRepositoryService
from ..utils import get_supabase_client

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["git-test-fixtures"])

# Path to test fixtures
FIXTURES_DIR = Path(__file__).parent.parent.parent.parent / "tests" / "git_integration" / "fixtures"

# Mapping of fixture names to their directories
FIXTURE_MAP = {"simple-commits": "simple-commits", "multi-branch": "multi-branch", "file-structure": "file-structure"}


class InitializeTestFixtureRequest(BaseModel):
    fixture_name: str


class InitializeTestFixtureResponse(BaseModel):
    success: bool
    message: str
    repo_id: str | None = None
    repo_name: str | None = None


@router.post("/projects/{project_id}/test-fixtures/initialize")
async def initialize_test_fixture(project_id: str, request: InitializeTestFixtureRequest):
    """
    Initialize a test fixture as the repository for a project.

    Copies the fixture repository to a temporary location and links it
    to the specified project, initializing it as a proper Git repository
    in Archon.

    Args:
        project_id: UUID of project to link fixture to
        request: Fixture initialization parameters

    Returns:
        Repository metadata with initialization status

    Raises:
        HTTPException 400: If fixture name is invalid
        HTTPException 404: If fixture not found
        HTTPException 500: If initialization fails
    """
    try:
        logfire.info(f"Initializing test fixture '{request.fixture_name}' for project {project_id}")

        # Validate fixture name
        if request.fixture_name not in FIXTURE_MAP:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid fixture name: {request.fixture_name}. Valid options: {list(FIXTURE_MAP.keys())}",
            )

        fixture_dir_name = FIXTURE_MAP[request.fixture_name]
        fixture_path = FIXTURES_DIR / fixture_dir_name / ".repo"

        if not fixture_path.exists():
            raise HTTPException(status_code=404, detail=f"Fixture directory not found: {fixture_path}")

        # Read EXPECTED.json for fixture metadata
        expected_file = FIXTURES_DIR / fixture_dir_name / "EXPECTED.json"
        if not expected_file.exists():
            raise HTTPException(status_code=404, detail=f"EXPECTED.json not found for fixture: {request.fixture_name}")

        with open(expected_file) as f:
            expected_data = json.load(f)

        supabase_client = get_supabase_client()

        # Use project_id directly as source_id
        source_id = project_id

        # Check if project already has a repository
        existing_repo_response = (
            supabase_client.table("archon_git_repositories")
            .select("id, source_id")
            .eq("source_id", project_id)
            .execute()
        )

        if existing_repo_response.data:
            # Delete existing repository first
            logfire.info(f"Removing existing repository for project {project_id}")
            repo_id = str(existing_repo_response.data[0]["id"])
            existing_source_id = str(existing_repo_response.data[0]["source_id"])
            supabase_client.table("archon_git_repositories").delete().eq("id", repo_id).execute()

            # Also delete the source entry using the actual source_id from the repo record
            supabase_client.table("archon_sources").delete().eq("source_id", existing_source_id).execute()

        # Clean up old temp directories for this project (Option A)
        temp_base_dir = Path(tempfile.gettempdir()) / "archon_test_fixtures"
        if temp_base_dir.exists():
            for old_temp_dir in temp_base_dir.glob(f"{project_id}_*"):
                if old_temp_dir.is_dir():
                    logfire.info(f"Removing old temp directory: {old_temp_dir}")
                    shutil.rmtree(old_temp_dir)

        # Copy fixture to a temp directory that will persist
        temp_dir = temp_base_dir / f"{project_id}_{request.fixture_name}"
        shutil.copytree(fixture_path, temp_dir)

        # Check if source already exists (for idempotency)
        existing_source_response = supabase_client.table("archon_sources").select("source_id").eq("source_id", source_id).execute()

        # Build source data with metadata
        source_data = {
            "source_id": source_id,
            "source_type": "git_repository",
            "source_url": str(temp_dir),
            "source_display_name": f"test-fixture-{request.fixture_name}",
            "title": f"test-fixture-{request.fixture_name}",
            "status": "active",
            "metadata": {
                "is_test_fixture": True,
                "fixture_name": request.fixture_name,
                "temp_path": str(temp_dir),
            },
        }

        if existing_source_response.data:
            # Update existing source
            logfire.info(f"Updating existing source for project {project_id}")
            source_response = supabase_client.table("archon_sources").update(source_data).eq("source_id", source_id).execute()
        else:
            # Create new source entry
            source_response = supabase_client.table("archon_sources").insert(source_data).execute()

        if not source_response.data:
            raise HTTPException(status_code=500, detail="Failed to create source entry for test fixture")

        # Register repository using GitRepositoryService
        git_service = GitRepositoryService(supabase_client)
        success, result = git_service.register_repository(
            repo_path=str(temp_dir),
            source_id=source_id,
            config={"is_test_fixture": True, "fixture_name": request.fixture_name},
        )

        if not success:
            # Cleanup on failure
            supabase_client.table("archon_sources").delete().eq("source_id", source_id).execute()
            raise HTTPException(
                status_code=500, detail=result.get("error", "Failed to register test fixture repository")
            )

        # Sync commits from all branches for multi-branch fixtures
        repo_id = result["repo_id"]
        default_branch = expected_data.get("default_branch", "main")
        all_branches = expected_data.get("branches", [default_branch])

        # Track total commits synced across all branches
        total_commits_synced = 0

        # Sync each branch to ensure all commits are captured
        for branch_name in all_branches:
            logger.info(f"Syncing branch: {branch_name}")
            sync_success, sync_result = git_service.sync_commits(
                repo_id=repo_id, branch_name=branch_name, max_commits=100
            )

            if not sync_success:
                logger.error(f"Failed to sync branch {branch_name}: {sync_result.get('error')}")
                logfire.warning(f"Failed to sync branch {branch_name}: {sync_result.get('error')}")
                # Continue to sync other branches even if one fails
                continue

            commits_synced = sync_result.get("commit_count", 0)
            total_commits_synced += commits_synced
            logger.info(f"Synced {commits_synced} commits from branch {branch_name}")

        logger.info(f"Total commits synced across all branches: {total_commits_synced}")

        logger.info(f"Successfully initialized test fixture '{request.fixture_name}' for project {project_id}")

        return InitializeTestFixtureResponse(
            success=True,
            message=f"Test fixture '{request.fixture_name}' initialized successfully",
            repo_id=repo_id,
            repo_name=result.get("repo_name"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initializing test fixture: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/projects/{project_id}/test-fixtures")
async def cleanup_test_fixtures(project_id: str):
    """
    Cleanup all test fixtures for a project.

    Deletes the repository record, source entry, and removes
    the temporary fixture files from disk.

    Args:
        project_id: UUID of project to cleanup

    Returns:
        Success message with cleanup details

    Raises:
        HTTPException 500: If cleanup fails
    """
    try:
        logfire.info(f"Cleaning up test fixtures for project {project_id}")

        supabase_client = get_supabase_client()

        # Get repository
        repo_response = (
            supabase_client.table("archon_git_repositories")
            .select("id, source_id")
            .eq("source_id", project_id)
            .execute()
        )

        if not repo_response.data:
            return {"success": True, "message": "No test fixtures found for this project", "deleted_count": 0}

        repo_record = repo_response.data[0]
        repo_id = str(repo_record["id"])
        source_id = str(repo_record["source_id"])

        # Get source to find temp directory path
        source_response = supabase_client.table("archon_sources").select("source_url").eq("id", source_id).execute()

        temp_path = None
        if source_response.data:
            temp_path = source_response.data[0].get("source_url")

        # Delete repository (cascade deletes commits and files via DB constraints)
        supabase_client.table("archon_git_repositories").delete().eq("id", repo_id).execute()

        # Delete source entry
        supabase_client.table("archon_sources").delete().eq("id", source_id).execute()

        # Remove temp directory if it exists
        if temp_path and Path(temp_path).exists():
            shutil.rmtree(temp_path)
            logfire.info(f"Removed temp directory: {temp_path}")

        logger.info(f"Successfully cleaned up test fixtures for project {project_id}")

        return {
            "success": True,
            "message": "Test fixtures cleaned up successfully",
            "deleted_count": 1,
            "temp_path_removed": temp_path is not None,
        }

    except Exception as e:
        logger.error(f"Error cleaning up test fixtures: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/test-fixtures/list")
async def list_test_fixtures():
    """
    List all available test fixtures.

    Returns:
        List of available fixture names and metadata
    """
    try:
        fixtures = []

        for fixture_name, fixture_dir in FIXTURE_MAP.items():
            expected_file = FIXTURES_DIR / fixture_dir / "EXPECTED.json"
            if expected_file.exists():
                with open(expected_file) as f:
                    data = json.load(f)

                fixtures.append(
                    {
                        "name": fixture_name,
                        "display_name": fixture_name.replace("-", " ").title(),
                        "commit_count": len(data.get("commits", [])),
                        "branch_count": len(data.get("branches", [])),
                        "file_count": len(data.get("files", [])),
                        "default_branch": data.get("default_branch", "main"),
                    }
                )

        return {"fixtures": fixtures}

    except Exception as e:
        logger.error(f"Error listing test fixtures: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
