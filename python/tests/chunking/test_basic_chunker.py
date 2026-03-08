"""Tests for BasicChunker."""


from src.server.services.chunking.chunkers.basic import BasicChunker, _smart_chunk_text


class TestSmartChunkText:
    """Test the underlying smart_chunk_text function."""

    def test_empty_text_returns_empty_list(self):
        """Empty text returns empty list."""
        assert _smart_chunk_text("") == []
        assert _smart_chunk_text(None) == []  # type: ignore

    def test_short_text_returns_single_chunk(self):
        """Short text returns single chunk."""
        result = _smart_chunk_text("This is a short text.")
        assert len(result) == 1
        assert result[0] == "This is a short text."

    def test_preserves_code_blocks(self):
        """Code blocks are preserved as units."""
        text = "Start\n\n```python\ndef hello():\n    pass\n```\n\nEnd"
        chunks = _smart_chunk_text(text, chunk_size=100)
        code_chunk = [c for c in chunks if "def hello" in c]
        assert len(code_chunk) == 1

    def test_breaks_at_paragraphs(self):
        """Text breaks at paragraph boundaries when chunk size forces it."""
        text = "This is a long paragraph. " * 50 + "\n\n" + "Another paragraph. " * 50
        chunks = _smart_chunk_text(text, chunk_size=200)
        assert len(chunks) > 1

    def test_merges_small_chunks(self):
        """Small consecutive chunks are merged."""
        text = "A\n\nB\n\nC"
        chunks = _smart_chunk_text(text, chunk_size=100)
        assert len(chunks) == 1 or all(len(c) >= 200 for c in chunks)


class TestBasicChunker:
    """Test the BasicChunker class."""

    def test_creates_chunk_results(self):
        """BasicChunker returns ChunkResult objects."""
        chunker = BasicChunker()
        results = chunker.chunk("Test content")
        assert len(results) > 0
        assert results[0].content == "Test content"
        assert results[0].index == 0

    def test_chunk_size_option(self):
        """Chunker respects chunk_size option."""
        chunker = BasicChunker(chunk_size=100)
        results = chunker.chunk("A" * 500, chunk_size=100)
        assert len(results) > 1

    def test_metadata_includes_chunker_name(self):
        """ChunkResult metadata includes chunker type."""
        chunker = BasicChunker()
        results = chunker.chunk("Test")
        assert results[0].metadata["chunker"] == "basic"

    def test_async_returns_same_as_sync(self):
        """Async version returns same results as sync."""
        import asyncio

        chunker = BasicChunker()
        text = "Test content for async"

        sync_results = chunker.chunk(text)

        async def get_async():
            return await chunker.chunk_async(text)

        async_results = asyncio.run(get_async())

        assert len(sync_results) == len(async_results)
        for s, a in zip(sync_results, async_results, strict=False):
            assert s.content == a.content
            assert s.index == a.index
