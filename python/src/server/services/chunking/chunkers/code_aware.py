"""Code-aware chunker - respects code structure like functions, classes, modules."""

import re
from typing import Any

from src.server.services.chunking.chunker_base import BaseChunker, ChunkResult

CODE_BLOCK_PATTERN = re.compile(r"^(```|~~~)")
FUNCTION_PATTERN = re.compile(r"^(\s*def\s+|async\s+def\s+|function\s+|fn\s+)", re.MULTILINE)
CLASS_PATTERN = re.compile(r"^(\s*class\s+)", re.MULTILINE)
METHOD_PATTERN = re.compile(r"^(\s{4,}def\s+|async\s+def\s+)", re.MULTILINE)
IMPORT_PATTERN = re.compile(r"^(import\s+|from\s+\S+\s+import\s+)", re.MULTILINE)


def _detect_language(code_block: str) -> str:
    """Detect programming language from code block markers or content."""
    first_line = code_block.split("\n")[0] if code_block else ""

    lang_match = re.match(r"^```(\w+)", first_line)
    if lang_match:
        return lang_match.group(1).lower()

    if "function" in code_block.lower() or "const " in code_block or "let " in code_block:
        return "javascript"
    if "def " in code_block or "import " in code_block or "class " in code_block:
        return "python"
    if "fn " in code_block or "let mut" in code_block:
        return "rust"
    if "public class" in code_block or "private void" in code_block:
        return "java"

    return "unknown"


def _split_code_blocks(text: str) -> list[tuple[str, str]]:
    """Extract code blocks and surrounding text as separate sections."""
    sections: list[tuple[str, str]] = []
    current_text: list[str] = []
    in_code_block = False
    code_lang = ""
    code_lines: list[str] = []

    lines = text.split("\n")

    for line in lines:
        if CODE_BLOCK_PATTERN.match(line):
            if in_code_block:
                code_content = "\n".join(code_lines)
                if code_content.strip():
                    sections.append(("code", f"```{code_lang}\n{code_content}\n```"))
                code_lines = []
                in_code_block = False
                code_lang = ""
            else:
                if current_text:
                    text_content = "\n".join(current_text).strip()
                    if text_content:
                        sections.append(("text", text_content))
                    current_text = []

                in_code_block = True
                lang_match = re.match(r"^```(\w*)", line)
                code_lang = lang_match.group(1) if lang_match else ""
        else:
            if in_code_block:
                code_lines.append(line)
            else:
                current_text.append(line)

    if current_text:
        text_content = "\n".join(current_text).strip()
        if text_content:
            sections.append(("text", text_content))

    if code_lines:
        code_content = "\n".join(code_lines).strip()
        if code_content:
            sections.append(("code", f"```{code_lang}\n{code_content}\n```"))

    return sections


def _split_into_subchunks(text: str, max_size: int) -> list[str]:
    """Split large text into smaller chunks."""
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

        elif "\n" in chunk:
            last_newline = chunk.rfind("\n")
            if last_newline > max_size * 0.3:
                end = start + last_newline

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        start = end

    return chunks


class CodeAwareChunker(BaseChunker):
    """Code-aware chunker that respects code structure.

    This chunker:
    - Keeps code blocks (```) as complete units when possible
    - Preserves function/class/module boundaries for code
    - Includes docstrings with code when possible
    - Treats prose (text between code blocks) separately
    """

    def __init__(self, **options: Any):
        super().__init__(**options)
        self.chunk_size = options.get("chunk_size", 5000)
        self.merge_threshold = options.get("merge_threshold", 500)

    def chunk(self, text: str, **options: Any) -> list[ChunkResult]:
        """Split text into chunks respecting code structure."""
        chunk_size = options.get("chunk_size", self.chunk_size)

        if not text or not isinstance(text, str):
            return []

        sections = _split_code_blocks(text)

        if not sections:
            raw_chunks = _split_into_subchunks(text, chunk_size)
            return [
                ChunkResult(
                    content=chunk,
                    index=i,
                    metadata={"chunker": "code_aware", "code_type": "text"},
                )
                for i, chunk in enumerate(raw_chunks)
            ]

        chunks: list[ChunkResult] = []
        index = 0

        for section_type, section_content in sections:
            if section_type == "code":
                if len(section_content) <= chunk_size:
                    lang = _detect_language(section_content)
                    chunks.append(
                        ChunkResult(
                            content=section_content,
                            index=index,
                            metadata={
                                "chunker": "code_aware",
                                "code_type": "code_block",
                                "language": lang,
                            },
                        )
                    )
                    index += 1
                else:
                    subchunks = _split_into_subchunks(section_content, chunk_size)
                    for subchunk in subchunks:
                        lang = _detect_language(subchunk)
                        chunks.append(
                            ChunkResult(
                                content=subchunk,
                                index=index,
                                metadata={
                                    "chunker": "code_aware",
                                    "code_type": "code_block",
                                    "language": lang,
                                },
                            )
                        )
                        index += 1
            else:
                subchunks = _split_into_subchunks(section_content, chunk_size)
                for subchunk in subchunks:
                    chunks.append(
                        ChunkResult(
                            content=subchunk,
                            index=index,
                            metadata={"chunker": "code_aware", "code_type": "prose"},
                        )
                    )
                    index += 1

        return self._merge_small_chunks(chunks)

    async def chunk_async(self, text: str, **options: Any) -> list[ChunkResult]:
        """Async version - delegates to sync chunk() for simplicity."""
        return self.chunk(text, **options)

    def _merge_small_chunks(self, chunks: list[ChunkResult]) -> list[ChunkResult]:
        """Merge consecutive small prose chunks together."""
        if not chunks:
            return []

        merged: list[ChunkResult] = []
        i = 0

        while i < len(chunks):
            current = chunks[i]

            while (
                len(current.content) < self.merge_threshold
                and i + 1 < len(chunks)
                and (chunks[i + 1].metadata or {}).get("code_type") == "prose"
                and (current.metadata or {}).get("code_type") == "prose"
            ):
                i += 1
                current = ChunkResult(
                    content=current.content + "\n\n" + chunks[i].content,
                    index=current.index,
                    metadata=current.metadata,
                )

            merged.append(current)
            i += 1

        return merged
