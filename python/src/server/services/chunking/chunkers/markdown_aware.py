"""Markdown-aware chunker - respects Markdown heading structure."""

import re
from typing import Any

from src.server.services.chunking.chunker_base import BaseChunker, ChunkResult

HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
CODE_BLOCK_PATTERN = re.compile(r"^```\w*\s*$", re.MULTILINE)


def _extract_heading_level(heading_text: str) -> int:
    """Extract the heading level from heading text."""
    match = HEADING_PATTERN.match(heading_text)
    if match:
        return len(match.group(1))
    return 1


def _build_section_path(headings: list[str]) -> list[str]:
    """Build a section path from a list of headings."""
    return headings


def _split_by_headings(text: str) -> list[tuple[str, str, int]]:
    """Split text by Markdown headings, returning (section_title, content, level) tuples."""
    if not text:
        return []

    sections = []
    current_headings: list[str] = []
    current_content_lines: list[str] = []
    current_level = 0

    lines = text.split("\n")

    for line in lines:
        heading_match = HEADING_PATTERN.match(line)

        if heading_match:
            if current_content_lines:
                content = "\n".join(current_content_lines).strip()
                if content:
                    section_title = current_headings[-1] if current_headings else "Introduction"
                    sections.append((section_title, content, current_level))

            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()

            while current_headings and _extract_heading_level(current_headings[-1]) >= level:
                current_headings.pop()

            current_headings.append(title)
            current_level = level
            current_content_lines = []
        else:
            current_content_lines.append(line)

    if current_content_lines:
        content = "\n".join(current_content_lines).strip()
        if content:
            section_title = current_headings[-1] if current_headings else "Introduction"
            sections.append((section_title, content, current_level))

    if sections and sections[0][2] == 0:
        return []

    return sections


def _split_into_subchunks(text: str, max_size: int) -> list[str]:
    """Split large sections into smaller chunks."""
    if len(text) <= max_size:
        return [text] if text.strip() else []

    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = start + max_size

        if end >= text_length:
            chunk = text[start:].strip()
            if chunk:
                chunks.append(chunk)
            break

        chunk = text[start:end]

        if "\n\n" in chunk:
            last_break = chunk.rfind("\n\n")
            if last_break > max_size * 0.3:
                end = start + last_break

        elif ". " in chunk:
            last_period = chunk.rfind(". ")
            if last_period > max_size * 0.3:
                end = start + last_period + 1

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        start = end

    return chunks


class MarkdownAwareChunker(BaseChunker):
    """Markdown-aware chunker that respects heading structure.

    This chunker:
    - Respects Markdown headings (# ## ###) as section boundaries
    - Never creates chunks that span unrelated top-level sections
    - Stores section_path in metadata for retrieval help
    - Falls back to paragraph/sentence splitting for large sections
    """

    def __init__(self, **options: Any):
        super().__init__(**options)
        self.chunk_size = options.get("chunk_size", 5000)
        self.merge_threshold = options.get("merge_threshold", 500)

    def chunk(self, text: str, **options: Any) -> list[ChunkResult]:
        """Split text into chunks respecting Markdown structure."""
        chunk_size = options.get("chunk_size", self.chunk_size)

        if not text or not isinstance(text, str):
            return []

        sections = _split_by_headings(text)

        if not sections:
            raw_chunks = _split_into_subchunks(text, chunk_size)
            return [
                ChunkResult(
                    content=chunk,
                    index=i,
                    order_index=i,
                    element_type="paragraph",
                    section_path=[],
                    section_title=None,
                    metadata={"chunker": "markdown_aware"},
                )
                for i, chunk in enumerate(raw_chunks)
            ]

        chunks: list[ChunkResult] = []
        index = 0
        current_headings: list[str] = []

        for section_title, section_content, level in sections:
            if level > 0:
                while len(current_headings) >= level:
                    current_headings.pop()
                current_headings.append(section_title)

            section_path = _build_section_path(current_headings) if current_headings else []

            subchunks = _split_into_subchunks(section_content, chunk_size)

            for subchunk in subchunks:
                chunks.append(
                    ChunkResult(
                        content=subchunk,
                        index=index,
                        order_index=index,
                        section_path=section_path,
                        section_title=section_title,
                        element_type="paragraph",
                        metadata={
                            "chunker": "markdown_aware",
                            "heading_level": level,
                        },
                    )
                )
                index += 1

        return self._merge_small_chunks(chunks)

    async def chunk_async(self, text: str, **options: Any) -> list[ChunkResult]:
        """Async version - delegates to sync chunk() for simplicity."""
        return self.chunk(text, **options)

    def _merge_small_chunks(self, chunks: list[ChunkResult]) -> list[ChunkResult]:
        """Merge consecutive small chunks that belong to the same section."""
        if not chunks:
            return []

        merged: list[ChunkResult] = []
        i = 0

        while i < len(chunks):
            current = chunks[i]

            while len(current.content) < self.merge_threshold and i + 1 < len(chunks):
                next_chunk = chunks[i + 1]
                if current.section_path == next_chunk.section_path:
                    i += 1
                    current = ChunkResult(
                        content=current.content + "\n\n" + next_chunk.content,
                        index=current.index,
                        order_index=current.order_index,
                        section_path=current.section_path,
                        section_title=current.section_title,
                        element_type=current.element_type,
                        metadata=current.metadata,
                    )
                else:
                    break

            merged.append(current)
            i += 1

        return merged
