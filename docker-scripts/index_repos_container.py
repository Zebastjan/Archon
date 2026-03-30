#!/usr/bin/env python3
"""
Index all 4 repositories from inside the container.
"""

import asyncio
import uuid
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

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

import sys

sys.path.insert(0, "/app/src")

from src.server.services.code_entity_service import CodeEntityService
from src.server.services.database.db_connector import (
    get_database_connector,
    initialize_database,
)
from src.server.services.languages import get_language_for_file


def is_supported_file(path):
    if any(part.startswith(".") or part in SKIP_PATTERNS for part in path.parts):
        return False
    return get_language_for_file(str(path)) is not None


def discover_files(repo_path):
    files = []
    extensions = [".py", ".ts", ".tsx", ".js", ".jsx", ".nim", ".rs", ".go"]
    for ext in extensions:
        for file_path in repo_path.rglob(f"*{ext}"):
            if is_supported_file(file_path):
                files.append(str(file_path.relative_to(repo_path)))
    return files


class SimpleFileProvider:
    def __init__(self, repo_path):
        self.repo_path = repo_path

    async def get_content(self, repo_id, commit_sha, file_path):
        full_path = self.repo_path / file_path
        try:
            return full_path.read_text(encoding="utf-8", errors="ignore")
        except (IOError, OSError):
            return ""


async def create_repo(db, name, local_path):
    repo_id = str(uuid.uuid4())
    await db.execute(
        """
        INSERT INTO archon_code_repos (id, name, local_path, created_at, updated_at)
        VALUES ($1, $2, $3, NOW(), NOW())
    """,
        repo_id,
        name,
        local_path,
    )
    return repo_id


async def index_repo(name, local_path):
    logger.info(f"\n{'=' * 60}")
    logger.info(f"INDEXING: {name}")
    logger.info(f"Path: {local_path}")
    logger.info(f"{'=' * 60}")

    path = Path(local_path)
    if not path.exists():
        logger.warning(f"  Path does not exist: {local_path}")
        return None

    files = discover_files(path)
    logger.info(f"  Found {len(files)} source files")

    if not files:
        logger.warning(f"  No files found")
        return None

    by_ext = {}
    for f in files:
        ext = Path(f).suffix or "no ext"
        by_ext[ext] = by_ext.get(ext, 0) + 1
    logger.info("  Files by type:")
    for ext, count in sorted(by_ext.items(), key=lambda x: -x[1]):
        logger.info(f"    {ext}: {count}")

    db = get_database_connector()
    repo_id = await create_repo(db, name, local_path)
    logger.info(f"  Created repo: {name} ({repo_id})")

    service = CodeEntityService()
    file_provider = SimpleFileProvider(path)

    logger.info(f"  Extracting entities...")
    results = await service.extract_and_store_entities(
        repo_id=repo_id,
        commit_sha="HEAD",
        file_paths=files,
        file_content_getter=file_provider.get_content,
    )

    logger.info(f"  ✓ Processed: {results.get('processed', 0)} files")
    logger.info(f"  ✓ Entities: {results.get('entities_created', 0)}")
    logger.info(f"  ✓ Relationships: {results.get('relationships_created', 0)}")

    return results


async def main():
    await initialize_database()

    repos = [
        ("archon-python", "/app/src"),
        ("syllablaze", "/syllablaze"),
        ("octofriend", "/octofriend"),
        ("Omnibus", "/Omnibus"),
    ]

    for name, path in repos:
        try:
            await index_repo(name, path)
        except Exception as e:
            logger.warning(f"  ERROR: {e}")
            import traceback

            traceback.print_exc()

    logger.info("\n" + "=" * 60)
    logger.info("INDEXING COMPLETE")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
