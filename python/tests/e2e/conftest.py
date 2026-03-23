"""E2E test configuration for Archon.

This module provides fixtures for end-to-end tests that require live services.
These tests connect to real databases and external services.
"""

import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# Set test environment
os.environ["TEST_MODE"] = "true"
os.environ["TESTING"] = "true"


@pytest.fixture(scope="session")
def e2e_database_url() -> str:
    """Get database URL for E2E tests.

    Uses ARCHON_DATABASE_URL from environment, or falls back to test database.
    """
    return os.environ.get(
        "ARCHON_DATABASE_URL",
        "postgresql://test:test@localhost:5434/test"
    )


@pytest.fixture
async def e2e_db_client(e2e_database_url: str):
    """Create a database client for E2E tests.

    This fixture provides a real database connection for tests that need
    to verify actual database operations.
    """
    # Import here to avoid circular imports
    try:
        from src.server.services.database import get_database_connector

        db = await get_database_connector()
        yield db
        await db.close()
    except Exception as e:
        pytest.skip(f"Database not available: {e}")


@pytest.fixture
def e2e_mock_supabase():
    """Mock Supabase client for E2E tests that need external service mocking."""
    mock = MagicMock()

    # Setup realistic response patterns
    mock.table = MagicMock(return_value=mock)
    mock.select = MagicMock(return_value=mock)
    mock.eq = MagicMock(return_value=mock)
    mock.execute = MagicMock(return_value=MagicMock(data=[]))

    return mock


@pytest.fixture
def e2e_test_project() -> dict[str, Any]:
    """Provide test project data for E2E tests."""
    return {
        "title": "E2E Test Project",
        "description": "Project created by E2E tests",
    }


@pytest.fixture
def e2e_test_task() -> dict[str, Any]:
    """Provide test task data for E2E tests."""
    return {
        "title": "E2E Test Task",
        "description": "Task created by E2E tests",
        "status": "todo",
    }
