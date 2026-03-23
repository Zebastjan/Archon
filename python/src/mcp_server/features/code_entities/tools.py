"""MCP tools for code entity operations.

Exposes capabilities to query extracted code entities and their relationships,
enabling AI agents to understand code structure and dependencies.
"""

from typing import Any

from mcp.server.fastmcp import FastMCP

from src.mcp_server.utils.error_handling import MCPErrorFormatter
from src.server.config.logfire_config import get_logger
from src.server.services.code_entity_service import CodeEntityService
from src.server.services.embedding_service import EmbeddingService

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
            logger.exception("codebase_find_entity_failed: %s", str(e))
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
            entity = await service.get_entity_by_id(entity_id)

            if not entity:
                return {
                    "success": False,
                    "error": f"Entity not found: {entity_id}",
                }

            # Build response
            result = {
                "id": entity["id"],
                "name": entity["name"],
                "entity_type": entity["entity_type"],
                "language": entity["language"],
                "file_path": entity["file_path"],
                "line_start": entity["line_start"],
                "line_end": entity["line_end"],
                "signature": entity.get("signature"),
                "docstring": entity.get("docstring"),
                "commit_sha": entity.get("commit_sha"),
                "repo_id": entity.get("repo_id"),
            }

            # Include source code if requested
            if include_source:
                result["source_code"] = entity.get("source_code")

            return {
                "success": True,
                "entity": result,
            }

        except Exception as e:
            logger.exception("codebase_get_entity_details_failed: %s", str(e))
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
            logger.exception("codebase_get_entity_context_failed: %s", str(e))
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
            service = CodeEntityService()
            embedding_service = EmbeddingService()

            # Generate embedding for the query
            query_embedding = await embedding_service.generate(text=query)

            if not query_embedding:
                return {
                    "success": False,
                    "error": "Failed to generate embedding for query",
                    "query": query,
                }

            embedding_dimension = len(query_embedding)

            # Search for similar entities
            entities = await service.search_entities(
                query_embedding=query_embedding,
                embedding_dimension=embedding_dimension,
                match_count=top_k * 2,  # Fetch extra for filtering
                repo_filter=repo_id,
            )

            # Apply filters
            if entity_type:
                entities = [e for e in entities if e.get("entity_type") == entity_type]
            if language:
                entities = [e for e in entities if e.get("language") == language]

            # Limit results
            entities = entities[:top_k]

            return {
                "success": True,
                "query": query,
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
                        "similarity": round(e.get("similarity", 0), 4),
                    }
                    for e in entities
                ],
            }

        except Exception as e:
            logger.exception("codebase_search_by_semantics_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
                "query": query,
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

            entities = await service.list_entities_in_file(
                repo_id=repo_id,
                file_path=file_path,
                entity_type=entity_type,
            )

            return {
                "success": True,
                "repo_id": repo_id,
                "file_path": file_path,
                "count": len(entities),
                "entities": [
                    {
                        "id": e["id"],
                        "name": e["name"],
                        "entity_type": e["entity_type"],
                        "language": e["language"],
                        "line_start": e["line_start"],
                        "line_end": e["line_end"],
                        "signature": e.get("signature"),
                        "docstring": e.get("docstring"),
                    }
                    for e in entities
                ],
            }

        except Exception as e:
            logger.exception("codebase_list_entities_in_file_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
                "file_path": file_path,
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

            stats = await service.get_repository_stats(repo_id)

            if not stats:
                return {
                    "success": False,
                    "error": f"Failed to get statistics for repository: {repo_id}",
                }

            return {
                "success": True,
                "stats": stats,
            }

        except Exception as e:
            logger.exception("codebase_get_repository_stats_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
            }

    @mcp.tool()
    async def codebase_entity_evolution(
        repo_id: str,
        entity_name: str,
        entity_type: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """
        Track an entity's evolution across commits.

        Shows all versions of an entity (function, class, etc.) across
        different commits, revealing how the code has changed over time.

        Args:
            repo_id: Repository UUID
            entity_name: Name of the entity to track
            entity_type: Optional filter by entity type (function, class, method, etc.)
            limit: Maximum number of versions to return (default 10)

        Returns:
            Dict with entity versions across commits

        Example:
            >>> await codebase_entity_evolution(
            ...     repo_id="uuid",
            ...     entity_name="authenticate_user",
            ...     entity_type="function"
            ... )
        """
        try:
            from src.server.services.database.db_connector import get_database_connector

            db = get_database_connector()

            # Build query
            query = """
                SELECT 
                    e.name,
                    e.entity_type,
                    e.file_path,
                    e.line_start,
                    e.line_end,
                    e.commit_sha,
                    e.parent_commit_sha,
                    e.branch_name,
                    e.change_type,
                    e.created_at,
                    e.source_code
                FROM archon_code_entities e
                JOIN archon_code_repos r ON e.repo_id = r.id
                WHERE r.id = $1
                  AND e.name = $2
            """

            params = [repo_id, entity_name]

            if entity_type:
                query += " AND e.entity_type = $3"
                params.append(entity_type)

            query += " ORDER BY e.created_at DESC LIMIT $" + str(len(params) + 1)
            params.append(limit)

            entities = await db.fetch(query, *params)

            return {
                "success": True,
                "entity_name": entity_name,
                "count": len(entities),
                "versions": [
                    {
                        "name": e["name"],
                        "entity_type": e["entity_type"],
                        "file_path": e["file_path"],
                        "lines": f"{e['line_start']}-{e['line_end']}",
                        "commit_sha": e["commit_sha"][:8] if e["commit_sha"] else None,
                        "branch": e["branch_name"],
                        "change_type": e["change_type"] or "unknown",
                        "created_at": str(e["created_at"]),
                    }
                    for e in entities
                ],
            }

        except Exception as e:
            logger.exception("codebase_entity_evolution_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
                "entity_name": entity_name,
            }

    @mcp.tool()
    async def codebase_commits(
        repo_id: str,
        limit: int = 20,
    ) -> dict[str, Any]:
        """
        List commits with code changes.

        Returns commits with summaries of what changed:
        number of entities added, modified, deleted.

        Args:
            repo_id: Repository UUID
            limit: Maximum number of commits to return (default 20)

        Returns:
            Dict with commits and change summaries

        Example:
            >>> await codebase_commits(repo_id="uuid", limit=10)
        """
        try:
            from src.server.services.database.db_connector import get_database_connector

            db = get_database_connector()

            commits = await db.fetch(
                """
                SELECT 
                    e.commit_sha,
                    e.branch_name,
                    COUNT(*) as entity_count,
                    COUNT(DISTINCT e.file_path) as files_changed,
                    COUNT(*) FILTER (WHERE e.change_type = 'added') as added,
                    COUNT(*) FILTER (WHERE e.change_type = 'modified') as modified,
                    COUNT(*) FILTER (WHERE e.change_type = 'deleted') as deleted
                FROM archon_code_entities e
                JOIN archon_code_repos r ON e.repo_id = r.id
                WHERE r.id = $1
                GROUP BY e.commit_sha, e.branch_name
                ORDER BY MAX(e.created_at) DESC
                LIMIT $2
                """,
                repo_id,
                limit,
            )

            return {
                "success": True,
                "count": len(commits),
                "commits": [
                    {
                        "commit_sha": c["commit_sha"][:8] if c["commit_sha"] else "unknown",
                        "branch": c["branch_name"],
                        "entities": c["entity_count"],
                        "files_changed": c["files_changed"],
                        "added": c["added"] or 0,
                        "modified": c["modified"] or 0,
                        "deleted": c["deleted"] or 0,
                    }
                    for c in commits
                ],
            }

        except Exception as e:
            logger.exception("codebase_commits_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
            }

    @mcp.tool()
    async def codebase_compare_branches(
        repo_id: str,
        branch1: str,
        branch2: str,
    ) -> dict[str, Any]:
        """
        Compare code entities between two branches.

        Shows entities unique to each branch and entities that differ
        between branches.

        Args:
            repo_id: Repository UUID
            branch1: First branch name (e.g., "main")
            branch2: Second branch name (e.g., "feature/auth")

        Returns:
            Dict with comparison results

        Example:
            >>> await codebase_compare_branches(
            ...     repo_id="uuid",
            ...     branch1="main",
            ...     branch2="feature/auth"
            ... )
        """
        try:
            from src.server.services.database.db_connector import get_database_connector

            db = get_database_connector()

            # Get entities unique to branch1
            branch1_only = await db.fetch(
                """
                SELECT DISTINCT e.name, e.entity_type, e.file_path
                FROM archon_code_entities e
                JOIN archon_code_repos r ON e.repo_id = r.id
                WHERE r.id = $1
                  AND e.branch_name = $2
                  AND e.entity_identity NOT IN (
                      SELECT entity_identity 
                      FROM archon_code_entities e2
                      JOIN archon_code_repos r2 ON e2.repo_id = r2.id
                      WHERE r2.id = $1 AND e2.branch_name = $3
                  )
                ORDER BY e.file_path, e.name
                LIMIT 50
                """,
                repo_id,
                branch1,
                branch2,
            )

            # Get entities unique to branch2
            branch2_only = await db.fetch(
                """
                SELECT DISTINCT e.name, e.entity_type, e.file_path
                FROM archon_code_entities e
                JOIN archon_code_repos r ON e.repo_id = r.id
                WHERE r.id = $1
                  AND e.branch_name = $2
                  AND e.entity_identity NOT IN (
                      SELECT entity_identity 
                      FROM archon_code_entities e2
                      JOIN archon_code_repos r2 ON e2.repo_id = r2.id
                      WHERE r2.id = $1 AND e2.branch_name = $3
                  )
                ORDER BY e.file_path, e.name
                LIMIT 50
                """,
                repo_id,
                branch2,
                branch1,
            )

            return {
                "success": True,
                "branch1": branch1,
                "branch2": branch2,
                "only_in_branch1": {
                    "count": len(branch1_only),
                    "entities": [
                        {"name": e["name"], "type": e["entity_type"], "file": e["file_path"]}
                        for e in branch1_only[:20]  # Limit to 20
                    ],
                },
                "only_in_branch2": {
                    "count": len(branch2_only),
                    "entities": [
                        {"name": e["name"], "type": e["entity_type"], "file": e["file_path"]}
                        for e in branch2_only[:20]  # Limit to 20
                    ],
                },
            }

        except Exception as e:
            logger.exception("codebase_compare_branches_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
            }

    @mcp.tool()
    async def codebase_when_added(
        repo_id: str,
        entity_name: str,
    ) -> dict[str, Any]:
        """
        Find when an entity was first added to the codebase.

        Returns the first commit where the entity appeared,
        including commit SHA, branch, and date.

        Args:
            repo_id: Repository UUID
            entity_name: Name of the entity

        Returns:
            Dict with first appearance information

        Example:
            >>> await codebase_when_added(
            ...     repo_id="uuid",
            ...     entity_name="UserService"
            ... )
        """
        try:
            from src.server.services.database.db_connector import get_database_connector

            db = get_database_connector()

            result = await db.fetchrow(
                """
                SELECT 
                    e.name,
                    e.entity_type,
                    e.file_path,
                    e.commit_sha,
                    e.branch_name,
                    MIN(e.created_at) as first_seen
                FROM archon_code_entities e
                JOIN archon_code_repos r ON e.repo_id = r.id
                WHERE r.id = $1
                  AND e.name = $2
                GROUP BY e.name, e.entity_type, e.file_path, e.commit_sha, e.branch_name
                ORDER BY first_seen ASC
                LIMIT 1
                """,
                repo_id,
                entity_name,
            )

            if not result:
                return {
                    "success": False,
                    "error": f"Entity '{entity_name}' not found",
                }

            return {
                "success": True,
                "entity_name": result["name"],
                "entity_type": result["entity_type"],
                "file_path": result["file_path"],
                "commit_sha": result["commit_sha"][:8] if result["commit_sha"] else None,
                "branch": result["branch_name"],
                "first_seen": str(result["first_seen"]),
            }

        except Exception as e:
            logger.exception("codebase_when_added_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
            }

    logger.info("code_entity_tools_registered")
