"""Data models for code storage operations.

Provides structured data classes to replace multi-parameter function signatures.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CodeExample:
    """Represents a single code example with metadata.

    Attributes:
        url: Source URL or identifier
        chunk_number: Chunk/index number
        code: The code content
        summary: Generated summary (optional)
        metadata: Additional metadata dict
    """

    url: str
    chunk_number: int
    code: str
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CodeExampleBatch:
    """Represents a batch of code examples for storage.

    Replaces the 13-parameter add_code_examples_to_supabase function signature.
    """

    examples: list[CodeExample]
    batch_size: int = 20
    url_to_full_document: dict[str, str] | None = None
    progress_callback: Callable | None = None
    provider: str | None = None
    embedding_provider: str | None = None

    def __post_init__(self):
        """Validate batch after creation."""
        if not self.examples:
            raise ValueError("Batch must contain at least one code example")

    @property
    def urls(self) -> list[str]:
        """Get list of URLs from examples."""
        return [ex.url for ex in self.examples]

    @property
    def chunk_numbers(self) -> list[int]:
        """Get list of chunk numbers from examples."""
        return [ex.chunk_number for ex in self.examples]

    @property
    def code_contents(self) -> list[str]:
        """Get list of code contents from examples."""
        return [ex.code for ex in self.examples]

    @property
    def summaries(self) -> list[str]:
        """Get list of summaries from examples."""
        return [ex.summary for ex in self.examples]

    @property
    def metadatas(self) -> list[dict[str, Any]]:
        """Get list of metadata from examples."""
        return [ex.metadata for ex in self.examples]


@dataclass
class SummaryResult:
    """Result of code summarization.

    Attributes:
        example_name: Generated name for the code example
        summary: Generated summary text
        is_fallback: Whether this is a fallback result
        error_message: Error message if generation failed
    """

    example_name: str
    summary: str
    is_fallback: bool = False
    error_message: str = ""

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary format."""
        return {
            "example_name": self.example_name,
            "summary": self.summary,
        }


@dataclass
class BatchSummaryResult:
    """Result of batch summarization operation.

    Attributes:
        summaries: List of SummaryResult objects
        success_count: Number of successful summaries
        failure_count: Number of failed summaries
        total_duration_ms: Total processing time in milliseconds
    """

    summaries: list[SummaryResult]
    success_count: int = 0
    failure_count: int = 0
    total_duration_ms: float = 0.0

    def __post_init__(self):
        """Calculate counts after creation."""
        if not self.summaries:
            return
        self.success_count = sum(1 for s in self.summaries if not s.error_message)
        self.failure_count = len(self.summaries) - self.success_count


@dataclass
class CodeBlock:
    """Represents a code block found in a document.

    Attributes:
        content: The code content
        language: Detected programming language
        start_line: Start line number in source
        end_line: End line number in source
        context: Surrounding text for context
    """

    content: str
    language: str = ""
    start_line: int = 0
    end_line: int = 0
    context: str = ""

    @property
    def line_count(self) -> int:
        """Number of lines in the code block."""
        return self.content.count("\n") + 1


@dataclass
class CodeExtractionResult:
    """Result of code extraction from a document.

    Attributes:
        blocks: List of extracted code blocks
        language: Detected primary language
        total_blocks: Total number of blocks found
    """

    blocks: list[CodeBlock]
    language: str = ""
    total_blocks: int = 0

    def __post_init__(self):
        """Calculate total blocks after creation."""
        self.total_blocks = len(self.blocks)


@dataclass
class StorageConfig:
    """Configuration for code storage operations.

    Attributes:
        use_contextual_embeddings: Whether to use contextual embeddings
        batch_size: Batch size for operations
        max_workers: Maximum parallel workers
        llm_timeout: LLM request timeout in seconds
        max_retries: Maximum retry attempts
    """

    use_contextual_embeddings: bool = False
    batch_size: int = 20
    max_workers: int = 3
    llm_timeout: float = 60.0
    max_retries: int = 2

    @classmethod
    async def from_settings(cls) -> "StorageConfig":
        """Create config from application settings."""
        from .config import (
            get_batch_size,
            get_llm_timeout,
            get_max_retries,
            get_max_workers,
            use_contextual_embeddings,
        )

        return cls(
            use_contextual_embeddings=await use_contextual_embeddings(),
            batch_size=await get_batch_size(),
            max_workers=await get_max_workers(),
            llm_timeout=await get_llm_timeout(),
            max_retries=await get_max_retries(),
        )
