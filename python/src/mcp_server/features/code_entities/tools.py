"""MCP tools for code entity operations.

Exposes capabilities to query extracted code entities and their relationships,
enabling AI agents to understand code structure and dependencies.
"""

from typing import Any

from mcp.server.fastmcp import FastMCP

from ....server.config.logfire_config import get_logger
from ....server.services.code_entity_service import CodeEntityService

logger = get_logger(__name__)


def register_code_entity_tools(mcp: FastMCP) -> None:
    """
    Register code entity MCP tools.

    Args:
        mcp: FastMCP server instance
    """
    logger.info("registering_code_entity_tools")

    @mcp.tool()
    async def codebase_find_entity(
        repo_id: str,
        name: str,
        entity_type: str | None = None,
        language: str | None = None,
    ) -> dict[str, Any]:
        """
        Find code entities by name in a repository.

        Searches for functions, classes, methods, or other code entities
        matching the given name (supports partial matching).

        Args:
            repo_id: Repository UUID
            name: Entity name to search for (partial match)
            entity_type: Optional filter by entity type (function, class, method, etc.)
            language: Optional filter by language (python, typescript, javascript)

        Returns:
            Dict with matching entities and count

        Example:
            >>> await codebase_find_entity(
            ...     repo_id="uuid",
            ...     name="get_user",
            ...     entity_type="function"
            ... )
        """
        try:
            service = CodeEntityService()

            # Build filter
            entities = await service.find_entity_by_name(repo_id, name, entity_type)

            # Apply language filter if specified
            if language and entities:
                entities = [e for e in entities if e.get("language") == language]

            return {
                "success": True,
                "count": len(entities),
                "entities": [
                    {
                        "id": e["id"],
                        "name": e["name"],
                        "entity_type": e["entity_type"],
                        "language": e["language"],
                        "file_path": e["file_path"],
                        "line_start": e["line_start"],
                        "line_end": e["line_end"],
                        "signature": e.get("signature"),
                        "docstring": e.get("docstring"),
                    }
                    for e in entities[:20]  # Limit to 20 results
                ],
            }

        except Exception as e:
            logger.exception("codebase_find_entity_failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "count": 0,
                "entities": [],
            }

    @mcp.tool()
    async def codebase_get_entity_details(
        entity_id: str,
        include_source: bool = False,
    ) -> dict[str, Any]:
        """
        Get detailed information about a specific code entity.

        Retrieves full details including source code, signature, and metadata.

        Args:
            entity_id: UUID of the entity
            include_source: Whether to include full source code (can be large)

        Returns:
            Dict with entity details

        Example:
            >>> await codebase_get_entity_details(
            ...     entity_id="uuid",
            ...     include_source=True
            ... )
        """
        try:
            service = CodeEntityService()

            # Get entity from database
            # Note: This requires adding a get_entity_by_id method to CodeEntityService
            # For now, we'll return an error indicating this needs implementation

            return {
                "success": False,
                "error": "Method not yet implemented - needs get_entity_by_id in CodeEntityService",
            }

        except Exception as e:
            logger.exception("codebase_get_entity_details_failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
            }

    @mcp.tool()
    async def codebase_get_entity_context(
        entity_id: str,
        include_callees: bool = True,
        include_callers: bool = True,
        max_depth: int = 1,
    ) -> dict[str, Any]:
        """
        Get context around a code entity including its relationships.

        Retrieves the entity and its related entities (functions it calls,
        functions that call it, classes it inherits from, etc.).

        Args:
            entity_id: UUID of the entity
            include_callees: Include entities this entity calls
            include_callers: Include entities that call this entity
            max_depth: How many relationship hops to follow (default 1)

        Returns:
            Dict with entity and related entities

        Example:
            >>> await codebase_get_entity_context(
            ...     entity_id="uuid",
            ...     include_callees=True,
            ...     include_callers=True
            ... )
        """
        try:
            service = CodeEntityService()

            # Build direction filter
            direction = "both"
            if include_callees and not include_callers:
                direction = "outgoing"
            elif include_callers and not include_callees:
                direction = "incoming"
            elif not include_callees and not include_callers:
                return {
                    "success": True,
                    "entity_id": entity_id,
                    "relationships": [],
                    "note": "No relationships requested",
                }

            relationships = await service.get_entity_relationships(
                entity_id=entity_id,
                relationship_types=None,  # All types
                direction=direction,
            )

            return {
                "success": True,
                "entity_id": entity_id,
                "relationship_count": len(relationships),
                "relationships": [
                    {
                        "relationship_id": r.get("relationship_id"),
                        "related_entity_id": r.get("related_entity_id"),
                        "relationship_type": r.get("relationship_type"),
                        "entity_name": r.get("entity_name"),
                        "entity_type": r.get("entity_type"),
                        "file_path": r.get("file_path"),
                    }
                    for r in relationships[:50]  # Limit results
                ],
            }

        except Exception as e:
            logger.exception("codebase_get_entity_context_failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
            }

    @mcp.tool()
    async def codebase_search_by_semantics(
        repo_id: str,
        query: str,
        entity_type: str | None = None,
        language: str | None = None,
        top_k: int = 10,
    ) -> dict[str, Any]:
        """
        Search code entities by semantic similarity.

        Uses vector embeddings to find code entities semantically similar
        to the query text. Good for finding functionality when you don't
        know the exact function names.

        Args:
            repo_id: Repository UUID
            query: Natural language query describing what you're looking for
            entity_type: Optional filter by entity type
            language: Optional filter by language
            top_k: Number of results to return (default 10)

        Returns:
            Dict with matching entities ranked by similarity

        Example:
            >>> await codebase_search_by_semantics(
            ...     repo_id="uuid",
            ...     query="user authentication",
            ...     entity_type="function"
            ... )
        """
        try:
            # Note: This requires integration with embedding service
            # For now, return a placeholder indicating this needs implementation

            return {
                "success": False,
                "error": "Semantic search not yet implemented - requires embedding generation",
                "query": query,
            }

        except Exception as e:
            logger.exception("codebase_search_by_semantics_failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
            }

    @mcp.tool()
    async def codebase_list_entities_in_file(
        repo_id: str,
        file_path: str,
        entity_type: str | None = None,
    ) -> dict[str, Any]:
        """
        List all code entities in a specific file.

        Retrieves all functions, classes, and other entities defined
        in the given file.

        Args:
            repo_id: Repository UUID
            file_path: Path to the file within the repository
            entity_type: Optional filter by entity type

        Returns:
            Dict with entities in the file

        Example:
            >>> await codebase_list_entities_in_file(
            ...     repo_id="uuid",
            ...     file_path="src/services/user.py"
            ... )
        """
        try:
            service = CodeEntityService()

            # This requires adding a method to CodeEntityService
            # For now, we'll use find_entity_by_name with empty filter
            # or we need to add a new method

            return {
                "success": False,
                "error": "Method not yet implemented - needs list_entities_in_file in CodeEntityService",
                "file_path": file_path,
            }

        except Exception as e:
            logger.exception("codebase_list_entities_in_file_failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
            }

    @mcp.tool()
    async def codebase_get_repository_stats(
        repo_id: str,
    ) -> dict[str, Any]:
        """
        Get statistics about code entities in a repository.

        Provides counts of entities by type, language, and relationships.

        Args:
            repo_id: Repository UUID

        Returns:
            Dict with repository statistics

        Example:
            >>> await codebase_get_repository_stats(repo_id="uuid")
        """
        try:
            service = CodeEntityService()

            # This would require adding aggregate query methods
            # For now, return placeholder

            return {
                "success": False,
                "error": "Method not yet implemented - needs aggregate queries in CodeEntityService",
            }

        except Exception as e:
            logger.exception("codebase_get_repository_stats_failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
            }

    logger.info("code_entity_tools_registered")
