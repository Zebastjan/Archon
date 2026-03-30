"""Simple test configuration for Archon - Essential tests only."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Set test environment - always override to ensure test isolation
# NOTE: These can be overridden by specific tests that need real DB
os.environ["TEST_MODE"] = "true"
os.environ["TESTING"] = "true"
# Set fake database credentials to prevent connection attempts
os.environ["ARCHON_DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"
os.environ["SUPABASE_URL"] = ""  # Disable Supabase
os.environ["SUPABASE_SERVICE_KEY"] = ""
# Set required port environment variables for ServiceDiscovery
os.environ["ARCHON_SERVER_PORT"] = "8181"
os.environ["ARCHON_MCP_PORT"] = "8051"
# ARCHON_AGENTS_PORT removed - agents now integrated into main server
os.environ["ARCHON_DB_PORT"] = "5432"

# Import database module first so patches can be applied
import sys
from pathlib import Path

# Add python/src to path BEFORE importing
PYTHON_SRC = Path(__file__).parent.parent / "src"
if str(PYTHON_SRC) not in sys.path:
    sys.path.insert(0, str(PYTHON_SRC))

if "src.server.services.database" not in sys.modules:
    from src.server.services import database

# Create mock database connector for global patches
mock_db = MagicMock()
mock_db.fetch = AsyncMock(return_value=[])
mock_db.fetchrow = AsyncMock(return_value=None)
mock_db.fetchval = AsyncMock(return_value=None)
mock_db.execute = AsyncMock(return_value="INSERT 0 1")
mock_db.insert = AsyncMock(return_value={"id": "test-id"})
mock_db.update = AsyncMock(return_value=[{"id": "test-id"}])
mock_db.delete = AsyncMock(return_value=[])
mock_db.select = AsyncMock(return_value=[])

# Apply global patches immediately for module imports
_global_patches = [
    patch("src.server.services.database.db_connector.get_database_connector", return_value=mock_db),
    patch("src.server.services.database.get_database_connector", return_value=mock_db),
]

for p in _global_patches:
    p.start()


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "real_db: mark test to use real database instead of mock")
    config.addinivalue_line("markers", "real_fs: mark test to use real filesystem instead of mock")


@pytest.fixture(autouse=True)
def ensure_test_environment():
    """Ensure test environment is properly set for each test."""
    # Force test environment settings - this runs before each test
    # But allow tests to override via markers
    os.environ["TEST_MODE"] = "true"
    os.environ["TESTING"] = "true"
    yield


@pytest.fixture(autouse=True)
def prevent_real_db_calls(request):
    """Automatically prevent any real database calls in all tests.

    Unless the test is marked with @pytest.mark.real_db, in which case
    we allow real database access.
    """
    # Check if test wants real DB
    if request.node.get_closest_marker("real_db"):
        # Test wants real DB - don't mock it
        yield
        return

    # Create a mock database connector to use everywhere
    mock_db = MagicMock()

    # Setup async methods with proper return values
    mock_db.fetch = AsyncMock(return_value=[])
    mock_db.fetchrow = AsyncMock(return_value=None)
    mock_db.fetchval = AsyncMock(return_value=None)
    mock_db.execute = AsyncMock(return_value="INSERT 0 1")
    mock_db.insert = AsyncMock(return_value={"id": "test-id"})
    mock_db.update = AsyncMock(return_value=[{"id": "test-id"}])
    mock_db.delete = AsyncMock(return_value=[])
    mock_db.select = AsyncMock(return_value=[])
    mock_db.initialize = AsyncMock()
    mock_db.close = AsyncMock()

    # Patch all the common ways to get a database connector
    with patch("src.server.services.database.db_connector.get_database_connector", return_value=mock_db):
        with patch("src.server.services.database.get_database_connector", return_value=mock_db):
            yield


@pytest.fixture
def mock_db_client():
    """Mock PostgreSQL database connector for testing.

    Returns a mock that mimics asyncpg-style database operations.
    Use this for PostgreSQL-based tests.
    """
    mock_db = MagicMock()

    # Setup async methods
    mock_db.fetch = AsyncMock(return_value=[])
    mock_db.fetchrow = AsyncMock(return_value=None)
    mock_db.fetchval = AsyncMock(return_value=None)
    mock_db.execute = AsyncMock(return_value="INSERT 0 1")
    mock_db.insert = AsyncMock(return_value={"id": "test-id"})
    mock_db.update = AsyncMock(return_value=[{"id": "test-id"}])
    mock_db.delete = AsyncMock(return_value=[])
    mock_db.select = AsyncMock(return_value=[])
    mock_db.initialize = AsyncMock()
    mock_db.close = AsyncMock()

    return mock_db


@pytest.fixture
def mock_supabase_client():
    """Mock Supabase client for testing (DEPRECATED - use mock_db_client instead).

    This fixture is kept for backward compatibility during migration.
    New tests should use mock_db_client.
    """
    mock_client = MagicMock()

    # Mock table operations with chaining support
    mock_table = MagicMock()
    mock_select = MagicMock()
    mock_insert = MagicMock()
    mock_update = MagicMock()
    mock_delete = MagicMock()

    # Setup method chaining for select
    mock_select.execute.return_value.data = []
    mock_select.eq.return_value = mock_select
    mock_select.neq.return_value = mock_select
    mock_select.order.return_value = mock_select
    mock_select.limit.return_value = mock_select
    mock_table.select.return_value = mock_select

    # Setup method chaining for insert
    mock_insert.execute.return_value.data = [{"id": "test-id"}]
    mock_table.insert.return_value = mock_insert

    # Setup method chaining for update
    mock_update.execute.return_value.data = [{"id": "test-id"}]
    mock_update.eq.return_value = mock_update
    mock_table.update.return_value = mock_update

    # Setup method chaining for delete
    mock_delete.execute.return_value.data = []
    mock_delete.eq.return_value = mock_delete
    mock_table.delete.return_value = mock_delete

    # Make table() return the mock table
    mock_client.table.return_value = mock_table

    # Mock auth operations
    mock_client.auth = MagicMock()
    mock_client.auth.get_user.return_value = None

    # Mock storage operations
    mock_client.storage = MagicMock()

    return mock_client


@pytest.fixture
def client(mock_db_client):
    """FastAPI test client with mocked database."""
    # Patch database connector
    with patch(
        "src.server.services.database.db_connector.get_database_connector",
        return_value=mock_db_client,
    ):
        with patch(
            "src.server.services.database.get_database_connector",
            return_value=mock_db_client,
        ):
            from unittest.mock import AsyncMock

            import src.server.main as server_main

            # Mark initialization as complete for testing (before accessing app)
            server_main._initialization_complete = True
            app = server_main.app

            # Mock the schema check to always return valid
            mock_schema_check = AsyncMock(return_value={"valid": True, "message": "Schema is up to date"})
            with patch("src.server.main._check_database_schema", new=mock_schema_check):
                return TestClient(app)


@pytest.fixture
def test_project():
    """Simple test project data."""
    return {"title": "Test Project", "description": "A test project for essential tests"}


@pytest.fixture
def test_task():
    """Simple test task data."""
    return {
        "title": "Test Task",
        "description": "A test task for essential tests",
        "status": "todo",
        "assignee": "User",
    }


@pytest.fixture
def test_knowledge_item():
    """Simple test knowledge item data."""
    return {
        "url": "https://example.com/test",
        "title": "Test Knowledge Item",
        "content": "This is test content for knowledge base",
        "source_id": "test-source",
    }
