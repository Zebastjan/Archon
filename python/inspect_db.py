#!/usr/bin/env python3
"""
Database inspection script to understand zombie crawl state.
"""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Load environment variables from .env file
from dotenv import load_dotenv

load_dotenv()

from server.utils import get_supabase_client


def print_section(title: str):
    """Print a section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def inspect_operation_progress():
    """Inspect the archon_operation_progress table."""
    print_section("OPERATION PROGRESS TABLE")

    supabase = get_supabase_client()

    # Get all operations, ordered by most recent first
    result = supabase.table("archon_operation_progress").select("*").order("updated_at", desc=True).execute()

    if not result.data:
        print("  No operations found in database.")
        return []

    print(f"\n  Found {len(result.data)} operations\n")

    for i, op in enumerate(result.data, 1):
        print(f"  {i}. Progress ID: {op.get('progress_id', 'N/A')}")
        print(f"     Status: {op.get('status', 'N/A')}")
        print(f"     Type: {op.get('operation_type', 'N/A')}")
        print(f"     Source ID: {op.get('source_id', 'NULL')}")
        print(f"     Progress: {op.get('progress', 0)}%")
        print(f"     Current URL: {op.get('current_url', 'N/A')}")
        print(f"     Total Pages: {op.get('total_pages', 0)}")
        print(f"     Processed Pages: {op.get('processed_pages', 0)}")
        print(f"     Documents Created: {op.get('documents_created', 0)}")
        print(f"     Code Blocks: {op.get('code_blocks_found', 0)}")
        print(f"     Created: {op.get('created_at', 'N/A')}")
        print(f"     Updated: {op.get('updated_at', 'N/A')}")
        print(f"     Error: {op.get('error_message', 'None')}")

        # Show stats if available
        stats = op.get('stats', {})
        if stats:
            print(f"     Stats: {stats}")

        print()

    return result.data


def inspect_sources(operations):
    """Inspect the archon_sources table."""
    print_section("SOURCES TABLE")

    supabase = get_supabase_client()

    # Get all sources
    result = supabase.table("archon_sources").select("*").order("created_at", desc=True).execute()

    if not result.data:
        print("  No sources found in database.")
        return

    print(f"\n  Found {len(result.data)} sources\n")

    # Create a map of source_id to operation for cross-reference
    op_by_source = {op.get('source_id'): op for op in operations if op.get('source_id')}

    for i, source in enumerate(result.data, 1):
        source_id = source.get('source_id', 'N/A')
        print(f"  {i}. Source ID: {source_id}")
        print(f"     Display Name: {source.get('display_name', 'N/A')}")
        print(f"     Source URL: {source.get('source_url', 'N/A')}")
        print(f"     Status: {source.get('status', 'N/A')}")
        print(f"     Documents Count: {source.get('documents_count', 0)}")
        print(f"     Code Examples Count: {source.get('code_examples_count', 0)}")
        print(f"     Created: {source.get('created_at', 'N/A')}")
        print(f"     Updated: {source.get('updated_at', 'N/A')}")

        # Show metadata if available
        metadata = source.get('metadata', {})
        if metadata:
            print(f"     Metadata: {metadata}")

        # Cross-reference with operations
        if source_id in op_by_source:
            op = op_by_source[source_id]
            print("     ⚠️  LINKED OPERATION:")
            print(f"         Progress ID: {op.get('progress_id')}")
            print(f"         Operation Status: {op.get('status')}")
            print(f"         Operation Progress: {op.get('progress')}%")

        print()


def inspect_crawl_url_state():
    """Inspect the archon_crawl_url_state table."""
    print_section("CRAWL URL STATE TABLE")

    supabase = get_supabase_client()

    # Get all crawl URL states
    result = supabase.table("archon_crawl_url_state").select("*").order("updated_at", desc=True).execute()

    if not result.data:
        print("  No crawl URL states found in database.")
        return

    print(f"\n  Found {len(result.data)} crawl URL state records\n")

    for i, state in enumerate(result.data, 1):
        print(f"  {i}. Source ID: {state.get('source_id', 'N/A')}")
        print(f"     URL: {state.get('url', 'N/A')}")
        print(f"     Status: {state.get('status', 'N/A')}")
        print(f"     Depth: {state.get('depth', 0)}")
        print(f"     Created: {state.get('created_at', 'N/A')}")
        print(f"     Updated: {state.get('updated_at', 'N/A')}")
        print()


def analyze_zombie_crawls(operations):
    """Analyze operations that might be zombie crawls."""
    print_section("ZOMBIE CRAWL ANALYSIS")

    zombies = [
        op for op in operations
        if op.get('status') in ['in_progress', 'crawling', 'starting', 'paused']
    ]

    if not zombies:
        print("  No zombie crawls found!")
        return

    print(f"\n  Found {len(zombies)} potential zombie crawls:\n")

    for i, zombie in enumerate(zombies, 1):
        print(f"  {i}. Progress ID: {zombie.get('progress_id')}")
        print(f"     Status: {zombie.get('status')}")
        print(f"     Source ID: {zombie.get('source_id', '⚠️  NULL')}")
        print(f"     Progress: {zombie.get('progress')}%")

        # Diagnose issues
        issues = []
        if not zombie.get('source_id'):
            issues.append("Missing source_id - cannot auto-resume")

        if zombie.get('status') == 'paused':
            issues.append("Marked as paused - should auto-resume on restart")

        if zombie.get('status') in ['in_progress', 'crawling', 'starting']:
            issues.append("Should have been marked as 'paused' on restart")

        if issues:
            print("     ⚠️  Issues:")
            for issue in issues:
                print(f"         - {issue}")

        print()


def main():
    """Main inspection routine."""
    print("\n" + "🔍 " * 30)
    print("   DATABASE INSPECTION - Zombie Crawl Investigation")
    print("🔍 " * 30)

    try:
        # Inspect each table
        operations = inspect_operation_progress()
        inspect_sources(operations)
        inspect_crawl_url_state()

        # Analyze zombies
        analyze_zombie_crawls(operations)

        print_section("SUMMARY")
        print(f"\n  Total Operations: {len(operations)}")
        zombies = [op for op in operations if op.get('status') in ['in_progress', 'crawling', 'starting', 'paused']]
        print(f"  Zombie Crawls: {len(zombies)}")

        completed = [op for op in operations if op.get('status') == 'completed']
        print(f"  Completed: {len(completed)}")

        failed = [op for op in operations if op.get('status') in ['failed', 'error']]
        print(f"  Failed: {len(failed)}")

        cancelled = [op for op in operations if op.get('status') == 'cancelled']
        print(f"  Cancelled: {len(cancelled)}")

        print("\n" + "=" * 80 + "\n")

    except Exception as e:
        print(f"\n❌ Error inspecting database: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
