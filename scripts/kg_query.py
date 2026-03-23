#!/usr/bin/env python3
"""
Knowledge Graph Query Tools for Archon.

Query across commits and branches to understand code evolution.

Usage:
    # Show entity evolution across commits
    python scripts/kg_query.py --repo archon --entity extract_entities --type method

    # Compare branches
    python scripts/kg_query.py --repo archon --compare-branches main feature/xyz

    # List commits with changes
    python scripts/kg_query.py --repo archon --commits-with-changes

    # Find when an entity was added/modified
    python scripts/kg_query.py --repo archon --when-added SomeClass
"""

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add python to path
sys.path.insert(0, str(Path(__file__).parent.parent / "python" / "src"))

from dotenv import load_dotenv
from server.services.database.db_connector import (
    get_database_connector,
    initialize_database,
)

load_dotenv(Path(__file__).parent.parent / ".env")


def format_entity(entity: dict) -> str:
    """Format entity for display."""
    return (
        f"  {entity['name']} ({entity['entity_type']})\n"
        f"    File: {entity['file_path']}\n"
        f"    Lines: {entity['line_start']}-{entity['line_end']}\n"
        f"    Commit: {entity['commit_sha'][:8]} ({entity['change_type'] or 'unknown'})\n"
    )


async def get_entity_evolution(
    db,
    repo_name: str,
    entity_name: str,
    entity_type: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """Get all versions of an entity across commits."""
    query = """
        SELECT 
            e.name,
            e.entity_type,
            e.file_path,
            e.line_start,
            e.line_end,
            e.commit_sha,
            e.parent_commit_sha,
            e.branch_name,
            e.change_type,
            e.created_at,
            e.source_code
        FROM archon_code_entities e
        JOIN archon_code_repos r ON e.repo_id = r.id
        WHERE r.name = $1
          AND e.name = $2
    """

    params = [repo_name, entity_name]

    if entity_type:
        query += " AND e.entity_type = $3"
        params.append(entity_type)

    query += " ORDER BY e.created_at DESC LIMIT $" + str(len(params) + 1)
    params.append(limit)

    return await db.fetch(query, *params)


async def compare_branches(
    db,
    repo_name: str,
    branch1: str,
    branch2: str,
) -> dict[str, Any]:
    """Compare entities between two branches."""
    # Get entities unique to branch1
    branch1_only = await db.fetch(
        """
        SELECT DISTINCT e.name, e.entity_type, e.file_path
        FROM archon_code_entities e
        JOIN archon_code_repos r ON e.repo_id = r.id
        WHERE r.name = $1
          AND e.branch_name = $2
          AND e.entity_identity NOT IN (
              SELECT entity_identity 
              FROM archon_code_entities e2
              JOIN archon_code_repos r2 ON e2.repo_id = r2.id
              WHERE r2.name = $1 AND e2.branch_name = $3
          )
        ORDER BY e.file_path, e.name
        """,
        repo_name,
        branch1,
        branch2,
    )

    # Get entities unique to branch2
    branch2_only = await db.fetch(
        """
        SELECT DISTINCT e.name, e.entity_type, e.file_path
        FROM archon_code_entities e
        JOIN archon_code_repos r ON e.repo_id = r.id
        WHERE r.name = $1
          AND e.branch_name = $2
          AND e.entity_identity NOT IN (
              SELECT entity_identity 
              FROM archon_code_entities e2
              JOIN archon_code_repos r2 ON e2.repo_id = r2.id
              WHERE r2.name = $1 AND e2.branch_name = $3
          )
        ORDER BY e.file_path, e.name
        """,
        repo_name,
        branch2,
        branch1,
    )

    # Get modified entities (same identity, different commit)
    modified = await db.fetch(
        """
        SELECT 
            e.name,
            e.entity_type,
            e.file_path,
            e.branch_name as branch,
            e.commit_sha,
            e.change_type
        FROM archon_code_entities e
        JOIN archon_code_repos r ON e.repo_id = r.id
        WHERE r.name = $1
          AND e.entity_identity IN (
              SELECT entity_identity
              FROM archon_code_entities
              WHERE repo_id = e.repo_id
              GROUP BY entity_identity
              HAVING COUNT(DISTINCT branch_name) > 1
          )
          AND e.branch_name IN ($2, $3)
        ORDER BY e.entity_identity, e.branch_name, e.commit_sha DESC
        """,
        repo_name,
        branch1,
        branch2,
    )

    return {
        f"only_in_{branch1}": branch1_only,
        f"only_in_{branch2}": branch2_only,
        "modified_in_both": modified,
    }


async def get_commits_with_changes(
    db,
    repo_name: str,
    limit: int = 20,
) -> list[dict]:
    """Get commits with summary of changes."""
    return await db.fetch(
        """
        SELECT 
            e.commit_sha,
            e.branch_name,
            COUNT(*) as entity_count,
            COUNT(DISTINCT e.file_path) as files_changed,
            COUNT(*) FILTER (WHERE e.change_type = 'added') as added,
            COUNT(*) FILTER (WHERE e.change_type = 'modified') as modified,
            COUNT(*) FILTER (WHERE e.change_type = 'deleted') as deleted
        FROM archon_code_entities e
        JOIN archon_code_repos r ON e.repo_id = r.id
        WHERE r.name = $1
        GROUP BY e.commit_sha, e.branch_name
        ORDER BY MAX(e.created_at) DESC
        LIMIT $2
        """,
        repo_name,
        limit,
    )


async def find_when_entity_added(
    db,
    repo_name: str,
    entity_name: str,
) -> dict | None:
    """Find when an entity was first added."""
    result = await db.fetchrow(
        """
        SELECT 
            e.name,
            e.entity_type,
            e.file_path,
            e.commit_sha,
            e.branch_name,
            MIN(e.created_at) as first_seen
        FROM archon_code_entities e
        JOIN archon_code_repos r ON e.repo_id = r.id
        WHERE r.name = $1
          AND e.name = $2
        GROUP BY e.name, e.entity_type, e.file_path, e.commit_sha, e.branch_name
        ORDER BY first_seen ASC
        LIMIT 1
        """,
        repo_name,
        entity_name,
    )

    return result


async def get_entity_diff(
    db,
    repo_name: str,
    entity_name: str,
    commit1: str,
    commit2: str,
) -> dict | None:
    """Get diff of entity between two commits."""
    entity1 = await db.fetchrow(
        """
        SELECT source_code, commit_sha
        FROM archon_code_entities e
        JOIN archon_code_repos r ON e.repo_id = r.id
        WHERE r.name = $1
          AND e.name = $2
          AND e.commit_sha = $3
        ORDER BY created_at DESC
        LIMIT 1
        """,
        repo_name,
        entity_name,
        commit1,
    )

    entity2 = await db.fetchrow(
        """
        SELECT source_code, commit_sha
        FROM archon_code_entities e
        JOIN archon_code_repos r ON e.repo_id = r.id
        WHERE r.name = $1
          AND e.name = $2
          AND e.commit_sha = $3
        ORDER BY created_at DESC
        LIMIT 1
        """,
        repo_name,
        entity_name,
        commit2,
    )

    if not entity1 or not entity2:
        return None

    return {
        "commit1": entity1["commit_sha"][:8],
        "commit2": entity2["commit_sha"][:8],
        "source1": entity1["source_code"],
        "source2": entity2["source_code"],
    }


async def main():
    parser = argparse.ArgumentParser(description="Knowledge Graph Query Tools")
    parser.add_argument(
        "--repo",
        required=True,
        choices=["archon", "syllablaze", "octofriend", "Omnibus"],
        help="Repository to query",
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # Evolution command
    evo_parser = subparsers.add_parser(
        "evolution", help="Show entity evolution across commits"
    )
    evo_parser.add_argument("--entity", required=True, help="Entity name")
    evo_parser.add_argument("--type", help="Entity type filter")
    evo_parser.add_argument("--limit", type=int, default=10, help="Max versions")

    # Compare branches command
    branch_parser = subparsers.add_parser(
        "compare-branches", help="Compare two branches"
    )
    branch_parser.add_argument("branch1", help="First branch")
    branch_parser.add_argument("branch2", help="Second branch")

    # Commits command
    commits_parser = subparsers.add_parser("commits", help="List commits with changes")
    commits_parser.add_argument("--limit", type=int, default=20)

    # When added command
    when_parser = subparsers.add_parser("when-added", help="Find when entity was added")
    when_parser.add_argument("--entity", required=True, help="Entity name")

    # Diff command
    diff_parser = subparsers.add_parser("diff", help="Show diff between commits")
    diff_parser.add_argument("--entity", required=True, help="Entity name")
    diff_parser.add_argument("--commit1", required=True, help="First commit")
    diff_parser.add_argument("--commit2", required=True, help="Second commit")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Initialize database
    await initialize_database()
    db = get_database_connector()

    if args.command == "evolution":
        print(f"\n📊 Entity Evolution: {args.entity}")
        print("=" * 60)

        versions = await get_entity_evolution(
            db, args.repo, args.entity, args.type, args.limit
        )

        if not versions:
            print(f"❌ Entity '{args.entity}' not found")
            return

        print(f"Found {len(versions)} versions:\n")
        for v in versions:
            print(f"Commit: {v['commit_sha'][:8]}")
            print(f"  Branch: {v['branch_name']}")
            print(f"  Type: {v['entity_type']}")
            print(f"  File: {v['file_path']}")
            print(f"  Lines: {v['line_start']}-{v['line_end']}")
            print(f"  Change: {v['change_type'] or 'unknown'}")
            print()

    elif args.command == "compare-branches":
        print(f"\n🔀 Branch Comparison: {args.branch1} vs {args.branch2}")
        print("=" * 60)

        result = await compare_branches(db, args.repo, args.branch1, args.branch2)

        only_1 = result[f"only_in_{args.branch1}"]
        only_2 = result[f"only_in_{args.branch2}"]
        modified = result["modified_in_both"]

        print(f"\nOnly in {args.branch1}: {len(only_1)} entities")
        for e in only_1[:5]:
            print(f"  - {e['name']} ({e['entity_type']}) in {e['file_path']}")
        if len(only_1) > 5:
            print(f"  ... and {len(only_1) - 5} more")

        print(f"\nOnly in {args.branch2}: {len(only_2)} entities")
        for e in only_2[:5]:
            print(f"  - {e['name']} ({e['entity_type']}) in {e['file_path']}")
        if len(only_2) > 5:
            print(f"  ... and {len(only_2) - 5} more")

        print(f"\nModified in both: {len(modified)} versions")

    elif args.command == "commits":
        print(f"\n📜 Commits with Changes: {args.repo}")
        print("=" * 60)

        commits = await get_commits_with_changes(db, args.repo, args.limit)

        print(
            f"\n{'Commit':<12} {'Branch':<30} {'Entities':>10} {'Files':>8} {'+':>5} {'~':>5} {'-':>5}"
        )
        print("-" * 75)

        for c in commits:
            print(
                f"{c['commit_sha'][:8]:<12} "
                f"{c['branch_name'][:28]:<30} "
                f"{c['entity_count']:>10} "
                f"{c['files_changed']:>8} "
                f"{c['added'] or 0:>5} "
                f"{c['modified'] or 0:>5} "
                f"{c['deleted'] or 0:>5}"
            )

    elif args.command == "when-added":
        print(f"\n🔍 When was '{args.entity}' added?")
        print("=" * 60)

        result = await find_when_entity_added(db, args.repo, args.entity)

        if not result:
            print(f"❌ Entity '{args.entity}' not found")
            return

        print(f"\n✅ First seen:")
        print(f"  Name: {result['name']}")
        print(f"  Type: {result['entity_type']}")
        print(f"  File: {result['file_path']}")
        print(f"  Commit: {result['commit_sha'][:8]}")
        print(f"  Branch: {result['branch_name']}")
        print(f"  Date: {result['first_seen']}")

    elif args.command == "diff":
        print(f"\n📝 Diff: {args.entity}")
        print(f"  {args.commit1} → {args.commit2}")
        print("=" * 60)

        result = await get_entity_diff(
            db, args.repo, args.entity, args.commit1, args.commit2
        )

        if not result:
            print("❌ Could not find entity in one or both commits")
            return

        print(f"\n--- {result['commit1']}")
        print(result["source1"][:500] if result["source1"] else "(not found)")
        print(f"\n+++ {result['commit2']}")
        print(result["source2"][:500] if result["source2"] else "(not found)")


if __name__ == "__main__":
    asyncio.run(main())
