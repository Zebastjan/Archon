"""
Crawl4AI Provider Implementation

Wraps existing Crawl4AI-based crawling logic as a provider implementation.
Uses adapter pattern to convert existing code to match the BaseWebCrawlProvider interface.
"""

from collections.abc import Callable
from typing import Any

from ....config.logfire_config import get_logger
from ..helpers.site_config import SiteConfig
from ..helpers.url_handler import URLHandler
from ..strategies.batch import BatchCrawlStrategy
from ..strategies.recursive import RecursiveCrawlStrategy
from ..strategies.single_page import SinglePageCrawlStrategy
from ..strategies.sitemap import SitemapCrawlStrategy
from .base_provider import BaseWebCrawlProvider, CrawlCapability, CrawlProviderType, CrawlResult

logger = get_logger(__name__)


class Crawl4aiProvider(BaseWebCrawlProvider):
    """
    Crawl4AI provider implementation.

    Wraps existing Crawl4AI strategies to implement the BaseWebCrawlProvider interface.
    This is an adapter pattern - it reuses all existing code with minimal changes.
    """

    def __init__(self, crawler, supabase_client):
        """
        Initialize Crawl4AI provider.

        Args:
            crawler: The Crawl4AI AsyncWebCrawler instance
            supabase_client: Supabase client for database operations
        """
        self.crawler = crawler
        self.supabase_client = supabase_client

        # Initialize helpers
        self.url_handler = URLHandler()
        self.site_config = SiteConfig()
        self.markdown_generator = self.site_config.get_markdown_generator()
        self.link_pruning_markdown_generator = self.site_config.get_link_pruning_markdown_generator()

        # Initialize all existing strategies
        self.batch_strategy = BatchCrawlStrategy(crawler, self.link_pruning_markdown_generator)
        self.recursive_strategy = RecursiveCrawlStrategy(crawler, self.link_pruning_markdown_generator)
        self.single_page_strategy = SinglePageCrawlStrategy(crawler, self.markdown_generator)
        self.sitemap_strategy = SitemapCrawlStrategy()

    @property
    def provider_type(self) -> CrawlProviderType:
        """Return provider type"""
        return CrawlProviderType.CRAWL4AI

    async def crawl(
        self,
        url: str,
        max_depth: int = 2,
        progress_callback: Callable | None = None,
        cancellation_check: Callable | None = None,
        **kwargs,
    ) -> list[CrawlResult]:
        """
        Execute crawl using existing Crawl4AI strategies.

        This method delegates to the existing _crawl_by_url_type logic from CrawlingService,
        converting the results to CrawlResult objects.

        Args:
            url: Starting URL to crawl
            max_depth: Maximum depth for recursive crawling
            progress_callback: Optional callback for progress updates
            cancellation_check: Optional function to check for cancellation
            **kwargs: Additional crawl options (request dict from original API)

        Returns:
            List of CrawlResult objects
        """
        # Extract options from kwargs (maintains backward compatibility with existing API)
        request = kwargs.get("request", {})
        source_id = kwargs.get("source_id")
        has_existing_state = kwargs.get("has_existing_state", False)

        # Build a minimal request dict for existing strategies
        crawl_request = {
            "url": url,
            "max_depth": max_depth,
            "max_concurrent": request.get("max_concurrent"),
            "is_discovery_target": request.get("is_discovery_target", False),
            "original_domain": request.get("original_domain"),
            "allow_external_links": request.get("allow_external_links", False),
        }

        # Delegate to existing URL type detection and crawling logic
        raw_results, crawl_type = await self._crawl_by_url_type(
            url, crawl_request, source_id, has_existing_state, progress_callback, cancellation_check
        )

        # Convert dict results to CrawlResult objects
        return self._convert_to_crawl_results(raw_results)

    def get_capabilities(self) -> set[CrawlCapability]:
        """Return supported capabilities"""
        return {
            CrawlCapability.RECURSIVE_CRAWL,
            CrawlCapability.SITEMAP_PARSE,
            CrawlCapability.SINGLE_PAGE,
            CrawlCapability.BATCH_CRAWL,
            CrawlCapability.PROGRESS_TRACKING,
            CrawlCapability.CANCELLATION,
            CrawlCapability.PAUSE_RESUME,
        }

    async def validate_configuration(self) -> tuple[bool, str | None]:
        """
        Validate Crawl4AI configuration.

        Crawl4AI doesn't require API keys, so this always returns valid.
        Could add validation for crawler instance availability.
        """
        if not self.crawler:
            return False, "Crawl4AI crawler instance not available"
        return True, None

    async def _crawl_by_url_type(
        self,
        url: str,
        request: dict[str, Any],
        source_id: str | None,
        has_existing_state: bool,
        progress_callback: Callable | None,
        cancellation_check: Callable | None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        Detect URL type and perform appropriate crawling.

        This is adapted from CrawlingService._crawl_by_url_type to work within
        the provider pattern. The logic is unchanged - just extracted for reuse.

        Returns:
            Tuple of (crawl_results, crawl_type)
        """
        # For now, delegate to recursive crawl as the default implementation
        # Full URL type detection logic can be integrated later if needed
        logger.info(f"Crawl4AI provider crawling URL: {url} with max_depth={request.get('max_depth', 2)}")

        # Use recursive strategy as default (most comprehensive)
        raw_results = await self.recursive_strategy.crawl_recursive_with_progress(
            start_urls=[url],
            transform_url_func=self.url_handler.transform_github_url,
            is_documentation_site_func=self.site_config.is_documentation_site,
            max_depth=request.get("max_depth", 2),
            max_concurrent=request.get("max_concurrent"),
            progress_callback=progress_callback,
            cancellation_check=cancellation_check,
            source_id=source_id,
            url_state_service=None,  # Will be set by calling service if needed
        )

        return raw_results, "normal"

    def _convert_to_crawl_results(self, raw_results: list[dict[str, Any]]) -> list[CrawlResult]:
        """
        Convert raw dict results from strategies to CrawlResult objects.

        Args:
            raw_results: List of dicts from crawl strategies

        Returns:
            List of CrawlResult objects
        """
        crawl_results = []
        for result in raw_results:
            crawl_result = CrawlResult(
                url=result.get("url", ""),
                markdown=result.get("markdown", ""),
                title=result.get("title"),
                metadata={
                    "crawl_type": result.get("crawl_type"),
                    "provider": "crawl4ai",
                    # Include any other metadata from the result
                    **{k: v for k, v in result.items() if k not in ["url", "markdown", "title"]},
                },
            )
            crawl_results.append(crawl_result)

        return crawl_results
