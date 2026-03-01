"""Docling-powered chunkers for PDF/DOCX processing."""

from pathlib import Path
from typing import Any


class DoclingNotInstalledError(ImportError):
    """Raised when docling is not installed but a Docling chunker is requested."""

    def __init__(self, strategy: str):
        self.strategy = strategy
        super().__init__(
            f"Docling is required for '{strategy}' chunking strategy. Install it with: pip install docling"
        )


from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
from docling_core.transforms.chunker.hierarchical_chunker import HierarchicalChunker as _DoclingHierarchicalChunker
from docling_core.transforms.chunker.hybrid_chunker import HybridChunker as _DoclingHybridChunker

from src.server.services.chunking.chunker_base import BaseChunker, ChunkResult


def _get_default_converter() -> DocumentConverter:
    """Get a default DocumentConverter instance."""
    pdf_options = PdfPipelineOptions()
    pdf_options.do_ocr = True
    pdf_options.do_table_structure = True

    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_cls=StandardPdfPipeline, pipeline_options=pdf_options),
        }
    )


class DoclingHierarchicalChunker(BaseChunker):
    """Docling-powered hierarchical chunker.

    Creates chunks that align strictly with document structural blocks
    (sections, subsections). Requires the docling package.

    This chunker:
    - Parses documents into a rich tree: sections, headings, paragraphs, tables, figures
    - Creates chunks strictly following the document hierarchy
    - Does NOT enforce target chunk sizes (use DoclingHybridChunker for that)

    Accepts:
        - File path (str/Path) to PDF/DOCX
        - Bytes content
        - DoclingDocument directly
    """

    def __init__(self, **options: Any):
        """Initialize the chunker.

        Args:
            **options: Configuration options (reserved for future use)
        """
        super().__init__(**options)
        self._converter = _get_default_converter()
        self._chunker = _DoclingHierarchicalChunker()

    def chunk(self, text: str, **options: Any) -> list[ChunkResult]:
        """Split document into chunks using hierarchical structure.

        Args:
            text: File path (str), bytes, or pre-processed DoclingDocument.
                  If string looks like a path, treats as file path.
            **options: Additional options (document=DoclingDocument for explicit input)

        Returns:
            List of ChunkResult objects with rich metadata

        Raises:
            FileNotFoundError: If file path doesn't exist
            ValueError: If input is invalid
        """

        doc = self._resolve_document(text, options)
        return self._chunk_document(doc)

    async def chunk_async(self, text: str, **options: Any) -> list[ChunkResult]:
        """Async version - same as sync for this chunker."""
        return self.chunk(text, **options)

    def _resolve_document(self, text: str, options: dict[str, Any]) -> "docling_core.types.doc.DoclingDocument":
        """Resolve input to a DoclingDocument."""
        import docling_core.types.doc

        if isinstance(text, docling_core.types.doc.DoclingDocument):
            return text

        if options.get("document") is not None:
            return options["document"]

        if isinstance(text, (bytes, str)):
            if isinstance(text, bytes):
                import tempfile

                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(text)
                    tmp_path = tmp.name

                try:
                    result = self._converter.convert(Path(tmp_path))
                    return result.document
                finally:
                    Path(tmp_path).unlink(missing_ok=True)
            else:
                path = Path(text)
                if path.exists():
                    result = self._converter.convert(path)
                    return result.document
                else:
                    raise ValueError(f"Text doesn't appear to be a valid file path: {text}")

        raise ValueError("Invalid input. Provide: file path, bytes, or DoclingDocument")

    def _chunk_document(self, doc: "docling_core.types.doc.DoclingDocument") -> list[ChunkResult]:
        """Chunk a DoclingDocument using hierarchical chunking."""
        doc_chunks = list(self._chunker.chunk(doc))

        results = []
        for idx, chunk in enumerate(doc_chunks):
            headings = chunk.meta.headings if hasattr(chunk.meta, "headings") and chunk.meta.headings else []
            section_path = headings[:-1] if len(headings) > 1 else []
            section_title = headings[-1] if headings else None

            page = None
            if hasattr(chunk.meta, "doc_items") and chunk.meta.doc_items:
                first_item = chunk.meta.doc_items[0]
                if hasattr(first_item, "prov") and first_item.prov:
                    page = first_item.prov[0].page_no

            element_type = self._determine_element_type(chunk)

            results.append(
                ChunkResult(
                    content=chunk.text,
                    index=idx,
                    section_path=section_path,
                    section_title=section_title,
                    page_number=page,
                    element_type=element_type,
                    order_index=idx,
                    token_estimate=self._estimate_tokens(chunk.text),
                    metadata={
                        "chunker": "docling_hierarchical",
                        "headings": headings,
                        "chunk_text": chunk.text,
                    },
                )
            )

        return results

    def _determine_element_type(self, chunk: Any) -> str:
        """Determine the element type from chunk metadata."""
        text = chunk.text.lower().strip()

        if text.startswith("#") or chunk.meta.headings:
            return "heading"
        if "table" in chunk.meta and chunk.meta.table:
            return "table"
        if "picture" in chunk.meta and chunk.meta.picture:
            return "figure"
        if "```" in chunk.text or "def " in chunk.text or "function" in text:
            return "code"

        return "paragraph"

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation (avg 4 chars per token)."""
        return len(text) // 4


class DoclingHybridChunker(BaseChunker):
    """Docling-powered hybrid chunker.

    Applies tokenization-aware refinements on top of document-based hierarchical chunking.
    This is the recommended chunker for most RAG use cases with PDFs/DOCX.
    Requires the docling package.

    This chunker:
    - Starts with document hierarchy but enforces target chunk sizes
    - Splits big sections and merges small ones within the same path
    - Tuned for embeddings and context window limits

    Accepts:
        - File path (str/Path) to PDF/DOCX
        - Bytes content
        - DoclingDocument directly
    """

    def __init__(self, **options: Any):
        """Initialize the chunker.

        Args:
            **options: Configuration options including:
                - max_tokens: Maximum tokens per chunk (default: 512)
                - overlap_tokens: Overlap between chunks (default: 50)
                - tokenizer: Tokenizer to use (default: sentence-transformers/all-MiniLM-L6-v2)
        """
        super().__init__(**options)
        self.max_tokens = options.get("max_tokens", 512)
        self.overlap_tokens = options.get("overlap_tokens", 50)
        tokenizer = options.get("tokenizer", "sentence-transformers/all-MiniLM-L6-v2")

        self._converter = _get_default_converter()
        self._chunker = _DoclingHybridChunker(
            tokenizer=tokenizer,
            max_tokens=self.max_tokens,
            merge_peers=True,
        )

    def chunk(self, text: str, **options: Any) -> list[ChunkResult]:
        """Split document into chunks using hybrid approach.

        Args:
            text: File path (str), bytes, or pre-processed DoclingDocument.
            **options: Additional options including:
                - max_tokens: Override max tokens per chunk
                - document: DoclingDocument for explicit input

        Returns:
            List of ChunkResult objects with rich metadata
        """

        doc = self._resolve_document(text, options)
        return self._chunk_document(doc)

    async def chunk_async(self, text: str, **options: Any) -> list[ChunkResult]:
        """Async version - same as sync for this chunker."""
        return self.chunk(text, **options)

    def _resolve_document(self, text: str, options: dict[str, Any]) -> "docling_core.types.doc.DoclingDocument":
        """Resolve input to a DoclingDocument."""
        import docling_core.types.doc

        if isinstance(text, docling_core.types.doc.DoclingDocument):
            return text

        if options.get("document") is not None:
            return options["document"]

        if isinstance(text, (bytes, str)):
            if isinstance(text, bytes):
                import tempfile

                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(text)
                    tmp_path = tmp.name

                try:
                    result = self._converter.convert(Path(tmp_path))
                    return result.document
                finally:
                    Path(tmp_path).unlink(missing_ok=True)
            else:
                path = Path(text)
                if path.exists():
                    result = self._converter.convert(path)
                    return result.document
                else:
                    raise ValueError(f"Text doesn't appear to be a valid file path: {text}")

        raise ValueError("Invalid input. Provide: file path, bytes, or DoclingDocument")

    def _chunk_document(self, doc: "docling_core.types.doc.DoclingDocument") -> list[ChunkResult]:
        """Chunk a DoclingDocument using hybrid chunking."""
        doc_chunks = list(self._chunker.chunk(doc))

        results = []
        for idx, chunk in enumerate(doc_chunks):
            headings = chunk.meta.headings if hasattr(chunk.meta, "headings") and chunk.meta.headings else []
            section_path = headings[:-1] if len(headings) > 1 else []
            section_title = headings[-1] if headings else None

            page = None
            if hasattr(chunk.meta, "doc_items") and chunk.meta.doc_items:
                first_item = chunk.meta.doc_items[0]
                if hasattr(first_item, "prov") and first_item.prov:
                    page = first_item.prov[0].page_no

            contextualized = chunk.text

            element_type = self._determine_element_type(chunk)

            results.append(
                ChunkResult(
                    content=contextualized,
                    index=idx,
                    section_path=section_path,
                    section_title=section_title,
                    page_number=page,
                    element_type=element_type,
                    order_index=idx,
                    token_estimate=self._estimate_tokens(contextualized),
                    metadata={
                        "chunker": "docling_hybrid",
                        "headings": headings,
                        "chunk_text": chunk.text,
                        "contextualized": True,
                    },
                )
            )

        return results

    def _determine_element_type(self, chunk: Any) -> str:
        """Determine the element type from chunk metadata."""
        text = chunk.text.lower().strip()

        if text.startswith("#") or chunk.meta.headings:
            return "heading"
        if "table" in chunk.meta and chunk.meta.table:
            return "table"
        if "picture" in chunk.meta and chunk.meta.picture:
            return "figure"
        if "```" in chunk.text or "def " in chunk.text or "function" in text:
            return "code"

        return "paragraph"

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation (avg 4 chars per token)."""
        return len(text) // 4


__all__ = [
    "DoclingHierarchicalChunker",
    "DoclingHybridChunker",
]
