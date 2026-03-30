"""Local document ingestion service.

Uses Dockling to parse local documents (Markdown, RST, PDF, ODT, etc.)
and extract structured text content with metadata.

Replaces the web crawling functionality with local document processing.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ...config.logfire_config import get_logger

logger = get_logger(__name__)


@dataclass
class DocumentMetadata:
    """Metadata extracted from a document.

    Attributes:
        title: Document title
        author: Document author (if available)
        created_at: Creation date
        modified_at: Last modified date
        file_type: File extension/format
        file_size: File size in bytes
        word_count: Estimated word count
        headings: List of headings/sections found
    """

    title: str = ""
    author: str = ""
    created_at: str = ""
    modified_at: str = ""
    file_type: str = ""
    file_size: int = 0
    word_count: int = 0
    headings: list[str] = field(default_factory=list)


@dataclass
class ParsedDocument:
    """Result of parsing a local document.

    Attributes:
        content: Clean text content
        metadata: Extracted metadata
        sections: List of document sections with headings
        source_path: Original file path
        success: Whether parsing succeeded
        error: Error message if parsing failed
    """

    content: str = ""
    metadata: DocumentMetadata = field(default_factory=DocumentMetadata)
    sections: list[dict[str, Any]] = field(default_factory=list)
    source_path: str = ""
    success: bool = False
    error: str = ""


class LocalDocumentService:
    """Service for ingesting and parsing local documents.

    Supports: Markdown, reStructuredText, PDF, ODT, DOCX, and other formats
    via Dockling integration.
    """

    # Supported file extensions
    SUPPORTED_EXTENSIONS = {
        ".md",
        ".markdown",
        ".rst",
        ".txt",
        ".pdf",
        ".odt",
        ".docx",
        ".doc",
        ".norg",
    }

    def __init__(self):
        """Initialize the document service."""
        self._parser = None

    def _get_parser(self):
        """Lazy-load the Dockling parser."""
        if self._parser is None:
            try:
                from docling import Docling

                self._parser = Docling()
                logger.info("Dockling parser initialized")
            except ImportError as e:
                logger.error(f"Failed to import Dockling: {e}")
                raise RuntimeError("Dockling not installed") from e
        return self._parser

    def is_supported(self, file_path: str | Path) -> bool:
        """Check if a file format is supported.

        Args:
            file_path: Path to the file

        Returns:
            True if the file format is supported
        """
        path = Path(file_path)
        return path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    async def parse_document(self, file_path: str | Path) -> ParsedDocument:
        """Parse a local document and extract structured content.

        Args:
            file_path: Path to the document file

        Returns:
            ParsedDocument with content, metadata, and sections
        """
        path = Path(file_path)

        # Validate file exists
        if not path.exists():
            return ParsedDocument(
                success=False,
                error=f"File not found: {file_path}",
                source_path=str(file_path),
            )

        # Validate format support
        if not self.is_supported(path):
            return ParsedDocument(
                success=False,
                error=f"Unsupported file format: {path.suffix}",
                source_path=str(file_path),
            )

        try:
            parser = self._get_parser()

            # Parse document with Dockling
            result = await self._parse_with_dockling(parser, path)

            logger.info(
                f"Document parsed successfully | path={path} | "
                f"type={result.metadata.file_type} | "
                f"sections={len(result.sections)}"
            )

            return result

        except Exception as e:
            logger.exception(f"Failed to parse document: {path}")
            return ParsedDocument(
                success=False,
                error=str(e),
                source_path=str(file_path),
            )

    async def _parse_with_dockling(self, parser, path: Path) -> ParsedDocument:
        """Parse document using Dockling.

        Args:
            parser: Dockling parser instance
            path: Path to document

        Returns:
            ParsedDocument with extracted content
        """
        # Read file stats
        stat = path.stat()

        # Use Dockling to parse document
        # Note: Actual implementation depends on Dockling API
        # This is a placeholder for the integration

        try:
            # Parse the document
            doc = parser.parse(str(path))

            # Extract text content
            content = doc.text if hasattr(doc, "text") else ""

            # Extract metadata
            metadata = DocumentMetadata(
                title=getattr(doc, "title", path.stem),
                author=getattr(doc, "author", ""),
                created_at=getattr(doc, "created_at", ""),
                modified_at=getattr(doc, "modified_at", ""),
                file_type=path.suffix.lower(),
                file_size=stat.st_size,
                word_count=len(content.split()),
                headings=getattr(doc, "headings", []),
            )

            # Extract sections
            sections = []
            if hasattr(doc, "sections"):
                for section in doc.sections:
                    sections.append(
                        {
                            "heading": getattr(section, "heading", ""),
                            "content": getattr(section, "text", ""),
                            "level": getattr(section, "level", 1),
                        }
                    )

            return ParsedDocument(
                content=content,
                metadata=metadata,
                sections=sections,
                source_path=str(path),
                success=True,
            )

        except Exception as e:
            logger.error(f"Dockling parsing failed: {e}")
            raise

    async def parse_multiple(self, file_paths: list[str | Path]) -> list[ParsedDocument]:
        """Parse multiple documents.

        Args:
            file_paths: List of paths to documents

        Returns:
            List of ParsedDocument results
        """
        import asyncio

        tasks = [self.parse_document(path) for path in file_paths]
        return await asyncio.gather(*tasks, return_exceptions=True)


# Convenience function for simple use cases
async def parse_document(file_path: str | Path) -> ParsedDocument:
    """Parse a single document.

    Args:
        file_path: Path to the document

    Returns:
        ParsedDocument with extracted content
    """
    service = LocalDocumentService()
    return await service.parse_document(file_path)
