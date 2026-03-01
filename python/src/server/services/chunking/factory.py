"""Factory for creating chunker instances."""

from src.server.services.chunking.chunker_base import BaseChunker
from src.server.services.chunking.chunkers import (
    BasicChunker,
    CodeAwareChunker,
    DoclingHierarchicalChunker,
    DoclingHybridChunker,
    MarkdownAwareChunker,
    TokenAwareChunker,
)
from src.server.services.chunking.exceptions import ChunkingStrategyError

CHUNKER_STRATEGIES: dict[str, type[BaseChunker]] = {
    "basic": BasicChunker,
    "token_aware": TokenAwareChunker,
    "markdown_aware": MarkdownAwareChunker,
    "code_aware": CodeAwareChunker,
    "docling_hierarchical": DoclingHierarchicalChunker,
    "docling_hybrid": DoclingHybridChunker,
}

AVAILABLE_STRATEGIES = list(CHUNKER_STRATEGIES.keys())


def get_chunker(strategy: str, **options) -> BaseChunker:
    """Get a chunker instance by strategy name.

    Args:
        strategy: The chunking strategy name ('basic', 'token_aware').
        **options: Configuration options passed to the chunker.

    Returns:
        An instance of the requested chunker.

    Raises:
        ChunkingStrategyError: If the strategy is not recognized.
    """
    strategy_lower = strategy.lower()

    if strategy_lower not in CHUNKER_STRATEGIES:
        raise ChunkingStrategyError(strategy, AVAILABLE_STRATEGIES)

    chunker_class = CHUNKER_STRATEGIES[strategy_lower]
    return chunker_class(**options)


__all__ = ["get_chunker", "CHUNKER_STRATEGIES", "AVAILABLE_STRATEGIES"]
