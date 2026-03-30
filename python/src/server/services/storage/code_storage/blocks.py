"""Code block extraction and processing utilities.

Handles extraction of code blocks from markdown content, deduplication,
and similarity comparison.
"""

import re
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any

from ....config.logfire_config import search_logger


def extract_code_blocks(markdown_content: str, min_length: int = None) -> list[dict[str, Any]]:
    """Extract code blocks from markdown content along with context.

    Args:
        markdown_content: Markdown text containing code blocks
        min_length: Minimum character length for code blocks (default: from env or 50)

    Returns:
        List of code block dictionaries with code, language, context, and metadata
    """
    if not markdown_content:
        return []

    # Default minimum length
    if min_length is None:
        import os

        min_length = int(os.getenv("CODE_BLOCK_MIN_LENGTH", "50"))

    blocks = []
    lines = markdown_content.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check for code block start
        fence_match = re.match(r"^(```|~~~)(\w*)\s*$", line)
        if fence_match:
            fence = fence_match.group(1)
            language = fence_match.group(2) or "text"
            code_lines = []
            i += 1

            # Collect code until closing fence
            while i < len(lines):
                if lines[i].strip().startswith(fence):
                    i += 1
                    break
                code_lines.append(lines[i])
                i += 1

            code = "\n".join(code_lines).strip()

            # Skip if too short
            if len(code) < min_length:
                continue

            # Get context before
            context_before = []
            for j in range(max(0, i - len(code_lines) - 3), i - len(code_lines)):
                if j >= 0 and not lines[j].strip().startswith(fence):
                    context_before.append(lines[j])

            # Get context after
            context_after = []
            for j in range(i, min(len(lines), i + 3)):
                if j < len(lines) and not lines[j].strip().startswith(fence):
                    context_after.append(lines[j])

            blocks.append({
                "code": code,
                "language": language.lower(),
                "context_before": "\n".join(context_before).strip(),
                "context_after": "\n".join(context_after).strip(),
                "line_number": i - len(code_lines),
                "char_count": len(code),
            })
        else:
            i += 1

    search_logger.debug(f"Extracted {len(blocks)} code blocks from content")
    return blocks


def normalize_code_for_comparison(code: str) -> str:
    """Normalize code for similarity comparison by removing version-specific variations.

    Args:
        code: Raw code string

    Returns:
        Normalized code string
    """
    if not code:
        return ""

    normalized = code

    # Remove comments
    normalized = re.sub(r"#.*$", "", normalized, flags=re.MULTILINE)
    normalized = re.sub(r"//.*$", "", normalized, flags=re.MULTILINE)
    normalized = re.sub(r"/\*.*?\*/", "", normalized, flags=re.DOTALL)

    # Remove string literals (keep structure)
    normalized = re.sub(r'"(?:[^"\\]|\\.)*"', '""', normalized)
    normalized = re.sub(r"'(?:[^'\\]|\\.)*'", "''", normalized)

    # Normalize whitespace
    normalized = re.sub(r"\s+", " ", normalized)

    # Normalize variable names (simple patterns)
    normalized = re.sub(r"\b[a-z_][a-z0-9_]*\b", "VAR", normalized, flags=re.IGNORECASE)

    # Remove leading/trailing whitespace
    normalized = normalized.strip().lower()

    return normalized


def calculate_code_similarity(code1: str, code2: str) -> float:
    """Calculate similarity between two code strings using normalized comparison.

    Args:
        code1: First code string
        code2: Second code string

    Returns:
        Similarity ratio between 0.0 and 1.0
    """
    if not code1 or not code2:
        return 0.0

    # Normalize both codes
    norm1 = normalize_code_for_comparison(code1)
    norm2 = normalize_code_for_comparison(code2)

    if not norm1 or not norm2:
        return 0.0

    # Use SequenceMatcher for similarity
    similarity = SequenceMatcher(None, norm1, norm2).ratio()

    return similarity


def _select_best_code_variant(similar_blocks: list[dict[str, Any]]) -> dict[str, Any]:
    """Select the best variant from a list of similar code blocks.

    Prefers blocks with:
    1. More context
    2. Proper language detection
    3. Better formatting
    4. Longer content (up to a point)

    Args:
        similar_blocks: List of similar code block dictionaries

    Returns:
        The best code block dictionary
    """
    if not similar_blocks:
        return {}

    if len(similar_blocks) == 1:
        return similar_blocks[0]

    best_block = None
    best_score = -1

    for block in similar_blocks:
        score = 0

        # Prefer blocks with context
        if block.get("context_before"):
            score += 10
        if block.get("context_after"):
            score += 10

        # Prefer specific languages over "text"
        language = block.get("language", "text")
        if language != "text":
            score += 20

        # Prefer reasonable length (not too short, not too long)
        char_count = block.get("char_count", 0)
        if 100 <= char_count <= 2000:
            score += 15
        elif char_count > 2000:
            score += 5  # Still okay but very long
        elif char_count >= 50:
            score += char_count // 10  # Partial credit

        # Prefer blocks with proper formatting (indentation)
        code = block.get("code", "")
        if "\n" in code and any(line.startswith("  ") or line.startswith("\t") for line in code.split("\n")):
            score += 10

        if score > best_score:
            best_score = score
            best_block = block

    return best_block or similar_blocks[0]


def deduplicate_code_blocks(blocks: list[dict[str, Any]], similarity_threshold: float = 0.85) -> list[dict[str, Any]]:
    """Deduplicate code blocks based on similarity.

    Args:
        blocks: List of code block dictionaries
        similarity_threshold: Similarity threshold for deduplication (0.0-1.0)

    Returns:
        Deduplicated list of code blocks
    """
    if not blocks:
        return []

    if len(blocks) == 1:
        return blocks

    # Group by language first
    by_language: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for block in blocks:
        lang = block.get("language", "text")
        by_language[lang].append(block)

    deduplicated = []

    for lang, lang_blocks in by_language.items():
        # Compare each block with others in same language
        used_indices = set()

        for i, block1 in enumerate(lang_blocks):
            if i in used_indices:
                continue

            # Find similar blocks
            similar = [block1]
            used_indices.add(i)

            for j, block2 in enumerate(lang_blocks):
                if j in used_indices or i == j:
                    continue

                code1 = block1.get("code", "")
                code2 = block2.get("code", "")

                similarity = calculate_code_similarity(code1, code2)

                if similarity >= similarity_threshold:
                    similar.append(block2)
                    used_indices.add(j)

            # Select best from similar group
            best = _select_best_code_variant(similar)
            if best:
                deduplicated.append(best)

    search_logger.debug(f"Deduplicated {len(blocks)} blocks to {len(deduplicated)} unique blocks")
    return deduplicated
