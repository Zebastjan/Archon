"""
Simple tests for provider abstraction - directly test the files without full import chain
"""

import pytest
import sys
from pathlib import Path

# Add providers directory directly to path to avoid full import chain
providers_path = Path(__file__).parent.parent.parent.parent.parent / "src" / "server" / "services" / "crawling" / "providers"
sys.path.insert(0, str(providers_path))

# Now import directly from the module files
from base_provider import (
    CrawlCapability,
    CrawlProviderError,
    CrawlProviderType,
    CrawlResult,
    TavilyAPIError,
    TavilyRateLimitError,
)


def test_crawl_result_creation():
    """Test creating CrawlResult instances"""
    result = CrawlResult(
        url="https://example.com",
        markdown="# Test Page\n\nContent here",
        title="Test Page",
        metadata={"provider": "tavily", "credits_used": 1},
    )

    assert result.url == "https://example.com"
    assert result.markdown == "# Test Page\n\nContent here"
    assert result.title == "Test Page"
    assert result.metadata["provider"] == "tavily"


def test_crawl_provider_error():
    """Test CrawlProviderError creation"""
    error = CrawlProviderError("Test error", fallback_available=True)

    assert str(error) == "Test error"
    assert error.fallback_available is True
    assert error.original_error is None


def test_tavily_rate_limit_error():
    """Test TavilyRateLimitError"""
    original_error = ValueError("429 Too Many Requests")
    error = TavilyRateLimitError(original_error=original_error)

    assert "rate limit exceeded" in str(error).lower()
    assert error.fallback_available is True
    assert error.original_error == original_error


def test_tavily_api_error():
    """Test TavilyAPIError"""
    original_error = ValueError("500 Internal Server Error")
    error = TavilyAPIError("API error occurred", status_code=500, original_error=original_error)

    assert "API error occurred" in str(error)
    assert error.status_code == 500
    assert error.fallback_available is True
    assert error.original_error == original_error


def test_crawl_provider_type_enum():
    """Test CrawlProviderType enum"""
    assert CrawlProviderType.TAVILY.value == "tavily"
    assert CrawlProviderType.CRAWL4AI.value == "crawl4ai"


def test_crawl_capability_enum():
    """Test CrawlCapability enum"""
    assert CrawlCapability.RECURSIVE_CRAWL.value == "recursive_crawl"
    assert CrawlCapability.PAUSE_RESUME.value == "pause_resume"
    assert CrawlCapability.PROGRESS_TRACKING.value == "progress_tracking"
