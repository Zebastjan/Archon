"""LLM-based code summarization.

Handles generation of code summaries using various LLM providers.
"""

import asyncio
import json
import time
from collections.abc import Callable
from typing import Any

from ....config.logfire_config import search_logger
from ...credential_service import credential_service
from ...llm_provider_service import (
    extract_message_text,
    get_llm_client,
    prepare_chat_completion_params,
)
from .config import get_llm_timeout, get_max_retries
from .extraction import extract_json_payload, parse_json_safely


async def generate_code_summary(
    code: str,
    language: str = "",
    provider: str | None = None,
    max_retries: int = 2,
) -> dict[str, str]:
    """Generate a summary for a code example using LLM.

    Args:
        code: The code example to summarize
        language: Programming language of the code
        provider: Optional LLM provider override
        max_retries: Maximum retry attempts

    Returns:
        Dict with 'example_name' and 'summary' keys
    """
    if not code or not code.strip():
        return {
            "example_name": "Code Example",
            "summary": "Empty code example.",
        }

    # Truncate very long code examples
    max_code_length = 8000
    if len(code) > max_code_length:
        code = code[:max_code_length] + "..."
        search_logger.debug(f"Truncated code example from {len(code)} to {max_code_length} chars")

    # Build prompt for LLM
    prompt = _build_summary_prompt(code, language)

    # Try with retries
    for attempt in range(max_retries + 1):
        try:
            result = await _call_llm_for_summary(prompt, provider)
            if result:
                return result
        except Exception as e:
            search_logger.warning(f"Summary generation attempt {attempt + 1} failed: {e}")
            if attempt < max_retries:
                await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff
            else:
                search_logger.error(f"All {max_retries + 1} summary generation attempts failed")

    # Fallback: generate basic summary
    return _generate_fallback_summary(code, language)


def _build_summary_prompt(code: str, language: str = "") -> str:
    """Build the prompt for code summarization.

    Args:
        code: Code to summarize
        language: Programming language

    Returns:
        Formatted prompt string
    """
    lang_hint = f" ({language})" if language else ""

    prompt = f"""Analyze this code example{lang_hint} and provide a JSON response with two fields:
- "example_name": A concise, descriptive name for this code (5-10 words)
- "summary": A brief explanation of what this code does and its key features (2-3 sentences)

Code:
```{language}
{code}
```

Respond with valid JSON only, no additional text."""

    return prompt


def _generate_fallback_summary(code: str, language: str = "") -> dict[str, str]:
    """Generate a basic fallback summary when LLM fails.

    Args:
        code: The code example
        language: Programming language

    Returns:
        Fallback summary dict
    """
    lang_str = f" ({language})" if language else ""

    # Count lines and approximate complexity
    lines = code.strip().split("\n")
    line_count = len(lines)

    # Try to extract function/class names
    import re

    functions = re.findall(r"(?:def|function|func)\s+(\w+)", code)
    classes = re.findall(r"(?:class)\s+(\w+)", code)

    description_parts = []
    if functions:
        description_parts.append(f"Contains functions: {', '.join(functions[:3])}")
    if classes:
        description_parts.append(f"Defines classes: {', '.join(classes[:3])}")

    description = "; ".join(description_parts) if description_parts else "Code example"

    return {
        "example_name": f"Code Example{lang_str}",
        "summary": f"{description}. {line_count} lines of code.",
    }


async def _call_llm_for_summary(prompt: str, provider: str | None = None) -> dict[str, str] | None:
    """Call LLM to generate summary.

    Args:
        prompt: The prompt to send
        provider: Optional provider override

    Returns:
        Parsed summary dict or None on failure
    """
    timeout = await get_llm_timeout()

    try:
        async with get_llm_client(provider=provider) as client:
            # Prepare parameters
            params = await prepare_chat_completion_params(
                provider=provider,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500,
            )

            # Make request with timeout
            start_time = time.time()
            response = await client.chat.completions.create(**params)
            duration_ms = (time.time() - start_time) * 1000

            # Extract text from response
            raw_response = extract_message_text(response)

            search_logger.debug(f"LLM summary generated in {duration_ms:.1f}ms")

            # Extract JSON from response
            json_str = extract_json_payload(raw_response)
            parsed = parse_json_safely(json_str)

            if parsed:
                return {
                    "example_name": parsed.get("example_name", "Code Example"),
                    "summary": parsed.get("summary", "Code example for demonstration purposes."),
                }

            return None

    except Exception as e:
        search_logger.error(f"LLM call failed: {e}")
        return None


async def generate_code_summaries_batch(
    code_blocks: list[dict[str, Any]],
    max_workers: int = 3,
    progress_callback: Callable | None = None,
    provider: str | None = None,
) -> list[dict[str, str]]:
    """Generate summaries for multiple code examples in parallel.

    Args:
        code_blocks: List of dicts with 'code' and optionally 'language' keys
        max_workers: Maximum concurrent LLM calls
        progress_callback: Optional async callback for progress updates
        provider: Optional LLM provider override

    Returns:
        List of summary dicts matching code_blocks order
    """
    if not code_blocks:
        return []

    semaphore = asyncio.Semaphore(max_workers)
    completed = 0
    total = len(code_blocks)

    async def summarize_with_semaphore(block: dict[str, Any]) -> dict[str, str]:
        nonlocal completed

        async with semaphore:
            result = await generate_code_summary(
                code=block.get("code", ""),
                language=block.get("language", ""),
                provider=provider,
            )

            completed += 1
            if progress_callback and asyncio.iscoroutinefunction(progress_callback):
                try:
                    await progress_callback(
                        "code_summaries",
                        int((completed / total) * 100),
                        f"Generated {completed}/{total} summaries",
                    )
                except Exception:
                    pass  # Don't fail on progress callback errors

            return result

    # Process in parallel with semaphore
    tasks = [summarize_with_semaphore(block) for block in code_blocks]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Handle any exceptions
    summaries = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            search_logger.error(f"Summary generation failed for block {i}: {result}")
            summaries.append(
                {
                    "example_name": "Code Example",
                    "summary": "Summary generation failed.",
                }
            )
        else:
            summaries.append(result)

    return summaries


async def validate_summary_quality(summary: dict[str, str]) -> tuple[bool, str]:
    """Validate that a generated summary meets quality standards.

    Args:
        summary: Summary dict with 'example_name' and 'summary'

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not summary:
        return False, "Empty summary"

    name = summary.get("example_name", "")
    desc = summary.get("summary", "")

    # Check for fallback/generic content
    generic_names = ["code example", "example", "sample"]
    if any(gen in name.lower() for gen in generic_names) and len(name) < 20:
        return False, "Summary appears to be generic fallback"

    # Check minimum length
    if len(desc) < 20:
        return False, "Summary too short"

    return True, ""
