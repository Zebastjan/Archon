"""File Watcher Service for incremental re-indexing (ADR-016).

Watches working tree for file changes and triggers lightweight re-indexing
of individual files when they are modified, without requiring a commit.
"""

import hashlib
import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from src.server.config.logfire_config import get_logger
from src.server.services.database import get_database_connector

logger = get_logger(__name__)

WATCHED_EXTENSIONS = frozenset(
    {
        ".py",
        ".ts",
        ".go",
        ".rs",  # code
        ".md",
        ".rst",
        ".org",
        ".norg",  # docs
        ".sql",
        ".yaml",
        ".toml",
        ".json",  # config
    }
)

IGNORE_PATTERNS = frozenset({".git/", "__pycache__/", "node_modules/", ".archon/", "dist/", "build/", "*.pyc"})


class IndexStatus(str, Enum):
    REINDEXED = "reindexed"
    UNCHANGED = "unchanged"
    SKIPPED = "skipped"


@dataclass
class IndexResult:
    """Result of an indexing operation."""

    status: IndexStatus
    filepath: str
    chunks_updated: int = 0
    embedding_ms: int = 0
    error: str | None = None


@dataclass
class WatcherConfig:
    """Configuration for file watcher."""

    enabled: bool = True
    debounce_ms: int = 500
    max_file_size_kb: int = 512
    watch_extensions: set[str] = field(default_factory=lambda: WATCHED_EXTENSIONS)


def _compute_content_hash(content: bytes) -> str:
    """Compute SHA256 hash of content."""
    return hashlib.sha256(content).hexdigest()


def _should_watch_file(filepath: str, config: WatcherConfig) -> bool:
    """Check if file should be watched based on extension and patterns."""
    path = Path(filepath)

    for ignore in IGNORE_PATTERNS:
        if ignore in str(filepath):
            return False

    if config.watch_extensions:
        return path.suffix in config.watch_extensions

    return path.suffix in WATCHED_EXTENSIONS


async def _get_last_indexed_hash(repo_id: str, file_path: str) -> str | None:
    """Get the last indexed hash for a file from the database."""
    try:
        db = get_database_connector()
        result = await db.fetchrow(
            """
            SELECT content_hash
            FROM archon_document_blobs
            WHERE source_id = $1 AND blob_uri LIKE $2
            ORDER BY created_at DESC LIMIT 1
            """,
            repo_id,
            f"%{file_path}",
        )
        if result:
            return result["content_hash"]
        return None
    except Exception:
        return None


async def _update_working_tree_chunks(
    repo_id: str,
    file_path: str,
    chunks: list[str],
    content_hash: str,
    commit_sha: str | None = None,
) -> int:
    """Update working_tree chunks for a file.

    Args:
        repo_id: Repository UUID
        file_path: Relative path to the file
        chunks: List of chunk content strings
        content_hash: SHA256 hash of the file content
        commit_sha: Commit SHA (None for working_tree source)

    Returns:
        Number of chunks updated
    """
    try:
        db = get_database_connector()

        # Delete existing working_tree chunks for this file
        await db.execute(
            """
            DELETE FROM archon_chunks
            WHERE repo_id = $1 AND file_path = $2 AND source = 'working_tree'
            """,
            repo_id,
            file_path,
        )

        # Insert new working_tree chunks
        count = 0
        for i, chunk_content in enumerate(chunks):
            token_count = len(chunk_content.split()) * 4 // 3
            await db.execute(
                """
                INSERT INTO archon_chunks
                (repo_id, file_path, chunk_index, content, token_count, source, commit_sha)
                VALUES ($1, $2, $3, $4, $5, 'working_tree', NULL)
                """,
                repo_id,
                file_path,
                i,
                chunk_content,
                token_count,
            )
            count += 1

        return count

    except Exception as e:
        logger.error(f"Failed to update working_tree chunks: {e}")
        return 0


async def reindex_single_file(
    repo_id: str,
    filepath: str,
    repo_root: str,
    content: str | None = None,
) -> IndexResult:
    """Re-index a single file in the working tree.

    Args:
        repo_id: Repository UUID
        filepath: Path relative to repo root
        repo_root: Absolute path to repository root
        content: Optional content override (if not provided, reads from disk)

    Returns:
        IndexResult with status and details
    """
    try:
        full_path = Path(repo_root) / filepath

        if not full_path.exists():
            return IndexResult(
                status=IndexStatus.SKIPPED,
                filepath=filepath,
                error="File not found",
            )

        file_size = full_path.stat().st_size
        if file_size > 512 * 1024:  # 512KB
            return IndexResult(
                status=IndexStatus.SKIPPED,
                filepath=filepath,
                error="File too large",
            )

        if content is None:
            try:
                content = full_path.read_text(encoding="utf-8", errors="ignore")
            except Exception as e:
                return IndexResult(
                    status=IndexStatus.SKIPPED,
                    filepath=filepath,
                    error=f"Could not read file: {e}",
                )

        content_hash = _compute_content_hash(content.encode("utf-8"))

        last_hash = await _get_last_indexed_hash(repo_id, filepath)
        if last_hash == content_hash:
            return IndexResult(
                status=IndexStatus.UNCHANGED,
                filepath=filepath,
            )

        # Basic chunking for now
        chunks = _chunk_content(content)

        # Update working_tree chunks
        start_time = time.monotonic()
        count = await _update_working_tree_chunks(repo_id, filepath, chunks, content_hash)
        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        return IndexResult(
            status=IndexStatus.REINDEXED,
            filepath=filepath,
            chunks_updated=count,
            embedding_ms=elapsed_ms,
        )

    except Exception as e:
        logger.error(f"Reindex failed for {filepath}: {e}")
        return IndexResult(
            status=IndexStatus.SKIPPED,
            filepath=filepath,
            error=str(e),
        )


def _chunk_content(content: str, chunk_size: int = 5000) -> list[str]:
    """Chunk content into manageable pieces."""
    if len(content) <= chunk_size:
        return [content] if content.strip() else []

    chunks = []
    start = 0
    text_length = len(content)

    while start < text_length:
        end = start + chunk_size

        if end >= text_length:
            chunk = content[start:].strip()
            if chunk:
                chunks.append(chunk)
            break

        # Try to break at paragraph boundary
        chunk = content[start:end]
        if "\n\n" in chunk:
            last_break = chunk.rfind("\n\n")
            if last_break > chunk_size * 0.3:
                end = start + last_break

        # Try to break at sentence boundary
        elif ". " in chunk:
            last_period = chunk.rfind(". ")
            if last_period > chunk_size * 0.3:
                end = start + last_period + 1

        chunk = content[start:end].strip()
        if chunk:
            chunks.append(chunk)

        start = end

    return chunks


class FileWatcherService:
    """Watches working tree for file changes and triggers incremental re-indexing.

    Runs as a background async task within the MCP server process.
    """

    def __init__(self, config: WatcherConfig | None = None):
        self.config = config or WatcherConfig()
        self._watching = False
        self._debounce_timers: dict[str, asyncio.TimerHandle] = {}
        self._last_indexed: dict[str, str] = {}
        self._repo_roots: dict[str, str] = {}

    async def on_file_changed(
        self,
        filepath: str,
        repo_id: str,
        repo_root: str,
    ) -> IndexResult:
        """Called when a watched file is saved.

        1. Check if file should be watched
        2. Compare content hash with last indexed hash
        3. If changed: re-chunk, update DB working_tree chunks
        4. If unchanged: no-op
        """
        if not _should_watch_file(filepath, self.config):
            return IndexResult(
                status=IndexStatus.SKIPPED,
                filepath=filepath,
                error="Not a watched file type",
            )

        return await reindex_single_file(repo_id, filepath, repo_root)

    async def reindex_all_modified(
        self,
        repo_id: str,
        repo_root: str,
        paths: list[str] | None = None,
    ) -> list[IndexResult]:
        """Re-index all modified files in the working tree.

        Args:
            repo_id: Repository UUID
            repo_root: Absolute path to repository root
            paths: Optional list of specific paths to check (None = all watched files)

        Returns:
            List of IndexResult for each processed file
        """
        results = []
        root = Path(repo_root)

        if paths is None:
            # Find all watched files
            paths = []
            for ext in self.config.watch_extensions:
                paths.extend(str(p.relative_to(root)) for p in root.rglob(f"*{ext}"))
                if len(paths) > 1000:
                    break

        for filepath in paths:
            result = await reindex_single_file(repo_id, filepath, repo_root)
            results.append(result)

        return results
