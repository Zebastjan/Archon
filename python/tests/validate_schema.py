#!/usr/bin/env python3
"""
Standalone database schema validation script.

This script validates that the archon_sources table has all expected columns
before the application starts. It uses docker exec to query the database,
so it doesn't require Python database dependencies.

Usage:
    python tests/validate_schema.py

Exit codes:
    0 - Schema is valid
    1 - Schema is invalid (missing columns)
    2 - Cannot connect to database
"""

import subprocess
import sys
from typing import Set

# Expected columns for archon_sources based on migrations
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
    "source_type",  # Type of source (git_repository, etc.)
    "status",  # Status (active, pending, etc.)
}


def validate_schema() -> bool:
    """Validate archon_sources table schema.

    Returns:
        True if schema is valid, False otherwise
    """
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
        missing = EXPECTED_ARCHON_SOURCES_COLUMNS - actual_columns
        if missing:
            print("❌ SCHEMA VALIDATION FAILED", file=sys.stderr)
            print(f"\narchon_sources table missing expected columns:", file=sys.stderr)
            for col in sorted(missing):
                print(f"  - {col}", file=sys.stderr)
            print(f"\nMissing migrations detected. Please run:", file=sys.stderr)
            print(
                f"  cd /home/zebastjan/dev/archon/migration/0.1.0/",
                file=sys.stderr,
            )
            print(
                f"  docker exec -i supabase-db psql -U postgres -d postgres < 013_add_provenance_tracking.sql",
                file=sys.stderr,
            )
            print(
                f"  docker exec -i supabase-db psql -U postgres -d postgres < 014_add_pipeline_tables.sql",
                file=sys.stderr,
            )
            return False

        # Check for unexpected columns (informational only)
        extra = actual_columns - EXPECTED_ARCHON_SOURCES_COLUMNS
        if extra:
            print(f"⚠️  WARNING: archon_sources has unexpected columns: {sorted(extra)}")

        print(f"✅ Schema validation passed - all {len(EXPECTED_ARCHON_SOURCES_COLUMNS)} expected columns present")
        return True

    except subprocess.CalledProcessError as e:
        print("❌ SCHEMA VALIDATION FAILED", file=sys.stderr)
        print(f"\nCould not connect to database via Docker:", file=sys.stderr)
        print(f"  {e.stderr}", file=sys.stderr)
        print(f"\nMake sure Supabase is running:", file=sys.stderr)
        print(f"  docker ps | grep supabase-db", file=sys.stderr)
        return False
    except Exception as e:
        print("❌ SCHEMA VALIDATION FAILED", file=sys.stderr)
        print(f"\nUnexpected error: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    if validate_schema():
        sys.exit(0)
    else:
        sys.exit(1)
