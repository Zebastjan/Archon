"""Tests for Working Tree Search Service."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from src.server.services.search.working_tree_search_service import (
    search_working_tree_chunks,
    search_all_chunks,
    get_working_tree_stats,
)


class TestSearchWorkingTreeChunks:
    """Test working tree chunk search."""

    @pytest.mark.asyncio
    async def test_search_returns_empty_on_embedding_failure(self):
        """Search returns empty list when embedding fails."""
        with patch(
            "src.server.services.search.working_tree_search_service.get_unified_embedding_service"
        ) as mock_service:
            mock_service.return_value.generate = AsyncMock(side_effect=Exception("Embedding failed"))

            results = await search_working_tree_chunks(
                query="test query",
                repo_id="test-repo-id",
            )

            assert results == []

    @pytest.mark.asyncio
    async def test_search_with_valid_embedding(self):
        """Search with valid embedding returns results."""
        with (
            patch(
                "src.server.services.search.working_tree_search_service.get_unified_embedding_service"
            ) as mock_embedding,
            patch("src.server.services.search.working_tree_search_service.get_database_connector") as mock_db,
        ):
            # Mock embedding service
            mock_embedding.return_value.generate = AsyncMock(return_value=[0.1] * 1024)

            # Mock database
            mock_result = MagicMock()
            mock_result.__getitem__ = lambda self, key: {
                "id": "chunk-1",
                "file_path": "src/test.py",
                "chunk_index": 0,
                "content": "test content",
                "token_count": 10,
                "similarity": 0.85,
            }[key]

            mock_db.return_value.fetch = AsyncMock(return_value=[mock_result])

            results = await search_working_tree_chunks(
                query="test query",
                repo_id="test-repo-id",
            )

            assert len(results) == 1
            assert results[0]["file_path"] == "src/test.py"
            assert results[0]["source"] == "working_tree"


class TestSearchAllChunks:
    """Test search across all chunk sources."""

    @pytest.mark.asyncio
    async def test_search_returns_empty_on_failure(self):
        """Search returns empty list when it fails."""
        with patch(
            "src.server.services.search.working_tree_search_service.get_unified_embedding_service"
        ) as mock_service:
            mock_service.return_value.generate = AsyncMock(side_effect=Exception("Failed"))

            results = await search_all_chunks(
                query="test query",
                repo_id="test-repo-id",
            )

            assert results == []

    @pytest.mark.asyncio
    async def test_search_empty_when_no_sources(self):
        """Search returns empty when both sources disabled."""
        results = await search_all_chunks(
            query="test",
            repo_id="test-repo-id",
            include_working_tree=False,
            include_committed=False,
        )

        assert results == []


class TestGetWorkingTreeStats:
    """Test working tree statistics."""

    @pytest.mark.asyncio
    async def test_stats_returns_success(self):
        """Stats returns success with valid data."""
        with patch("src.server.services.search.working_tree_search_service.get_database_connector") as mock_db:
            # Mock chunk counts
            mock_chunk_counts = [
                {"source": "working_tree", "count": 10},
                {"source": "committed", "count": 50},
            ]
            mock_file_counts = [
                {"file_path": "src/test.py", "chunk_count": 5},
            ]

            mock_db.return_value.fetch = AsyncMock(side_effect=[mock_chunk_counts, mock_file_counts])
            mock_db.return_value.fetchval = AsyncMock(return_value=8)

            stats = await get_working_tree_stats("test-repo-id")

            assert stats["success"] is True
            assert stats["chunks_by_source"]["working_tree"] == 10
            assert stats["working_tree_embeddings"] == 8

    @pytest.mark.asyncio
    async def test_stats_returns_error_on_failure(self):
        """Stats returns error when database fails."""
        with patch("src.server.services.search.working_tree_search_service.get_database_connector") as mock_db:
            mock_db.return_value.fetch = AsyncMock(side_effect=Exception("DB error"))

            stats = await get_working_tree_stats("test-repo-id")

            assert stats["success"] is False
            assert "error" in stats
