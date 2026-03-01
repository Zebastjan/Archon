"""Custom exceptions for chunking service.

These exceptions follow the principle: "fail fast and loud" for data integrity issues,
while allowing batch processes to continue by skipping failed items.
"""

from typing import Any


class ChunkingError(Exception):
    """Base exception for all chunking-related errors."""

    def __init__(
        self,
        message: str,
        text_preview: str | None = None,
        chunk_index: int | None = None,
        **kwargs: Any,
    ):
        """Initialize chunking error with context.

        Args:
            message: Error description.
            text_preview: Preview of text that failed (max 200 chars).
            chunk_index: Index of chunk being processed when error occurred.
            **kwargs: Additional metadata.
        """
        self.text_preview = text_preview[:200] if text_preview else None
        self.chunk_index = chunk_index
        self.metadata = kwargs
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for JSON serialization."""
        return {
            "error_type": self.__class__.__name__,
            "message": str(self),
            "text_preview": self.text_preview,
            "chunk_index": self.chunk_index,
            "metadata": self.metadata,
        }


class ChunkingStrategyError(ChunkingError):
    """Raised when an invalid or unsupported chunking strategy is requested."""

    def __init__(self, strategy: str, available_strategies: list[str] | None = None):
        """Initialize strategy error.

        Args:
            strategy: The invalid strategy name.
            available_strategies: List of valid strategy names.
        """
        msg = f"Unknown chunking strategy: '{strategy}'"
        if available_strategies:
            msg += f". Available strategies: {', '.join(available_strategies)}"
        super().__init__(msg, strategy=strategy, available_strategies=available_strategies or [])


class ChunkingValidationError(ChunkingError):
    """Raised when input validation fails (e.g., empty or invalid text)."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, **kwargs)


class ChunkingProcessingError(ChunkingError):
    """Raised when chunking processing fails (e.g., parsing error)."""

    def __init__(self, message: str, original_error: Exception | None = None, **kwargs):
        super().__init__(message, **kwargs)
        self.original_error = original_error
        if original_error:
            self.metadata["original_error_type"] = type(original_error).__name__
            self.metadata["original_error_message"] = str(original_error)
