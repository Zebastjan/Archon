"""JSON extraction utilities for LLM responses.

Handles extracting and cleaning JSON from various LLM output formats.
"""

from ....config.logfire_config import search_logger
from ...llm_provider_service import (
    extract_json_from_reasoning,
    synthesize_json_from_reasoning,
)


# Common reasoning text starters to detect non-JSON responses
REASONING_STARTERS = [
    "okay, let's see",
    "okay, let me",
    "let me think",
    "first, i need to",
    "looking at this",
    "i need to",
    "analyzing",
    "let me work through",
    "thinking about",
    "let me see",
]


def is_reasoning_text_response(text: str) -> bool:
    """Detect if response is reasoning text rather than direct JSON.

    Args:
        text: The raw LLM response text

    Returns:
        True if the text appears to be reasoning rather than JSON
    """
    if not text or len(text) < 20:
        return False

    text_lower = text.lower().strip()

    # Check for XML-style thinking tags (common in models with extended thinking)
    if text_lower.startswith("<thinking>") or "<thinking>" in text_lower[:100]:
        return True

    # Check if it's clearly not JSON (starts with reasoning text)
    starts_with_reasoning = any(text_lower.startswith(starter) for starter in REASONING_STARTERS)

    # Check if it lacks immediate JSON structure
    lacks_immediate_json = not text_lower.lstrip().startswith("{")

    return starts_with_reasoning and lacks_immediate_json


def clean_json_response(raw_response: str) -> str:
    """Clean JSON response by removing markdown fences and extra text.

    Args:
        raw_response: Raw response potentially wrapped in markdown

    Returns:
        Cleaned JSON string
    """
    if not raw_response:
        return raw_response

    cleaned = raw_response.strip()

    # Remove markdown code fences
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        # Drop opening fence
        lines = lines[1:]
        # Drop closing fence if present
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    # Trim any leading/trailing text outside the outermost JSON braces
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end >= start:
        cleaned = cleaned[start : end + 1]

    return cleaned.strip()


def extract_json_payload(raw_response: str, context_code: str = "", language: str = "") -> str:
    """Extract JSON payload from LLM response with multiple fallback strategies.

    Args:
        raw_response: Raw LLM response text
        context_code: Optional context code for reasoning extraction
        language: Optional language hint for reasoning extraction

    Returns:
        Extracted JSON string (or minimal valid JSON on failure)
    """
    if not raw_response:
        return raw_response

    cleaned = raw_response.strip()

    # Check if this looks like reasoning text first
    if is_reasoning_text_response(cleaned):
        # Try intelligent extraction from reasoning text with context
        extracted = extract_json_from_reasoning(cleaned, context_code, language)
        if extracted:
            return extracted

        # synthesize_json_from_reasoning may return nothing; synthesize a fallback JSON if so
        fallback_json = synthesize_json_from_reasoning("", context_code, language)
        if fallback_json:
            return fallback_json

        # If all else fails, return a minimal valid JSON object to avoid downstream errors
        search_logger.warning("Could not extract JSON from reasoning text, using fallback")
        return '{"example_name": "Code Example", "summary": "Code example extracted from context."}'

    # Clean markdown fences and extract JSON
    return clean_json_response(cleaned)


def parse_json_safely(json_str: str) -> dict | None:
    """Safely parse JSON string with error handling.

    Args:
        json_str: JSON string to parse

    Returns:
        Parsed dict or None if parsing fails
    """
    if not json_str or not json_str.strip():
        return None

    import json

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        search_logger.debug(f"JSON parse error: {e}")
        return None


def extract_code_snippets(text: str) -> list[str]:
    """Extract code snippets from text using regex patterns.

    Args:
        text: Text potentially containing code snippets

    Returns:
        List of extracted code snippets
    """
    import re

    snippets = []

    # Match markdown code blocks
    code_block_pattern = r"```(?:\w+)?\n(.*?)\n```"
    for match in re.finditer(code_block_pattern, text, re.DOTALL):
        snippet = match.group(1).strip()
        if snippet:
            snippets.append(snippet)

    # Match inline code
    inline_pattern = r"`([^`]+)`"
    for match in re.finditer(inline_pattern, text):
        snippet = match.group(1).strip()
        if snippet and len(snippet) > 10:  # Only substantial snippets
            snippets.append(snippet)

    return snippets


def truncate_text(text: str, max_length: int = 500) -> str:
    """Truncate text to maximum length with ellipsis.

    Args:
        text: Text to truncate
        max_length: Maximum length before truncation

    Returns:
        Truncated text
    """
    if not text or len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."
