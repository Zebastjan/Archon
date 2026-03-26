"""Tests for FileWatcherService (ADR-016)."""

import pytest
import tempfile
import os
from pathlib import Path

from src.server.services.file_watcher_service import (
    FileWatcherService,
    WatcherConfig,
    IndexStatus,
    _compute_content_hash,
    _should_watch_file,
    _chunk_content,
    reindex_single_file,
)


class TestComputeContentHash:
    """Test content hash computation."""

    def test_basic_hash(self):
        """Test basic hash computation."""
        content = b"hello world"
        hash1 = _compute_content_hash(content)
        hash2 = _compute_content_hash(content)
        assert hash1 == hash2
        assert len(hash1) == 64

    def test_different_content_different_hash(self):
        """Different content produces different hash."""
        hash1 = _compute_content_hash(b"hello")
        hash2 = _compute_content_hash(b"world")
        assert hash1 != hash2

    def test_empty_content(self):
        """Empty content has a hash."""
        hash1 = _compute_content_hash(b"")
        assert hash1


class TestShouldWatchFile:
    """Test file watch filtering."""

    def test_python_files_watched(self):
        """Python files should be watched."""
        config = WatcherConfig()
        assert _should_watch_file("src/app.py", config)

    def test_markdown_files_watched(self):
        """Markdown files should be watched."""
        config = WatcherConfig()
        assert _should_watch_file("docs/README.md", config)

    def test_javascript_files_not_watched(self):
        """JavaScript files not in default extensions."""
        config = WatcherConfig()
        assert not _should_watch_file("src/app.js", config)

    def test_git_files_ignored(self):
        """Files in .git/ are ignored."""
        config = WatcherConfig()
        assert not _should_watch_file(".git/objects/hash", config)

    def test_pycache_ignored(self):
        """__pycache__ files are ignored."""
        config = WatcherConfig()
        assert not _should_watch_file("src/__pycache__/app.pyc", config)


class TestChunkContent:
    """Test content chunking."""

    def test_short_content_no_split(self):
        """Short content returns single chunk."""
        content = "Hello world"
        chunks = _chunk_content(content)
        assert len(chunks) == 1
        assert chunks[0] == content

    def test_empty_content(self):
        """Empty content returns empty list."""
        chunks = _chunk_content("")
        assert chunks == []

    def test_large_content_splits(self):
        """Large content is split into chunks."""
        content = "word " * 5000
        chunks = _chunk_content(content, chunk_size=100)
        assert len(chunks) > 1

    def test_paragraph_boundary_split(self):
        """Content can split at paragraph boundaries."""
        content = "Para1.\n\n" + "x" * 200 + "\n\nPara2."
        chunks = _chunk_content(content, chunk_size=100)
        assert len(chunks) > 1


class TestFileWatcherService:
    """Test FileWatcherService."""

    def test_default_config(self):
        """Default configuration is applied."""
        service = FileWatcherService()
        assert service.config.enabled
        assert service.config.debounce_ms == 500

    def test_custom_config(self):
        """Custom configuration is respected."""
        config = WatcherConfig(enabled=False, debounce_ms=1000)
        service = FileWatcherService(config)
        assert not service.config.enabled
        assert service.config.debounce_ms == 1000

    @pytest.mark.asyncio
    async def test_on_file_changed_skips_unwatched(self):
        """Unwatched files are skipped."""
        service = FileWatcherService()
        result = await service.on_file_changed("test.js", "repo-id", "/tmp/repo")
        assert result.status == IndexStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_reindex_all_modified_empty_dir(self):
        """Empty directory returns empty results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = FileWatcherService()
            results = await service.reindex_all_modified("repo-id", tmpdir)
            assert results == []
