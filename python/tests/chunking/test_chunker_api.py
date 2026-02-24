"""Tests for chunking module API."""

import pytest

from src.server.services.chunking.chunker_base import BaseChunker, ChunkResult
from src.server.services.chunking.exceptions import ChunkingError, ChunkingStrategyError
from src.server.services.chunking.factory import get_chunker


class TestChunkerFactory:
    """Test the chunker factory."""

    def test_get_basic_chunker(self):
        """Factory returns BasicChunker for 'basic' strategy."""
        chunker = get_chunker("basic")
        assert isinstance(chunker, BaseChunker)

    def test_get_token_aware_chunker(self):
        """Factory returns TokenAwareChunker for 'token_aware' strategy."""
        chunker = get_chunker("token_aware")
        assert isinstance(chunker, BaseChunker)

    def test_invalid_strategy_raises_error(self):
        """Invalid strategy raises ChunkingStrategyError."""
        with pytest.raises(ChunkingStrategyError):
            get_chunker("nonexistent_strategy")

    def test_factory_stores_options(self):
        """Factory passes options to chunker."""
        chunker = get_chunker("basic", chunk_size=1000)
        # Options should be available on the chunker
        assert hasattr(chunker, "options")
        assert chunker.options.get("chunk_size") == 1000


class TestChunkResult:
    """Test the ChunkResult dataclass."""

    def test_chunk_result_creation(self):
        """ChunkResult stores all fields correctly."""
        result = ChunkResult(
            content="test content",
            index=0,
            section_path="Intro > Getting Started",
            token_estimate=100,
            metadata={"source": "test"},
        )
        assert result.content == "test content"
        assert result.index == 0
        assert result.section_path == "Intro > Getting Started"
        assert result.token_estimate == 100
        assert result.metadata["source"] == "test"

    def test_chunk_result_defaults(self):
        """ChunkResult has sensible defaults."""
        result = ChunkResult(content="test", index=0)
        assert result.section_path is None
        assert result.token_estimate is None
        assert result.metadata is None


class TestBaseChunkerInterface:
    """Test the BaseChunker abstract interface."""

    def test_chunk_is_abstract(self):
        """chunk() must be implemented by subclasses."""
        with pytest.raises(TypeError):
            BaseChunker()

    def test_subclass_must_implement_chunk(self):
        """Subclass without chunk() raises error."""

        class IncompleteChunker(BaseChunker):
            pass

        with pytest.raises(TypeError):
            IncompleteChunker()

    def test_subclass_can_implement_chunk(self):
        """Subclass with chunk() can be instantiated."""

        class SimpleChunker(BaseChunker):
            def chunk(self, text: str, **options):
                return [ChunkResult(content=text[:100], index=0)]

            async def chunk_async(self, text: str, **options):
                return self.chunk(text, **options)

        chunker = SimpleChunker()
        results = chunker.chunk("hello world")
        assert len(results) == 1
        assert results[0].content == "hello world"


class TestChunkingError:
    """Test exception handling."""

    def test_chunking_error_to_dict(self):
        """ChunkingError serializes to dict."""
        error = ChunkingError("test error", text_preview="preview", chunk_index=5)
        error_dict = error.to_dict()
        assert error_dict["error_type"] == "ChunkingError"
        assert error_dict["message"] == "test error"
        assert error_dict["text_preview"] == "preview"
        assert error_dict["chunk_index"] == 5

    def test_chunking_error_preserves_metadata(self):
        """ChunkingError preserves metadata."""
        error = ChunkingError("test", chunk_index=0)
        error.metadata["custom_key"] = "custom_value"
        assert error.metadata["custom_key"] == "custom_value"
        assert error.to_dict()["metadata"]["custom_key"] == "custom_value"
