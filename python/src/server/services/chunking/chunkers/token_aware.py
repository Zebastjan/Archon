"""Token-aware chunker - chunks based on token count with overlap."""

import asyncio
from collections.abc import Callable

from src.server.services.chunking.chunker_base import BaseChunker, ChunkResult


def estimate_tokens(text: str) -> int:
    """Estimate token count using simple word-based approximation.

    This is a rough approximation: ~4 characters per token on average.
    For more accurate counting, a proper tokenizer would be needed.
    """
    return len(text) // 4


class TokenAwareChunker(BaseChunker):
    """Token-aware chunker that respects token limits with optional overlap.

    This chunker:
    - Uses token estimates instead of character counts
    - Breaks at paragraph/sentence boundaries when possible
    - Supports overlap between chunks (10-20% recommended)
    - Stores token_estimate in each ChunkResult
    """

    def __init__(self, **options):
        super().__init__(**options)
        self.target_tokens = options.get("target_tokens", 512)
        self.overlap_tokens = options.get("overlap_tokens", 50)
        self.token_estimator = options.get("token_estimator", estimate_tokens)

    def chunk(self, text: str, **options) -> list[ChunkResult]:
        """Split text into token-aware chunks."""
        target = options.get("target_tokens", self.target_tokens)
        overlap = options.get("overlap_tokens", self.overlap_tokens)
        estimator = options.get("token_estimator", self.token_estimator)

        if not text or not isinstance(text, str):
            return []

        chunks: list[ChunkResult] = []
        start = 0
        text_length = len(text)
        index = 0

        while start < text_length:
            end = start + (target * 4)

            if end >= text_length:
                chunk_text = text[start:].strip()
                if chunk_text:
                    chunks.append(
                        ChunkResult(
                            content=chunk_text,
                            index=index,
                            order_index=index,
                            element_type="paragraph",
                            token_estimate=estimator(chunk_text),
                            metadata={"chunker": "token_aware", "target_tokens": target},
                        )
                    )
                break

            chunk_text = text[start:end]

            if "\n\n" in chunk_text:
                last_break = chunk_text.rfind("\n\n")
                if last_break > (target * 4) * 0.3:
                    end = start + last_break
                    chunk_text = text[start:end].strip()
            elif ". " in chunk_text:
                last_period = chunk_text.rfind(". ")
                if last_period > (target * 4) * 0.3:
                    end = start + last_period + 1
                    chunk_text = text[start:end].strip()

            if chunk_text:
                chunks.append(
                    ChunkResult(
                        content=chunk_text,
                        index=index,
                        order_index=index,
                        element_type="paragraph",
                        token_estimate=estimator(chunk_text),
                        metadata={"chunker": "token_aware", "target_tokens": target},
                    )
                )
                index += 1

            chunk_size = target * 4
            overlap_chars = min(overlap * 4, chunk_size // 2) if overlap > 0 else 0
            start = end - overlap_chars if overlap > 0 else end

        return self._merge_small_chunks(chunks)

    def _merge_small_chunks(self, chunks: list[ChunkResult], min_size: int = 200) -> list[ChunkResult]:
        """Merge consecutive small chunks together."""
        if not chunks:
            return []

        merged: list[ChunkResult] = []
        i = 0

        while i < len(chunks):
            current = chunks[i]

            while len(current.content) < min_size and i + 1 < len(chunks):
                i += 1
                current = ChunkResult(
                    content=current.content + "\n\n" + chunks[i].content,
                    index=current.index,
                    order_index=current.order_index,
                    element_type=current.element_type,
                    token_estimate=current.token_estimate,
                    metadata=current.metadata,
                )

            merged.append(current)
            i += 1

        return merged

    async def chunk_async(
        self,
        text: str,
        progress_callback: Callable | None = None,
        **options,
    ) -> list[ChunkResult]:
        """Async version with optional progress reporting."""
        if len(text) > 50000:
            loop = asyncio.get_event_loop()
            chunks = await loop.run_in_executor(None, self.chunk, text, **options)
        else:
            chunks = self.chunk(text, **options)

        if progress_callback:
            await progress_callback("Text chunking completed", 100)

        return chunks
