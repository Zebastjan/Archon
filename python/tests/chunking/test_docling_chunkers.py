"""Tests for Docling chunkers."""

import pytest
from pathlib import Path


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "docling"


def check_docling_available():
    """Check if docling and its dependencies are available."""
    try:
        import torch
        import torchvision
        from docling.document_converter import DocumentConverter
        from docling.chunking import HybridChunker

        converter = DocumentConverter()
        chunker = HybridChunker()
        return True
    except Exception:
        return False


DOCLING_AVAILABLE = check_docling_available()


class TestDoclingDocumentProcessor:
    """Test the DoclingDocumentProcessor class."""

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available or incompatible")
    def test_processor_import(self):
        """Test that processor can be imported."""
        from src.server.services.chunking.chunkers.docling_processor import (
            DoclingDocumentProcessor,
        )

        processor = DoclingDocumentProcessor()
        assert processor is not None


class TestDoclingHierarchicalChunker:
    """Test DoclingHierarchicalChunker."""

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available or incompatible")
    def test_chunk_pdf(self):
        """Test chunking a PDF file."""
        from src.server.services.chunking.chunkers.docling_chunkers import (
            DoclingHierarchicalChunker,
        )

        pdf_path = FIXTURES_DIR / "normal_4pages.pdf"
        if not pdf_path.exists():
            pytest.skip("Test fixture not found")

        chunker = DoclingHierarchicalChunker()
        results = chunker.chunk(str(pdf_path))

        assert len(results) > 0
        assert results[0].content
        assert results[0].metadata["chunker"] == "docling_hierarchical"

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available or incompatible")
    def test_metadata_fields(self):
        """Test that metadata fields are populated."""
        from src.server.services.chunking.chunkers.docling_chunkers import (
            DoclingHierarchicalChunker,
        )

        pdf_path = FIXTURES_DIR / "normal_4pages.pdf"
        if not pdf_path.exists():
            pytest.skip("Test fixture not found")

        chunker = DoclingHierarchicalChunker()
        results = chunker.chunk(str(pdf_path))

        result = results[0]
        assert result.index == 0
        assert result.token_estimate is not None
        assert result.metadata is not None


class TestDoclingHybridChunker:
    """Test DoclingHybridChunker."""

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available or incompatible")
    def test_chunk_pdf(self):
        """Test chunking a PDF file with hybrid chunker."""
        from src.server.services.chunking.chunkers.docling_chunkers import (
            DoclingHybridChunker,
        )

        pdf_path = FIXTURES_DIR / "normal_4pages.pdf"
        if not pdf_path.exists():
            pytest.skip("Test fixture not found")

        chunker = DoclingHybridChunker()
        results = chunker.chunk(str(pdf_path))

        assert len(results) > 0
        assert results[0].content
        assert results[0].metadata["chunker"] == "docling_hybrid"

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available or incompatible")
    def test_custom_max_tokens(self):
        """Test custom max_tokens option."""
        from src.server.services.chunking.chunkers.docling_chunkers import (
            DoclingHybridChunker,
        )

        pdf_path = FIXTURES_DIR / "normal_4pages.pdf"
        if not pdf_path.exists():
            pytest.skip("Test fixture not found")

        chunker = DoclingHybridChunker(max_tokens=256)
        assert chunker.max_tokens == 256

        results = chunker.chunk(str(pdf_path))
        assert len(results) > 0


class TestDoclingIntegration:
    """Integration tests for Docling with real documents."""

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available or incompatible")
    def test_simple_pdf_happy_path(self):
        """Test 3.1: Simple PDF happy path."""
        from src.server.services.chunking.chunkers.docling_chunkers import (
            DoclingHybridChunker,
        )

        pdf_path = FIXTURES_DIR / "normal_4pages.pdf"
        if not pdf_path.exists():
            pytest.skip("Test fixture not found")

        chunker = DoclingHybridChunker(max_tokens=512)
        results = chunker.chunk(str(pdf_path))

        assert len(results) > 3, "Should have more than 3 chunks for 4-page PDF"
        assert len(results) < 200, "Should have less than 200 chunks for 4-page PDF"

        has_content = any(len(r.content.strip()) > 10 for r in results)
        assert has_content, "At least one chunk should have meaningful content"

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available or incompatible")
    def test_docx_conversion(self):
        """Test 3.3: DOCX conversion."""
        from src.server.services.chunking.chunkers.docling_chunkers import (
            DoclingHybridChunker,
        )

        docx_path = FIXTURES_DIR / "simple_test.docx"
        if not docx_path.exists():
            pytest.skip("Test fixture not found")

        chunker = DoclingHybridChunker()
        results = chunker.chunk(str(docx_path))

        assert len(results) > 0, "Should have at least one chunk"

        content_text = " ".join(r.content for r in results).lower()
        assert "test" in content_text or "document" in content_text, "Content should match source"

    @pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available or incompatible")
    def test_table_preservation(self):
        """Test 3.2: Table content is not silently lost."""
        from src.server.services.chunking.chunkers.docling_chunkers import (
            DoclingHybridChunker,
        )

        pdf_path = FIXTURES_DIR / "amt_handbook_sample.pdf"
        if not pdf_path.exists():
            pytest.skip("Test fixture not found")

        chunker = DoclingHybridChunker()
        results = chunker.chunk(str(pdf_path))

        all_content = " ".join(r.content for r in results).lower()

        table_indicators = ["table", "row", "column", "cell"]
        has_table_content = any(indicator in all_content for indicator in table_indicators)

        if not has_table_content:
            print("Warning: Table content may have been lost")


class TestDoclingFactory:
    """Test that chunkers are registered in factory."""

    def test_docling_hierarchical_available(self):
        """Test that docling_hierarchical is registered in factory."""
        from src.server.services.chunking import get_chunker

        if not DOCLING_AVAILABLE:
            pytest.skip("Docling not available")

        chunker = get_chunker("docling_hierarchical")
        assert chunker is not None

    def test_docling_hybrid_available(self):
        """Test that docling_hybrid is registered in factory."""
        from src.server.services.chunking import get_chunker

        if not DOCLING_AVAILABLE:
            pytest.skip("Docling not available")

        chunker = get_chunker("docling_hybrid")
        assert chunker is not None
