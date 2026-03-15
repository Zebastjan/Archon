"""
Base Search Strategy

Implements the foundational vector similarity search that all other strategies build upon.
This is the core semantic search functionality.
"""

from typing import Any

from ...config.logfire_config import get_logger, safe_span
from ..database import get_database_connector

logger = get_logger(__name__)

# Fixed similarity threshold for vector results
SIMILARITY_THRESHOLD = 0.05


class BaseSearchStrategy:
    """Base strategy implementing fundamental vector similarity search"""

    def __init__(self):
        """Initialize search strategy"""
        pass

    async def vector_search(
        self,
        query_embedding: list[float],
        match_count: int,
        filter_metadata: dict | None = None,
        table_rpc: str = "match_archon_crawled_pages",
    ) -> list[dict[str, Any]]:
        """
        Perform basic vector similarity search.

        This is the foundational semantic search that all strategies use.

        Args:
            query_embedding: The embedding vector for the query
            match_count: Number of results to return
            filter_metadata: Optional metadata filters
            table_rpc: The RPC function to call (match_archon_crawled_pages or match_archon_code_examples)

        Returns:
            List of matching documents with similarity scores
        """
        with safe_span("base_vector_search", table=table_rpc, match_count=match_count) as span:
            try:
                db = get_database_connector()
                import json

                # Build filter parameter
                if filter_metadata:
                    if "source" in filter_metadata:
                        source_filter = filter_metadata["source"]
                        filter_param = {}
                    else:
                        source_filter = None
                        filter_param = filter_metadata
                else:
                    source_filter = None
                    filter_param = {}

                # Execute PostgreSQL function call
                # Functions expect: query_embedding, match_count, [source_filter], [filter]
                if source_filter:
                    results = await db.fetch(
                        f"SELECT * FROM {table_rpc}($1, $2, $3, $4)",
                        query_embedding,
                        match_count,
                        source_filter,
                        json.dumps(filter_param)
                    )
                else:
                    results = await db.fetch(
                        f"SELECT * FROM {table_rpc}($1, $2, $3)",
                        query_embedding,
                        match_count,
                        json.dumps(filter_param)
                    )

                # Filter by similarity threshold
                filtered_results = []
                for result in results:
                    similarity = float(result.get("similarity", 0.0))
                    if similarity >= SIMILARITY_THRESHOLD:
                        filtered_results.append(dict(result))

                span.set_attribute("results_found", len(filtered_results))
                span.set_attribute(
                    "results_filtered",
                    len(results) - len(filtered_results),
                )

                return filtered_results

            except Exception as e:
                logger.error(f"Vector search failed: {e}")
                span.set_attribute("error", str(e))
                return []
