"""End-to-end test for crawl checkpoint/resume functionality.

This test verifies that:
1. Pause saves URL state correctly
2. Resume skips already-embedded URLs
3. Crawl continues from checkpoint (not from scratch)

Critical test case:
- Start crawl of multi-page site
- Pause after some pages are embedded
- Verify URL state tracking
- Resume
- Verify checkpoint filtering works (only remaining pages are crawled)
"""

import asyncio
from unittest.mock import MagicMock

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
        "https://example.com/page4",
        "https://example.com/page5",
        "https://example.com/page6",
        "https://example.com/page7",
        "https://example.com/page8",
        "https://example.com/page9",
        "https://example.com/page10",
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
def mock_supabase_with_state_tracking():
    """Create a mock Supabase client that tracks URL state."""
    client = MagicMock()

    # Track URL states in memory
    url_states = {}
    sources = {}
    documents = {}

    def mock_table(table_name):
        mock_table_obj = MagicMock()

        if table_name == "archon_crawl_url_state":
            # URL state tracking
            def mock_upsert(records, **kwargs):
                for record in records:
                    key = (record["source_id"], record["url"])
                    if key not in url_states:
                        url_states[key] = record.copy()
                mock_execute = MagicMock()
                mock_execute.data = records
                return mock_execute

            def mock_update(data):
                """Returns a match object that can be chained."""
                mock_match_obj = MagicMock()

                def mock_match(filters):
                    """Update matching records and return execute object."""
                    source_id = filters.get("source_id")
                    url = filters.get("url")

                    # Update matching records
                    for key, record in url_states.items():
                        if record.get("source_id") == source_id and record.get("url") == url:
                            record.update(data)

                    mock_execute_obj = MagicMock()
                    key = (source_id, url)
                    mock_execute_obj.data = [url_states.get(key)] if key in url_states else []
                    mock_match_obj.execute = MagicMock(return_value=mock_execute_obj)
                    return mock_match_obj

                mock_match_obj.match = mock_match
                return mock_match_obj

            def mock_select(*fields, **kwargs):
                """Returns a match object for querying."""
                count_mode = kwargs.get("count")
                mock_select_obj = MagicMock()

                def mock_match(filters):
                    """Filter records and return execute object."""
                    source_id = filters.get("source_id")
                    status = filters.get("status")

                    # Filter records
                    results = []
                    for key, record in url_states.items():
                        match = True
                        if source_id is not None and record.get("source_id") != source_id:
                            match = False
                        if status is not None and record.get("status") != status:
                            match = False
                        if match:
                            results.append(record)

                    mock_execute_obj = MagicMock()
                    mock_execute_obj.data = results
                    mock_execute_obj.count = len(results) if count_mode == "exact" else None
                    mock_select_obj.execute = MagicMock(return_value=mock_execute_obj)
                    return mock_select_obj

                mock_select_obj.match = mock_match
                return mock_select_obj

            def mock_delete():
                """Returns a match object for deletion."""
                mock_delete_obj = MagicMock()

                def mock_match(filters):
                    """Delete matching records."""
                    source_id = filters.get("source_id")

                    # Delete matching records
                    keys_to_delete = []
                    for key, record in url_states.items():
                        if record.get("source_id") == source_id:
                            keys_to_delete.append(key)

                    for key in keys_to_delete:
                        del url_states[key]

                    mock_execute_obj = MagicMock()
                    mock_execute_obj.data = []
                    mock_delete_obj.execute = MagicMock(return_value=mock_execute_obj)
                    return mock_delete_obj

                mock_delete_obj.match = mock_match
                return mock_delete_obj

            mock_table_obj.upsert = mock_upsert
            mock_table_obj.update = mock_update
            mock_table_obj.select = mock_select
            mock_table_obj.delete = mock_delete

        elif table_name == "archon_sources":
            # Sources table
            def mock_select(*fields):
                mock_select_obj = MagicMock()

                def mock_eq(field, value):
                    """Filter by equality."""
                    mock_execute_obj = MagicMock()
                    if field == "source_id" and value in sources:
                        mock_execute_obj.data = [sources[value]]
                    else:
                        mock_execute_obj.data = []
                    mock_select_obj.execute = MagicMock(return_value=mock_execute_obj)
                    return mock_select_obj

                mock_select_obj.eq = mock_eq
                return mock_select_obj

            def mock_insert(data):
                """Insert source records."""
                if isinstance(data, list):
                    for item in data:
                        sources[item["source_id"]] = item
                else:
                    sources[data["source_id"]] = data
                mock_execute_obj = MagicMock()
                mock_execute_obj.data = [data] if not isinstance(data, list) else data
                return mock_execute_obj

            mock_table_obj.select = mock_select
            mock_table_obj.insert = mock_insert

        elif table_name == "archon_documents":
            # Documents table (for tracking embeddings)
            def mock_insert(data):
                if isinstance(data, list):
                    for item in data:
                        doc_id = item.get("document_id", len(documents))
                        documents[doc_id] = item
                else:
                    doc_id = data.get("document_id", len(documents))
                    documents[doc_id] = data
                mock_execute_obj = MagicMock()
                mock_execute_obj.data = [data] if not isinstance(data, list) else data
                return mock_execute_obj

            mock_table_obj.insert = mock_insert

        return mock_table_obj

    client.table = mock_table
    client._url_states = url_states  # Expose for test assertions
    client._sources = sources
    client._documents = documents

    return client


@pytest.fixture(autouse=True)
def cleanup_progress_tracker():
    """Clean up ProgressTracker state between tests."""
    yield
    ProgressTracker._progress_states.clear()


class TestCrawlCheckpointResume:
    """End-to-end tests for crawl checkpoint and resume."""

    @pytest.mark.asyncio
    async def test_resume_skips_already_embedded_urls(
        self,
        mock_crawler_with_sitemap,
        mock_supabase_with_state_tracking,
        mock_sitemap_urls
    ):
        """Test that resume skips URLs that are already embedded.

        Scenario:
        1. Start crawl of 10-page sitemap
        2. Simulate embedding first 5 pages
        3. Mark those 5 as "embedded" in URL state
        4. Resume crawl (should process only remaining 5 pages)
        5. Verify checkpoint filtering worked
        """
        progress_id = "test-checkpoint-resume"
        source_id = "source-checkpoint-test"

        # Initialize URL state service
        url_state_service = CrawlUrlStateService(mock_supabase_with_state_tracking)

        # Initialize URLs in pending state
        url_state_service.initialize_urls(source_id, mock_sitemap_urls)

        # Simulate that first 5 URLs are already embedded
        embedded_urls = mock_sitemap_urls[:5]
        for url in embedded_urls:
            url_state_service.mark_embedded(source_id, url)

        # Verify initial state
        crawl_state = url_state_service.get_crawl_state(source_id)
        assert crawl_state["embedded"] == 5, "Should have 5 embedded URLs"
        assert crawl_state["pending"] == 5, "Should have 5 pending URLs"
        assert crawl_state["total"] == 10, "Should have 10 total URLs"

        # Get embedded URLs
        actual_embedded = url_state_service.get_embedded_urls(source_id)
        assert len(actual_embedded) == 5, "Should retrieve 5 embedded URLs"
        assert set(actual_embedded) == set(embedded_urls), "Embedded URLs should match"

        # Create crawling service with progress tracker
        service = CrawlingService(
            crawler=mock_crawler_with_sitemap,
            supabase_client=mock_supabase_with_state_tracking,
            progress_id=progress_id
        )

        # Test the filtering method directly
        remaining_urls = await service._filter_already_processed_urls(source_id, mock_sitemap_urls)

        # Verify filtering worked
        assert len(remaining_urls) == 5, "Should have 5 remaining URLs after filtering"
        expected_remaining = set(mock_sitemap_urls[5:])
        assert set(remaining_urls) == expected_remaining, "Remaining URLs should be the last 5"

        # Verify the embedded URLs were skipped
        for url in embedded_urls:
            assert url not in remaining_urls, f"Embedded URL {url} should be filtered out"

    @pytest.mark.asyncio
    async def test_has_existing_state_detection(
        self,
        mock_supabase_with_state_tracking,
        mock_sitemap_urls
    ):
        """Test that has_existing_state correctly detects existing crawl state."""
        source_id = "source-state-detection"

        url_state_service = CrawlUrlStateService(mock_supabase_with_state_tracking)

        # Initially no state
        assert url_state_service.has_existing_state(source_id) is False

        # Initialize some URLs
        url_state_service.initialize_urls(source_id, mock_sitemap_urls)

        # Now should have state
        assert url_state_service.has_existing_state(source_id) is True

        # Mark some as embedded
        for url in mock_sitemap_urls[:3]:
            url_state_service.mark_embedded(source_id, url)

        # Still should have state
        assert url_state_service.has_existing_state(source_id) is True

        # Get state details
        crawl_state = url_state_service.get_crawl_state(source_id)
        assert crawl_state["embedded"] == 3
        assert crawl_state["pending"] == 7
        assert crawl_state["total"] == 10

    @pytest.mark.asyncio
    async def test_pause_preserves_url_state(
        self,
        mock_crawler_with_sitemap,
        mock_supabase_with_state_tracking,
        mock_sitemap_urls
    ):
        """Test that pausing a crawl preserves URL state for resume.

        Scenario:
        1. Initialize crawl with URLs
        2. Mark some as fetched
        3. Mark some as embedded
        4. Verify state is preserved
        5. Simulate pause
        6. Verify state still preserved after pause
        """
        progress_id = "test-pause-state"
        source_id = "source-pause-test"

        # Initialize progress tracker
        tracker = ProgressTracker(progress_id, operation_type="crawl")
        await tracker.update(
            status="starting",
            progress=0,
            log="Starting crawl",
            source_id=source_id
        )

        # Initialize URL state
        url_state_service = CrawlUrlStateService(mock_supabase_with_state_tracking)
        url_state_service.initialize_urls(source_id, mock_sitemap_urls)

        # Simulate crawl progress: first 3 embedded, next 2 fetched, rest pending
        for url in mock_sitemap_urls[:3]:
            url_state_service.mark_embedded(source_id, url)

        for url in mock_sitemap_urls[3:5]:
            url_state_service.mark_fetched(source_id, url)

        # Update progress tracker
        await tracker.update(
            status="crawling",
            progress=30,
            log="Crawling pages (3/10 embedded)",
            processed_pages=3,
            total_pages=10
        )

        # Verify state before pause
        crawl_state_before = url_state_service.get_crawl_state(source_id)
        assert crawl_state_before["embedded"] == 3
        assert crawl_state_before["fetched"] == 2
        assert crawl_state_before["pending"] == 5

        # Pause
        await ProgressTracker.pause_operation(progress_id)

        # Verify state preserved after pause
        crawl_state_after = url_state_service.get_crawl_state(source_id)
        assert crawl_state_after["embedded"] == 3, "Embedded count should be preserved"
        assert crawl_state_after["fetched"] == 2, "Fetched count should be preserved"
        assert crawl_state_after["pending"] == 5, "Pending count should be preserved"

        # Verify progress tracker state
        progress_data = ProgressTracker.get_progress(progress_id)
        assert progress_data["status"] == "paused"
        assert progress_data["progress"] == 30
        assert progress_data["source_id"] == source_id
        assert progress_data.get("processed_pages") == 3
        assert progress_data.get("total_pages") == 10

    @pytest.mark.asyncio
    async def test_clear_state_after_completion(
        self,
        mock_supabase_with_state_tracking,
        mock_sitemap_urls
    ):
        """Test that state is cleared after successful completion."""
        source_id = "source-clear-test"

        url_state_service = CrawlUrlStateService(mock_supabase_with_state_tracking)

        # Initialize and complete all URLs
        url_state_service.initialize_urls(source_id, mock_sitemap_urls)
        for url in mock_sitemap_urls:
            url_state_service.mark_embedded(source_id, url)

        # Verify all embedded
        crawl_state = url_state_service.get_crawl_state(source_id)
        assert crawl_state["embedded"] == 10
        assert crawl_state["pending"] == 0

        # Clear state
        url_state_service.clear_state(source_id)

        # Verify state cleared
        assert url_state_service.has_existing_state(source_id) is False
        crawl_state_after = url_state_service.get_crawl_state(source_id)
        assert crawl_state_after["total"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
