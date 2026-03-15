"""
Knowledge Summary Service

Provides lightweight summary data for knowledge items to minimize data transfer.
Optimized for frequent polling and card displays.
"""

from typing import Any

from ...config.logfire_config import safe_logfire_error, safe_logfire_info
from ..database import get_database_connector


class KnowledgeSummaryService:
    """
    Service for providing lightweight knowledge item summaries.
    Designed for efficient polling with minimal data transfer.
    """

    def __init__(self):
        """Initialize the knowledge summary service."""
        pass

    async def get_summaries(
        self,
        page: int = 1,
        per_page: int = 20,
        knowledge_type: str | None = None,
        search: str | None = None,
    ) -> dict[str, Any]:
        """
        Get lightweight summaries of knowledge items.

        Returns only essential data needed for card displays:
        - Basic metadata (title, url, type, tags)
        - Counts only (no actual content)
        - Minimal processing overhead

        Args:
            page: Page number (1-based)
            per_page: Items per page
            knowledge_type: Optional filter by knowledge type
            search: Optional search term

        Returns:
            Dict with minimal item summaries and pagination info
        """
        try:
            safe_logfire_info(f"Fetching knowledge summaries | page={page} | per_page={per_page}")

            db = get_database_connector()
            import json

            # Build WHERE clause dynamically
            where_clauses = []
            params = []
            param_count = 1

            # Apply knowledge type filter
            if knowledge_type:
                where_clauses.append(f"metadata @> ${param_count}")
                params.append(json.dumps({"knowledge_type": knowledge_type}))
                param_count += 1

            # Apply search filter
            if search:
                search_pattern = f"%{search}%"
                where_clauses.append(
                    f"(title ILIKE ${param_count} OR summary ILIKE ${param_count})"
                )
                params.append(search_pattern)
                param_count += 1

            where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

            # Get total count
            count_result = await db.fetch(
                f"SELECT COUNT(*) as count FROM archon_sources {where_sql}",
                *params
            )
            total = count_result[0]["count"] if count_result else 0

            # Apply pagination
            start_idx = (page - 1) * per_page
            params.extend([per_page, start_idx])

            # Execute main query with pagination
            sources = await db.fetch(
                f"""
                SELECT source_id, title, summary, metadata, source_url, created_at, updated_at
                FROM archon_sources {where_sql}
                ORDER BY updated_at DESC
                LIMIT ${param_count} OFFSET ${param_count + 1}
                """,
                *params
            )

            # Get source IDs for batch operations
            source_ids = [s["source_id"] for s in sources]

            # Batch fetch counts only (no content!)
            summaries = []

            if source_ids:
                # Get document counts in a single query
                doc_counts = await self._get_document_counts_batch(source_ids)

                # Get code example counts in a single query
                code_counts = await self._get_code_example_counts_batch(source_ids)

                # Get first URLs in a single query
                first_urls = await self._get_first_urls_batch(source_ids)

                # Build summaries
                for source in sources:
                    source_id = source["source_id"]
                    metadata = source.get("metadata", {})

                    # Use the original source_url from the source record (the URL the user entered)
                    # Fall back to first crawled page URL, then to source:// format as last resort
                    source_url = source.get("source_url")
                    if source_url:
                        first_url = source_url
                    else:
                        first_url = first_urls.get(source_id, f"source://{source_id}")

                    source_type = metadata.get("source_type", "file" if first_url.startswith("file://") else "url")

                    # Extract knowledge_type - check metadata first, otherwise default based on source content
                    # The metadata should always have it if it was crawled properly
                    knowledge_type_value = metadata.get("knowledge_type")
                    if not knowledge_type_value:
                        # Fallback: If not in metadata, default to "technical" for now
                        # This handles legacy data that might not have knowledge_type set
                        safe_logfire_info(f"Knowledge type not found in metadata for {source_id}, defaulting to technical")
                        knowledge_type_value = "technical"

                    summary = {
                        "source_id": source_id,
                        "title": source.get("title", source.get("summary", "Untitled")),
                        "url": first_url,
                        "status": "active",  # Always active for now
                        "document_count": doc_counts.get(source_id, 0),
                        "code_examples_count": code_counts.get(source_id, 0),
                        "knowledge_type": knowledge_type_value,
                        "source_type": source_type,
                        "created_at": source.get("created_at"),
                        "updated_at": source.get("updated_at"),
                        "metadata": metadata,  # Include full metadata (contains tags)
                    }
                    summaries.append(summary)

            safe_logfire_info(
                f"Knowledge summaries fetched | count={len(summaries)} | total={total}"
            )

            return {
                "items": summaries,
                "total": total,
                "page": page,
                "per_page": per_page,
                "pages": (total + per_page - 1) // per_page if per_page > 0 else 0,
            }

        except Exception as e:
            safe_logfire_error(f"Failed to get knowledge summaries | error={str(e)}")
            raise

    async def _get_document_counts_batch(self, source_ids: list[str]) -> dict[str, int]:
        """
        Get document counts for multiple sources in a single query.

        Args:
            source_ids: List of source IDs

        Returns:
            Dict mapping source_id to document count
        """
        try:
            db = get_database_connector()

            # Use GROUP BY for efficient batch counting
            placeholders = ", ".join(f"${i+1}" for i in range(len(source_ids)))
            result = await db.fetch(
                f"""
                SELECT source_id, COUNT(*) as count
                FROM archon_crawled_pages
                WHERE source_id IN ({placeholders})
                GROUP BY source_id
                """,
                *source_ids
            )

            # Convert to dict
            counts = {row["source_id"]: row["count"] for row in result}

            # Ensure all source_ids have an entry (default to 0)
            for source_id in source_ids:
                if source_id not in counts:
                    counts[source_id] = 0

            return counts

        except Exception as e:
            safe_logfire_error(f"Failed to get document counts | error={str(e)}")
            return dict.fromkeys(source_ids, 0)

    async def _get_code_example_counts_batch(self, source_ids: list[str]) -> dict[str, int]:
        """
        Get code example counts for multiple sources efficiently.

        Args:
            source_ids: List of source IDs

        Returns:
            Dict mapping source_id to code example count
        """
        try:
            db = get_database_connector()

            # Use GROUP BY for efficient batch counting
            placeholders = ", ".join(f"${i+1}" for i in range(len(source_ids)))
            result = await db.fetch(
                f"""
                SELECT source_id, COUNT(*) as count
                FROM archon_code_examples
                WHERE source_id IN ({placeholders})
                GROUP BY source_id
                """,
                *source_ids
            )

            # Convert to dict
            counts = {row["source_id"]: row["count"] for row in result}

            # Ensure all source_ids have an entry (default to 0)
            for source_id in source_ids:
                if source_id not in counts:
                    counts[source_id] = 0

            return counts

        except Exception as e:
            safe_logfire_error(f"Failed to get code example counts | error={str(e)}")
            return dict.fromkeys(source_ids, 0)

    async def _get_first_urls_batch(self, source_ids: list[str]) -> dict[str, str]:
        """
        Get first URL for each source in a batch.

        Args:
            source_ids: List of source IDs

        Returns:
            Dict mapping source_id to first URL
        """
        try:
            db = get_database_connector()

            # Get all first URLs in one query using DISTINCT ON
            placeholders = ", ".join(f"${i+1}" for i in range(len(source_ids)))
            result = await db.fetch(
                f"""
                SELECT DISTINCT ON (source_id) source_id, url
                FROM archon_crawled_pages
                WHERE source_id IN ({placeholders})
                ORDER BY source_id, created_at ASC
                """,
                *source_ids
            )

            # Group by source_id, keeping first URL for each
            urls = {}
            for item in result:
                source_id = item["source_id"]
                if source_id not in urls:
                    urls[source_id] = item["url"]

            # Provide defaults for any missing
            for source_id in source_ids:
                if source_id not in urls:
                    urls[source_id] = f"source://{source_id}"

            return urls

        except Exception as e:
            safe_logfire_error(f"Failed to get first URLs | error={str(e)}")
            return {sid: f"source://{sid}" for sid in source_ids}
