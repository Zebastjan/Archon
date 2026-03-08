"""Tests for CodeAwareChunker."""


from src.server.services.chunking.chunkers.code_aware import CodeAwareChunker, _detect_language, _split_code_blocks


class TestDetectLanguage:
    """Test language detection."""

    def test_python_detection(self):
        """Detects Python from def/class keywords."""
        code = "def hello():\n    return 'world'"
        assert _detect_language(code) == "python"

    def test_javascript_detection(self):
        """Detects JavaScript from const/let."""
        code = "const x = () => { return 1; }"
        assert _detect_language(code) == "javascript"

    def test_from_code_block_marker(self):
        """Detects from code block marker."""
        code = "```python\ndef foo():\n    pass\n```"
        assert _detect_language(code) == "python"


class TestSplitCodeBlocks:
    """Test code block splitting."""

    def test_no_code_blocks(self):
        """Text without code blocks returns single text section."""
        text = "Just some prose."
        result = _split_code_blocks(text)
        assert len(result) == 1
        assert result[0][0] == "text"

    def test_single_code_block(self):
        """Text with single code block."""
        text = "Some text\n\n```python\nx = 1\n```\n\nMore text"
        result = _split_code_blocks(text)
        assert len(result) == 3

    def test_multiple_code_blocks(self):
        """Text with multiple code blocks."""
        text = "First code:\n\n```js\nconst a = 1;\n```\n\nThen:\n\n```python\nx = 2\n```"
        result = _split_code_blocks(text)
        assert len(result) == 4


class TestCodeAwareChunker:
    """Test CodeAwareChunker."""

    def test_empty_text_returns_empty_list(self):
        """Empty text returns empty list."""
        chunker = CodeAwareChunker()
        results = chunker.chunk("")
        assert results == []

    def test_prose_only(self):
        """Text without code uses prose type."""
        chunker = CodeAwareChunker()
        text = "Just some prose content here."
        results = chunker.chunk(text)

        assert len(results) == 1
        assert results[0].metadata["chunker"] == "code_aware"
        assert results[0].metadata["code_type"] == "prose"

    def test_preserves_code_blocks(self):
        """Chunker preserves code blocks as units."""
        chunker = CodeAwareChunker(chunk_size=5000)
        text = "Some text\n\n```python\ndef hello():\n    print('world')\n```\n\nMore text"
        results = chunker.chunk(text)

        code_results = [r for r in results if "```" in r.content]
        assert len(code_results) > 0

    def test_metadata_includes_code_type(self):
        """Metadata includes code_type."""
        chunker = CodeAwareChunker()
        text = "# Code\n\n```python\nx = 1\n```\n\nSome prose."
        results = chunker.chunk(text)

        code_types = {r.metadata.get("code_type") for r in results}
        assert "code_block" in code_types
        assert "prose" in code_types

    def test_metadata_includes_language(self):
        """Metadata includes detected language."""
        chunker = CodeAwareChunker()
        text = "```python\nx = 1\n```"
        results = chunker.chunk(text)

        languages = {r.metadata.get("language") for r in results}
        assert "python" in languages

    def test_async_returns_same_as_sync(self):
        """Async version returns same results as sync."""
        chunker = CodeAwareChunker()
        text = "Some text\n\n```python\nx = 1\n```"

        sync_results = chunker.chunk(text)

        async def get_async():
            return await chunker.chunk_async(text)

        import asyncio

        async_results = asyncio.run(get_async())

        assert len(sync_results) == len(async_results)
        for s, a in zip(sync_results, async_results, strict=False):
            assert s.content == a.content
            assert s.metadata == a.metadata
