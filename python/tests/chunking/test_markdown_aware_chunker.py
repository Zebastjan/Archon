"""Tests for MarkdownAwareChunker."""


from src.server.services.chunking.chunkers.markdown_aware import (
    MarkdownAwareChunker,
    _build_section_path,
    _split_by_headings,
)


class TestSplitByHeadings:
    """Test heading detection."""

    def test_no_headings_returns_empty(self):
        """Text without headings returns empty list."""
        result = _split_by_headings("Just some plain text.")
        assert result == []

    def test_single_heading(self):
        """Text with single heading."""
        text = "# Title\n\nSome content here."
        result = _split_by_headings(text)
        assert len(result) == 1
        assert result[0][0] == "Title"
        assert "Some content here" in result[0][1]

    def test_multiple_headings(self):
        """Text with multiple headings."""
        text = "# Intro\n\nIntro content.\n\n# Section 1\n\nSection 1 content.\n\n# Section 2\n\nSection 2 content."
        result = _split_by_headings(text)
        assert len(result) == 3

    def test_nested_headings(self):
        """Text with nested headings."""
        text = "# Main\n\nMain content.\n\n## Sub\n\nSub content."
        result = _split_by_headings(text)
        assert len(result) == 2


class TestBuildSectionPath:
    """Test section path building."""

    def test_single_heading(self):
        """Single heading path."""
        result = _build_section_path(["Introduction"])
        assert result == "Introduction"

    def test_nested_headings(self):
        """Nested heading path."""
        result = _build_section_path(["Guide", "Installation", "Linux"])
        assert result == "Guide > Installation > Linux"


class TestMarkdownAwareChunker:
    """Test MarkdownAwareChunker."""

    def test_empty_text_returns_empty_list(self):
        """Empty text returns empty list."""
        chunker = MarkdownAwareChunker()
        results = chunker.chunk("")
        assert results == []

    def test_no_headings_uses_fallback(self):
        """Text without headings falls back to basic chunking."""
        chunker = MarkdownAwareChunker(chunk_size=100)
        text = "word " * 50
        results = chunker.chunk(text)
        assert len(results) > 0
        assert results[0].metadata["chunker"] == "markdown_aware"
        assert results[0].metadata["section_path"] == ""

    def test_respects_headings(self):
        """Chunker respects heading boundaries."""
        chunker = MarkdownAwareChunker(chunk_size=5000)
        text = "# Title\n\nIntro paragraph here.\n\n# Section 1\n\nContent in section 1."
        results = chunker.chunk(text)

        assert len(results) == 2

        assert results[0].metadata["section_title"] == "Title"
        assert "Intro" in results[0].content

        assert results[1].metadata["section_title"] == "Section 1"
        assert "section 1" in results[1].content.lower()

    def test_metadata_includes_section_path(self):
        """Metadata includes section_path for content under headings."""
        chunker = MarkdownAwareChunker(chunk_size=10000)
        text = "# Main\n\n## Sub\n\nContent here."
        results = chunker.chunk(text)

        has_path = any(r.metadata.get("section_path") for r in results)
        assert has_path

    def test_metadata_includes_heading_level(self):
        """Metadata includes heading_level for content under headings."""
        chunker = MarkdownAwareChunker(chunk_size=10000)
        text = "# H1\n\n## H2\n\n### H3\n\nContent"
        results = chunker.chunk(text)

        has_level = any(r.metadata.get("heading_level") for r in results)
        assert has_level

    def test_async_returns_same_as_sync(self):
        """Async version returns same results as sync."""
        chunker = MarkdownAwareChunker()
        text = "# Title\n\nSome content here."

        sync_results = chunker.chunk(text)

        async def get_async():
            return await chunker.chunk_async(text)

        import asyncio

        async_results = asyncio.run(get_async())

        assert len(sync_results) == len(async_results)
        for s, a in zip(sync_results, async_results, strict=False):
            assert s.content == a.content
            assert s.metadata == a.metadata
