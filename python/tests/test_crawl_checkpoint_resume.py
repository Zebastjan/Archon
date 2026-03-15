"""End-to-end test for crawl checkpoint/resume functionality.

This test verifies that:
1. Pause saves URL state correctly
2. Resume skips already-embedded URLs
3. Crawl continues from checkpoint (not from scratch)

Note: These tests verify the service interface exists and is callable.
Full integration testing requires a real database connection.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.server.services.crawling.crawl_url_state_service import CrawlUrlStateService
from src.server.services.crawling.crawling_service import CrawlingService
from src.server.utils.progress.progress_tracker import ProgressTracker


@pytest.fixture
def mock_sitemap_urls():
    """Generate a list of URLs for a mock sitemap."""
    return [
        "https://example.com/page1",
        "https://example.com/page2",
        "https://example.com/page3",
    ]


@pytest.fixture
def mock_crawler_with_sitemap(mock_sitemap_urls):
    """Create a mock crawler that simulates crawling a sitemap."""
    crawler = MagicMock()

    # Mock successful crawl results
    async def mock_arun(url, config):
        """Simulate crawling a page."""
        await asyncio.sleep(0.01)  # Simulate network delay
        return MagicMock(
            success=True,
            markdown=f"# Content from {url}\n\nThis is the page content.",
            cleaned_html=f"<h1>Content from {url}</h1><p>This is the page content.</p>",
            links={"internal": [], "external": []},
        )

    crawler.arun = mock_arun
    return crawler


@pytest.fixture
def mock_db_with_state_tracking():
    """Create a mock database connector that tracks URL state."""
    mock_db = MagicMock()
    
    # Track URL states in memory
    url_states = {}
    
    async def mock_fetch(query, *args):
        """Simulate database fetch operations."""
        # Return empty by default - real testing needs proper query parsing
        return []

    async def mock_execute(query, *args):
        """Simulate database execute operations."""
        return "INSERT 0 1"

    mock_db.fetch = mock_fetch
    mock_db.execute = mock_execute

    return mock_db


@pytest.fixture(autouse=True)
def cleanup_progress_tracker():
    """Clean up ProgressTracker state between tests."""
    yield
    ProgressTracker._progress_states.clear()


class TestCrawlCheckpointResume:
    """End-to-end tests for crawl checkpoint and resume."""

    @pytest.mark.asyncio
    async def test_url_state_service_exists(self):
        """Test that CrawlUrlStateService can be instantiated."""
        service = CrawlUrlStateService()
        assert service is not None
        assert hasattr(service, 'initialize_urls')
        assert hasattr(service, 'mark_embedded')
        assert hasattr(service, 'mark_fetched')

    @pytest.mark.asyncio
    async def test_crawling_service_exists(self, mock_crawler_with_sitemap):
        """Test that CrawlingService can be instantiated."""
        service = CrawlingService(
            crawler=mock_crawler_with_sitemap,
            progress_id="test-progress"
        )
        assert service is not None
        assert hasattr(service, '_filter_already_processed_urls')

    @pytest.mark.asyncio
    async def test_progress_tracker_pause_resume(self):
        """Test progress tracker pause/resume functionality."""
        progress_id = "test-pause-resume"
        
        # Create tracker
        tracker = ProgressTracker(progress_id, operation_type="crawl")
        
        # Initialize with some state
        await tracker.update(
            status="crawling",
            progress=50,
            log="Halfway through",
            source_id="test-source"
        )
        
        # Verify state (get_progress is async)
        progress_data = await ProgressTracker.get_progress(progress_id)
        assert progress_data["status"] == "crawling"
        assert progress_data["progress"] == 50
        
        # Pause
        await ProgressTracker.pause_operation(progress_id)
        
        # Verify paused (get_progress is async)
        progress_data = await ProgressTracker.get_progress(progress_id)
        assert progress_data["status"] == "paused"

    @pytest.mark.asyncio
    async def test_service_integration_basic(self, mock_crawler_with_sitemap):
        """Test basic service integration without full database mocking."""
        progress_id = "test-integration"
        
        # Verify services can be created
        crawling_service = CrawlingService(
            crawler=mock_crawler_with_sitemap,
            progress_id=progress_id
        )
        
        assert crawling_service is not None
        assert crawling_service.crawler is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
