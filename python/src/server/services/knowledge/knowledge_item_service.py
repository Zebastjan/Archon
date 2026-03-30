"""
Knowledge Item Service

Handles all knowledge item CRUD operations and data transformations.
"""

from typing import Any

from ...config.logfire_config import safe_logfire_error, safe_logfire_info
from ..database import get_database_connector


class KnowledgeItemService:
    """
    Service for managing knowledge items including listing, filtering, updating, and deletion.
    """

    def __init__(self):
        """Initialize the knowledge item service."""
        pass

    async def list_items(
        self,
        page: int = 1,
        per_page: int = 20,
        knowledge_type: str | None = None,
        search: str | None = None,
    ) -> dict[str, Any]:
        """
        List knowledge items with pagination and filtering.

        Args:
            page: Page number (1-based)
            per_page: Items per page
            knowledge_type: Filter by knowledge type
            search: Search term for filtering

        Returns:
            Dict containing items, pagination info, and total count
        """
        try:
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
                    f"(title ILIKE ${param_count} OR summary ILIKE ${param_count} OR source_id ILIKE ${param_count})"
                )
                params.append(search_pattern)
                param_count += 1

            where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

            # Get total count
            count_result = await db.fetch(f"SELECT COUNT(*) as count FROM archon_sources {where_sql}", *params)
            total = count_result[0]["count"] if count_result else 0

            # Apply pagination
            start_idx = (page - 1) * per_page
            params.extend([per_page, start_idx])

            # Execute main query with pagination
            sources = await db.fetch(
                f"SELECT * FROM archon_sources {where_sql} LIMIT ${param_count} OFFSET ${param_count + 1}", *params
            )

            # Get source IDs for batch queries
            source_ids = [source["source_id"] for source in sources]

            # Debug log source IDs
            safe_logfire_info(f"Source IDs for batch query: {source_ids}")

            # Batch fetch related data to avoid N+1 queries
            first_urls = {}
            code_example_counts = {}
            chunk_counts = {}

            if source_ids:
                # Batch fetch first URLs
                placeholders = ", ".join(f"${i + 1}" for i in range(len(source_ids)))
                urls_result = await db.fetch(
                    f"SELECT DISTINCT ON (source_id) source_id, url FROM archon_crawled_pages WHERE source_id IN ({placeholders})",
                    *source_ids,
                )

                # Group URLs by source_id (take first one for each)
                for item in urls_result:
                    if item["source_id"] not in first_urls:
                        first_urls[item["source_id"]] = item["url"]

                # Get code example counts per source - NO CONTENT, just counts!
                # Fetch counts individually for each source
                for source_id in source_ids:
                    count_result = await db.fetch(
                        "SELECT COUNT(*) as count FROM archon_code_examples WHERE source_id = $1", source_id
                    )
                    code_example_counts[source_id] = count_result[0]["count"] if count_result else 0

                # Ensure all sources have a count (default to 0)
                for source_id in source_ids:
                    if source_id not in code_example_counts:
                        code_example_counts[source_id] = 0
                    chunk_counts[source_id] = 0  # Default to 0 to avoid timeout

                safe_logfire_info(f"Code example counts: {code_example_counts}")

            # Transform sources to items with batched data
            items = []
            for source in sources:
                source_id = source["source_id"]
                source_metadata = source.get("metadata", {})

                # Use the original source_url from the source record (the URL the user entered)
                # Fall back to first crawled page URL, then to source:// format as last resort
                source_url = source.get("source_url")
                if source_url:
                    display_url = source_url
                else:
                    display_url = first_urls.get(source_id, f"source://{source_id}")

                code_examples_count = code_example_counts.get(source_id, 0)
                chunks_count = chunk_counts.get(source_id, 0)

                # Determine source type - use display_url for type detection
                source_type = self._determine_source_type(source_metadata, display_url)

                item = {
                    "id": source_id,
                    "title": source.get("title", source.get("summary", "Untitled")),
                    "url": display_url,
                    "source_id": source_id,
                    "source_type": source_type,  # Add top-level source_type field
                    "code_examples": [{"count": code_examples_count}]
                    if code_examples_count > 0
                    else [],  # Minimal array just for count display
                    # Provenance tracking fields
                    "embedding_model": source.get("embedding_model"),
                    "embedding_dimensions": source.get("embedding_dimensions"),
                    "embedding_provider": source.get("embedding_provider"),
                    "vectorizer_settings": source.get("vectorizer_settings"),
                    "summarization_model": source.get("summarization_model"),
                    "last_crawled_at": source.get("last_crawled_at"),
                    "last_vectorized_at": source.get("last_vectorized_at"),
                    "metadata": {
                        "knowledge_type": source_metadata.get("knowledge_type", "technical"),
                        "tags": source_metadata.get("tags", []),
                        "source_type": source_type,
                        "status": "active",
                        "description": source_metadata.get("description", source.get("summary", "")),
                        "chunks_count": chunks_count,
                        "word_count": source.get("total_word_count", 0),
                        "estimated_pages": round(source.get("total_word_count", 0) / 250, 1),
                        "pages_tooltip": f"{round(source.get('total_word_count', 0) / 250, 1)} pages (≈ {source.get('total_word_count', 0):,} words)",
                        "last_scraped": source.get("updated_at"),
                        "file_name": source_metadata.get("file_name"),
                        "file_type": source_metadata.get("file_type"),
                        "update_frequency": source_metadata.get("update_frequency", 7),
                        "code_examples_count": code_examples_count,
                        **source_metadata,
                    },
                    "created_at": source.get("created_at"),
                    "updated_at": source.get("updated_at"),
                }
                items.append(item)

            safe_logfire_info(f"Knowledge items retrieved | total={total} | page={page} | filtered_count={len(items)}")

            return {
                "items": items,
                "total": total,
                "page": page,
                "per_page": per_page,
                "pages": (total + per_page - 1) // per_page,
            }

        except Exception as e:
            safe_logfire_error(f"Failed to list knowledge items | error={str(e)}")
            raise

    async def get_item(self, source_id: str) -> dict[str, Any] | None:
        """
        Get a single knowledge item by source ID.

        Args:
            source_id: The source ID to retrieve

        Returns:
            Knowledge item dict or None if not found
        """
        try:
            safe_logfire_info(f"Getting knowledge item | source_id={source_id}")

            # Get the source record
            db = get_database_connector()
            result = await db.fetch("SELECT * FROM archon_sources WHERE source_id = $1", source_id)

            if not result:
                return None

            # Transform the source to item format
            item = await self._transform_source_to_item(dict(result[0]))
            return item

        except Exception as e:
            safe_logfire_error(f"Failed to get knowledge item | error={str(e)} | source_id={source_id}")
            return None

    async def update_item(self, source_id: str, updates: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        """
        Update a knowledge item's metadata.

        Args:
            source_id: The source ID to update
            updates: Dictionary of fields to update

        Returns:
            Tuple of (success, result)
        """
        try:
            safe_logfire_info(f"Updating knowledge item | source_id={source_id} | updates={updates}")

            db = get_database_connector()
            import json

            # Prepare update data
            update_data = {}

            # Handle title updates
            if "title" in updates:
                update_data["title"] = updates["title"]

            # Handle metadata updates
            metadata_fields = [
                "description",
                "knowledge_type",
                "tags",
                "status",
                "update_frequency",
                "group_name",
            ]
            metadata_updates = {k: v for k, v in updates.items() if k in metadata_fields}

            if metadata_updates:
                # Get current metadata
                current_response = await db.fetch("SELECT metadata FROM archon_sources WHERE source_id = $1", source_id)
                if current_response:
                    current_metadata = current_response[0].get("metadata", {})
                    current_metadata.update(metadata_updates)
                    update_data["metadata"] = current_metadata
                else:
                    update_data["metadata"] = metadata_updates

            # Build dynamic UPDATE query
            set_clauses = []
            params = []
            param_count = 1

            for key, value in update_data.items():
                set_clauses.append(f"{key} = ${param_count}")
                # Serialize metadata as JSON
                if key == "metadata":
                    params.append(json.dumps(value))
                else:
                    params.append(value)
                param_count += 1

            params.append(source_id)

            # Perform the update
            result = await db.fetch(
                f"UPDATE archon_sources SET {', '.join(set_clauses)} WHERE source_id = ${param_count} RETURNING *",
                *params,
            )

            if result:
                safe_logfire_info(f"Knowledge item updated successfully | source_id={source_id}")
                return True, {
                    "success": True,
                    "message": f"Successfully updated knowledge item {source_id}",
                    "source_id": source_id,
                }
            else:
                safe_logfire_error(f"Knowledge item not found | source_id={source_id}")
                return False, {"error": f"Knowledge item {source_id} not found"}

        except Exception as e:
            safe_logfire_error(f"Failed to update knowledge item | error={str(e)} | source_id={source_id}")
            return False, {"error": str(e)}

    async def get_available_sources(self) -> dict[str, Any]:
        """
        Get all available sources with their details.

        Returns:
            Dict containing sources list and count
        """
        try:
            # Query the sources table
            db = get_database_connector()
            result = await db.fetch("SELECT * FROM archon_sources ORDER BY source_id")

            # Format the sources
            sources = []
            if result:
                for source in result:
                    sources.append(
                        {
                            "source_id": source.get("source_id"),
                            "title": source.get("title", source.get("summary", "Untitled")),
                            "summary": source.get("summary"),
                            "metadata": source.get("metadata", {}),
                            "total_words": source.get("total_words", source.get("total_word_count", 0)),
                            "update_frequency": source.get("update_frequency", 7),
                            # Provenance tracking fields
                            "embedding_model": source.get("embedding_model"),
                            "embedding_dimensions": source.get("embedding_dimensions"),
                            "embedding_provider": source.get("embedding_provider"),
                            "vectorizer_settings": source.get("vectorizer_settings"),
                            "summarization_model": source.get("summarization_model"),
                            "last_crawled_at": source.get("last_crawled_at"),
                            "last_vectorized_at": source.get("last_vectorized_at"),
                            "created_at": source.get("created_at"),
                            "updated_at": source.get("updated_at", source.get("created_at")),
                        }
                    )

            return {"success": True, "sources": sources, "count": len(sources)}

        except Exception as e:
            safe_logfire_error(f"Failed to get available sources | error={str(e)}")
            return {"success": False, "error": str(e), "sources": [], "count": 0}

    async def _get_all_sources(self) -> list[dict[str, Any]]:
        """Get all sources from the database."""
        result = await self.get_available_sources()
        return result.get("sources", [])

    async def _transform_source_to_item(self, source: dict[str, Any]) -> dict[str, Any]:
        """
        Transform a source record into a knowledge item with enriched data.

        Args:
            source: The source record from database

        Returns:
            Transformed knowledge item
        """
        source_metadata = source.get("metadata", {})
        source_id = source["source_id"]

        # Get first page URL
        first_page_url = await self._get_first_page_url(source_id)

        # Determine source type
        source_type = self._determine_source_type(source_metadata, first_page_url)

        # Get code examples
        code_examples = await self._get_code_examples(source_id)

        return {
            "id": source_id,
            "title": source.get("title", source.get("summary", "Untitled")),
            "url": first_page_url,
            "source_id": source_id,
            "code_examples": code_examples,
            # Provenance tracking fields
            "embedding_model": source.get("embedding_model"),
            "embedding_dimensions": source.get("embedding_dimensions"),
            "embedding_provider": source.get("embedding_provider"),
            "vectorizer_settings": source.get("vectorizer_settings"),
            "summarization_model": source.get("summarization_model"),
            "last_crawled_at": source.get("last_crawled_at"),
            "last_vectorized_at": source.get("last_vectorized_at"),
            "needs_revectorization": await self._check_needs_revectorization(source),
            "metadata": {
                # Spread source_metadata first, then override with computed values
                **source_metadata,
                "knowledge_type": source_metadata.get("knowledge_type", "technical"),
                "tags": source_metadata.get("tags", []),
                "source_type": source_type,  # This should be the correctly determined source_type
                "status": "active",
                "description": source_metadata.get("description", source.get("summary", "")),
                "chunks_count": await self._get_chunks_count(source_id),  # Get actual chunk count
                "word_count": source.get("total_words", 0),
                "estimated_pages": round(source.get("total_words", 0) / 250, 1),  # Average book page = 250 words
                "pages_tooltip": f"{round(source.get('total_words', 0) / 250, 1)} pages (≈ {source.get('total_words', 0):,} words)",
                "last_scraped": source.get("updated_at"),
                "file_name": source_metadata.get("file_name"),
                "file_type": source_metadata.get("file_type"),
                "update_frequency": source.get("update_frequency", 7),
                "code_examples_count": len(code_examples),
            },
            "created_at": source.get("created_at"),
            "updated_at": source.get("updated_at"),
        }

    async def _get_first_page_url(self, source_id: str) -> str:
        """Get the first page URL for a source."""
        try:
            db = get_database_connector()
            pages_response = await db.fetch(
                "SELECT url FROM archon_crawled_pages WHERE source_id = $1 LIMIT 1", source_id
            )

            if pages_response:
                return pages_response[0].get("url", f"source://{source_id}")

        except Exception as e:
            safe_logfire_error(f"Failed to get first page URL for {source_id}: {e}")

        return f"source://{source_id}"

    async def _get_code_examples(self, source_id: str) -> list[dict[str, Any]]:
        """Get code examples for a source."""
        try:
            db = get_database_connector()
            code_examples_response = await db.fetch(
                "SELECT id, content, summary, metadata FROM archon_code_examples WHERE source_id = $1", source_id
            )

            return [dict(row) for row in code_examples_response] if code_examples_response else []

        except Exception as e:
            safe_logfire_error(f"Failed to get code examples for {source_id}: {e}")
            return []

    async def _check_needs_revectorization(self, source: dict[str, Any]) -> bool:
        """Check if re-vectorization is needed by comparing current settings with stored provenance."""
        try:
            from ..credential_service import credential_service

            stored_embedding_model = source.get("embedding_model")
            stored_embedding_provider = source.get("embedding_provider")
            stored_vectorizer_settings = source.get("vectorizer_settings") or {}

            if not stored_embedding_model:
                return False

            current_embedding_model = await credential_service.get_credential("EMBEDDING_MODEL")
            current_embedding_provider_config = await credential_service.get_active_provider("embedding")
            current_embedding_provider = current_embedding_provider_config.get("provider", "openai")

            if current_embedding_model and stored_embedding_model != current_embedding_model:
                return True

            if stored_embedding_provider and stored_embedding_provider != current_embedding_provider:
                return True

            current_use_contextual = await credential_service.get_credential("USE_CONTEXTUAL_EMBEDDINGS", False)
            stored_use_contextual = stored_vectorizer_settings.get("use_contextual", False)
            if current_use_contextual != stored_use_contextual:
                return True

            current_chunk_size = await credential_service.get_credential("CHUNK_SIZE", 512)
            stored_chunk_size = stored_vectorizer_settings.get("chunk_size", 512)
            if current_chunk_size != stored_chunk_size:
                return True

            return False

        except Exception as e:
            safe_logfire_error(f"Failed to check re-vectorization needs: {e}")
            return False

    def _determine_source_type(self, metadata: dict[str, Any], url: str) -> str:
        """Determine the source type from metadata or URL pattern."""
        stored_source_type = metadata.get("source_type")
        if stored_source_type:
            return stored_source_type

        # Legacy fallback - check URL pattern
        return "file" if url.startswith("file://") else "url"

    def _filter_by_search(self, items: list[dict[str, Any]], search: str) -> list[dict[str, Any]]:
        """Filter items by search term."""
        search_lower = search.lower()
        return [
            item
            for item in items
            if search_lower in item["title"].lower()
            or search_lower in item["metadata"].get("description", "").lower()
            or any(search_lower in tag.lower() for tag in item["metadata"].get("tags", []))
        ]

    def _filter_by_knowledge_type(self, items: list[dict[str, Any]], knowledge_type: str) -> list[dict[str, Any]]:
        """Filter items by knowledge type."""
        return [item for item in items if item["metadata"].get("knowledge_type") == knowledge_type]

    async def _get_chunks_count(self, source_id: str) -> int:
        """Get the actual number of chunks for a source."""
        try:
            # Count the actual rows in crawled_pages for this source
            db = get_database_connector()
            result = await db.fetch(
                "SELECT COUNT(*) as count FROM archon_crawled_pages WHERE source_id = $1", source_id
            )

            # Return the count of pages (chunks)
            return result[0]["count"] if result else 0

        except Exception as e:
            # If we can't get chunk count, return 0
            safe_logfire_info(f"Failed to get chunk count for {source_id}: {e}")
            return 0
