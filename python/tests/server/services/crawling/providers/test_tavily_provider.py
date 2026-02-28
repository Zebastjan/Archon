"""
Tests for Tavily provider implementation

Uses mocks to avoid burning API credits during tests.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.server.services.crawling.providers.base_provider import (
    CrawlCapability,
    CrawlProviderType,
    TavilyAPIError,
    TavilyRateLimitError,
)
from src.server.services.crawling.providers.tavily_provider import TavilyProvider


@pytest.fixture
def mock_tavily_response():
    """Mock Tavily API response"""
    return {
        "results": [
            {
                "url": "https://example.com/page1",
                "raw_content": "# Page 1\n\nThis is page 1 content",
            },
            {
                "url": "https://example.com/page2",
                "raw_content": "## Page 2 Heading\n\nThis is page 2 content",
            },
        ],
        "usage": {"credits": 10},
    }


@pytest.mark.asyncio
async def test_tavily_provider_initialization():
    """Test Tavily provider initialization"""
    provider = TavilyProvider(api_key="test_key_12345")

    assert provider.api_key == "test_key_12345"
    assert provider.provider_type == CrawlProviderType.TAVILY


@pytest.mark.asyncio
async def test_tavily_provider_capabilities():
    """Test Tavily provider capabilities"""
    provider = TavilyProvider(api_key="test_key")

    capabilities = provider.get_capabilities()

    assert CrawlCapability.RECURSIVE_CRAWL in capabilities
    assert CrawlCapability.CANCELLATION in capabilities
    # Tavily doesn't support pause/resume in Stage 1
    assert CrawlCapability.PAUSE_RESUME not in capabilities


@pytest.mark.asyncio
async def test_tavily_provider_validate_configuration():
    """Test configuration validation"""
    # Valid configuration
    provider = TavilyProvider(api_key="test_key")
    is_valid, error = await provider.validate_configuration()
    assert is_valid is True
    assert error is None

    # Invalid configuration (no API key)
    provider_no_key = TavilyProvider(api_key="")
    is_valid, error = await provider_no_key.validate_configuration()
    assert is_valid is False
    assert "not configured" in error.lower()


@pytest.mark.asyncio
async def test_tavily_crawl_success(mock_tavily_response):
    """Test successful Tavily crawl with mocked API"""
    provider = TavilyProvider(api_key="test_key")

    # Mock the Tavily client
    with patch.object(provider, "client", create=True) as mock_client:
        mock_client.crawl = MagicMock(return_value=mock_tavily_response)

        results = await provider.crawl(url="https://example.com", max_depth=2)

        # Verify results
        assert len(results) == 2
        assert results[0].url == "https://example.com/page1"
        assert results[0].markdown == "# Page 1\n\nThis is page 1 content"
        assert results[0].title == "Page 1"
        assert results[0].metadata["provider"] == "tavily"

        assert results[1].url == "https://example.com/page2"
        assert results[1].title == "Page 2 Heading"

        # Verify API was called correctly
        mock_client.crawl.assert_called_once()
        call_args = mock_client.crawl.call_args
        assert call_args.kwargs["url"] == "https://example.com"
        assert call_args.kwargs["max_depth"] == 2
        assert call_args.kwargs["limit"] == 100
        assert call_args.kwargs["format"] == "markdown"


@pytest.mark.asyncio
async def test_tavily_crawl_depth_clamping(mock_tavily_response):
    """Test that depth is clamped to allowed range"""
    provider = TavilyProvider(api_key="test_key")

    with patch.object(provider, "client", create=True) as mock_client:
        mock_client.crawl = MagicMock(return_value=mock_tavily_response)

        # Test depth > 3 (should be clamped to 3)
        await provider.crawl(url="https://example.com", max_depth=5)
        assert mock_client.crawl.call_args.kwargs["max_depth"] == 3

        # Test depth < 1 (should be clamped to 1)
        await provider.crawl(url="https://example.com", max_depth=0)
        assert mock_client.crawl.call_args.kwargs["max_depth"] == 1


@pytest.mark.asyncio
async def test_tavily_crawl_rate_limit_error():
    """Test handling of rate limit errors"""
    provider = TavilyProvider(api_key="test_key")

    with patch.object(provider, "client", create=True) as mock_client:
        mock_client.crawl = MagicMock(side_effect=Exception("Rate limit exceeded"))

        with pytest.raises(TavilyRateLimitError) as exc_info:
            await provider.crawl(url="https://example.com")

        assert exc_info.value.fallback_available is True


@pytest.mark.asyncio
async def test_tavily_crawl_api_error():
    """Test handling of API errors"""
    provider = TavilyProvider(api_key="test_key")

    with patch.object(provider, "client", create=True) as mock_client:
        mock_client.crawl = MagicMock(side_effect=Exception("500 Internal Server Error"))

        with pytest.raises(TavilyAPIError) as exc_info:
            await provider.crawl(url="https://example.com")

        assert exc_info.value.fallback_available is True
        assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_tavily_crawl_empty_content_error():
    """Test that empty content raises error per CLAUDE.md"""
    provider = TavilyProvider(api_key="test_key")

    # Mock empty response
    empty_response = {"results": [], "usage": {"credits": 0}}

    with patch.object(provider, "client", create=True) as mock_client:
        mock_client.crawl = MagicMock(return_value=empty_response)

        with pytest.raises(TavilyAPIError) as exc_info:
            await provider.crawl(url="https://example.com")

        assert "no content" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_tavily_crawl_with_progress_callback(mock_tavily_response):
    """Test progress callback during crawl"""
    provider = TavilyProvider(api_key="test_key")
    progress_updates = []

    async def progress_callback(status, progress, message, **kwargs):
        progress_updates.append({"status": status, "progress": progress, "message": message})

    with patch.object(provider, "client", create=True) as mock_client:
        mock_client.crawl = MagicMock(return_value=mock_tavily_response)

        await provider.crawl(url="https://example.com", max_depth=2, progress_callback=progress_callback)

        # Should have received progress updates
        assert len(progress_updates) > 0
        # First update should be starting
        assert progress_updates[0]["progress"] == 0
        assert "starting" in progress_updates[0]["message"].lower()


@pytest.mark.asyncio
async def test_tavily_crawl_with_cancellation():
    """Test cancellation during crawl"""
    provider = TavilyProvider(api_key="test_key")
    cancelled = False

    def cancellation_check():
        nonlocal cancelled
        if cancelled:
            raise asyncio.CancelledError("Cancelled by user")

    with patch.object(provider, "client", create=True) as mock_client:
        # Simulate cancellation before API call
        cancelled = True

        with pytest.raises(asyncio.CancelledError):
            await provider.crawl(url="https://example.com", cancellation_check=cancellation_check)


@pytest.mark.asyncio
async def test_extract_title_from_markdown():
    """Test title extraction from markdown"""
    provider = TavilyProvider(api_key="test_key")

    # Test H1 extraction
    markdown_h1 = "# Main Title\n\nContent here"
    title = provider._extract_title_from_markdown(markdown_h1)
    assert title == "Main Title"

    # Test H2 extraction (fallback)
    markdown_h2 = "Some text\n\n## Secondary Title\n\nMore content"
    title = provider._extract_title_from_markdown(markdown_h2)
    assert title == "Secondary Title"

    # Test no heading
    markdown_no_heading = "Just plain text"
    title = provider._extract_title_from_markdown(markdown_no_heading)
    assert title is None
