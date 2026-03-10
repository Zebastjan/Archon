"""
Integration Tests with Real Database

These tests run against a real PostgreSQL database with pgvector.
They validate actual RPC functions, database schema, and queries.

Setup:
  docker-compose -f docker-compose.test.yml up -d
  pytest -m integration

Teardown:
  docker-compose -f docker-compose.test.yml down -v
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest

# Mock non-database modules before importing
sys.modules["openai"] = MagicMock()
sys.modules["src.server.services.embeddings"] = MagicMock()
sys.modules["src.server.services.embeddings.embedding_service"] = MagicMock()

# Import after mocking
import psycopg2
from psycopg2.extras import RealDictCursor

pytestmark = pytest.mark.integration


def get_test_db_url() -> str:
    """Get test database URL from environment or use default."""
    return os.getenv("TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/archon_test")


def get_db_connection():
    """Create a database connection."""
    conn = psycopg2.connect(
        host="localhost",
        port=5433,
        database="archon_test",
        user="postgres",
        password="postgres",
    )
    conn.autocommit = True
    return conn


@pytest.fixture(scope="session")
def db_connection():
    """Provide database connection for integration tests."""
    try:
        conn = get_db_connection()
        yield conn
        conn.close()
    except Exception as e:
        pytest.skip(f"Integration test database not available: {e}")


@pytest.fixture
def db_cursor(db_connection):
    """Provide database cursor for tests."""
    cursor = db_connection.cursor(cursor_factory=RealDictCursor)
    yield cursor
    cursor.close()


@pytest.fixture
def test_repository(db_cursor):
    """Create a test repository and yield its ID, cleanup after test."""
    db_cursor.execute(
        """
        INSERT INTO archon_git_repositories (repository_path_normalized, repository_url)
        VALUES (%s, %s)
        RETURNING id
        """,
        ("/test/repo", "https://github.com/test/repo"),
    )
    repo_id = db_cursor.fetchone()["id"]

    yield repo_id

    # Cleanup - cascade will delete commits
    db_cursor.execute("DELETE FROM archon_git_repositories WHERE id = %s", (repo_id,))


class TestRealDatabaseSchema:
    """Tests that validate database schema and constraints."""

    def test_database_connection(self, db_cursor):
        """Test database is reachable and schema exists."""
        db_cursor.execute("SELECT 1 as value")
        result = db_cursor.fetchone()
        assert result["value"] == 1

    def test_pgvector_extension_loaded(self, db_cursor):
        """Verify pgvector extension is available."""
        db_cursor.execute("SELECT * FROM pg_extension WHERE extname = 'vector'")
        result = db_cursor.fetchone()
        assert result is not None, "pgvector extension not loaded"

    def test_git_commits_table_exists(self, db_cursor):
        """Verify archon_git_commits table exists."""
        db_cursor.execute(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'archon_git_commits'
            ) as table_exists
            """
        )
        result = db_cursor.fetchone()
        assert result["table_exists"] is True


class TestRealRPCFunctions:
    """Tests that validate RPC functions work correctly."""

    def test_upsert_commit_rpc_basic(self, db_cursor, test_repository):
        """Test commit upsert RPC function with basic parameters."""
        repo_id = test_repository

        # Insert first commit
        db_cursor.execute(
            """
            SELECT upsert_git_commit_with_branch_merge(
                %s, %s, %s, %s, %s, %s, %s, %s
            )
            """,
            (
                repo_id,
                "abc123",
                "Test Author",
                "test@example.com",
                datetime.now(timezone.utc),
                "Test commit",
                [],  # parent_shas
                ["main"],
            ),
        )
        result = db_cursor.fetchone()
        commit_id = result["upsert_git_commit_with_branch_merge"]
        assert commit_id is not None

        # Verify commit was inserted
        db_cursor.execute("SELECT * FROM archon_git_commits WHERE id = %s", (commit_id,))
        commit = db_cursor.fetchone()
        assert commit["commit_sha"] == "abc123"
        assert commit["message"] == "Test commit"
        assert commit["branches"] == ["main"]

    def test_upsert_commit_rpc_merge_branches(self, db_cursor, test_repository):
        """Test that upsert merges branches correctly."""
        repo_id = test_repository

        # First insert with main branch
        db_cursor.execute(
            """
            SELECT upsert_git_commit_with_branch_merge(
                %s, %s, %s, %s, %s, %s, %s, %s
            )
            """,
            (
                repo_id,
                "merge123",
                "Test Author",
                "test@example.com",
                datetime.now(timezone.utc),
                "Test commit",
                [],  # parent_shas
                ["main"],
            ),
        )
        result = db_cursor.fetchone()
        commit_id = result["upsert_git_commit_with_branch_merge"]

        # Second upsert with develop branch
        db_cursor.execute(
            """
            SELECT upsert_git_commit_with_branch_merge(
                %s, %s, %s, %s, %s, %s, %s, %s
            )
            """,
            (
                repo_id,
                "merge123",
                "Updated Author",
                "updated@example.com",
                datetime.now(timezone.utc),
                "Updated message",
                [],  # parent_shas
                ["develop"],
            ),
        )
        result = db_cursor.fetchone()
        same_commit_id = result["upsert_git_commit_with_branch_merge"]

        # Should return same commit ID
        assert same_commit_id == commit_id

        # Verify branches were merged
        db_cursor.execute(
            """
            SELECT branches FROM archon_git_commits WHERE id = %s
            """,
            (commit_id,),
        )
        commit = db_cursor.fetchone()
        branches = set(commit["branches"])
        assert branches == {"main", "develop"}

    def test_upsert_commit_rpc_with_parent_shas(self, db_cursor, test_repository):
        """Test that merge commit parent_shas are properly stored."""
        repo_id = test_repository

        # Insert parent commits
        db_cursor.execute(
            """
            SELECT upsert_git_commit_with_branch_merge(
                %s, %s, %s, %s, %s, %s, %s, %s
            )
            """,
            (
                repo_id,
                "parent1",
                "Parent Author 1",
                "parent1@test.com",
                datetime.now(timezone.utc),
                "Parent commit 1",
                [],
                ["main"],
            ),
        )

        db_cursor.execute(
            """
            SELECT upsert_git_commit_with_branch_merge(
                %s, %s, %s, %s, %s, %s, %s, %s
            )
            """,
            (
                repo_id,
                "parent2",
                "Parent Author 2",
                "parent2@test.com",
                datetime.now(timezone.utc),
                "Parent commit 2",
                [],
                ["feature"],
            ),
        )

        # Insert merge commit with two parents
        db_cursor.execute(
            """
            SELECT upsert_git_commit_with_branch_merge(
                %s, %s, %s, %s, %s, %s, %s, %s
            )
            """,
            (
                repo_id,
                "merge_commit",
                "Merge Author",
                "merge@test.com",
                datetime.now(timezone.utc),
                "Merge feature into main",
                ["parent1", "parent2"],  # Multiple parents
                ["main"],
            ),
        )
        result = db_cursor.fetchone()
        merge_commit_id = result["upsert_git_commit_with_branch_merge"]

        # Verify merge commit has both parents
        db_cursor.execute(
            """
            SELECT parent_shas FROM archon_git_commits WHERE id = %s
            """,
            (merge_commit_id,),
        )
        commit = db_cursor.fetchone()
        parent_shas = commit["parent_shas"]
        assert len(parent_shas) == 2
        assert "parent1" in parent_shas
        assert "parent2" in parent_shas


class TestRealVectorSimilarity:
    """Tests that validate pgvector similarity calculations."""

    def test_search_commits_by_embedding(self, db_cursor, test_repository):
        """Test semantic search RPC function."""
        repo_id = test_repository

        # Insert commit with embedding
        db_cursor.execute(
            """
            SELECT upsert_git_commit_with_branch_merge(
                %s, %s, %s, %s, %s, %s, %s, %s
            )
            """,
            (
                repo_id,
                "search123",
                "Dev",
                "dev@test.com",
                datetime.now(timezone.utc),
                "Add search feature",
                [],
                ["main"],
            ),
        )
        result = db_cursor.fetchone()
        commit_id = result["upsert_git_commit_with_branch_merge"]

        # Update with embedding
        test_embedding = [0.1] * 1536
        db_cursor.execute(
            """
            UPDATE archon_git_commits
            SET embedding_1536 = %s::vector(1536)
            WHERE id = %s
            """,
            (test_embedding, commit_id),
        )

        # Search with similar embedding
        query_embedding = [0.12] * 1536
        db_cursor.execute(
            """
            SELECT * FROM search_commits_by_embedding(
                %s::vector(1536), %s, %s, %s, %s, %s, %s
            )
            """,
            (query_embedding, 10, 0.0, repo_id, None, None, None),
        )
        results = db_cursor.fetchall()

        assert len(results) >= 1
        assert results[0]["commit_sha"] == "search123"
        assert results[0]["similarity"] > 0.5

    def test_cosine_similarity_calculation(self, db_cursor, test_repository):
        """Verify pgvector cosine similarity works correctly with orthogonal vectors."""
        repo_id = test_repository

        # Insert commit with embedding (unit vector in first dimension)
        db_cursor.execute(
            """
            SELECT upsert_git_commit_with_branch_merge(
                %s, %s, %s, %s, %s, %s, %s, %s
            )
            """,
            (
                repo_id,
                "vec1",
                "Test",
                "test@test.com",
                datetime.now(timezone.utc),
                "Vector 1",
                [],
                ["main"],
            ),
        )
        result = db_cursor.fetchone()
        commit_id = result["upsert_git_commit_with_branch_merge"]

        embedding_1 = [1.0] + [0.0] * 1535
        db_cursor.execute(
            """
            UPDATE archon_git_commits
            SET embedding_1536 = %s::vector(1536)
            WHERE id = %s
            """,
            (embedding_1, commit_id),
        )

        # Search with orthogonal vector (unit vector in second dimension)
        embedding_2 = [0.0] + [1.0] + [0.0] * 1534
        db_cursor.execute(
            """
            SELECT * FROM search_commits_by_embedding(
                %s::vector(1536), %s, %s, %s, %s, %s, %s
            )
            """,
            (embedding_2, 10, 0.0, repo_id, None, None, None),
        )
        results = db_cursor.fetchall()

        # Similarity should be close to 0.0 (orthogonal vectors)
        if len(results) > 0:
            assert results[0]["similarity"] < 0.1


class TestRealIntegrationWorkflows:
    """End-to-end integration tests."""

    def test_full_commit_sync_and_search_workflow(self, db_cursor):
        """Test complete workflow: register repo -> sync commits -> search."""
        # 1. Register repository
        db_cursor.execute(
            """
            INSERT INTO archon_git_repositories (repository_path_normalized, repository_url)
            VALUES (%s, %s)
            RETURNING id
            """,
            ("/workflow/test", "https://github.com/test/workflow"),
        )
        repo_id = db_cursor.fetchone()["id"]

        try:
            # 2. Sync multiple commits
            commits = [
                {"sha": f"commit{i}", "message": f"Feature {i}", "intent": "feature" if i % 2 == 0 else "bugfix"}
                for i in range(5)
            ]

            for commit in commits:
                db_cursor.execute(
                    """
                    SELECT upsert_git_commit_with_branch_merge(
                        %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        repo_id,
                        commit["sha"],
                        "Dev",
                        "dev@test.com",
                        datetime.now(timezone.utc),
                        commit["message"],
                        [],
                        ["main"],
                    ),
                )

            # 3. Verify all commits were synced
            db_cursor.execute(
                "SELECT COUNT(*) as count FROM archon_git_commits WHERE repo_id = %s",
                (repo_id,),
            )
            count = db_cursor.fetchone()["count"]
            assert count == 5

        finally:
            # Cleanup
            db_cursor.execute("DELETE FROM archon_git_repositories WHERE id = %s", (repo_id,))


# Documentation for running integration tests
"""
Integration Test Setup Guide
=============================

1. Start test database:
   cd python/tests/git_integration
   docker-compose -f docker-compose.test.yml up -d

2. Wait for database to be ready:
   docker-compose -f docker-compose.test.yml logs -f postgres
   # Wait for "database system is ready to accept connections"

3. Run integration tests:
   pytest -m integration -v

4. Stop and cleanup:
   docker-compose -f docker-compose.test.yml down -v

Environment Variables:
  TEST_DATABASE_URL: PostgreSQL connection string (optional)
    Default: postgresql://postgres:postgres@localhost:5433/archon_test

Notes:
  - Integration tests are marked with @pytest.mark.integration
  - Use -m "not integration" to skip them
  - Use -m integration to run only them
  - Database schema is auto-created from test_db_setup.sql on container start
"""
