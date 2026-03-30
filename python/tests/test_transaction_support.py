"""
Test transaction support in DatabaseConnector.

These tests verify that transactions work correctly with commit/rollback.
"""

import pytest
import pytest_asyncio
import asyncio
from contextlib import asynccontextmanager

# Need to import from src
import sys

sys.path.insert(0, "src")

from src.server.services.database.db_connector import (
    DatabaseConnector,
    DatabaseConfig,
    TransactionError,
)


@pytest_asyncio.fixture
async def test_db():
    """Create a test database connection."""
    config = DatabaseConfig.from_env()
    db = DatabaseConnector(config)
    await db.initialize()
    yield db
    await db.close()


@pytest.mark.asyncio
async def test_transaction_commits_on_success(test_db):
    """Test that transaction commits when no exception is raised."""
    # Generate a unique test ID
    import uuid

    test_id = str(uuid.uuid4())

    try:
        async with test_db.transaction() as conn:
            # Insert a test row
            await conn.execute(
                "INSERT INTO archon_settings (key, value) VALUES ($1, $2)", f"test_transaction_{test_id}", "test_value"
            )

        # Verify the row was committed
        result = await test_db.fetchrow("SELECT * FROM archon_settings WHERE key = $1", f"test_transaction_{test_id}")
        assert result is not None
        assert result["value"] == "test_value"

    finally:
        # Clean up
        await test_db.execute("DELETE FROM archon_settings WHERE key = $1", f"test_transaction_{test_id}")


@pytest.mark.asyncio
async def test_transaction_rolls_back_on_exception(test_db):
    """Test that transaction rolls back when exception is raised."""
    import uuid

    test_id = str(uuid.uuid4())

    try:
        try:
            async with test_db.transaction() as conn:
                # Insert a test row
                await conn.execute(
                    "INSERT INTO archon_settings (key, value) VALUES ($1, $2)", f"test_rollback_{test_id}", "test_value"
                )
                # Raise an exception to trigger rollback
                raise ValueError("Test rollback")
        except ValueError:
            pass  # Expected

        # Verify the row was NOT committed (rolled back)
        result = await test_db.fetchrow("SELECT * FROM archon_settings WHERE key = $1", f"test_rollback_{test_id}")
        assert result is None, "Row should have been rolled back"

    finally:
        # Clean up just in case
        await test_db.execute("DELETE FROM archon_settings WHERE key = $1", f"test_rollback_{test_id}")


@pytest.mark.asyncio
async def test_transaction_multiple_operations_atomic(test_db):
    """Test that multiple operations in a transaction are atomic."""
    import uuid

    test_id = str(uuid.uuid4())

    try:
        try:
            async with test_db.transaction() as conn:
                # First insert
                await conn.execute(
                    "INSERT INTO archon_settings (key, value) VALUES ($1, $2)", f"test_multi_1_{test_id}", "value1"
                )
                # Second insert
                await conn.execute(
                    "INSERT INTO archon_settings (key, value) VALUES ($1, $2)", f"test_multi_2_{test_id}", "value2"
                )
                # Fail after both inserts
                raise ValueError("Trigger rollback")
        except ValueError:
            pass

        # Verify neither row was committed
        result1 = await test_db.fetchrow("SELECT * FROM archon_settings WHERE key = $1", f"test_multi_1_{test_id}")
        result2 = await test_db.fetchrow("SELECT * FROM archon_settings WHERE key = $1", f"test_multi_2_{test_id}")
        assert result1 is None
        assert result2 is None

    finally:
        # Clean up
        await test_db.execute("DELETE FROM archon_settings WHERE key LIKE $1", f"test_multi_%_{test_id}")


@pytest.mark.asyncio
async def test_transaction_method_exists(test_db):
    """Test that transaction() method is available."""
    assert hasattr(test_db, "transaction")
    assert callable(test_db.transaction)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
