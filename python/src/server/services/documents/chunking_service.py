"""Semantic chunking service for documents.

Chunks documents respecting structure (headings, sections, paragraphs)
rather than arbitrary character counts.
"""

from dataclasses import dataclass, field
from typing import Any

from ...config.logfire_config import get_logger

logger = get_logger(__name__)


@dataclass
class DocumentChunk:
    """A semantic chunk of a document.

    Attributes:
        content: The chunk text content
        heading: Section heading (if any)
        level: Heading level (1-6) or 0 for body
        index: Chunk index in document
        metadata: Additional metadata
    """

    content: str
    heading: str = ""
    level: int = 0
    index: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def word_count(self) -> int:
        """Approximate word count."""
        return len(self.content.split())


class ChunkingService:
    """Service for semantic document chunking.

    Respects document structure (headings, paragraphs) rather than
    splitting at arbitrary character boundaries.
    """

    # Default chunk size targets
    DEFAULT_TARGET_WORDS = 250
    DEFAULT_MAX_WORDS = 500
    DEFAULT_MIN_WORDS = 50

    def __init__(
        self,
        target_words: int = DEFAULT_TARGET_WORDS,
        max_words: int = DEFAULT_MAX_WORDS,
        min_words: int = DEFAULT_MIN_WORDS,
    ):
        """Initialize chunking service.

        Args:
            target_words: Target words per chunk
            max_words: Maximum words per chunk
            min_words: Minimum words per chunk
        """
        self.target_words = target_words
        self.max_words = max_words
        self.min_words = min_words

    def chunk_document(
        self,
        content: str,
        sections: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> list[DocumentChunk]:
        """Chunk a document semantically.

        Args:
            content: Full document content
            sections: Optional pre-extracted sections with headings
            metadata: Document metadata to include in chunks

        Returns:
            List of semantic chunks
        """
        chunks = []

        if sections:
            # Use provided sections
            for idx, section in enumerate(sections):
                section_chunks = self._chunk_section(section, idx, metadata or {})
                chunks.extend(section_chunks)
        else:
            # Chunk by paragraphs
            chunks = self._chunk_by_paragraphs(content, metadata or {})

        logger.info(f"Document chunked | chunks={len(chunks)} | target_words={self.target_words}")

        return chunks

    def _chunk_section(
        self,
        section: dict[str, Any],
        index: int,
        metadata: dict[str, Any],
    ) -> list[DocumentChunk]:
        """Chunk a single section.

        Args:
            section: Section dict with heading, content, level
            index: Section index
            metadata: Document metadata

        Returns:
            List of chunks for this section
        """
        content = section.get("content", "")
        heading = section.get("heading", "")
        level = section.get("level", 1)

        words = content.split()
        word_count = len(words)

        # If section is small enough, keep as single chunk
        if word_count <= self.max_words:
            return [
                DocumentChunk(
                    content=content,
                    heading=heading,
                    level=level,
                    index=index,
                    metadata={**metadata, "section_heading": heading},
                )
            ]

        # Split large sections at paragraph boundaries
        chunks = []
        paragraphs = content.split("\n\n")
        current_content = []
        current_words = 0
        chunk_index = 0

        for paragraph in paragraphs:
            para_words = len(paragraph.split())

            # Check if adding this paragraph exceeds max
            if current_words + para_words > self.max_words and current_content:
                # Save current chunk
                chunks.append(
                    DocumentChunk(
                        content="\n\n".join(current_content),
                        heading=heading,
                        level=level,
                        index=index * 1000 + chunk_index,
                        metadata={**metadata, "section_heading": heading},
                    )
                )
                current_content = []
                current_words = 0
                chunk_index += 1

            current_content.append(paragraph)
            current_words += para_words

        # Add remaining content
        if current_content:
            chunks.append(
                DocumentChunk(
                    content="\n\n".join(current_content),
                    heading=heading,
                    level=level,
                    index=index * 1000 + chunk_index,
                    metadata={**metadata, "section_heading": heading},
                )
            )

        return chunks

    def _chunk_by_paragraphs(self, content: str, metadata: dict[str, Any]) -> list[DocumentChunk]:
        """Chunk document by paragraphs.

        Args:
            content: Document content
            metadata: Document metadata

        Returns:
            List of chunks
        """
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]

        if not paragraphs:
            return []

        chunks = []
        current_content = []
        current_words = 0
        index = 0

        for paragraph in paragraphs:
            para_words = len(paragraph.split())

            # Check if adding exceeds target
            if current_words + para_words > self.target_words and current_words >= self.min_words:
                # Save chunk
                chunks.append(
                    DocumentChunk(
                        content="\n\n".join(current_content),
                        index=index,
                        metadata=metadata,
                    )
                )
                current_content = []
                current_words = 0
                index += 1

            current_content.append(paragraph)
            current_words += para_words

        # Add final chunk
        if current_content:
            chunks.append(
                DocumentChunk(
                    content="\n\n".join(current_content),
                    index=index,
                    metadata=metadata,
                )
            )

        return chunks


# Convenience function
def chunk_document(
    content: str,
    sections: list[dict[str, Any]] | None = None,
    target_words: int = 250,
) -> list[DocumentChunk]:
    """Chunk a document semantically.

    Args:
        content: Document content
        sections: Optional pre-extracted sections
        target_words: Target words per chunk

    Returns:
        List of document chunks
    """
    service = ChunkingService(target_words=target_words)
    return service.chunk_document(content, sections)
