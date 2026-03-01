"""Chunking services for document processing.

This module provides a pluggable API for different chunking strategies.
"""

from .chunker_base import BaseChunker, ChunkResult
from .exceptions import (
    ChunkingError,
    ChunkingProcessingError,
    ChunkingStrategyError,
    ChunkingValidationError,
)
from .factory import AVAILABLE_STRATEGIES, CHUNKER_STRATEGIES, get_chunker

__all__ = [
    # Base classes
    "BaseChunker",
    "ChunkResult",
    # Exceptions
    "ChunkingError",
    "ChunkingStrategyError",
    "ChunkingValidationError",
    "ChunkingProcessingError",
    # Factory
    "get_chunker",
    "CHUNKER_STRATEGIES",
    "AVAILABLE_STRATEGIES",
]
