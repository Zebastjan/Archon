#!/usr/bin/env python3
"""
Multi-commit indexer for Archon Knowledge Graph.

Indexes multiple commits per repository to enable:
- Cross-commit queries ("how did this entity change?")
- Branch comparison
- Entity evolution tracking

Usage:
    cd /home/zebastjan/dev/archon
    python scripts/index_commits.py --repo archon --commits 10
    python scripts/index_commits.py --repo Omnibus --branch main --commits 5
"""

import argparse
import asyncio
import hashlib
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Add python to path
sys.path.insert(0, str(Path(__file__).parent.parent / "python" / "src"))

from dotenv import load_dotenv
from server.services.code_entity_service import CodeEntityService
from server.services.database.db_connector import (
    get_database_connector,
    initialize_database,
)
from server.services.languages import get_language_for_file

load_dotenv(Path(__file__).parent.parent / ".env")

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Skip patterns for file discovery
SKIP_PATTERNS = {
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "node_modules",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "dist",
    "build",
    ".egg-info",
    ".tox",
    ".coverage",
    "htmlcov",
    ".next",
    ".nuxt",
    ".svelte-kit",
    "target",
    ".cargo",
}


def get_commits(
    repo_path: str, branch: str | None = None, limit: int = 10
) -> list[dict]:
    """Get list of commits to index."""
    commits = []

    try:
        # Build git log command
        cmd = ["git", "log", f"--max-count={limit}", "--pretty=format:%H|%h|%s|%ci"]
        if branch:
            cmd.append(branch)

        result = subprocess.run(
            cmd,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            logger.error(f"Failed to get commits: {result.stderr}")
            return commits

        # Parse commits
        lines = result.stdout.strip().split("\n")
        parent_sha = None

        for i, line in enumerate(lines):
            parts = line.split("|", 3)
            if len(parts) < 4:
                continue

            full_sha, short_sha, message, timestamp = parts

            # Get parent SHA (next commit in list is the parent)
            if i < len(lines) - 1:
                parent_parts = lines[i + 1].split("|", 3)
                if len(parent_parts) > 0:
                    parent_sha = parent_parts[0]
            else:
                # Try to get parent from git
                parent_result = subprocess.run(
                    ["git", "rev-parse", f"{full_sha}~1"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                parent_sha = (
                    parent_result.stdout.strip()
                    if parent_result.returncode == 0
                    else None
                )

            commits.append(
                {
                    "full_sha": full_sha,
                    "short_sha": short_sha,
                    "message": message,
                    "timestamp": timestamp,
                    "parent_sha": parent_sha,
                }
            )

        return commits

    except Exception as e:
        logger.error(f"Error getting commits: {e}")
        return commits


def get_changed_files(
    repo_path: str, commit_sha: str, parent_sha: str | None = None
) -> list[dict]:
    """Get files changed in a commit with change type."""
    files = []

    try:
        # If no parent, treat all files as added
        if not parent_sha:
            result = subprocess.run(
                ["git", "ls-tree", "-r", "--name-only", commit_sha],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                for file in result.stdout.strip().split("\n"):
                    if is_supported_file(repo_path, file):
                        files.append(
                            {
                                "path": file,
                                "change_type": "added",
                            }
                        )
            return files

        # Get diff stats
        result = subprocess.run(
            [
                "git",
                "diff-tree",
                "--no-commit-id",
                "--name-status",
                "-r",
                parent_sha,
                commit_sha,
            ],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return files

        # Parse file changes
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue

            parts = line.split("\t")
            if len(parts) < 2:
                continue

            status = parts[0][0]  # A, M, D, R, etc.
            file_path = parts[1]

            if not is_supported_file(repo_path, file_path):
                continue

            change_type = {
                "A": "added",
                "M": "modified",
                "D": "deleted",
                "R": "renamed",
            }.get(status, "modified")

            files.append(
                {
                    "path": file_path,
                    "change_type": change_type,
                }
            )

        return files

    except Exception as e:
        logger.error(f"Error getting changed files: {e}")
        return files


def is_supported_file(repo_path: str, file_path: str) -> bool:
    """Check if file should be processed."""
    path = Path(file_path)

    # Skip patterns
    if any(part.startswith(".") or part in SKIP_PATTERNS for part in path.parts):
        return False

    # Check extension
    return get_language_for_file(file_path) is not None


async def get_file_content_at_commit(
    repo_path: str, commit_sha: str, file_path: str
) -> str:
    """Get file content at specific commit."""
    try:
        result = subprocess.run(
            ["git", "show", f"{commit_sha}:{file_path}"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            return result.stdout
        else:
            return ""
    except Exception as e:
        logger.warning(f"Failed to get content for {file_path}@{commit_sha[:8]}: {e}")
        return ""


async def index_commit(
    repo_name: str,
    repo_path: str,
    repo_id: str,
    commit: dict,
    branch: str,
    db,
) -> dict:
    """Index a single commit."""
    commit_sha = commit["full_sha"]
    parent_sha = commit["parent_sha"]

    logger.info(
        f"  Processing commit {commit['short_sha']}: {commit['message'][:50]}..."
    )

    # Get changed files
    changed_files = get_changed_files(repo_path, commit_sha, parent_sha)

    if not changed_files:
        logger.info(f"    No supported files changed")
        return {
            "status": "skipped",
            "reason": "no_files",
            "commit": commit["short_sha"],
        }

    logger.info(f"    {len(changed_files)} files changed")

    # Check for deleted files (need to mark entities as deleted)
    deleted_files = [f["path"] for f in changed_files if f["change_type"] == "deleted"]
    if deleted_files:
        # Mark entities as deleted in parent commit
        await mark_entities_deleted(db, repo_id, parent_sha, deleted_files)
        logger.info(f"    Marked {len(deleted_files)} files as deleted")

    # Process only added/modified files
    files_to_index = [f for f in changed_files if f["change_type"] != "deleted"]

    if not files_to_index:
        return {"status": "success", "entities": 0, "commit": commit["short_sha"]}

    # Extract and store entities
    service = CodeEntityService()

    total_entities = 0
    for file_info in files_to_index:
        file_path = file_info["path"]
        change_type = file_info["change_type"]

        content = await get_file_content_at_commit(repo_path, commit_sha, file_path)
        if not content:
            continue

        # Check language support
        lang_support = get_language_for_file(file_path)
        if not lang_support:
            continue

        # Extract entities
        try:
            entities, relationships = lang_support.extract_entities_and_relationships(
                content, file_path
            )
        except Exception as e:
            logger.warning(f"    Parse error in {file_path}: {e}")
            continue

        # Store entities with change_type
        for entity in entities:
            entity_identity = hashlib.md5(
                f"{repo_id}{file_path}{entity.name}{entity.entity_type}".encode()
            ).hexdigest()

            await store_entity_with_metadata(
                db=db,
                repo_id=repo_id,
                commit_sha=commit_sha,
                parent_sha=parent_sha,
                branch_name=branch,
                file_path=file_path,
                language=lang_support.language_id,
                entity=entity,
                entity_identity=entity_identity,
                change_type=change_type,
            )
            total_entities += 1

        # Store relationships
        for rel in relationships:
            await store_relationship(db, repo_id, commit_sha, rel)

    logger.info(f"    ✓ Indexed {total_entities} entities")

    return {
        "status": "success",
        "entities": total_entities,
        "commit": commit["short_sha"],
    }


async def store_entity_with_metadata(
    db,
    repo_id: str,
    commit_sha: str,
    parent_sha: str | None,
    branch_name: str,
    file_path: str,
    language: str,
    entity,
    entity_identity: str,
    change_type: str,
):
    """Store entity with full knowledge graph metadata."""
    query = """
        INSERT INTO archon_code_entities (
            repo_id, file_path, line_start, line_end, entity_type,
            name, signature, docstring, source_code, language, commit_sha,
            embedding_model, embedding_dimension, entity_identity,
            branch_name, parent_commit_sha, change_type
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
        ON CONFLICT (repo_id, file_path, name, entity_type, commit_sha) DO UPDATE SET
            line_start = EXCLUDED.line_start,
            line_end = EXCLUDED.line_end,
            source_code = EXCLUDED.source_code,
            docstring = EXCLUDED.docstring,
            change_type = EXCLUDED.change_type,
            updated_at = NOW()
        RETURNING id
    """

    try:
        await db.fetchrow(
            query,
            repo_id,
            file_path,
            entity.line_start,
            entity.line_end,
            entity.entity_type,
            entity.name,
            entity.signature,
            entity.docstring,
            entity.source_code,
            language,
            commit_sha,
            None,  # embedding_model
            None,  # embedding_dimension
            entity_identity,
            branch_name,
            parent_sha,
            change_type,
        )
    except Exception as e:
        logger.warning(f"Failed to store entity {entity.name}: {e}")


async def store_relationship(db, repo_id: str, commit_sha: str, relationship):
    """Store entity relationship."""
    # Implementation would store relationships
    # For now, skip to focus on entity tracking
    pass


async def mark_entities_deleted(
    db, repo_id: str, parent_commit_sha: str, file_paths: list[str]
):
    """Mark entities as deleted in a commit."""
    # Mark all entities in these files at parent commit as deleted
    for file_path in file_paths:
        await db.execute(
            """
            UPDATE archon_code_entities 
            SET change_type = 'deleted'
            WHERE repo_id = $1 
              AND file_path = $2 
              AND commit_sha = $3
              AND change_type IS DISTINCT FROM 'deleted'
            """,
            repo_id,
            file_path,
            parent_commit_sha,
        )


async def main():
    parser = argparse.ArgumentParser(
        description="Index multiple commits for knowledge graph"
    )
    parser.add_argument(
        "--repo",
        required=True,
        choices=["archon", "syllablaze", "octofriend", "Omnibus"],
        help="Repository to index",
    )
    parser.add_argument(
        "--commits",
        type=int,
        default=10,
        help="Number of commits to index (default: 10)",
    )
    parser.add_argument(
        "--branch",
        default=None,
        help="Branch to index (default: current branch)",
    )
    parser.add_argument(
        "--all-branches",
        action="store_true",
        help="Index commits from all branches",
    )

    args = parser.parse_args()

    # Configure git safe directories
    import subprocess

    for repo_path in ["/archon", "/syllablaze", "/octofriend", "/Omnibus"]:
        subprocess.run(
            ["git", "config", "--global", "--add", "safe.directory", repo_path],
            capture_output=True,
        )

    # Map repo names to paths
    REPO_PATHS = {
        "archon": "/archon",
        "syllablaze": "/syllablaze",
        "octofriend": "/octofriend",
        "Omnibus": "/Omnibus",
    }

    repo_path = REPO_PATHS[args.repo]

    logger.info("=" * 60)
    logger.info(f"MULTI-COMMIT INDEXER")
    logger.info(f"Repo: {args.repo}")
    logger.info(f"Commits: {args.commits}")
    logger.info(f"Branch: {args.branch or 'current'}")
    logger.info("=" * 60)

    # Initialize database
    await initialize_database()
    db = get_database_connector()

    # Get repo ID
    repo_result = await db.fetchrow(
        "SELECT id FROM archon_code_repos WHERE name = $1",
        args.repo,
    )

    if not repo_result:
        logger.error(f"Repository '{args.repo}' not found in database")
        logger.info("Run 'make index-repos' first")
        return

    repo_id = repo_result["id"]

    # Get commits
    if args.all_branches:
        # Get commits from all branches
        branches_result = subprocess.run(
            ["git", "branch", "-a", "--format=%(refname:short)"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        branches = [
            b.strip() for b in branches_result.stdout.strip().split("\n") if b.strip()
        ]

        all_commits = []
        for branch in branches:
            branch_commits = get_commits(repo_path, branch, args.commits)
            all_commits.extend(branch_commits)

        # Deduplicate by commit SHA
        seen = set()
        commits = []
        for c in all_commits:
            if c["full_sha"] not in seen:
                seen.add(c["full_sha"])
                commits.append(c)
    else:
        commits = get_commits(repo_path, args.branch, args.commits)

    if not commits:
        logger.error("No commits found")
        return

    logger.info(f"Found {len(commits)} commits to index")

    # Get current branch name
    branch_result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    current_branch = branch_result.stdout.strip() or "unknown"

    # Index each commit
    results = []
    for commit in commits:
        result = await index_commit(
            args.repo,
            repo_path,
            repo_id,
            commit,
            current_branch,
            db,
        )
        results.append(result)
        await asyncio.sleep(0.1)  # Brief pause

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("INDEXING COMPLETE")
    logger.info("=" * 60)

    successful = [r for r in results if r.get("status") == "success"]
    skipped = [r for r in results if r.get("status") == "skipped"]

    total_entities = sum(r.get("entities", 0) for r in successful)

    logger.info(f"Commits indexed: {len(successful)}")
    logger.info(f"Commits skipped: {len(skipped)}")
    logger.info(f"Total entities: {total_entities}")
    logger.info("=" * 60)

    # Show commit summary
    for result in results[:5]:
        if result.get("status") == "success":
            logger.info(f"  ✓ {result['commit']}: {result['entities']} entities")


if __name__ == "__main__":
    asyncio.run(main())
