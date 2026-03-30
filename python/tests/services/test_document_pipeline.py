"""Tests for document pipeline.

Tests for document ingestion, chunking, embedding generation, and storage.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import tempfile
import os


class TestDocumentIngestionService:
    """Test the document ingestion service."""

    @pytest.fixture
    def ingestion_service(self):
        """Create a document ingestion service instance for testing."""
        from src.server.services.document_ingestion_service import DocumentIngestionService
        return DocumentIngestionService()

    def test_initialization(self, ingestion_service):
        """Test service initialization."""
        assert ingestion_service is not None

    @pytest.mark.asyncio
    async def test_ingest_text_success(self, ingestion_service):
        """Test successful text ingestion."""
        with patch.object(ingestion_service, '_chunk_and_store') as mock_chunk:
            mock_chunk.return_value = {"success": True, "chunks_stored": 5}
            
            result = await ingestion_service.ingest_text(
                content="Test document content",
                title="Test Document",
                source_url="file://test.txt"
            )
            
            assert result["success"] is True
            assert result["chunks_stored"] == 5

    @pytest.mark.asyncio
    async def test_ingest_text_empty_content(self, ingestion_service):
        """Test ingestion with empty content."""
        result = await ingestion_service.ingest_text(
            content="",
            title="Test Document"
        )
        
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_ingest_markdown_success(self, ingestion_service):
        """Test successful markdown ingestion."""
        with patch.object(ingestion_service, '_chunk_and_store') as mock_chunk:
            mock_chunk.return_value = {"success": True, "chunks_stored": 3}
            
            result = await ingestion_service.ingest_markdown(
                content="# Title\n\nContent",
                title="Test Markdown",
                source_url="file://test.md"
            )
            
            assert result["success"] is True
            assert result["chunks_stored"] == 3


class TestDocumentChunking:
    """Test document chunking functionality."""

    def test_chunk_by_size(self):
        """Test chunking text by size."""
        from src.server.services.chunking.chunking_service import ChunkingService
        
        chunker = ChunkingService(chunk_size=100, chunk_overlap=20)
        text = "This is a test sentence. " * 50  # Create long text
        
        chunks = chunker.chunk_text(text)
        
        assert len(chunks) > 0
        assert all(len(chunk) <= 100 for chunk in chunks)

    def test_chunk_preserves_structure(self):
        """Test that chunking preserves document structure."""
        from src.server.services.chunking.chunking_service import ChunkingService
        
        chunker = ChunkingService(chunk_size=500, chunk_overlap=50)
        text = "# Heading 1\n\nParagraph 1.\n\n# Heading 2\n\nParagraph 2."
        
        chunks = chunker.chunk_text(text, preserve_structure=True)
        
        # Verify headings are preserved in chunks
        assert any("# Heading 1" in chunk for chunk in chunks)
        assert any("# Heading 2" in chunk for chunk in chunks)

    def test_chunk_empty_text(self):
        """Test chunking empty text."""
        from src.server.services.chunking.chunking_service import ChunkingService
        
        chunker = ChunkingService(chunk_size=100)
        chunks = chunker.chunk_text("")
        
        assert chunks == []


class TestDocumentParser:
    """Test document parsing functionality."""

    def test_extract_text_from_txt(self):
        """Test extracting text from plain text file."""
        from src.server.utils.document_parser import extract_text_from_document
        
        content = b"This is plain text content."
        result = extract_text_from_document(content, "test.txt", "text/plain")
        
        assert result == "This is plain text content."

    def test_extract_text_from_md(self):
        """Test extracting text from markdown file."""
        from src.server.utils.document_parser import extract_text_from_document
        
        content = b"# Title\n\nContent"
        result = extract_text_from_document(content, "test.md", "text/markdown")
        
        assert "# Title" in result
        assert "Content" in result

    def test_extract_text_unsupported_type(self):
        """Test extracting text from unsupported file type."""
        from src.server.utils.document_parser import extract_text_from_document
        
        with pytest.raises(ValueError):
            extract_text_from_document(b"content", "test.xyz", "application/unknown")


class TestEmbeddingGeneration:
    """Test embedding generation in pipeline."""

    @pytest.mark.asyncio
    @patch('src.server.services.embeddings.embedding_service.EmbeddingService.generate_embedding')
    async def test_generate_embeddings_for_chunks(self, mock_generate):
        """Test generating embeddings for document chunks."""
        mock_generate.return_value = [0.1, 0.2, 0.3]
        
        from src.server.services.embeddings.embedding_service import EmbeddingService
        
        service = EmbeddingService()
        chunks = ["chunk 1", "chunk 2", "chunk 3"]
        
        embeddings = []
        for chunk in chunks:
            embedding = await service.generate_embedding(chunk)
            embeddings.append(embedding)
        
        assert len(embeddings) == 3
        assert all(len(emb) == 3 for emb in embeddings)

    @pytest.mark.asyncio
    async def test_batch_embedding_generation(self):
        """Test batch embedding generation."""
        from src.server.services.embeddings.embedding_service import EmbeddingService
        
        service = EmbeddingService()
        
        with patch.object(service, 'generate_embeddings_batch') as mock_batch:
            mock_batch.return_value = [[0.1, 0.2], [0.3, 0.4]]
            
            texts = ["text 1", "text 2"]
            embeddings = await service.generate_embeddings_batch(texts)
            
            assert len(embeddings) == 2


class TestDocumentStorage:
    """Test document storage in pipeline."""

    @pytest.mark.asyncio
    async def test_store_document_chunks(self):
        """Test storing document chunks in database."""
        from src.server.services.document_ingestion_service import DocumentIngestionService
        
        service = DocumentIngestionService()
        
        with patch('src.server.services.database.db_connector.db_connector.execute') as mock_execute:
            mock_execute.return_value = AsyncMock()
            
            chunks = [
                {"content": "chunk 1", "embedding": [0.1, 0.2]},
                {"content": "chunk 2", "embedding": [0.3, 0.4]},
            ]
            
            result = await service._store_chunks(chunks, "test-source")
            
            assert result["success"] is True
            assert result["chunks_stored"] == 2

    @pytest.mark.asyncio
    async def test_store_document_with_metadata(self):
        """Test storing document with metadata."""
        from src.server.services.document_ingestion_service import DocumentIngestionService
        
        service = DocumentIngestionService()
        
        with patch('src.server.services.database.db_connector.db_connector.execute') as mock_execute:
            mock_execute.return_value = AsyncMock()
            
            result = await service.ingest_text(
                content="Test content",
                title="Test Doc",
                metadata={"author": "test", "tags": ["test", "doc"]},
            )
            
            assert result["success"] is True


class TestPipelineIntegration:
    """Integration tests for the full document pipeline."""

    @pytest.mark.asyncio
    @patch('src.server.services.document_ingestion_service.DocumentIngestionService._chunk_and_store')
    @patch('src.server.services.embeddings.embedding_service.EmbeddingService.generate_embedding')
    async def test_full_pipeline_text_document(self, mock_embedding, mock_chunk_store):
        """Test full pipeline for text document."""
        mock_embedding.return_value = [0.1] * 384
        mock_chunk_store.return_value = {"success": True, "chunks_stored": 5, "source_id": "test-123"}
        
        from src.server.services.document_ingestion_service import get_document_ingestion_service
        
        service = get_document_ingestion_service()
        
        result = await service.ingest_text(
            content="This is a test document with multiple sentences. " * 20,
            title="Integration Test Document",
            source_url="file://integration_test.txt",
        )
        
        assert result["success"] is True
        assert "source_id" in result
        assert result["chunks_stored"] > 0

    @pytest.mark.asyncio
    async def test_pipeline_error_handling(self):
        """Test pipeline error handling."""
        from src.server.services.document_ingestion_service import DocumentIngestionService
        
        service = DocumentIngestionService()
        
        with patch.object(service, '_chunk_and_store', side_effect=Exception("DB Error")):
            result = await service.ingest_text(
                content="Test content",
                title="Error Test"
            )
            
            assert result["success"] is False
            assert "error" in result
