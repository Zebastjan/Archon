"""
Settings API endpoints for Archon

Handles:
- OpenAI API key management
- Other credentials and configuration
- Settings storage and retrieval
- Dev/test utilities (git test fixtures)
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Import logging
from ..config.logfire_config import logfire
from ..services.credential_service import credential_service, initialize_credentials
from ..utils import get_supabase_client

router = APIRouter(prefix="/api", tags=["settings"])


class CredentialRequest(BaseModel):
    key: str
    value: str
    is_encrypted: bool = False
    category: str | None = None
    description: str | None = None


class CredentialUpdateRequest(BaseModel):
    value: str
    is_encrypted: bool | None = None
    category: str | None = None
    description: str | None = None


class CredentialResponse(BaseModel):
    success: bool
    message: str


# Credential Management Endpoints
@router.get("/credentials")
async def list_credentials(category: str | None = None):
    """List all credentials and their categories."""
    try:
        logfire.info(f"Listing credentials | category={category}")
        credentials = await credential_service.list_all_credentials()

        if category:
            # Filter by category
            credentials = [cred for cred in credentials if cred.category == category]

        result_count = len(credentials)
        logfire.info(f"Credentials listed successfully | count={result_count} | category={category}")

        return [
            {
                "key": cred.key,
                "value": cred.value,
                "encrypted_value": cred.encrypted_value,
                "is_encrypted": cred.is_encrypted,
                "category": cred.category,
                "description": cred.description,
            }
            for cred in credentials
        ]
    except Exception as e:
        logfire.error(f"Error listing credentials | category={category} | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.get("/credentials/categories/{category}")
async def get_credentials_by_category(category: str):
    """Get all credentials for a specific category."""
    try:
        logfire.info(f"Getting credentials by category | category={category}")
        credentials = await credential_service.get_credentials_by_category(category)

        logfire.info(f"Credentials retrieved by category | category={category} | count={len(credentials)}")

        return {"credentials": credentials}
    except Exception as e:
        logfire.error(f"Error getting credentials by category | category={category} | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.post("/credentials")
async def create_credential(request: CredentialRequest):
    """Create or update a credential."""
    try:
        logfire.info(
            f"Creating/updating credential | key={request.key} | is_encrypted={request.is_encrypted} | category={request.category}"
        )

        success = await credential_service.set_credential(
            key=request.key,
            value=request.value,
            is_encrypted=request.is_encrypted,
            category=request.category,
            description=request.description,
        )

        if success:
            logfire.info(f"Credential saved successfully | key={request.key} | is_encrypted={request.is_encrypted}")

            return {
                "success": True,
                "message": f"Credential {request.key} {'encrypted and ' if request.is_encrypted else ''}saved successfully",
            }
        else:
            logfire.error(f"Failed to save credential | key={request.key}")
            raise HTTPException(status_code=500, detail={"error": "Failed to save credential"})

    except Exception as e:
        logfire.error(f"Error creating credential | key={request.key} | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


# Define optional settings with their default values
# These are user preferences that should return defaults instead of 404
# This prevents console errors in the frontend when settings haven't been explicitly set
# The frontend can check the 'is_default' flag to know if it's a default or user-set value
OPTIONAL_SETTINGS_WITH_DEFAULTS = {
    "DISCONNECT_SCREEN_ENABLED": "true",  # Show disconnect screen when server is unavailable
    "PROJECTS_ENABLED": "false",  # Enable project management features
    "LOGFIRE_ENABLED": "false",  # Enable Pydantic Logfire integration
}


@router.get("/credentials/{key}")
async def get_credential(key: str):
    """Get a specific credential by key."""
    try:
        logfire.info(f"Getting credential | key={key}")
        # Never decrypt - always get metadata only for encrypted credentials
        value = await credential_service.get_credential(key, decrypt=False)

        if value is None:
            # Check if this is an optional setting with a default value
            if key in OPTIONAL_SETTINGS_WITH_DEFAULTS:
                logfire.info(f"Returning default value for optional setting | key={key}")
                return {
                    "key": key,
                    "value": OPTIONAL_SETTINGS_WITH_DEFAULTS[key],
                    "is_default": True,
                    "category": "features",
                    "description": f"Default value for {key}",
                }

            logfire.warning(f"Credential not found | key={key}")
            raise HTTPException(status_code=404, detail={"error": f"Credential {key} not found"})

        logfire.info(f"Credential retrieved successfully | key={key}")

        if isinstance(value, dict) and value.get("is_encrypted"):
            return {
                "key": key,
                "value": "[ENCRYPTED]",
                "is_encrypted": True,
                "category": value.get("category"),
                "description": value.get("description"),
                "has_value": bool(value.get("encrypted_value")),
            }

        # For non-encrypted credentials, return the actual value
        return {"key": key, "value": value, "is_encrypted": False}

    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Error getting credential | key={key} | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.put("/credentials/{key}")
async def update_credential(key: str, request: dict[str, Any]):
    """Update an existing credential."""
    try:
        logfire.info(f"Updating credential | key={key}")

        # Handle both CredentialUpdateRequest and full Credential object formats
        if isinstance(request, dict):
            # If the request contains a 'value' field directly, use it
            value = request.get("value", "")
            is_encrypted = request.get("is_encrypted")
            category = request.get("category")
            description = request.get("description")
        else:
            value = request.value
            is_encrypted = request.is_encrypted
            category = request.category
            description = request.description

        # Get existing credential to preserve metadata if not provided
        existing_creds = await credential_service.list_all_credentials()
        existing = next((c for c in existing_creds if c.key == key), None)

        if existing is None:
            # If credential doesn't exist, create it
            is_encrypted = is_encrypted if is_encrypted is not None else False
            logfire.info(f"Creating new credential via PUT | key={key}")
        else:
            # Preserve existing values if not provided
            if is_encrypted is None:
                is_encrypted = existing.is_encrypted
            if category is None:
                category = existing.category
            if description is None:
                description = existing.description
            logfire.info(f"Updating existing credential | key={key} | category={category}")

        success = await credential_service.set_credential(
            key=key,
            value=value,
            is_encrypted=is_encrypted,
            category=category,
            description=description,
        )

        if success:
            logfire.info(f"Credential updated successfully | key={key} | is_encrypted={is_encrypted}")

            return {"success": True, "message": f"Credential {key} updated successfully"}
        else:
            logfire.error(f"Failed to update credential | key={key}")
            raise HTTPException(status_code=500, detail={"error": "Failed to update credential"})

    except Exception as e:
        logfire.error(f"Error updating credential | key={key} | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.delete("/credentials/{key}")
async def delete_credential(key: str):
    """Delete a credential."""
    try:
        logfire.info(f"Deleting credential | key={key}")
        success = await credential_service.delete_credential(key)

        if success:
            logfire.info(f"Credential deleted successfully | key={key}")

            return {"success": True, "message": f"Credential {key} deleted successfully"}
        else:
            logfire.error(f"Failed to delete credential | key={key}")
            raise HTTPException(status_code=500, detail={"error": "Failed to delete credential"})

    except Exception as e:
        logfire.error(f"Error deleting credential | key={key} | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.post("/credentials/initialize")
async def initialize_credentials_endpoint():
    """Reload credentials from database."""
    try:
        logfire.info("Reloading credentials from database")
        await initialize_credentials()

        logfire.info("Credentials reloaded successfully")

        return {"success": True, "message": "Credentials reloaded from database"}
    except Exception as e:
        logfire.error(f"Error reloading credentials | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.get("/database/metrics")
async def database_metrics():
    """Get database metrics and statistics."""
    try:
        logfire.info("Getting database metrics")
        supabase_client = get_supabase_client()

        # Get various table counts
        tables_info = {}

        # Get projects count
        projects_response = supabase_client.table("archon_projects").select("id", count="exact").execute()
        tables_info["projects"] = projects_response.count if projects_response.count is not None else 0

        # Get tasks count
        tasks_response = supabase_client.table("archon_tasks").select("id", count="exact").execute()
        tables_info["tasks"] = tasks_response.count if tasks_response.count is not None else 0

        # Get crawled pages count
        pages_response = supabase_client.table("archon_crawled_pages").select("id", count="exact").execute()
        tables_info["crawled_pages"] = pages_response.count if pages_response.count is not None else 0

        # Get settings count
        settings_response = supabase_client.table("archon_settings").select("id", count="exact").execute()
        tables_info["settings"] = settings_response.count if settings_response.count is not None else 0

        total_records = sum(tables_info.values())
        logfire.info(f"Database metrics retrieved | total_records={total_records} | tables={tables_info}")

        return {
            "status": "healthy",
            "database": "supabase",
            "tables": tables_info,
            "total_records": total_records,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logfire.error(f"Error getting database metrics | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.get("/settings/health")
async def settings_health():
    """Health check for settings API."""
    logfire.info("Settings health check requested")
    result = {"status": "healthy", "service": "settings"}

    return result


@router.post("/credentials/status-check")
async def check_credential_status(request: dict[str, list[str]]):
    """Check status of API credentials by actually decrypting and validating them.

    This endpoint is specifically for frontend status indicators and returns
    decrypted credential values for connectivity testing.
    """
    try:
        credential_keys = request.get("keys", [])
        logfire.info(f"Checking status for credentials: {credential_keys}")

        result = {}

        for key in credential_keys:
            try:
                # Get decrypted value for status checking
                decrypted_value = await credential_service.get_credential(key, decrypt=True)

                if decrypted_value and isinstance(decrypted_value, str) and decrypted_value.strip():
                    result[key] = {"key": key, "value": decrypted_value, "has_value": True}
                else:
                    result[key] = {"key": key, "value": None, "has_value": False}

            except Exception as e:
                logfire.warning(f"Failed to get credential for status check: {key} | error={str(e)}")
                result[key] = {"key": key, "value": None, "has_value": False, "error": str(e)}

        logfire.info(
            f"Credential status check completed | checked={len(credential_keys)} | found={len([k for k, v in result.items() if v.get('has_value')])}"
        )
        return result

    except Exception as e:
        logfire.error(f"Error in credential status check | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


FIXTURES_DIR = Path(__file__).parent.parent.parent.parent / "tests" / "git_integration" / "fixtures"


class GitTestFixtureInfo(BaseModel):
    name: str
    path: str
    commit_count: int
    branch_count: int
    file_count: int
    has_binary_files: bool


class GitTestFixtureDetails(BaseModel):
    name: str
    branches: list[str]
    commits: list[dict[str, Any]]
    files: list[dict[str, Any]]
    default_branch: str


@router.get("/dev/git-test-fixtures", response_model=list[GitTestFixtureInfo])
async def list_git_test_fixtures():
    """
    List all available git test fixtures.

    These fixtures are used for testing git integration functionality
    and can be used to verify backend/frontend test alignment.
    """
    try:
        logfire.info("Listing git test fixtures")

        if not FIXTURES_DIR.exists():
            logfire.warning(f"Fixtures directory not found: {FIXTURES_DIR}")
            return []

        fixtures = []

        for fixture_path in FIXTURES_DIR.iterdir():
            if not fixture_path.is_dir():
                continue

            expected_file = fixture_path / "EXPECTED.json"
            if not expected_file.exists():
                continue

            try:
                with open(expected_file) as f:
                    expected = json.load(f)

                branches = expected.get("branches", [])
                commits = expected.get("commits", [])
                files = expected.get("files", [])
                has_binary = any(f.get("is_binary", False) for f in files)

                fixtures.append(
                    GitTestFixtureInfo(
                        name=fixture_path.name,
                        path=str(fixture_path),
                        commit_count=len(commits),
                        branch_count=len(branches),
                        file_count=len(files),
                        has_binary_files=has_binary,
                    )
                )
            except Exception as e:
                logfire.warning(f"Failed to parse fixture {fixture_path.name}: {e}")
                continue

        logfire.info(f"Found {len(fixtures)} git test fixtures")
        return fixtures

    except Exception as e:
        logfire.error(f"Error listing git test fixtures: {e}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.get("/dev/git-test-fixtures/{fixture_name}", response_model=GitTestFixtureDetails)
async def get_git_test_fixture(fixture_name: str):
    """
    Get details of a specific git test fixture.

    Returns the full EXPECTED.json content for the fixture,
    including commits, branches, and files with metadata.
    """
    try:
        logfire.info(f"Getting git test fixture: {fixture_name}")

        fixture_path = FIXTURES_DIR / fixture_name
        expected_file = fixture_path / "EXPECTED.json"

        if not fixture_path.exists():
            raise HTTPException(status_code=404, detail=f"Fixture '{fixture_name}' not found")

        if not expected_file.exists():
            raise HTTPException(status_code=404, detail=f"EXPECTED.json not found for '{fixture_name}'")

        with open(expected_file) as f:
            expected = json.load(f)

        return GitTestFixtureDetails(
            name=fixture_name,
            branches=expected.get("branches", []),
            commits=expected.get("commits", []),
            files=expected.get("files", []),
            default_branch=expected.get("default_branch", "main"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Error getting git test fixture {fixture_name}: {e}")
        raise HTTPException(status_code=500, detail={"error": str(e)})
