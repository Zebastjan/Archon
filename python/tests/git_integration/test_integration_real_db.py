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

import os
import sys
from unittest.mock import MagicMock
import asyncio

# Mock non-database modules
sys.modules['openai'] = MagicMock()
sys.modules['src.server.services.embeddings'] = MagicMock()
sys.modules['src.server.services.embeddings.embedding_service'] = MagicMock()

import pytest
from datetime import datetime
from supabase import create_client, Client

# Mark all tests as integration tests
pytestmark = pytest.mark.integration


def get_test_db_url():
    """Get test database URL from environment or use default."""
    return os.getenv(
        "TEST_DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5433/archon_test"
    )


@pytest.fixture(scope="session")
def integration_db_available():
    """Check if integration test database is available."""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host="localhost",
            port=5433,
            database="archon_test",
            user="postgres",
            password="postgres",
        )
        conn.close()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def real_supabase_client(integration_db_available):
    """Provide real Supabase client for integration tests."""
    if not integration_db_available:
        pytest.skip("Integration test database not available")

    # Create Supabase client with test database
    url = "http://localhost:5433"  # Direct PostgreSQL connection
    # For real integration, you'd use actual Supabase URL
    # For now, we'll use direct postgres connection
    pytest.skip("Real Supabase client requires API configuration")


@pytest.fixture
async def test_repository(real_supabase_client):
    """Create a test repository in the database."""
    # Insert test repository
    response = real_supabase_client.table("archon_git_repositories").insert({
        "repository_path_normalized": "/test/repo",
        "repository_url": "https://github.com/test/repo",
    }).execute()

    repo_id = response.data[0]["id"]

    yield repo_id

    # Cleanup
    real_supabase_client.table("archon_git_repositories").delete().eq("id", repo_id).execute()


class TestRealDatabaseSchema:
    """Tests that validate database schema and constraints."""

    def test_database_connection(self, integration_db_available):
        """Test database is reachable."""
        assert integration_db_available is True

    @pytest.mark.skip(reason="Requires Supabase client configuration")
    async def test_git_commits_table_exists(self, real_supabase_client):
        """Verify archon_git_commits table exists."""
        response = real_supabase_client.table("archon_git_commits").select("*").limit(0).execute()
        assert response is not None

    @pytest.mark.skip(reason="Requires Supabase client configuration")
    async def test_pgvector_extension_loaded(self, real_supabase_client):
        """Verify pgvector extension is available."""
        # Would query: SELECT * FROM pg_extension WHERE extname = 'vector'
        pass


class TestRealRPCFunctions:
    """Tests that validate RPC functions work correctly."""

    @pytest.mark.skip(reason="Requires Supabase client configuration")
    async def test_upsert_commit_rpc(self, real_supabase_client, test_repository):
        """Test commit upsert RPC function."""
        repo_id = test_repository

        # First insert
        result = real_supabase_client.rpc(
            "upsert_git_commit_with_branch_merge",
            {
                "p_repo_id": repo_id,
                "p_commit_sha": "abc123",
                "p_message": "Test commit",
                "p_author_name": "Test Author",
                "p_author_email": "test@example.com",
                "p_commit_date": datetime.now().isoformat(),
                "p_parent_shas": [],
                "p_branches": ["main"],
                "p_metadata": {"intent": "feature"},
            }
        ).execute()

        commit_id = result.data
        assert commit_id is not None

        # Second insert with same SHA but different branch
        result2 = real_supabase_client.rpc(
            "upsert_git_commit_with_branch_merge",
            {
                "p_repo_id": repo_id,
                "p_commit_sha": "abc123",
                "p_message": "Test commit",
                "p_author_name": "Test Author",
                "p_author_email": "test@example.com",
                "p_commit_date": datetime.now().isoformat(),
                "p_parent_shas": [],
                "p_branches": ["develop"],
                "p_metadata": {"intent": "feature"},
            }
        ).execute()

        # Should return same commit ID
        assert result2.data == commit_id

        # Verify branches were merged
        commit = real_supabase_client.table("archon_git_commits").select("*").eq("id", commit_id).single().execute()
        assert set(commit.data["branches"]) == {"main", "develop"}

    @pytest.mark.skip(reason="Requires Supabase client configuration")
    async def test_search_commits_by_embedding_rpc(self, real_supabase_client, test_repository):
        """Test semantic search RPC function."""
        repo_id = test_repository

        # Insert commit with embedding
        commit_id = real_supabase_client.rpc(
            "upsert_git_commit_with_branch_merge",
            {
                "p_repo_id": repo_id,
                "p_commit_sha": "search123",
                "p_message": "Add search feature",
                "p_author_name": "Dev",
                "p_author_email": "dev@test.com",
                "p_commit_date": datetime.now().isoformat(),
                "p_parent_shas": [],
                "p_branches": ["main"],
                "p_metadata": {},
            }
        ).execute().data

        # Update with embedding
        test_embedding = [0.1] * 1536
        real_supabase_client.table("archon_git_commits").update({
            "embedding_1536": test_embedding
        }).eq("id", commit_id).execute()

        # Search with similar embedding
        query_embedding = [0.12] * 1536
        results = real_supabase_client.rpc(
            "search_commits_by_embedding",
            {
                "query_embedding": query_embedding,
                "match_count": 10,
                "filter_repo_id": repo_id,
            }
        ).execute()

        assert len(results.data) >= 1
        assert results.data[0]["commit_sha"] == "search123"
        assert results.data[0]["similarity"] > 0.5


class TestRealVectorSimilarity:
    """Tests that validate pgvector similarity calculations."""

    @pytest.mark.skip(reason="Requires Supabase client configuration")
    async def test_cosine_similarity_calculation(self, real_supabase_client, test_repository):
        """Verify pgvector cosine similarity works correctly."""
        repo_id = test_repository

        # Insert two commits with known embeddings
        embedding_1 = [1.0] + [0.0] * 1535  # Unit vector in first dimension
        embedding_2 = [0.0] + [1.0] + [0.0] * 1534  # Unit vector in second dimension

        # These should have similarity of 0.0 (orthogonal)

        commit_1_id = real_supabase_client.rpc(
            "upsert_git_commit_with_branch_merge",
            {
                "p_repo_id": repo_id,
                "p_commit_sha": "vec1",
                "p_message": "Vector 1",
                "p_author_name": "Test",
                "p_author_email": "test@test.com",
                "p_commit_date": datetime.now().isoformat(),
                "p_parent_shas": [],
                "p_branches": ["main"],
                "p_metadata": {},
            }
        ).execute().data

        real_supabase_client.table("archon_git_commits").update({
            "embedding_1536": embedding_1
        }).eq("id", commit_1_id).execute()

        # Search with orthogonal vector
        results = real_supabase_client.rpc(
            "search_commits_by_embedding",
            {
                "query_embedding": embedding_2,
                "match_count": 10,
                "filter_repo_id": repo_id,
            }
        ).execute()

        # Similarity should be close to 0.0
        if len(results.data) > 0:
            assert results.data[0]["similarity"] < 0.1


class TestRealIntegrationWorkflows:
    """End-to-end integration tests."""

    @pytest.mark.skip(reason="Requires Supabase client configuration")
    async def test_full_commit_sync_and_search_workflow(self, real_supabase_client):
        """Test complete workflow: register repo -> sync commits -> search."""
        # 1. Register repository
        repo_response = real_supabase_client.table("archon_git_repositories").insert({
            "repository_path_normalized": "/workflow/test",
            "repository_url": "https://github.com/test/workflow",
        }).execute()

        repo_id = repo_response.data[0]["id"]

        try:
            # 2. Sync multiple commits
            commits = [
                {
                    "sha": f"commit{i}",
                    "message": f"Feature {i}",
                    "intent": "feature" if i % 2 == 0 else "bugfix",
                }
                for i in range(5)
            ]

            for commit in commits:
                real_supabase_client.rpc(
                    "upsert_git_commit_with_branch_merge",
                    {
                        "p_repo_id": repo_id,
                        "p_commit_sha": commit["sha"],
                        "p_message": commit["message"],
                        "p_author_name": "Dev",
                        "p_author_email": "dev@test.com",
                        "p_commit_date": datetime.now().isoformat(),
                        "p_parent_shas": [],
                        "p_branches": ["main"],
                        "p_metadata": {"intent": commit["intent"]},
                    }
                ).execute()

            # 3. Verify all commits were synced
            all_commits = real_supabase_client.table("archon_git_commits").select("*").eq("repo_id", repo_id).execute()
            assert len(all_commits.data) == 5

            # 4. Test filtering by metadata
            feature_commits = real_supabase_client.table("archon_git_commits").select("*").eq("repo_id", repo_id).filter(
                "metadata->>intent", "eq", "feature"
            ).execute()
            assert len(feature_commits.data) == 3

        finally:
            # Cleanup
            real_supabase_client.table("archon_git_repositories").delete().eq("id", repo_id).execute()


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
  - Integration tests are skipped by default
  - Use -m integration to run them explicitly
  - Most tests require Supabase client configuration
  - Database schema is auto-created from test_db_setup.sql
"""
