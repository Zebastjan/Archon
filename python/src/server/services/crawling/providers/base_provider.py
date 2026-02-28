"""
Base Provider Interface for Web Crawling

Defines the abstract interface that all web crawl providers must implement.
This ensures consistent behavior across different crawling backends (Tavily, Crawl4AI, etc.).
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class CrawlProviderType(Enum):
    """Supported crawl providers"""

    TAVILY = "tavily"
    CRAWL4AI = "crawl4ai"


class CrawlCapability(Enum):
    """Capabilities that a provider can support"""

    RECURSIVE_CRAWL = "recursive_crawl"  # Can follow links recursively
    SITEMAP_PARSE = "sitemap_parse"  # Can parse sitemaps
    SINGLE_PAGE = "single_page"  # Can crawl single pages
    BATCH_CRAWL = "batch_crawl"  # Can crawl multiple URLs in batch
    PROGRESS_TRACKING = "progress_tracking"  # Provides real-time progress
    CANCELLATION = "cancellation"  # Supports cancellation
    PAUSE_RESUME = "pause_resume"  # Supports pause/resume


@dataclass
class CrawlResult:
    """
    Standardized crawl result format.

    All providers must return results in this format to ensure downstream
    pipeline (chunking, embedding) works uniformly.
    """

    url: str  # URL that was crawled
    markdown: str  # Markdown content extracted from the page
    title: Optional[str]  # Page title (extracted from H1/metadata)
    metadata: dict[str, Any]  # Provider-specific metadata


class BaseWebCrawlProvider(ABC):
    """
    Abstract base class for web crawl providers.

    All crawl providers (Tavily, Crawl4AI, future providers) must implement
    this interface to ensure consistent behavior and compatibility with the
    existing ingestion pipeline.
    """

    @property
    @abstractmethod
    def provider_type(self) -> CrawlProviderType:
        """Return the provider type"""
        pass

    @abstractmethod
    async def crawl(
        self,
        url: str,
        max_depth: int = 2,
        progress_callback: Optional[Callable] = None,
        cancellation_check: Optional[Callable] = None,
        **kwargs,
    ) -> list[CrawlResult]:
        """
        Execute crawl and return standardized results.

        Args:
            url: Starting URL to crawl
            max_depth: Maximum depth for recursive crawling
            progress_callback: Optional callback for progress updates
                               Signature: async (status: str, progress: int, message: str, **kwargs) -> None
            cancellation_check: Optional function to check for cancellation
                               Signature: () -> None (raises CancelledError if cancelled)
            **kwargs: Provider-specific options

        Returns:
            List of CrawlResult objects

        Raises:
            CrawlProviderError: If crawl fails
            asyncio.CancelledError: If cancelled via cancellation_check
        """
        pass

    @abstractmethod
    def get_capabilities(self) -> set[CrawlCapability]:
        """
        Return set of supported capabilities.

        Returns:
            Set of CrawlCapability enum values
        """
        pass

    @abstractmethod
    async def validate_configuration(self) -> tuple[bool, Optional[str]]:
        """
        Check if provider is properly configured (API keys, etc.).

        Returns:
            Tuple of (is_valid, error_message)
            - is_valid: True if configuration is valid
            - error_message: None if valid, error message if invalid
        """
        pass


class CrawlProviderError(Exception):
    """
    Base exception for crawl provider errors.

    Attributes:
        message: Human-readable error message
        fallback_available: Whether fallback to another provider is possible
        original_error: Original exception that caused this error
    """

    def __init__(
        self, message: str, fallback_available: bool = True, original_error: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.fallback_available = fallback_available
        self.original_error = original_error


class TavilyRateLimitError(CrawlProviderError):
    """Tavily API rate limit exceeded"""

    def __init__(
        self, message: str = "Tavily API rate limit exceeded", original_error: Optional[Exception] = None
    ):
        super().__init__(message, fallback_available=True, original_error=original_error)


class TavilyAPIError(CrawlProviderError):
    """Tavily API error (4xx/5xx)"""

    def __init__(
        self, message: str, status_code: Optional[int] = None, original_error: Optional[Exception] = None
    ):
        super().__init__(message, fallback_available=True, original_error=original_error)
        self.status_code = status_code
