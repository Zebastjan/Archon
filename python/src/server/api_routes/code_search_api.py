"""Code Search API Routes

Provides semantic search over code entities using vector similarity.
"""

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..config.logfire_config import get_logger, safe_logfire_error
from ..services.database import get_database_connector
from ..services.embeddings.embedding_service import create_embedding

logger = get_logger(__name__)
router = APIRouter(prefix="/api/code", tags=["code-search"])


class CodeSearchRequest(BaseModel):
    """Request model for code search."""

    query: str
    match_count: int = 10
    repo_id: str | None = None
    entity_type: str | None = None
    branch_name: str | None = None  # Filter by branch
    commit_sha: str | None = None  # Filter by commit


@router.post("/search")
async def search_code_entities(request: CodeSearchRequest) -> dict[str, Any]:
    """Search code entities using semantic similarity.

    Args:
        request: CodeSearchRequest with query and optional filters

    Returns:
        Dictionary with search results
    """
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=422, detail="Query is required")

    try:
        # Create embedding for query
        query_embedding = await create_embedding(request.query)

        if not query_embedding:
            logger.error("Failed to create embedding for query")
            return {
                "success": False,
                "results": [],
                "query": request.query,
                "error": "Failed to create embedding",
            }

        # Search using database function
        db = get_database_connector()

        # Build filter
        filter_json = {}
        if request.entity_type:
            filter_json["entity_type"] = request.entity_type

        # Convert embedding to PostgreSQL vector format
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        # Call match function with higher match_count to account for branch filtering
        # Fetch 3x the requested amount to allow for branch filtering
        fetch_count = request.match_count * 3 if (request.branch_name or request.commit_sha) else request.match_count
        results = await db.fetch(
            "SELECT * FROM match_archon_code_entities($1::vector, $2, $3, $4)",
            embedding_str,
            fetch_count,
            json.dumps(filter_json),
            request.repo_id,
        )

        # Fetch full entity details including branch/commit info
        if results:
            entity_ids = [str(r["id"]) for r in results]
            placeholders = ",".join(f"${i + 1}" for i in range(len(entity_ids)))
            entity_details = await db.fetch(
                f"""SELECT id, repo_id, file_path, entity_type, name, signature, docstring, 
                          source_code, language, branch_name, commit_sha
                   FROM archon_code_entities 
                   WHERE id IN ({placeholders})""",
                *entity_ids,
            )
            # Create lookup by ID
            entity_lookup = {str(e["id"]): e for e in entity_details}
        else:
            entity_lookup = {}

        # Format results and apply branch/commit filtering
        formatted_results = []
        for result in results:
            entity = entity_lookup.get(str(result["id"]))
            if not entity:
                continue

            # Filter by branch if specified
            if request.branch_name and entity.get("branch_name") != request.branch_name:
                continue

            # Filter by commit if specified (partial match)
            if request.commit_sha:
                entity_commit = entity.get("commit_sha", "")
                if not entity_commit or not entity_commit.startswith(request.commit_sha):
                    continue

            formatted_results.append(
                {
                    "id": str(result["id"]),
                    "repo_id": str(result["repo_id"]) if result["repo_id"] else None,
                    "file_path": result["file_path"],
                    "entity_type": result["entity_type"],
                    "name": result["name"],
                    "signature": result["signature"],
                    "docstring": result["docstring"],
                    "source_code": result["source_code"][:500] if result["source_code"] else None,  # Truncate
                    "language": result["language"],
                    "similarity": float(result["similarity"]),
                    "branch_name": entity.get("branch_name"),
                    "commit_sha": entity.get("commit_sha", "")[:8] if entity.get("commit_sha") else None,
                }
            )

        # Limit to requested count after filtering
        formatted_results = formatted_results[: request.match_count]

        return {
            "success": True,
            "results": formatted_results,
            "query": request.query,
            "match_count": request.match_count,
            "total_found": len(formatted_results),
            "repo_filter": request.repo_id,
            "entity_type_filter": request.entity_type,
            "branch_filter": request.branch_name,
            "commit_filter": request.commit_sha[:8] if request.commit_sha else None,
            "version_scoped": bool(request.branch_name or request.commit_sha),
        }

    except Exception as e:
        logger.error(f"Code search failed: {e}")
        safe_logfire_error(f"Code search failed | error={str(e)} | query={request.query[:50]}")
        raise HTTPException(status_code=500, detail={"error": f"Search failed: {str(e)}"})


@router.get("/repos/{repo_id}/entities")
async def get_repo_entities(
    repo_id: str,
    name: str | None = None,
    entity_type: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """Get entities for a specific repository.

    Args:
        repo_id: Repository ID
        name: Optional filter by entity name (case-insensitive partial match)
        entity_type: Optional filter by entity type
        limit: Maximum number of results
        offset: Pagination offset

    Returns:
        Dictionary with entities list
    """
    try:
        db = get_database_connector()

        # Build query based on filters
        if name and entity_type:
            # Filter by both name and entity_type
            results = await db.fetch(
                """SELECT id, file_path, entity_type, name, signature, docstring, 
                          line_start, line_end, language, commit_sha
                   FROM archon_code_entities 
                   WHERE repo_id = $1 
                     AND name ILIKE $2 
                     AND entity_type = $3
                   ORDER BY file_path, name
                   LIMIT $4 OFFSET $5""",
                repo_id,
                f"%{name}%",
                entity_type,
                limit,
                offset,
            )
        elif name:
            # Filter by name only
            results = await db.fetch(
                """SELECT id, file_path, entity_type, name, signature, docstring, 
                          line_start, line_end, language, commit_sha
                   FROM archon_code_entities 
                   WHERE repo_id = $1 
                     AND name ILIKE $2
                   ORDER BY file_path, name
                   LIMIT $3 OFFSET $4""",
                repo_id,
                f"%{name}%",
                limit,
                offset,
            )
        elif entity_type:
            # Filter by entity_type only
            results = await db.fetch(
                """SELECT id, file_path, entity_type, name, signature, docstring, 
                          line_start, line_end, language, commit_sha
                   FROM archon_code_entities 
                   WHERE repo_id = $1 
                     AND entity_type = $2
                   ORDER BY file_path, name
                   LIMIT $3 OFFSET $4""",
                repo_id,
                entity_type,
                limit,
                offset,
            )
        else:
            # No filters
            results = await db.fetch(
                """SELECT id, file_path, entity_type, name, signature, docstring, 
                          line_start, line_end, language, commit_sha
                   FROM archon_code_entities 
                   WHERE repo_id = $1
                   ORDER BY file_path, name
                   LIMIT $2 OFFSET $3""",
                repo_id,
                limit,
                offset,
            )

        entities = [dict(row) for row in results]

        return {
            "success": True,
            "entities": entities,
            "repo_id": repo_id,
            "name_filter": name,
            "entity_type_filter": entity_type,
            "limit": limit,
            "offset": offset,
            "count": len(entities),
        }

    except Exception as e:
        logger.error(f"Failed to get repo entities: {e}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.get("/entity/{entity_id}")
async def get_entity_details(entity_id: str) -> dict[str, Any]:
    """Get full details for a specific entity.

    Args:
        entity_id: Entity UUID

    Returns:
        Dictionary with entity details
    """
    try:
        db = get_database_connector()

        result = await db.fetchrow(
            """SELECT * FROM archon_code_entities WHERE id = $1""",
            entity_id,
        )

        if not result:
            raise HTTPException(status_code=404, detail="Entity not found")

        return {
            "success": True,
            "entity": dict(result),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get entity: {e}")
        raise HTTPException(status_code=500, detail={"error": str(e)})
