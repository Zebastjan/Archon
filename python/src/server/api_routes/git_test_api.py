"""
Git Test Fixtures API endpoints for Archon

Handles:
- Initializing test fixtures as project repositories
- Cleanup of test fixtures
"""

import json
import shutil
import tempfile
import uuid
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

        # Generate unique source_id per fixture to prevent overwrites
        source_id = f"{project_id}:{request.fixture_name}"

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

        # Create documents from repository files for knowledge base visibility
        documents_created = 0

        # DEBUG: Write to file so user can see what's happening
        debug_log_path = Path("/tmp/archon_fixture_debug.log")
        with open(debug_log_path, "a") as f:
            from datetime import datetime
            f.write(f"\n{'='*80}\n")
            f.write(f"[{datetime.now()}] Initializing fixture: {request.fixture_name}\n")
            f.write(f"Repository ID: {repo_id}\n")

        try:
            # Get repository metadata to find current HEAD
            repo_metadata_response = (
                supabase_client.table("archon_git_repositories")
                .select("current_head_sha")
                .eq("id", repo_id)
                .execute()
            )

            if repo_metadata_response.data and repo_metadata_response.data[0].get("current_head_sha"):
                head_sha = repo_metadata_response.data[0]["current_head_sha"]

                # Get file tree from HEAD
                file_tree_success, file_tree_result = git_service.get_file_tree(
                    repo_id=repo_id, commit_sha=head_sha, path_prefix=None
                )

                logfire.info(f"File tree retrieval: success={file_tree_success}, files={len(file_tree_result.get('files', []))}")

                # DEBUG logging to file
                with open(debug_log_path, "a") as f:
                    f.write(f"File tree success: {file_tree_success}\n")
                    f.write(f"Files found: {len(file_tree_result.get('files', []))}\n")

                if file_tree_success and file_tree_result.get("files"):
                    # Create documents for each file (filter for text files)
                    logfire.info(f"Processing {len(file_tree_result['files'])} files for document creation")

                    with open(debug_log_path, "a") as f:
                        f.write(f"Starting to process {len(file_tree_result['files'])} files...\n")

                    for file_info in file_tree_result["files"]:
                        # Skip binary files and very large files
                        if file_info.get("is_binary") or file_info.get("file_size", 0) > 1_000_000:
                            logfire.info(f"Skipping binary/large file: {file_info.get('file_path')}")
                            with open(debug_log_path, "a") as f:
                                f.write(f"  SKIPPED (binary/large): {file_info.get('file_path')}\n")
                            continue

                        file_path = file_info.get("file_path")
                        if not file_path:
                            logfire.warning("File info missing file_path, skipping")
                            with open(debug_log_path, "a") as f:
                                f.write(f"  SKIPPED (no file_path): {file_info}\n")
                            continue

                        logfire.info(f"Processing file for document creation: {file_path}")
                        with open(debug_log_path, "a") as f:
                            f.write(f"  Processing: {file_path}\n")

                        # Get file content
                        try:
                            with open(debug_log_path, "a") as f:
                                f.write(f"    Calling get_file_content(repo_id={repo_id}, commit_sha={head_sha[:8]}..., file_path={file_path})\n")

                            content_success, content_result = git_service.get_file_content(
                                repo_id=repo_id, commit_sha=head_sha, file_path=file_path
                            )

                            with open(debug_log_path, "a") as f:
                                f.write(f"    get_file_content returned: success={content_success}\n")

                            logfire.info(f"Content retrieval for {file_path}: success={content_success}")
                        except Exception as file_error:
                            with open(debug_log_path, "a") as f:
                                f.write(f"    ❌ ERROR in get_file_content: {file_error}\n")
                            raise

                        if content_success and content_result.get("content"):
                            # Create document blob (metadata)
                            import hashlib
                            content = content_result["content"]
                            content_hash = hashlib.sha256(content.encode()).hexdigest()

                            blob_data = {
                                "source_id": source_id,
                                "source_type": "git",
                                "blob_uri": f"git://{repo_id}/{head_sha}/{file_path}",
                                "content_hash": content_hash,
                                "content_length": len(content),
                                "download_status": "downloaded",
                            }

                            blob_response = supabase_client.table("archon_document_blobs").insert(blob_data).execute()

                            if blob_response.data:
                                blob_id = blob_response.data[0]["id"]

                                # Create chunk with actual content
                                chunk_data = {
                                    "blob_id": blob_id,
                                    "chunk_index": 0,
                                    "content": content,
                                    "token_count": len(content.split()) * 4 // 3,
                                }

                                supabase_client.table("archon_chunks").insert(chunk_data).execute()
                                documents_created += 1

                                with open(debug_log_path, "a") as f:
                                    f.write(f"    ✓ Created blob and chunk for {file_path}\n")

                    logfire.info(f"Created {documents_created} documents for test fixture {request.fixture_name}")

                    with open(debug_log_path, "a") as f:
                        f.write(f"\nFINAL COUNT: {documents_created} documents created\n")
                        f.write(f"{'='*80}\n")
                else:
                    logfire.warning(f"Could not get file tree for HEAD {head_sha}")
            else:
                logfire.warning(f"Could not find HEAD SHA for repository {repo_id}")

        except Exception as e:
            # Don't fail the whole initialization if document creation fails
            logger.warning(f"Failed to create documents for test fixture: {e}")
            logfire.warning(f"Failed to create documents for test fixture: {e}")

            # DEBUG: Write exception to file
            with open(debug_log_path, "a") as f:
                import traceback
                f.write(f"\n❌ EXCEPTION during document creation:\n")
                f.write(f"{str(e)}\n")
                f.write(f"{traceback.format_exc()}\n")
                f.write(f"{'='*80}\n")

        logger.info(
            f"Successfully initialized test fixture '{request.fixture_name}' for project {project_id} "
            f"with {total_commits_synced} commits and {documents_created} documents"
        )

        return InitializeTestFixtureResponse(
            success=True,
            message=f"Test fixture '{request.fixture_name}' initialized successfully with {documents_created} documents",
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

    Deletes all repository records, source entries, and removes
    the temporary fixture files from disk for all fixtures matching
    the project_id pattern.

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

        # Find all test fixture sources for this project (pattern: {project_id}:*)
        # We use ilike for pattern matching with : as delimiter
        source_response = (
            supabase_client.table("archon_sources")
            .select("source_id, source_url, metadata")
            .ilike("source_id", f"{project_id}:%")
            .execute()
        )

        if not source_response.data:
            return {"success": True, "message": "No test fixtures found for this project", "deleted_count": 0}

        deleted_count = 0
        temp_paths_removed = []

        # Process each fixture source
        for source_record in source_response.data:
            # Type guard: ensure source_record is a dict
            if not isinstance(source_record, dict):
                continue

            source_id = source_record["source_id"]
            temp_path = source_record.get("source_url")

            # Find and delete associated repository
            repo_response = (
                supabase_client.table("archon_git_repositories")
                .select("id")
                .eq("source_id", source_id)
                .execute()
            )

            if repo_response.data:
                repo_id = str(repo_response.data[0]["id"])
                # Delete repository (cascade deletes commits and files via DB constraints)
                supabase_client.table("archon_git_repositories").delete().eq("id", repo_id).execute()
                logfire.info(f"Deleted repository {repo_id} for source {source_id}")

            # Delete associated documents (if any were created)
            supabase_client.table("archon_document_blobs").delete().eq("source_id", source_id).execute()

            # Delete source entry
            supabase_client.table("archon_sources").delete().eq("source_id", source_id).execute()
            logfire.info(f"Deleted source {source_id}")

            # Remove temp directory if it exists
            if temp_path and Path(temp_path).exists():
                shutil.rmtree(temp_path)
                temp_paths_removed.append(temp_path)
                logfire.info(f"Removed temp directory: {temp_path}")

            deleted_count += 1

        logger.info(f"Successfully cleaned up {deleted_count} test fixtures for project {project_id}")

        return {
            "success": True,
            "message": f"Cleaned up {deleted_count} test fixture(s) successfully",
            "deleted_count": deleted_count,
            "temp_paths_removed": temp_paths_removed,
        }

    except Exception as e:
        logger.error(f"Error cleaning up test fixtures: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/projects/{project_id}/test-fixtures")
async def get_initialized_test_fixtures(project_id: str):
    """
    Get list of initialized test fixtures for a project.

    Returns fixture names, source IDs, and document counts.

    Args:
        project_id: UUID of project to query

    Returns:
        List of initialized fixtures with metadata
    """
    try:
        logfire.info(f"Getting initialized test fixtures for project {project_id}")

        supabase_client = get_supabase_client()

        # Find all test fixture sources for this project (pattern: {project_id}:*)
        source_response = (
            supabase_client.table("archon_sources")
            .select("source_id, source_display_name, metadata")
            .ilike("source_id", f"{project_id}:%")
            .execute()
        )

        initialized_fixtures = []

        for source_record in source_response.data:
            if not isinstance(source_record, dict):
                continue

            source_id = source_record.get("source_id")
            metadata = source_record.get("metadata", {})

            # Only include test fixtures
            if not metadata.get("is_test_fixture"):
                continue

            # Count documents for this fixture
            doc_count_response = (
                supabase_client.table("archon_document_blobs")
                .select("id", count="exact")
                .eq("source_id", source_id)
                .execute()
            )

            document_count = doc_count_response.count or 0

            fixture_name = metadata.get("fixture_name", source_id.split(":")[-1])

            initialized_fixtures.append(
                {
                    "name": fixture_name,
                    "source_id": source_id,
                    "document_count": document_count,
                    "display_name": f"test-fixture-{fixture_name}",
                }
            )

        return {"fixtures": initialized_fixtures, "project_id": project_id}

    except Exception as e:
        logger.error(f"Error getting initialized test fixtures: {e}", exc_info=True)
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


@router.get("/debug/logs")
async def get_debug_logs():
    """
    Get debug logs from test fixture initialization.

    Returns:
        Debug log file contents
    """
    try:
        debug_log_path = Path("/tmp/archon_fixture_debug.log")

        if not debug_log_path.exists():
            return {"content": "No debug logs yet. Initialize a test fixture to generate logs."}

        with open(debug_log_path, "r") as f:
            content = f.read()

        return {"content": content}

    except Exception as e:
        logger.error(f"Error reading debug logs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
