"""Basic chunker - wraps existing smart_chunk_text functionality."""

from typing import Any

from src.server.services.chunking.chunker_base import BaseChunker, ChunkResult


def _smart_chunk_text(text: str, chunk_size: int = 5000) -> list[str]:
    """Split text into chunks intelligently, preserving context.

    This is the existing logic from BaseStorageService.smart_chunk_text.
    """
    if not text or not isinstance(text, str):
        return []

    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = start + chunk_size

        if end >= text_length:
            chunk = text[start:].strip()
            if chunk:
                chunks.append(chunk)
            break

        chunk = text[start:end]

        code_block_pos = chunk.rfind("```")
        if code_block_pos != -1 and code_block_pos > chunk_size * 0.3:
            end = start + code_block_pos

        elif "\n\n" in chunk:
            last_break = chunk.rfind("\n\n")
            if last_break > chunk_size * 0.3:
                end = start + last_break

        elif ". " in chunk:
            last_period = chunk.rfind(". ")
            if last_period > chunk_size * 0.3:
                end = start + last_period + 1

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        start = end

    if chunks:
        combined_chunks: list[str] = []
        i = 0
        while i < len(chunks):
            current = chunks[i]

            while len(current) < 200 and i + 1 < len(chunks):
                i += 1
                current = current + "\n\n" + chunks[i]

            combined_chunks.append(current)
            i += 1

        chunks = combined_chunks

    return chunks


class BasicChunker(BaseChunker):
    """Basic chunker that wraps the existing smart_chunk_text functionality.

    This chunker:
    - Preserves code blocks (```) as complete units when possible
    - Prefers to break at paragraph boundaries (\\n\\n)
    - Falls back to sentence boundaries (. ) if needed
    - Only splits mid-content when absolutely necessary
    """

    def __init__(self, **options: Any):
        super().__init__(**options)
        self.chunk_size = options.get("chunk_size", 5000)

    def chunk(self, text: str, **options: Any) -> list[ChunkResult]:
        """Split text into chunks using the existing smart_chunk_text logic."""
        chunk_size = options.get("chunk_size", self.chunk_size)
        raw_chunks = _smart_chunk_text(text, chunk_size=chunk_size)

        return [
            ChunkResult(
                content=chunk,
                index=i,
                metadata={"chunker": "basic", "char_count": len(chunk)},
            )
            for i, chunk in enumerate(raw_chunks)
        ]

    async def chunk_async(self, text: str, **options: Any) -> list[ChunkResult]:
        """Async version - delegates to sync chunk() for simplicity."""
        return self.chunk(text, **options)
