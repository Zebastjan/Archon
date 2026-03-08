"""Tests for Git test fixtures API."""

import json
import pytest
from fastapi import status
from unittest.mock import MagicMock, patch
from pathlib import Path

from src.server.api_routes.git_test_api import (
    initialize_test_fixture,
    cleanup_test_fixtures,
    list_test_fixtures,
    FIXTURE_MAP,
)


class TestGitTestFixturesAPI:
    """Test suite for Git test fixtures API endpoints."""

    @pytest.fixture
    def mock_supabase_with_schema(self):
        """Create mock Supabase client that validates schema columns."""
        mock_client = MagicMock()

        # Define valid columns for archon_sources
        valid_source_columns = {
            "source_id",
            "source_url",
            "source_display_name",
            "title",
            "source_type",
            "status",
            "summary",
            "total_word_count",
            "metadata",
            "created_at",
            "updated_at",
            "embedding_model",
            "embedding_dimensions",
            "embedding_provider",
            "vectorizer_settings",
            "summarization_model",
            "last_crawled_at",
            "last_vectorized_at",
            "pipeline_status",
            "pipeline_error",
            "pipeline_completed_at",
            "code_examples_count",
            "document_count",
            "repo_id",
        }

        # Track what columns are actually used
        used_columns = set()

        def validate_insert(table_name, data):
            """Validate that insert data only uses valid columns."""
            if table_name == "archon_sources":
                for key in data.keys():
                    if key not in valid_source_columns:
                        raise ValueError(
                            f"Invalid column '{key}' for archon_sources. Valid columns: {sorted(valid_source_columns)}"
                        )
                    used_columns.add(key)
            return MagicMock(execute=MagicMock(return_value=MagicMock(data=[{"id": "test-source-id"}])))

        def mock_table(name):
            table_mock = MagicMock()
            table_mock.name = name

            def insert_side_effect(data):
                return validate_insert(name, data)

            table_mock.insert.side_effect = insert_side_effect
            table_mock.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            table_mock.delete.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

            return table_mock

        mock_client.table.side_effect = mock_table
        mock_client._used_columns = used_columns

        return mock_client

    @pytest.mark.asyncio
    async def test_initialize_test_fixture_validates_schema(self, mock_supabase_with_schema):
        """Test that fixture initialization validates against actual schema."""
        from src.server.api_routes.git_test_api import initialize_test_fixture
        from src.server.api_routes.git_test_api import InitializeTestFixtureRequest

        with patch("src.server.api_routes.git_test_api.get_supabase_client", return_value=mock_supabase_with_schema):
            with patch("src.server.api_routes.git_test_api.GitRepositoryService") as mock_git_service:
                # Mock successful repository registration
                mock_service = MagicMock()
                mock_service.register_repository.return_value = (
                    True,
                    {"repo_id": "test-repo-id", "repo_name": "test-repo"},
                )
                mock_service.sync_commits.return_value = (True, {"commit_count": 3})
                mock_git_service.return_value = mock_service

                # Mock fixture path exists
                with patch("src.server.api_routes.git_test_api.Path.exists", return_value=True):
                    with patch("src.server.api_routes.git_test_api.shutil.copytree"):
                        with patch(
                            "src.server.api_routes.git_test_api.json.load",
                            return_value={"default_branch": "main", "commits": []},
                        ):
                            with patch("builtins.open", create=True):
                                request = InitializeTestFixtureRequest(fixture_name="simple-commits")

                                # This should NOT raise schema errors
                                response = await initialize_test_fixture("test-project-id", request)

                                # Verify response
                                assert response.success is True
                                assert response.repo_id == "test-repo-id"

                                # Verify we used valid columns
                                used_cols = mock_supabase_with_schema._used_columns
                                invalid_cols = used_cols - {
                                    "source_id",
                                    "source_url",
                                    "source_display_name",
                                    "title",
                                    "source_type",
                                    "status",
                                    "summary",
                                    "total_word_count",
                                    "metadata",
                                    "created_at",
                                    "updated_at",
                                    "embedding_model",
                                    "embedding_dimensions",
                                    "embedding_provider",
                                    "vectorizer_settings",
                                    "summarization_model",
                                    "last_crawled_at",
                                    "last_vectorized_at",
                                    "pipeline_status",
                                    "pipeline_error",
                                    "pipeline_completed_at",
                                    "code_examples_count",
                                    "document_count",
                                    "repo_id",
                                }
                                assert not invalid_cols, f"Used invalid columns: {invalid_cols}"

    @pytest.mark.asyncio
    async def test_initialize_test_fixture_rejects_invalid_columns(self):
        """Test that using invalid column names raises appropriate errors."""
        # This test verifies our validation catches schema mismatches
        mock_client = MagicMock()

        def strict_insert(data):
            # Simulate PostgREST behavior: reject unknown columns
            valid_columns = {"source_type", "source_url", "source_display_name", "title", "status"}
            for key in data.keys():
                if key not in valid_columns:
                    from postgrest.exceptions import APIError

                    raise APIError(
                        {
                            "message": f"Could not find the '{key}' column of 'archon_sources' in the schema cache",
                            "code": "PGRST204",
                        }
                    )
            return MagicMock(execute=MagicMock(return_value=MagicMock(data=[{"id": "test-id"}])))

        mock_table = MagicMock()
        mock_table.insert.side_effect = strict_insert
        mock_table.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        mock_client.table.return_value = mock_table

        with patch("src.server.api_routes.git_test_api.get_supabase_client", return_value=mock_client):
            with patch("src.server.api_routes.git_test_api.Path.exists", return_value=True):
                with patch("src.server.api_routes.git_test_api.json.load", return_value={}):
                    with patch("builtins.open", create=True):
                        from src.server.api_routes.git_test_api import InitializeTestFixtureRequest

                        request = InitializeTestFixtureRequest(fixture_name="simple-commits")

                        # This should catch the APIError and convert to HTTPException
                        with pytest.raises(Exception) as exc_info:
                            await initialize_test_fixture("test-project-id", request)

                        # Verify error handling
                        assert exc_info.value is not None

    @pytest.mark.asyncio
    async def test_cleanup_test_fixtures(self, mock_supabase_with_schema):
        """Test cleanup endpoint removes test fixtures properly."""
        with patch("src.server.api_routes.git_test_api.get_supabase_client", return_value=mock_supabase_with_schema):
            with patch("src.server.api_routes.git_test_api.Path.exists", return_value=True):
                with patch("src.server.api_routes.git_test_api.shutil.rmtree") as mock_rmtree:
                    # Mock existing repository
                    mock_supabase_with_schema.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
                        data=[{"id": "test-repo-id", "source_id": "test-source-id"}]
                    )
                    mock_supabase_with_schema.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
                        data=[{"url": "/tmp/test/path"}]
                    )

                    response = await cleanup_test_fixtures("test-project-id")

                    assert response["success"] is True
                    assert response["deleted_count"] == 1

    @pytest.mark.asyncio
    async def test_list_test_fixtures(self):
        """Test listing available test fixtures."""
        with patch("src.server.api_routes.git_test_api.Path.exists", return_value=True):
            with patch(
                "src.server.api_routes.git_test_api.json.load",
                return_value={
                    "commits": [1, 2, 3],
                    "branches": ["main"],
                    "files": ["a.txt", "b.txt"],
                    "default_branch": "main",
                },
            ):
                with patch("builtins.open", create=True):
                    response = await list_test_fixtures()

                    assert "fixtures" in response
                    fixtures = response["fixtures"]

                    # Should have all three fixtures
                    assert len(fixtures) == 3
                    fixture_names = {f["name"] for f in fixtures}
                    assert fixture_names == {"simple-commits", "multi-branch", "file-structure"}


class TestSchemaValidation:
    """Tests specifically for database schema validation."""

    def test_archon_sources_columns_match_code(self):
        """Test that code uses only valid archon_sources columns."""
        # Read the actual API file to check column usage
        import inspect
        from src.server.api_routes import git_test_api

        source = inspect.getsource(git_test_api.initialize_test_fixture)

        # These columns should NOT be in the code (they don't exist)
        invalid_columns = ['"name"', '"url"']

        for col in invalid_columns:
            assert col not in source, f"Code uses invalid column {col} in archon_sources insert"

        # These columns SHOULD be in the code (they exist)
        valid_columns = ['"source_url"', '"source_display_name"', '"title"']
        found_valid = [col for col in valid_columns if col in source]

        assert len(found_valid) >= 2, "Code should use valid columns for archon_sources"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
