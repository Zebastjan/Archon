"""
Database Metrics Service

Handles retrieval of database statistics and metrics.
"""

from datetime import datetime
from typing import Any

from ...config.logfire_config import safe_logfire_error, safe_logfire_info
from ..database import get_database_connector


class DatabaseMetricsService:
    """
    Service for retrieving database metrics and statistics.
    """

    def __init__(self):
        """Initialize the database metrics service."""
        pass

    async def get_metrics(self) -> dict[str, Any]:
        """
        Get database metrics and statistics.

        Returns:
            Dictionary containing database metrics
        """
        try:
            safe_logfire_info("Getting database metrics")

            db = get_database_connector()

            # Get counts from various tables
            metrics = {}

            # Sources count
            sources_result = await db.fetch("SELECT COUNT(*) as count FROM archon_sources")
            metrics["sources_count"] = sources_result[0]["count"] if sources_result else 0

            # Crawled pages count
            pages_result = await db.fetch("SELECT COUNT(*) as count FROM archon_crawled_pages")
            metrics["pages_count"] = pages_result[0]["count"] if pages_result else 0

            # Code examples count
            try:
                code_examples_result = await db.fetch("SELECT COUNT(*) as count FROM archon_code_examples")
                metrics["code_examples_count"] = code_examples_result[0]["count"] if code_examples_result else 0
            except Exception as e:
                logger.warning(f"Failed to get code examples count: {e}")
                metrics["code_examples_count"] = 0

            # Add timestamp
            metrics["timestamp"] = datetime.now().isoformat()

            # Calculate additional metrics
            metrics["average_pages_per_source"] = (
                round(metrics["pages_count"] / metrics["sources_count"], 2) if metrics["sources_count"] > 0 else 0
            )

            safe_logfire_info(
                f"Database metrics retrieved | sources={metrics['sources_count']} | pages={metrics['pages_count']} | code_examples={metrics['code_examples_count']}"
            )

            return metrics

        except Exception as e:
            safe_logfire_error(f"Failed to get database metrics | error={str(e)}")
            raise

    async def get_storage_statistics(self) -> dict[str, Any]:
        """
        Get storage statistics including sizes and counts by type.

        Returns:
            Dictionary containing storage statistics
        """
        try:
            db = get_database_connector()
            stats = {}

            # Get knowledge type distribution
            knowledge_types_result = await db.fetch(
                "SELECT metadata->>'knowledge_type' as knowledge_type FROM archon_sources"
            )

            if knowledge_types_result:
                type_counts = {}
                for row in knowledge_types_result:
                    ktype = row.get("knowledge_type", "unknown")
                    type_counts[ktype] = type_counts.get(ktype, 0) + 1
                stats["knowledge_type_distribution"] = type_counts

            # Get recent activity
            recent_sources = await db.fetch(
                "SELECT source_id, created_at FROM archon_sources ORDER BY created_at DESC LIMIT 5"
            )

            stats["recent_sources"] = [
                {"source_id": s["source_id"], "created_at": s["created_at"]} for s in (recent_sources or [])
            ]

            return stats

        except Exception as e:
            safe_logfire_error(f"Failed to get storage statistics | error={str(e)}")
            return {}
