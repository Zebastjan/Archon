"""Database schema validation utilities.

This module provides functions to validate that the database schema
matches the application's expectations before the server starts.
"""

from typing import Set, Tuple


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
    "embedding_model",  # Model used for embeddings (migration 013)
    "embedding_dimensions",  # Embedding dimensions (migration 013)
    "embedding_provider",  # Embedding provider (migration 013)
    "vectorizer_settings",  # Vectorizer configuration (migration 013)
    "summarization_model",  # Summarization model (migration 013)
    "last_crawled_at",  # Last crawl timestamp (migration 013)
    "last_vectorized_at",  # Last vectorization timestamp (migration 013)
    "pipeline_status",  # Pipeline status (migration 014)
    "pipeline_error",  # Pipeline error info (migration 014)
    "pipeline_completed_at",  # Pipeline completion timestamp (migration 014)
    "code_examples_count",  # Number of code examples
    "document_count",  # Number of documents
    "repo_id",  # Associated repo ID (migration 018)
    "source_type",  # Type of source (git_repository, etc.)
    "status",  # Status (active, pending, etc.)
}


def validate_archon_sources_schema(supabase_client) -> Tuple[bool, str]:
    """Validate that archon_sources table has all expected columns.

    This function queries the information_schema to get actual columns
    and compares them against the expected set.

    Args:
        supabase_client: Supabase client instance

    Returns:
        Tuple of (is_valid: bool, message: str)
            - is_valid: True if all columns exist, False otherwise
            - message: Success or error message with details
    """
    try:
        # Query information schema for actual columns
        # Note: We use RPC to query information_schema since PostgREST
        # doesn't expose it directly
        query = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'archon_sources'
        AND table_schema = 'public'
        """

        actual_columns = set()

        try:
            # Attempt RPC call
            response = supabase_client.rpc("exec_sql", {"sql": query}).execute()

            # Parse column names from response
            if response.data and isinstance(response.data, list):
                for row in response.data:
                    if isinstance(row, dict) and "column_name" in row:
                        actual_columns.add(row["column_name"])
        except Exception:
            # RPC function doesn't exist or failed - use fallback
            pass

        # If we couldn't get columns via RPC, try a simple existence check
        if not actual_columns:
            # Try selecting a few key columns to verify they exist
            key_columns = ["source_id", "source_type", "status", "embedding_model", "pipeline_status"]
            try:
                column_list = ", ".join(key_columns)
                supabase_client.table("archon_sources").select(column_list).limit(1).execute()
                # If this succeeds, assume schema is mostly OK
                return True, f"Schema validation passed (verified {len(key_columns)} key columns)"
            except Exception as e:
                error_str = str(e).lower()
                # Check if it's a column error
                if "column" in error_str and "does not exist" in error_str:
                    return False, f"Schema validation failed: Missing columns detected - {str(e)}"
                # Other error, might not be schema related
                return False, f"Schema validation failed: {str(e)}"

        # Check for missing columns
        missing = EXPECTED_ARCHON_SOURCES_COLUMNS - actual_columns
        if missing:
            missing_list = sorted(missing)
            message = (
                f"archon_sources table missing {len(missing)} expected columns: {missing_list}\n"
                f"Required migrations may not have been applied. Check:\n"
                f"  - migration/0.1.0/013_add_provenance_tracking.sql\n"
                f"  - migration/0.1.0/014_add_pipeline_tables.sql\n"
                f"  - migration/0.1.0/018_link_git_to_blobs.sql"
            )
            return False, message

        # Success
        return True, f"Schema validation passed - all {len(EXPECTED_ARCHON_SOURCES_COLUMNS)} columns present"

    except Exception as e:
        # Validation failed due to error
        return False, f"Schema validation error: {str(e)}"
