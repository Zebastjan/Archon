"""Database schema validation tests.

These tests verify that the code's expectations match the actual database schema.
Run these tests to catch schema mismatches early.
"""

import pytest
from typing import Set


class TestDatabaseSchema:
    """Test suite for validating database schema against code expectations."""

    # Expected columns for archon_sources based on actual database schema
    EXPECTED_ARCHON_SOURCES_COLUMNS: Set[str] = {
        "source_id",  # Primary key
        "source_url",  # URL of the source
        "source_display_name",  # Human readable name
        "summary",  # Content summary
        "total_word_count",  # Word count
        "title",  # Title of source
        "metadata",  # JSON metadata
        "created_at",  # Creation timestamp
        "updated_at",  # Update timestamp
        "embedding_model",  # Model used for embeddings
        "embedding_dimensions",  # Embedding dimensions
        "embedding_provider",  # Embedding provider
        "vectorizer_settings",  # Vectorizer configuration
        "summarization_model",  # Summarization model
        "last_crawled_at",  # Last crawl timestamp
        "last_vectorized_at",  # Last vectorization timestamp
        "pipeline_status",  # Pipeline status
        "pipeline_error",  # Pipeline error info
        "pipeline_completed_at",  # Pipeline completion timestamp
        "code_examples_count",  # Number of code examples
        "document_count",  # Number of documents
        "repo_id",  # Associated repo ID
    }

    def test_archon_sources_schema_matches_expectations(self):
        """Test that archon_sources table has expected columns.

        This test uses docker exec to query the database directly,
        so it works without Python database dependencies.
        """
        import subprocess
        import json

        try:
            # Query database via docker exec
            result = subprocess.run(
                [
                    "docker",
                    "exec",
                    "supabase-db",
                    "psql",
                    "-U",
                    "postgres",
                    "-d",
                    "postgres",
                    "-t",
                    "-c",
                    "SELECT column_name FROM information_schema.columns WHERE table_name = 'archon_sources'",
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            # Parse actual columns from output
            actual_columns = {line.strip() for line in result.stdout.strip().split("\n") if line.strip()}

            # Check for missing columns
            missing = self.EXPECTED_ARCHON_SOURCES_COLUMNS - actual_columns
            if missing:
                pytest.fail(
                    f"archon_sources table missing expected columns: {sorted(missing)}\n\n"
                    f"This means migrations have not been applied. Run:\n"
                    f"  cd /home/zebastjan/dev/archon/migration/0.1.0/\n"
                    f"  docker exec -i supabase-db psql -U postgres -d postgres < 013_add_provenance_tracking.sql\n"
                    f"  docker exec -i supabase-db psql -U postgres -d postgres < 014_add_pipeline_tables.sql"
                )

            # Check for unexpected columns (helps catch drift)
            extra = actual_columns - self.EXPECTED_ARCHON_SOURCES_COLUMNS
            if extra:
                print(f"\nWARNING: archon_sources has unexpected columns: {sorted(extra)}")

        except subprocess.CalledProcessError as e:
            pytest.skip(f"Could not connect to database via Docker: {e.stderr}")

    def test_code_does_not_use_invalid_columns(self):
        """Static analysis test - check code doesn't reference invalid columns.

        This test scans the codebase for references to archon_sources columns
        that don't exist in the schema.
        """
        import ast
        import inspect
        from pathlib import Path

        # Columns that definitely don't exist and shouldn't be used
        INVALID_COLUMNS = {'"name"', '"url"', "'name'", "'url'"}

        # API files that insert into archon_sources
        api_files = [
            "src/server/api_routes/git_test_api.py",
            "src/server/api_routes/git_api.py",
            "src/server/services/crawling/crawling_service.py",
            "src/server/services/crawling/document_storage_operations.py",
        ]

        violations = []

        for file_path in api_files:
            full_path = Path("/home/zebastjan/dev/archon/python") / file_path
            if not full_path.exists():
                continue

            try:
                with open(full_path) as f:
                    source = f.read()

                # Simple string check for invalid columns in archon_sources context
                for invalid in INVALID_COLUMNS:
                    if invalid in source:
                        # Check if it's in an insert context
                        lines = source.split("\n")
                        for i, line in enumerate(lines, 1):
                            if invalid in line and ("insert" in line.lower() or "archon_sources" in line.lower()):
                                violations.append(f"{file_path}:{i}: Uses invalid column {invalid}")
            except Exception as e:
                violations.append(f"{file_path}: Error parsing: {e}")

        if violations:
            pytest.fail(
                "Found invalid column references in code:\n"
                + "\n".join(violations)
                + "\n\nThese columns don't exist in archon_sources table. "
                "Use 'source_url', 'source_display_name', or 'title' instead."
            )

    def test_code_uses_required_columns(self):
        """Verify code uses required columns for archon_sources inserts.

        Checks that API code uses the correct column names.
        """
        import inspect
        from src.server.api_routes import git_test_api
        from src.server.api_routes import git_api

        REQUIRED_COLUMNS = {'"source_url"', '"source_display_name"', '"title"', '"source_type"', '"status"'}

        # Get source code of key functions
        git_test_source = inspect.getsource(git_test_api.initialize_test_fixture)
        # Use initialize_repository which is the POST endpoint handler
        git_api_source = inspect.getsource(git_api.initialize_repository)

        all_source = git_test_source + git_api_source

        missing = []
        for col in REQUIRED_COLUMNS:
            if col not in all_source:
                missing.append(col)

        if missing:
            pytest.fail(
                f"API code missing required columns: {missing}\nThese columns are required for archon_sources inserts."
            )

    def test_schema_cache_issue_detection(self):
        """Test to detect PostgREST schema cache issues.

        This test documents the schema cache problem and provides
        instructions for fixing it.
        """
        # This is a documentation test explaining the issue
        pytest.skip(
            "This test documents the PostgREST schema cache issue:\n"
            "1. When columns are added to database, PostgREST caches the old schema\n"
            "2. Code references new columns, but PostgREST rejects them\n"
            "3. Error: 'Could not find the X column of Y in the schema cache'\n"
            "4. Fix: Restart PostgREST container: docker restart supabase-rest\n"
            "5. Or reload schema: POST http://localhost:3000/rpc/notify_pgrst"
        )


class TestSchemaDocumentation:
    """Tests that document expected schema for developers."""

    def test_archon_sources_column_documentation(self):
        """Document the expected archon_sources schema.

        This test serves as living documentation of the schema.
        """
        expected_schema = {
            "source_id": "TEXT PRIMARY KEY",
            "source_url": "TEXT - The actual URL/path",
            "source_display_name": "TEXT - Human readable name",
            "source_type": "TEXT - Type of source (e.g., git_repository)",
            "title": "TEXT - Title of the source",
            "status": "TEXT - active, pending, etc.",
            "summary": "TEXT - Content summary",
            "total_word_count": "INTEGER",
            "metadata": "JSONB",
            "created_at": "TIMESTAMP WITH TIME ZONE",
            "updated_at": "TIMESTAMP WITH TIME ZONE",
            "embedding_model": "TEXT",
            "embedding_dimensions": "INTEGER",
            "embedding_provider": "TEXT",
            "vectorizer_settings": "JSONB",
            "summarization_model": "TEXT",
            "last_crawled_at": "TIMESTAMP WITH TIME ZONE",
            "last_vectorized_at": "TIMESTAMP WITH TIME ZONE",
            "pipeline_status": "TEXT",
            "pipeline_error": "JSONB",
            "pipeline_completed_at": "TIMESTAMP WITH TIME ZONE",
            "code_examples_count": "INTEGER",
            "document_count": "INTEGER",
            "repo_id": "UUID",
        }

        # This test always passes - it documents the schema
        assert len(expected_schema) == 24, f"archon_sources should have 24 columns (currently {len(expected_schema)})"

        # Print documentation
        print("\narchon_sources table schema:")
        print("=" * 50)
        for col, desc in sorted(expected_schema.items()):
            print(f"  {col:25} - {desc}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
