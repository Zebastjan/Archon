#!/usr/bin/env python3
"""
EMERGENCY FIX: Clean up the embedding disaster

Problems:
1. 884k entities including node_modules (should be ~5-10k)
2. Zero embeddings generated
3. archon-ui data needs to be deleted
4. No checkpointing on embedding script
5. Wayland crashes from VRAM exhaustion

Solutions:
1. Delete all archon-ui entities
2. Delete all node_modules entities from all repos
3. Fix git_repository_service.py to exclude common dirs
4. Create proper BGE-M3 embedding script with checkpointing
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent / "python" / "src"))

from server.services.database.db_connector import (
    get_database_connector,
    initialize_database,
)


async def cleanup_database():
    """Clean up bogus entities from database."""
    print("=" * 80)
    print("EMERGENCY DATABASE CLEANUP")
    print("=" * 80)
    print(f"Started: {datetime.now().isoformat()}")
    print()

    await initialize_database()
    db = get_database_connector()

    # Get current counts
    print("Getting current entity counts...")
    total = await db.fetchval("SELECT COUNT(*) FROM archon_code_entities")
    print(f"  Total entities: {total:,}")

    # Count by repo
    repos = await db.fetch("""
        SELECT repo_id, COUNT(*) as count
        FROM archon_code_entities
        GROUP BY repo_id
    """)
    print("\nBy repository:")
    for r in repos:
        print(f"  {r['repo_id']}: {r['count']:,}")

    # Count node_modules entities
    node_modules = await db.fetchval("""
        SELECT COUNT(*) FROM archon_code_entities
        WHERE file_path LIKE '%node_modules%'
    """)
    print(f"\n  Entities from node_modules: {node_modules:,}")

    # Count archon-ui entities
    archon_ui = await db.fetchval("""
        SELECT COUNT(*) FROM archon_code_entities
        WHERE repo_id IN (
            SELECT id FROM archon_code_repos WHERE name ILIKE '%archon-ui%'
        )
    """)
    print(f"  archon-ui entities: {archon_ui:,}")

    # ASK BEFORE DELETING
    print("\n" + "=" * 80)
    print("DELETION PLAN:")
    print("=" * 80)
    print(f"1. Delete ALL archon-ui entities: {archon_ui:,}")
    print(f"2. Delete ALL node_modules entities: {node_modules:,}")
    print(f"3. Remaining after cleanup: {total - archon_ui - node_modules:,}")
    print()

    response = input("Proceed with deletion? Type 'DELETE' to confirm: ")
    if response != "DELETE":
        print("Cancelled.")
        return

    # Delete archon-ui entities
    print("\nDeleting archon-ui entities...")
    result = await db.execute("""
        DELETE FROM archon_code_entities
        WHERE repo_id IN (
            SELECT id FROM archon_code_repos WHERE name ILIKE '%archon-ui%'
        )
    """)
    print(f"  Deleted archon-ui entities")

    # Delete node_modules entities
    print("\nDeleting node_modules entities...")
    result = await db.execute("""
        DELETE FROM archon_code_entities
        WHERE file_path LIKE '%node_modules%'
    """)
    print(f"  Deleted node_modules entities")

    # Delete other common junk directories
    junk_patterns = [
        "%/.git/%",
        "%/__pycache__/%",
        "%/.pytest_cache/%",
        "%/.mypy_cache/%",
        "%/venv/%",
        "%/.venv/%",
        "%/build/%",
        "%/dist/%",
        "%/.tox/%",
        "%/.eggs/%",
        "%/*.egg-info/%",
    ]

    for pattern in junk_patterns:
        count = await db.fetchval(
            """
            SELECT COUNT(*) FROM archon_code_entities
            WHERE file_path LIKE $1
        """,
            pattern,
        )
        if count > 0:
            print(f"  Deleting {count:,} entities matching {pattern}")
            await db.execute(
                """
                DELETE FROM archon_code_entities WHERE file_path LIKE $1
            """,
                pattern,
            )

    # Get final count
    final = await db.fetchval("SELECT COUNT(*) FROM archon_code_entities")
    print(f"\nFinal entity count: {final:,} (removed {total - final:,})")

    print("\n" + "=" * 80)
    print("CLEANUP COMPLETE")
    print("=" * 80)


async def fix_git_service():
    """Fix the git repository service to exclude common directories."""
    print("\n" + "=" * 80)
    print("FIXING git_repository_service.py")
    print("=" * 80)

    service_file = (
        Path(__file__).resolve().parent
        / "python"
        / "src"
        / "server"
        / "services"
        / "git"
        / "git_repository_service.py"
    )

    if not service_file.exists():
        print(f"ERROR: File not found: {service_file}")
        return

    content = service_file.read_text()

    # Check if fix already applied
    if "EXCLUDED_DIRECTORIES" in content:
        print("Fix already applied!")
        return

    # Find the get_file_tree method and add exclusion logic
    # We need to add exclusion after the path prefix check

    old_code = """                    # Filter by path prefix if provided
                    if path_prefix and not item_path.startswith(path_prefix):
                        continue

                    file_info = {"""

    new_code = """                    # Filter by path prefix if provided
                    if path_prefix and not item_path.startswith(path_prefix):
                        continue

                    # Exclude common directories (node_modules, .git, etc)
                    EXCLUDED_DIRECTORIES = {
                        "node_modules", ".git", "__pycache__", ".pytest_cache",
                        ".mypy_cache", "venv", ".venv", "build", "dist",
                        ".tox", ".eggs", ".pnpm", ".next", ".nuxt"
                    }
                    if any(f"/{excl}/" in item_path or item_path.startswith(f"{excl}/") 
                           for excl in EXCLUDED_DIRECTORIES):
                        continue

                    file_info = {"""

    if old_code in content:
        content = content.replace(old_code, new_code)
        service_file.write_text(content)
        print("✓ Fixed git_repository_service.py to exclude common directories")
    else:
        print("WARNING: Could not find the exact code to patch")
        print("You may need to manually add the EXCLUDED_DIRECTORIES check")


if __name__ == "__main__":
    try:
        asyncio.run(cleanup_database())
        asyncio.run(fix_git_service())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
