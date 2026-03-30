"""Code Storage Service - Split into modular components.

This package provides code extraction and storage functionality,
organized into logical modules:

- config: Configuration and settings management
- extraction: JSON extraction utilities for LLM responses
- summarization: LLM-based code summarization
- models: Data models for code storage operations
- blocks: Code block extraction and deduplication
- database: Database operations for code examples
"""

from .blocks import (
    calculate_code_similarity,
    deduplicate_code_blocks,
    extract_code_blocks,
    normalize_code_for_comparison,
)
from .config import (
    CodeStorageConfig,
    get_batch_size,
    get_embedding_batch_size,
    get_llm_timeout,
    get_max_retries,
    get_max_workers,
    use_contextual_embeddings,
)
from .database import (
    add_code_examples_to_supabase,
    delete_code_examples_for_document,
    get_code_examples_for_document,
)
from .extraction import (
    extract_code_snippets,
    extract_json_payload,
    is_reasoning_text_response,
    parse_json_safely,
    truncate_text,
)
from .models import (
    BatchSummaryResult,
    CodeBlock,
    CodeExample,
    CodeExampleBatch,
    CodeExtractionResult,
    StorageConfig,
    SummaryResult,
)
from .summarization import (
    generate_code_summary,
    generate_code_summaries_batch,
    validate_summary_quality,
)

__all__ = [
    # Config
    "CodeStorageConfig",
    "get_batch_size",
    "get_max_workers",
    "get_llm_timeout",
    "get_max_retries",
    "use_contextual_embeddings",
    "get_embedding_batch_size",
    # Extraction
    "extract_json_payload",
    "is_reasoning_text_response",
    "parse_json_safely",
    "extract_code_snippets",
    "truncate_text",
    # Summarization
    "generate_code_summary",
    "generate_code_summaries_batch",
    "validate_summary_quality",
    # Models
    "CodeExample",
    "CodeExampleBatch",
    "CodeBlock",
    "SummaryResult",
    "BatchSummaryResult",
    "CodeExtractionResult",
    "StorageConfig",
    # Blocks
    "extract_code_blocks",
    "normalize_code_for_comparison",
    "calculate_code_similarity",
    "deduplicate_code_blocks",
    # Database
    "add_code_examples_to_supabase",
    "get_code_examples_for_document",
    "delete_code_examples_for_document",
]
