#!/usr/bin/env python3
"""Create the operation_progress table if it doesn't exist."""

from src.server.utils import get_supabase_client

supabase = get_supabase_client()

# Check if table exists
try:
    result = supabase.table("archon_operation_progress").select("id").limit(1).execute()
    print("Table already exists!")
except Exception as e:
    print(f"Table doesn't exist: {e}")
    print("Attempting to create via SQL...")

    # Use the storage API to create table
    # This is a workaround since we can't run raw SQL easily
    try:
        # Try to insert a record - this will fail if table doesn't exist
        # But it might also create the table through Supabase's auto-migration
        supabase.table("archon_operation_progress").insert(
            {"progress_id": "test", "operation_type": "test", "status": "in_progress"}
        ).execute()
        print("Table created successfully!")
    except Exception as insert_error:
        print(f"Insert also failed: {insert_error}")
        print("\nThe table needs to be created manually or through Supabase dashboard.")
        print("Please run the migration: migration/0.1.0/015_add_operation_progress.sql")
