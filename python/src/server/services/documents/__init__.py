"""Document processing services.

Provides local document ingestion and processing pipeline using Dockling.
Replaces the removed web crawling functionality with local document support.

Modules:
- local_document_service: Parse local documents (PDF, Markdown, RST, etc.)
- chunking_service: Semantic chunking respecting document structure
- summarization_service: Generate document and section summaries
"""

from .chunking_service import (
    ChunkingService,
    DocumentChunk,
    chunk_document,
)
from .local_document_service import (
    LocalDocumentService,
    DocumentMetadata,
    ParsedDocument,
    parse_document,
)
from .summarization_service import (
    DocumentSummary,
    SummarizationService,
    summarize_document,
    summarize_sections,
)

__all__ = [
    # Local document service
    "LocalDocumentService",
    "parse_document",
    "ParsedDocument",
    "DocumentMetadata",
    # Chunking service
    "ChunkingService",
    "DocumentChunk",
    "chunk_document",
    # Summarization service
    "SummarizationService",
    "DocumentSummary",
    "summarize_document",
    "summarize_sections",
]
