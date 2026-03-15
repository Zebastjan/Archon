"""
Crawl URL State Service

Tracks per-URL crawl progress to enable checkpoint/resume functionality.
"""

from datetime import UTC, datetime

from ...config.logfire_config import get_logger, safe_logfire_error, safe_logfire_info
from ..database import get_database_connector

logger = get_logger(__name__)


class CrawlUrlStateService:
    """
    Service for tracking crawl URL state to enable resumable crawls.
    """

    def __init__(self):
        """Initialize the crawl URL state service."""
        self.table_name = "archon_crawl_url_state"

    async def initialize_urls(self, source_id: str, urls: list[str], max_retries: int = 3) -> dict[str, int]:
        """
        Initialize URLs in pending state for a crawl.

        Args:
            source_id: The source ID for this crawl
            urls: List of URLs to track
            max_retries: Maximum retry attempts per URL

        Returns:
            Dict with counts of inserted/skipped URLs
        """
        if not urls:
            return {"inserted": 0, "skipped": 0}

        db = get_database_connector()
        now = datetime.now(UTC).isoformat()
        inserted = 0

        try:
            # Insert each URL with ON CONFLICT DO NOTHING for upsert behavior
            for url in urls:
                result = await db.fetch(
                    f"""
                    INSERT INTO {self.table_name}
                    (source_id, url, status, max_retries, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (source_id, url) DO NOTHING
                    RETURNING id
                    """,
                    source_id,
                    url,
                    "pending",
                    max_retries,
                    now,
                    now,
                )
                if result:
                    inserted += 1

            skipped = len(urls) - inserted

            safe_logfire_info(
                f"Initialized crawl URL state | source_id={source_id} | inserted={inserted} | skipped={skipped}"
            )

            return {"inserted": inserted, "skipped": skipped}
        except Exception as e:
            safe_logfire_error(f"Failed to initialize URL state: {e}")
            raise

    async def mark_fetched(self, source_id: str, url: str) -> bool:
        """
        Mark a URL as fetched.

        Args:
            source_id: The source ID
            url: The URL that was fetched

        Returns:
            True if successful
        """
        return await self._update_status(source_id, url, "fetched")

    async def mark_embedded(self, source_id: str, url: str) -> bool:
        """
        Mark a URL as embedded (complete).

        Args:
            source_id: The source ID
            url: The URL that was embedded

        Returns:
            True if successful
        """
        return await self._update_status(source_id, url, "embedded")

    async def mark_failed(self, source_id: str, url: str, error_message: str) -> bool:
        """
        Mark a URL as failed and increment retry count.

        Args:
            source_id: The source ID
            url: The URL that failed
            error_message: The error message

        Returns:
            True if successful (or if max retries exceeded and marked as failed permanently)
        """
        try:
            # Get current state
            db = get_database_connector()
            result = await db.fetch(
                f"SELECT retry_count, max_retries FROM {self.table_name} WHERE source_id = $1 AND url = $2",
                source_id,
                url
            )

            if not result:
                return False

            current = dict(result[0])
            retry_count = current.get("retry_count", 0) + 1
            max_retries = current.get("max_retries", 3)

            # Check if we should keep trying or give up
            if retry_count >= max_retries:
                # Max retries exceeded - mark as permanently failed
                return await self._update_status(source_id, url, "failed", error_message)
            else:
                # Increment retry count, keep as pending for retry
                await db.execute(
                    f"""
                    UPDATE {self.table_name}
                    SET retry_count = $1, error_message = $2, status = $3, updated_at = $4
                    WHERE source_id = $5 AND url = $6
                    """,
                    retry_count,
                    error_message,
                    "pending",
                    datetime.now(UTC).isoformat(),
                    source_id,
                    url,
                )

                safe_logfire_info(f"URL will retry | url={url} | retry={retry_count}/{max_retries}")
                return True

        except Exception as e:
            safe_logfire_error(f"Failed to mark URL as failed: {e}")
            return False

    async def _update_status(self, source_id: str, url: str, status: str, error_message: str | None = None) -> bool:
        """
        Update the status of a URL.

        Args:
            source_id: The source ID
            url: The URL
            status: New status
            error_message: Optional error message

        Returns:
            True if successful
        """
        try:
            db = get_database_connector()
            now = datetime.now(UTC).isoformat()

            if error_message:
                await db.execute(
                    f"UPDATE {self.table_name} SET status = $1, error_message = $2, updated_at = $3 WHERE source_id = $4 AND url = $5",
                    status,
                    error_message,
                    now,
                    source_id,
                    url,
                )
            else:
                await db.execute(
                    f"UPDATE {self.table_name} SET status = $1, updated_at = $2 WHERE source_id = $3 AND url = $4",
                    status,
                    now,
                    source_id,
                    url,
                )

            return True
        except Exception as e:
            safe_logfire_error(f"Failed to update URL status: {e}")
            return False

    async def get_pending_urls(self, source_id: str) -> list[str]:
        """
        Get URLs that are still pending for a source.

        Args:
            source_id: The source ID

        Returns:
            List of pending URLs
        """
        return await self._get_urls_by_status(source_id, "pending")

    async def get_fetched_urls(self, source_id: str) -> list[str]:
        """
        Get URLs that have been fetched but not embedded.

        Args:
            source_id: The source ID

        Returns:
            List of fetched URLs
        """
        return await self._get_urls_by_status(source_id, "fetched")

    async def get_embedded_urls(self, source_id: str) -> list[str]:
        """
        Get URLs that have been embedded (completed).

        Args:
            source_id: The source ID

        Returns:
            List of embedded URLs
        """
        return await self._get_urls_by_status(source_id, "embedded")

    async def get_failed_urls(self, source_id: str) -> list[str]:
        """
        Get URLs that have permanently failed.

        Args:
            source_id: The source ID

        Returns:
            List of failed URLs
        """
        return await self._get_urls_by_status(source_id, "failed")

    async def _get_urls_by_status(self, source_id: str, status: str) -> list[str]:
        """
        Get URLs by status.

        Args:
            source_id: The source ID
            status: The status to filter by

        Returns:
            List of URLs
        """
        try:
            db = get_database_connector()
            result = await db.fetch(
                f"SELECT url FROM {self.table_name} WHERE source_id = $1 AND status = $2",
                source_id,
                status
            )

            return [row["url"] for row in result]
        except Exception as e:
            safe_logfire_error(f"Failed to get URLs by status: {e}")
            return []

    async def get_crawl_state(self, source_id: str) -> dict[str, int]:
        """
        Get the current state of a crawl.

        Args:
            source_id: The source ID

        Returns:
            Dict with counts by status: {pending, fetched, embedded, failed, total}
        """
        counts = {"pending": 0, "fetched": 0, "embedded": 0, "failed": 0, "total": 0}
        try:
            db = get_database_connector()
            result = await db.fetch(
                f"SELECT status FROM {self.table_name} WHERE source_id = $1",
                source_id
            )

            for row in result:
                status = row.get("status", "pending")
                if status in counts:
                    counts[status] += 1
                counts["total"] += 1

            return counts
        except Exception as e:
            safe_logfire_error(f"Failed to get crawl state: {e}")
            return counts

    async def has_existing_state(self, source_id: str) -> bool:
        """
        Check if there is existing crawl state for a source.

        Args:
            source_id: The source ID

        Returns:
            True if there is existing state
        """
        try:
            db = get_database_connector()
            result = await db.fetch(
                f"SELECT COUNT(*) as count FROM {self.table_name} WHERE source_id = $1",
                source_id
            )

            return (result[0]["count"] if result else 0) > 0
        except Exception as e:
            safe_logfire_error(f"Failed to check existing state: {e}")
            return False

    async def clear_state(self, source_id: str) -> bool:
        """
        Clear all state for a source (for fresh start).

        Args:
            source_id: The source ID

        Returns:
            True if successful
        """
        try:
            db = get_database_connector()
            await db.execute(
                f"DELETE FROM {self.table_name} WHERE source_id = $1",
                source_id
            )

            safe_logfire_info(f"Cleared crawl URL state | source_id={source_id}")
            return True
        except Exception as e:
            safe_logfire_error(f"Failed to clear crawl state: {e}")
            return False


# Singleton instance
crawl_url_state_service: CrawlUrlStateService | None = None


def get_crawl_url_state_service() -> CrawlUrlStateService:
    """
    Get the singleton crawl URL state service instance.

    Returns:
        CrawlUrlStateService instance
    """
    global crawl_url_state_service
    if crawl_url_state_service is None:
        crawl_url_state_service = CrawlUrlStateService()
    return crawl_url_state_service
