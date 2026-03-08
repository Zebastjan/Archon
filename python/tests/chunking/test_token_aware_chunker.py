"""Tests for TokenAwareChunker."""


from src.server.services.chunking.chunkers.token_aware import TokenAwareChunker, estimate_tokens


class TestEstimateTokens:
    """Test token estimation."""

    def test_basic_estimation(self):
        """Token estimate is roughly 1/4 of character count."""
        text = "hello world"
        assert estimate_tokens(text) == 2

    def test_longer_text(self):
        """Longer text gets proportionally higher estimate."""
        text = "a" * 400
        assert estimate_tokens(text) == 100


class TestTokenAwareChunker:
    """Test TokenAwareChunker."""

    def test_empty_text_returns_empty_list(self):
        """Empty text returns empty list."""
        chunker = TokenAwareChunker()
        results = chunker.chunk("")
        assert results == []

    def test_respects_target_tokens(self):
        """Chunker respects target_tokens option."""
        chunker = TokenAwareChunker(target_tokens=50)
        text = "word " * 100
        results = chunker.chunk(text)
        for r in results:
            if r.token_estimate:
                assert r.token_estimate <= 60

    def test_token_estimate_in_results(self):
        """Token estimate is included in results."""
        chunker = TokenAwareChunker(target_tokens=50)
        results = chunker.chunk("Some text here")
        assert results[0].token_estimate is not None
        assert results[0].token_estimate > 0

    def test_metadata_includes_chunker_name(self):
        """Metadata includes chunker type."""
        chunker = TokenAwareChunker()
        results = chunker.chunk("Test")
        assert results[0].metadata["chunker"] == "token_aware"

    def test_metadata_includes_target_tokens(self):
        """Metadata includes target token count."""
        chunker = TokenAwareChunker(target_tokens=256)
        results = chunker.chunk("Test content")
        assert results[0].metadata["target_tokens"] == 256

    def test_overlap_reduces_duplication(self):
        """Overlap option causes some content duplication."""
        chunker_no_overlap = TokenAwareChunker(target_tokens=50, overlap_tokens=0)
        chunker_with_overlap = TokenAwareChunker(target_tokens=50, overlap_tokens=20)

        text = "word " * 80

        results_no_overlap = chunker_no_overlap.chunk(text)
        results_with_overlap = chunker_with_overlap.chunk(text)

        assert len(results_with_overlap) > len(results_no_overlap)

    def test_async_returns_same_as_sync(self):
        """Async version returns same results as sync."""
        import asyncio

        chunker = TokenAwareChunker(target_tokens=50)
        text = "word " * 50

        sync_results = chunker.chunk(text)

        async def get_async():
            return await chunker.chunk_async(text)

        async_results = asyncio.run(get_async())

        assert len(sync_results) == len(async_results)

    def test_merges_small_chunks(self):
        """Very small chunks are merged."""
        chunker = TokenAwareChunker(target_tokens=100)
        text = "a\n\nb\n\nc"
        results = chunker.chunk(text)
        assert len(results) == 1
