"""MCP Tools for Codebase Intelligence

Exposes code entity search and analysis through MCP protocol.
Designed for integration with Claude Code, OpenCode, Windsurf, etc.
"""

import json
from typing import Any

from src.server.services.code_entity_service import CodeEntityService
from src.server.services.database.db_connector import get_database_connector, initialize_database
from src.server.services.embedding_service import get_embedding_service


class CodebaseMCPTools:
    """MCP tools for codebase intelligence.

    These tools expose code search, semantic similarity, and relationship
    traversal to AI agents through the MCP protocol.
    """

    def __init__(self):
        self._code_service = CodeEntityService()
        self._embedding_service = get_embedding_service()

    async def _ensure_db(self):
        """Ensure database is initialized."""
        await initialize_database()
        db = get_database_connector()
        await db.initialize()
        return db

    # =========================================================================
    # CORE SEARCH TOOLS
    # =========================================================================

    async def codebase_find_entity(self, repo_id: str, query: str, entity_type: str | None = None) -> dict[str, Any]:
        """Find code entities by name (fuzzy match).

        Use this when you know the approximate name of a function, class, or method
        and want to find its exact location and signature.

        Args:
            repo_id: Repository UUID (use 'archon-python', 'syllablaze', or 'octofriend')
            query: Entity name or partial name (e.g., "extract_entities")
            entity_type: Optional filter: 'function', 'method', 'class', 'interface'

        Returns:
            List of matching entities with file paths, line numbers, and signatures

        Example:
            >>> await codebase_find_entity("archon-python", "extract_entities")
            >>> await codebase_find_entity("archon-python", "CodeEntity", "class")
        """
        try:
            results = await self._code_service.find_entity_by_name(repo_id, query, entity_type)
            return {
                "status": "success",
                "count": len(results),
                "results": [
                    {
                        "id": r["id"],
                        "name": r["name"],
                        "type": r["entity_type"],
                        "file": r["file_path"],
                        "line": r["line_start"],
                        "signature": r.get("signature", ""),
                        "language": r["language"],
                    }
                    for r in results[:20]  # Limit to 20 results
                ],
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def codebase_semantic_search(self, repo_id: str, query: str, limit: int = 10) -> dict[str, Any]:
        """Search code by semantic meaning (not just name matching).

        Use this when you want to find code related to a concept, not just
        by exact name. Great for "find all functions that handle authentication"
        or "show me database connection code".

        Args:
            repo_id: Repository UUID
            query: Natural language description (e.g., "database connection pooling")
            limit: Maximum results (default 10)

        Returns:
            Ranked list of semantically similar code entities

        Example:
            >>> await codebase_semantic_search("archon-python", "handle git commits")
            >>> await codebase_semantic_search("octofriend", "MCP tool registration")
        """
        try:
            db = await self._ensure_db()

            # Generate embedding for query
            embedding = await self._embedding_service.generate_for_code_entity(
                name=query,
                signature=None,
                docstring=None,
                source_code=None,
            )

            if not embedding:
                return {"status": "error", "message": "Failed to generate query embedding"}

            # Search with 1024 dimension
            results = await self._code_service.search_entities(
                query_embedding=embedding,
                embedding_dimension=1024,
                match_count=limit,
                repo_filter=repo_id,
            )

            return {
                "status": "success",
                "count": len(results),
                "query": query,
                "results": [
                    {
                        "id": r["id"],
                        "name": r["name"],
                        "type": r["entity_type"],
                        "file": r["file_path"],
                        "line": r["line_start"],
                        "signature": r.get("signature", ""),
                        "similarity": round(r.get("similarity", 0), 3),
                    }
                    for r in results
                ],
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def codebase_get_entity_context(self, entity_id: str) -> dict[str, Any]:
        """Get full context for a code entity including relationships.

        Use this after finding an entity to understand:
        - What calls this entity (callers)
        - What this entity calls (callees)
        - What class/file it belongs to
        - Full source code

        Args:
            entity_id: UUID of the entity (from find_entity or semantic_search)

        Returns:
            Full entity details with relationships

        Example:
            >>> await codebase_get_entity_context("uuid-from-previous-search")
        """
        try:
            db = await self._ensure_db()

            # Get entity details
            entity = await self._code_service.get_entity_by_id(entity_id)
            if not entity:
                return {"status": "error", "message": f"Entity {entity_id} not found"}

            # Get relationships
            outgoing = await self._code_service.get_entity_relationships(entity_id, direction="outgoing")
            incoming = await self._code_service.get_entity_relationships(entity_id, direction="incoming")

            return {
                "status": "success",
                "entity": {
                    "id": entity["id"],
                    "name": entity["name"],
                    "type": entity["entity_type"],
                    "file": entity["file_path"],
                    "line_start": entity["line_start"],
                    "line_end": entity["line_end"],
                    "signature": entity.get("signature", ""),
                    "docstring": entity.get("docstring", ""),
                    "source_code": entity.get("source_code", "")[:2000],  # Truncate
                    "language": entity["language"],
                },
                "relationships": {
                    "calls": [  # This entity calls these
                        {"name": r["entity_name"], "type": r["entity_type"], "file": r["file_path"]}
                        for r in outgoing
                        if r["relationship_type"] == "CALLS"
                    ],
                    "called_by": [  # These call this entity
                        {"name": r["entity_name"], "type": r["entity_type"], "file": r["file_path"]}
                        for r in incoming
                        if r["relationship_type"] == "CALLS"
                    ],
                    "inherits_from": [
                        {"name": r["entity_name"], "type": r["entity_type"]}
                        for r in outgoing
                        if r["relationship_type"] == "INHERITS"
                    ],
                    "inherited_by": [
                        {"name": r["entity_name"], "type": r["entity_type"]}
                        for r in incoming
                        if r["relationship_type"] == "INHERITS"
                    ],
                },
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def codebase_find_callers(self, repo_id: str, function_name: str) -> dict[str, Any]:
        """Find all code that calls a specific function.

        Use this to understand impact of changes or find usage examples.

        Args:
            repo_id: Repository UUID
            function_name: Name of the function to find callers for

        Returns:
            List of entities that call the specified function

        Example:
            >>> await codebase_find_callers("archon-python", "extract_entities")
        """
        try:
            # First find the entity
            entities = await self._code_service.find_entity_by_name(repo_id, function_name)
            if not entities:
                return {"status": "error", "message": f"Function {function_name} not found"}

            # Get callers for first match
            entity_id = entities[0]["id"]
            incoming = await self._code_service.get_entity_relationships(
                entity_id, relationship_types=["CALLS"], direction="incoming"
            )

            return {
                "status": "success",
                "target": entities[0]["name"],
                "file": entities[0]["file_path"],
                "caller_count": len(incoming),
                "callers": [
                    {
                        "name": r["entity_name"],
                        "type": r["entity_type"],
                        "file": r["file_path"],
                        "line": r["metadata"].get("line", "unknown") if r["metadata"] else "unknown",
                    }
                    for r in incoming
                ],
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def codebase_repo_stats(self, repo_id: str) -> dict[str, Any]:
        """Get high-level statistics about a repository.

        Use this to understand codebase structure before diving in.

        Args:
            repo_id: Repository UUID

        Returns:
            Summary statistics: entity counts by type, language distribution

        Example:
            >>> await codebase_repo_stats("archon-python")
        """
        try:
            stats = await self._code_service.get_repository_stats(repo_id)
            return {
                "status": "success",
                "repo_id": repo_id,
                "summary": {
                    "by_type": stats.get("by_type", {}),
                    "by_language": stats.get("by_language", {}),
                    "total_relationships": stats.get("total_relationships", 0),
                },
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # =========================================================================
    # UTILITY TOOLS
    # =========================================================================

    async def codebase_list_repos(self) -> dict[str, Any]:
        """List all ingested repositories.

        Use this to discover available repositories before querying.
        """
        try:
            db = await self._ensure_db()

            results = await db.fetch("""
                SELECT DISTINCT repo_id, 
                       MIN(file_path) as sample_file,
                       COUNT(*) as entity_count
                FROM archon_code_entities
                GROUP BY repo_id
                ORDER BY entity_count DESC
            """)

            return {
                "status": "success",
                "count": len(results),
                "repositories": [
                    {
                        "repo_id": r["repo_id"],
                        "name": r["sample_file"].split("/")[0] if r["sample_file"] else "unknown",
                        "entity_count": r["entity_count"],
                    }
                    for r in results
                ],
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def codebase_find_by_file(self, repo_id: str, file_path: str) -> dict[str, Any]:
        """List all entities in a specific file.

        Use this when you know the file and want to see what's defined in it.

        Args:
            repo_id: Repository UUID
            file_path: Relative file path (e.g., "src/server/services/code_entity_service.py")
        """
        try:
            db = await self._ensure_db()

            results = await db.fetch(
                """
                SELECT id, name, entity_type, line_start, signature
                FROM archon_code_entities
                WHERE repo_id = $1 AND file_path = $2
                ORDER BY line_start
            """,
                repo_id,
                file_path,
            )

            return {
                "status": "success",
                "file": file_path,
                "count": len(results),
                "entities": [
                    {
                        "id": r["id"],
                        "name": r["name"],
                        "type": r["entity_type"],
                        "line": r["line_start"],
                        "signature": r.get("signature", ""),
                    }
                    for r in results
                ],
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


# Singleton for fast access
_codebase_tools: CodebaseMCPTools | None = None


def get_codebase_tools() -> CodebaseMCPTools:
    """Get or create codebase tools singleton."""
    global _codebase_tools
    if _codebase_tools is None:
        _codebase_tools = CodebaseMCPTools()
    return _codebase_tools
