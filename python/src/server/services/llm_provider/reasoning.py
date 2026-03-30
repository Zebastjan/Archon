"""
LLM Provider Reasoning Module

Provides reasoning model support and message extraction utilities.
"""

import json
import re
from typing import Any

from ...config.logfire_config import get_logger

logger = get_logger(__name__)


def is_reasoning_model(model_name: str) -> bool:
    """
    Unified check for reasoning models across providers.

    Normalizes vendor prefixes (openai/, openrouter/, x-ai/, deepseek/) before checking
    known reasoning families (OpenAI GPT-5, o1, o3; xAI Grok; DeepSeek-R; etc.).
    """
    if not model_name:
        return False

    model_lower = model_name.lower()

    # Normalize vendor prefixes (e.g., openai/gpt-5-nano, openrouter/x-ai/grok-4)
    if "/" in model_lower:
        parts = model_lower.split("/")
        # Drop known vendor prefixes while keeping the final model identifier
        known_prefixes = {"openai", "openrouter", "x-ai", "deepseek", "anthropic"}
        filtered_parts = [part for part in parts if part not in known_prefixes]
        if filtered_parts:
            model_lower = filtered_parts[-1]
        else:
            model_lower = parts[-1]

    if ":" in model_lower:
        model_lower = model_lower.split(":", 1)[-1]

    reasoning_prefixes = (
        "gpt-5",
        "o1",
        "o3",
        "o4",
        "grok",
        "deepseek-r",
        "deepseek-reasoner",
        "deepseek-chat-r",
    )

    return model_lower.startswith(reasoning_prefixes)


def _extract_reasoning_strings(value: Any) -> list[str]:
    """Convert reasoning payload fragments into plain-text strings."""
    if value is None:
        return []

    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []

    if isinstance(value, list | tuple | set):
        collected: list[str] = []
        for item in value:
            collected.extend(_extract_reasoning_strings(item))
        return collected

    if isinstance(value, dict):
        candidates = []
        for key in ("text", "summary", "content", "message", "value"):
            if value.get(key):
                candidates.extend(_extract_reasoning_strings(value[key]))
        # Some providers nest reasoning parts under "parts"
        if value.get("parts"):
            candidates.extend(_extract_reasoning_strings(value["parts"]))
        return candidates

    # Handle pydantic-style objects with attributes
    for attr in ("text", "summary", "content", "value"):
        if hasattr(value, attr):
            attr_value = getattr(value, attr)
            if attr_value:
                return _extract_reasoning_strings(attr_value)

    return []


def _get_message_attr(message: Any, attribute: str) -> Any:
    """Safely access message attributes that may be dict keys or properties."""
    if hasattr(message, attribute):
        return getattr(message, attribute)
    if isinstance(message, dict):
        return message.get(attribute)
    return None


def extract_message_text(choice: Any) -> tuple[str, str, bool]:
    """Extract primary content and reasoning text from a chat completion choice."""
    if not choice:
        return "", "", False

    message = _get_message_attr(choice, "message")
    if message is None:
        return "", "", False

    raw_content = _get_message_attr(message, "content")
    content_text = raw_content.strip() if isinstance(raw_content, str) else ""

    reasoning_fragments: list[str] = []

    # Extract reasoning_content (OpenAI o1/o3, Grok)
    reasoning_content = _get_message_attr(message, "reasoning_content")
    if reasoning_content:
        reasoning_fragments.extend(_extract_reasoning_strings(reasoning_content))

    # Fallback: reasoning or reasoning_text
    if not reasoning_fragments:
        for key in ("reasoning", "reasoning_text"):
            val = _get_message_attr(message, key)
            if val:
                reasoning_fragments.extend(_extract_reasoning_strings(val))
                break

    # Combine reasoning fragments
    reasoning_text = "\n".join(reasoning_fragments).strip()

    has_reasoning = bool(reasoning_text)

    return content_text, reasoning_text, has_reasoning


def _is_reasoning_text(text: str) -> bool:
    """Check if text appears to be reasoning content."""
    if not text:
        return False

    reasoning_indicators = [
        r"I need to",
        r"Let me",
        r"First,",
        r"Step \d+",
        r"Reasoning:",
        r"Thinking:",
    ]

    for indicator in reasoning_indicators:
        if re.search(indicator, text, re.IGNORECASE):
            return True

    return False


def extract_json_from_reasoning(reasoning_text: str, context_code: str = "", language: str = "") -> str:
    """
    Extract JSON from reasoning text using multiple strategies.

    Args:
        reasoning_text: The reasoning content that may contain JSON
        context_code: Optional code context for synthesis hints
        language: Optional language for synthesis (e.g., 'python', 'json')

    Returns:
        Extracted or synthesized JSON string
    """
    if not reasoning_text:
        return synthesize_json_from_reasoning("", context_code, language)

    # Strategy 1: Look for JSON code blocks
    json_patterns = [
        r"```(?:json)?\s*\n(.*?)\n```",  # Markdown code blocks
        r"```(.*?)```",  # Generic code blocks
        r"\{[^{}]*\}",  # Simple JSON objects
        r"\[[^\[\]]*\]",  # Simple JSON arrays
    ]

    for pattern in json_patterns:
        matches = re.findall(pattern, reasoning_text, re.DOTALL)
        for match in matches:
            try:
                # Validate it's valid JSON
                json.loads(match.strip())
                return match.strip()
            except json.JSONDecodeError:
                continue

    # Strategy 2: Look for JSON-like structures in the text
    # Try to find balanced braces
    brace_start = reasoning_text.find("{")
    if brace_start >= 0:
        brace_count = 0
        brace_end = brace_start
        for i, char in enumerate(reasoning_text[brace_start:]):
            if char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count == 0:
                    brace_end = brace_start + i + 1
                    break

        if brace_end > brace_start:
            candidate = reasoning_text[brace_start:brace_end]
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pass

    # Strategy 3: Synthesize JSON from reasoning
    return synthesize_json_from_reasoning(reasoning_text, context_code, language)


def synthesize_json_from_reasoning(reasoning_text: str, context_code: str = "", language: str = "") -> str:
    """
    Synthesize a JSON response from reasoning text.

    This is a fallback when no valid JSON is found in reasoning content.
    Creates a structured response based on the reasoning.

    Args:
        reasoning_text: The reasoning content
        context_code: Optional code context
        language: Optional language hint

    Returns:
        A synthesized JSON string
    """
    # Default synthesis for unknown contexts
    synthesis = {
        "reasoning": reasoning_text.strip() if reasoning_text else "",
        "synthesized": True,
        "context": context_code[:100] if context_code else "",
    }

    # Try to extract code blocks if present
    code_pattern = r"```(\w+)?\s*\n(.*?)\n```"
    code_matches = re.findall(code_pattern, reasoning_text, re.DOTALL)

    if code_matches:
        detected_language, code_content = code_matches[0]
        synthesis["code"] = code_content.strip()
        if detected_language:
            synthesis["language"] = detected_language

    # Try to extract numbered steps or lists
    step_pattern = r"(?:^|\n)(?:\d+\.\s*|[-*]\s*)(.+?)(?=\n(?:\d+\.\s*|[-*]\s*)|$)"
    steps = re.findall(step_pattern, reasoning_text, re.MULTILINE | re.DOTALL)
    if steps:
        synthesis["steps"] = [s.strip() for s in steps if s.strip()]

    return json.dumps(synthesis, indent=2)


def prepare_chat_completion_params(model: str, params: dict) -> dict:
    """
    Prepare parameters for chat completion based on model requirements.

    Some reasoning models (like OpenAI's o1/o3 series) use 'max_completion_tokens'
    instead of 'max_tokens'.

    Args:
        model: The model name
        params: The original parameters

    Returns:
        Modified parameters dict
    """
    if not model:
        return params

    modified_params = params.copy()

    if requires_max_completion_tokens(model):
        # Convert max_tokens to max_completion_tokens for reasoning models
        if "max_tokens" in modified_params and "max_completion_tokens" not in modified_params:
            modified_params["max_completion_tokens"] = modified_params.pop("max_tokens")

    return modified_params


def requires_max_completion_tokens(model_name: str) -> bool:
    """
    Check if a model requires max_completion_tokens instead of max_tokens.

    OpenAI's o1, o3, and some reasoning models use max_completion_tokens.

    Args:
        model_name: The model name

    Returns:
        bool: True if the model requires max_completion_tokens
    """
    if not model_name:
        return False

    model_lower = model_name.lower()

    # Models that require max_completion_tokens
    reasoning_models = [
        "o1",
        "o3",
        "o4",
        "gpt-5",
    ]

    for prefix in reasoning_models:
        if model_lower.startswith(prefix) or f"/{prefix}" in model_lower:
            return True

    return False
