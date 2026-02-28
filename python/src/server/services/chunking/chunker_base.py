"""Chunking module base classes and interfaces."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ChunkResult:
    """Result of a chunking operation.

    Attributes:
        content: The text content of the chunk.
        index: Zero-based index of this chunk in the sequence.
        section_path: Hierarchical path of headings (e.g., ["Guide", "Installation"]).
        section_title: Title of the current section or heading.
        page_number: Page number for PDF/DOCX sources.
        element_type: Type of content (paragraph, heading, table, figure, code, list).
        order_index: Global ordering index within document (survives re-chunking).
        token_estimate: Estimated token count for this chunk.
        metadata: Additional metadata about this chunk.
    """

    content: str
    index: int
    section_path: list[str] | None = None
    section_title: str | None = None
    page_number: int | None = None
    element_type: str = "paragraph"
    order_index: int | None = None
    token_estimate: int | None = None
    metadata: dict[str, Any] | None = None


class BaseChunker(ABC):
    """Abstract base class for all chunkers.

    Implementors must provide both sync and async versions of chunk().
    """

    def __init__(self, **options):
        """Initialize chunker with configuration options.

        Args:
            **options: Configuration options (e.g., chunk_size, overlap).
        """
        self.options = options

    @abstractmethod
    def chunk(self, text: str, **options) -> list[ChunkResult]:
        """Split text into chunks synchronously.

        Args:
            text: Text to chunk.
            **options: Override options for this specific chunk operation.

        Returns:
            List of ChunkResult objects.
        """
        ...

    @abstractmethod
    async def chunk_async(self, text: str, **options) -> list[ChunkResult]:
        """Split text into chunks asynchronously.

        Args:
            text: Text to chunk.
            **options: Override options for this specific chunk operation.

        Returns:
            List of ChunkResult objects.
        """
        ...
