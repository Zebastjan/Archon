"""
Tavily Provider Implementation

Implements web crawling using the Tavily API.
Tavily provides a specialized web crawling service optimized for modern websites.
"""

import asyncio
import re
from collections.abc import Callable
from typing import Any, Optional

from ....config.logfire_config import get_logger, safe_logfire_error, safe_logfire_info, safe_logfire_warning
from .base_provider import (
    BaseWebCrawlProvider,
    CrawlCapability,
    CrawlProviderType,
    CrawlResult,
    TavilyAPIError,
    TavilyRateLimitError,
)

logger = get_logger(__name__)

# Conservative Stage 1 limits per plan
MAX_DEPTH_ALLOWED = 3  # Cap at 3 (Tavily supports 1-5)
MAX_PAGES_PER_CRAWL = 100  # Conservative limit for Stage 1
DEFAULT_TIMEOUT = 150  # Tavily default timeout in seconds


class TavilyProvider(BaseWebCrawlProvider):
    """
    Tavily provider implementation.

    Uses Tavily's web crawling API to fetch and process web content.
    Stage 1: Basic URL + depth integration with conservative limits.
    """

    def __init__(self, api_key: str):
        """
        Initialize Tavily provider.

        Args:
            api_key: Tavily API key
        """
        self.api_key = api_key
        self._client = None

    @property
    def client(self):
        """Lazy-load Tavily client to avoid import errors if library not installed"""
        if self._client is None:
            try:
                from tavily import TavilyClient

                self._client = TavilyClient(api_key=self.api_key)
            except ImportError as e:
                raise ImportError(
                    "tavily-python package not installed. Install with: uv add --group server tavily-python"
                ) from e
        return self._client

    @property
    def provider_type(self) -> CrawlProviderType:
        """Return provider type"""
        return CrawlProviderType.TAVILY

    async def crawl(
        self,
        url: str,
        max_depth: int = 2,
        progress_callback: Optional[Callable] = None,
        cancellation_check: Optional[Callable] = None,
        **kwargs,
    ) -> list[CrawlResult]:
        """
        Execute crawl using Tavily API.

        Stage 1 implementation:
        - Basic URL + depth integration
        - Conservative limits (max 100 pages, depth 1-3)
        - NO preflight mapping or cost estimation
        - Simulated progress tracking (Tavily doesn't provide real-time progress)

        Args:
            url: Starting URL to crawl
            max_depth: Maximum depth (clamped to 1-3)
            progress_callback: Optional callback for progress updates
            cancellation_check: Optional function to check for cancellation
            **kwargs: Additional options (ignored in Stage 1)

        Returns:
            List of CrawlResult objects

        Raises:
            TavilyRateLimitError: If rate limit exceeded
            TavilyAPIError: If API call fails
            asyncio.CancelledError: If cancelled via cancellation_check
        """
        # Check for cancellation before starting
        if cancellation_check:
            cancellation_check()

        # Clamp depth to allowed range
        clamped_depth = max(1, min(max_depth, MAX_DEPTH_ALLOWED))
        if clamped_depth != max_depth:
            safe_logfire_warning(
                f"Tavily: max_depth={max_depth} clamped to {clamped_depth} (allowed range: 1-{MAX_DEPTH_ALLOWED})"
            )

        # Notify progress: starting
        if progress_callback:
            await progress_callback("crawling", 0, f"Starting Tavily crawl of {url} (depth={clamped_depth})")

        safe_logfire_info(
            f"Tavily crawl starting | url={url} | max_depth={clamped_depth} | limit={MAX_PAGES_PER_CRAWL}"
        )

        try:
            # Execute Tavily crawl API (blocking I/O - run in thread pool)
            response = await asyncio.to_thread(
                self.client.crawl,
                url=url,
                max_depth=clamped_depth,
                limit=MAX_PAGES_PER_CRAWL,
                format="markdown",
                include_usage=True,
            )

            # Check for cancellation after API call
            if cancellation_check:
                cancellation_check()

        except Exception as e:
            error_msg = str(e).lower()

            # Handle rate limiting
            if "rate limit" in error_msg or "429" in error_msg:
                safe_logfire_error(f"Tavily rate limit exceeded | url={url}")
                raise TavilyRateLimitError(f"Tavily API rate limit exceeded for {url}", original_error=e)

            # Handle API errors (4xx/5xx)
            if any(x in error_msg for x in ["400", "401", "403", "404", "500", "502", "503"]):
                # Extract status code if possible
                status_match = re.search(r"(\d{3})", error_msg)
                status_code = int(status_match.group(1)) if status_match else None

                safe_logfire_error(f"Tavily API error | status={status_code} | url={url} | error={e}")
                raise TavilyAPIError(
                    f"Tavily API error (status={status_code}): {str(e)}", status_code=status_code, original_error=e
                )

            # Unknown error - wrap and raise
            safe_logfire_error(f"Tavily crawl failed | url={url} | error={e}")
            raise TavilyAPIError(f"Tavily crawl failed: {str(e)}", original_error=e)

        # Parse response and convert to CrawlResult
        results = self._parse_tavily_response(response, url)

        # Empty content check - fail fast per CLAUDE.md
        if not results:
            error_msg = f"Tavily returned no content for {url}"
            safe_logfire_error(error_msg)
            raise TavilyAPIError(error_msg)

        # Simulate progress updates since Tavily doesn't provide real-time progress
        if progress_callback:
            total_pages = len(results)
            for i, result in enumerate(results):
                progress_percent = int(((i + 1) / total_pages) * 100)
                await progress_callback(
                    "crawling",
                    progress_percent,
                    f"Processed {i + 1}/{total_pages} pages from Tavily",
                    processed_pages=i + 1,
                    total_pages=total_pages,
                )

        safe_logfire_info(
            f"Tavily crawl completed | url={url} | pages={len(results)} | "
            f"credits_used={response.get('usage', {}).get('credits', 'N/A')}"
        )

        return results

    def get_capabilities(self) -> set[CrawlCapability]:
        """
        Return supported capabilities.

        Stage 1: Tavily provides recursive crawling but no pause/resume or real-time progress.
        """
        return {
            CrawlCapability.RECURSIVE_CRAWL,  # Tavily follows links up to max_depth
            CrawlCapability.CANCELLATION,  # Can check cancellation before/after API call
            # NOTE: No PROGRESS_TRACKING (simulated), no PAUSE_RESUME (stateless)
        }

    async def validate_configuration(self) -> tuple[bool, Optional[str]]:
        """
        Validate Tavily API key.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.api_key:
            return False, "Tavily API key not configured"

        # Could add a test API call here to validate the key, but that burns credits
        # For now, just check if key is present
        return True, None

    def _parse_tavily_response(self, response: dict[str, Any], original_url: str) -> list[CrawlResult]:
        """
        Parse Tavily API response and convert to CrawlResult objects.

        Tavily response format:
        {
            "results": [
                {
                    "url": "https://example.com/page",
                    "raw_content": "# Page Title\n\nContent...",
                    ...
                }
            ],
            "usage": {
                "credits": 10
            }
        }

        Args:
            response: Tavily API response
            original_url: Original URL that was crawled

        Returns:
            List of CrawlResult objects
        """
        results = []
        raw_results = response.get("results", [])
        usage = response.get("usage", {})
        credits_used = usage.get("credits", 0)

        for raw_result in raw_results:
            url = raw_result.get("url", original_url)
            markdown = raw_result.get("raw_content", "")

            # Extract title from first H1 or H2 in markdown
            title = self._extract_title_from_markdown(markdown)
            if not title:
                # Fallback: use URL path as title
                title = url.split("/")[-1] or url

            # Build metadata
            metadata = {
                "provider": "tavily",
                "credits_used_per_page": credits_used / max(len(raw_results), 1),  # Estimate per-page cost
                "total_credits_used": credits_used,
                "tavily_raw": raw_result,  # Store original response for debugging
            }

            results.append(CrawlResult(url=url, markdown=markdown, title=title, metadata=metadata))

        return results

    def _extract_title_from_markdown(self, markdown: str) -> Optional[str]:
        """
        Extract title from markdown content.

        Looks for first H1 or H2 heading.

        Args:
            markdown: Markdown content

        Returns:
            Title string or None
        """
        if not markdown:
            return None

        # Look for H1 (# Title)
        h1_match = re.search(r"^#\s+(.+)$", markdown, re.MULTILINE)
        if h1_match:
            return h1_match.group(1).strip()

        # Fallback to H2 (## Title)
        h2_match = re.search(r"^##\s+(.+)$", markdown, re.MULTILINE)
        if h2_match:
            return h2_match.group(1).strip()

        return None
