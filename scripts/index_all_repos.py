#!/usr/bin/env python3
"""
Index all 4 repositories from scratch.

Repos:
1. archon-python - Main Python codebase
2. syllablaze - Python project
3. octofriend - TypeScript project
4. Omnibus - Mixed language project

Usage:
    cd /home/zebastjan/dev/archon
    python scripts/index_all_repos.py
"""

import asyncio
import logging
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

# Add python to path
sys.path.insert(0, str(Path(__file__).parent.parent / "python" / "src"))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from server.services.code_entity_service import CodeEntityService
from server.services.database.db_connector import (
    get_database_connector,
    initialize_database,
)
from server.services.languages import get_language_for_file

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
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

# Repo configurations - using container mount paths
REPOS = [
    {
        "name": "archon",
        "path": "/archon",
        "description": "Main Archon AI agent framework",
    },
    {
        "name": "syllablaze",
        "path": "/syllablaze",
        "description": "Syllablaze project",
    },
    {
        "name": "octofriend",
        "path": "/octofriend",
        "description": "OctoFriend MCP platform",
    },
    {
        "name": "Omnibus",
        "path": "/Omnibus",
        "description": "Omnibus project",
    },
]


def configure_git_safe_directories():
    """Add repos to git safe.directory to avoid 'dubious ownership' errors."""
    import subprocess

    for repo in REPOS:
        try:
            subprocess.run(
                ["git", "config", "--global", "--add", "safe.directory", repo["path"]],
                capture_output=True,
                timeout=5,
            )
        except (subprocess.CalledProcessError, OSError):
            pass


def is_supported_file(path: Path) -> bool:
    """Check if file should be processed."""
    if any(part.startswith(".") or part in SKIP_PATTERNS for part in path.parts):
        return False
    return get_language_for_file(str(path)) is not None


def discover_files(repo_path: Path) -> list[str]:
    """Discover all supported source files in repo."""
    files = []
    extensions = [".py", ".ts", ".tsx", ".js", ".jsx", ".nim", ".rs", ".go"]

    for ext in extensions:
        for file_path in repo_path.rglob(f"*{ext}"):
            if is_supported_file(file_path):
                files.append(str(file_path.relative_to(repo_path)))

    return files


class SimpleFileProvider:
    """Simple file content provider that reads from disk."""

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path

    async def get_content(self, repo_id: str, commit_sha: str, file_path: str) -> str:
        full_path = self.repo_path / file_path
        try:
            return full_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logger.warning(f"Failed to read {file_path}: {e}")
            return ""


async def create_repo(db, name: str, local_path: str, description: str) -> str:
    """Create a repo record and return its ID. Updates if exists."""
    import subprocess

    # Check if repo already exists
    existing = await db.fetchrow(
        "SELECT id FROM archon_code_repos WHERE local_path = $1",
        local_path,
    )

    if existing:
        repo_id = existing["id"]
        # Delete existing entities for this repo
        await db.execute(
            "DELETE FROM archon_code_entities WHERE repo_id = $1",
            repo_id,
        )
        logger.info(f"  Updated existing repo: {name} ({repo_id})")
        return repo_id

    repo_id = str(uuid.uuid4())

    # Get git info if available
    commit_sha = "unknown"
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=local_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            commit_sha = result.stdout.strip()[:8]
    except (subprocess.CalledProcessError, OSError):
        pass

    await db.execute(
        """
        INSERT INTO archon_code_repos (id, name, local_path, created_at, updated_at)
        VALUES ($1, $2, $3, NOW(), NOW())
    """,
        repo_id,
        name,
        local_path,
    )

    logger.info(f"  Created repo: {name} ({repo_id})")
    return repo_id


async def index_repo(repo_config: dict) -> dict:
    """Index a single repository with proper git tracking."""
    name = repo_config["name"]
    local_path = repo_config["path"]
    desc = repo_config.get("description", "")

    logger.info(f"\n{'=' * 60}")
    logger.info(f"INDEXING: {name}")
    logger.info(f"Path: {local_path}")
    logger.info(f"{'=' * 60}")

    path = Path(local_path)
    if not path.exists():
        logger.warning(f"  ⚠️  Path does not exist: {local_path}")
        return {"status": "skipped", "reason": "path_not_found", "name": name}

    # Discover files
    files = discover_files(path)
    logger.info(f"  Found {len(files)} source files")

    if not files:
        return {"status": "skipped", "reason": "no_files", "name": name}

    # File breakdown
    by_ext = {}
    for f in files:
        ext = Path(f).suffix or "no ext"
        by_ext[ext] = by_ext.get(ext, 0) + 1

    logger.info("  Files by type:")
    for ext, count in sorted(by_ext.items(), key=lambda x: -x[1]):
        logger.info(f"    {ext}: {count}")

    # Get git info
    import subprocess

    commit_sha = "unknown"
    branch_name = "unknown"
    parent_commit_sha = None

    try:
        # Get current commit SHA
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=local_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            commit_sha = result.stdout.strip()

        # Get current branch
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=local_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            branch_name = result.stdout.strip() or "detached"

        # Get parent commit SHA
        result = subprocess.run(
            ["git", "rev-parse", "HEAD~1"],
            cwd=local_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            parent_commit_sha = result.stdout.strip()

        logger.info(
            f"  Git: {branch_name}@{commit_sha[:8]} (parent: {parent_commit_sha[:8] if parent_commit_sha else 'none'})"
        )
    except Exception as e:
        logger.warning(f"  Could not get git info: {e}")

    # Initialize services
    await initialize_database()
    db = get_database_connector()

    # Create repo in database
    repo_id = await create_repo(db, name, local_path, desc)

    # Update repo with git info
    await db.execute(
        """
        UPDATE archon_code_repos 
        SET last_commit_sha = $1, branch = $2
        WHERE id = $3
        """,
        commit_sha[:8] if commit_sha != "unknown" else commit_sha,
        branch_name,
        repo_id,
    )

    # Extract entities
    service = CodeEntityService()
    file_provider = SimpleFileProvider(path)

    logger.info(f"  Extracting entities...")
    results = await service.extract_and_store_entities(
        repo_id=repo_id,
        commit_sha=commit_sha,
        file_paths=files,
        file_content_getter=file_provider.get_content,
        branch_name=branch_name,
        parent_commit_sha=parent_commit_sha,
    )

    logger.info(f"  ✓ Extracted:")
    logger.info(f"    Files processed: {results.get('processed', 0)}")
    logger.info(f"    Entities created: {results.get('entities_created', 0)}")
    logger.info(f"    Relationships: {results.get('relationships_created', 0)}")

    if results.get("errors"):
        logger.info(f"    Errors: {len(results.get('errors', []))}")

    return {
        "status": "success",
        "repo_id": repo_id,
        "name": name,
        "files": results.get("processed", 0),
        "entities": results.get("entities_created", 0),
        "relationships": results.get("relationships_created", 0),
    }


async def main():
    # Configure git safe directories first
    configure_git_safe_directories()

    logger.info("=" * 60)
    logger.info("ARCHON REPOSITORY INDEXER")
    logger.info(f"Started: {datetime.now().isoformat()}")
    logger.info("=" * 60)

    results = []
    for repo in REPOS:
        result = await index_repo(repo)
        results.append(result)
        # Brief pause between repos
        await asyncio.sleep(1)

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("INDEXING COMPLETE")
    logger.info("=" * 60)

    total_entities = 0
    total_files = 0

    for r in results:
        if r.get("status") == "success":
            logger.info(f"✓ {r['name']}: {r['entities']} entities, {r['files']} files")
            total_entities += r.get("entities", 0)
            total_files += r.get("files", 0)
        else:
            logger.info(f"✗ {r['name']}: {r['status']} - {r.get('reason', '')}")

    logger.info(f"\nTotal: {total_entities} entities from {total_files} files")
    logger.info("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Error: {e}")
        sys.exit(1)
