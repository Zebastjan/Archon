"""
Knowledge Source Management API Routes

Handles source operations:
- List available sources for RAG
- Delete sources
"""

from typing import Any

from fastapi import APIRouter, HTTPException

from ...config.logfire_config import get_logger, safe_logfire_error, safe_logfire_info
from ...services.knowledge import KnowledgeItemService
from ...services.source_management_service import SourceManagementService

logger = get_logger(__name__)
router = APIRouter()


@router.get("/rag/sources")
async def get_available_sources() -> dict[str, Any]:
    """Get all available sources for RAG queries."""
    try:
        # Use KnowledgeItemService
        service = KnowledgeItemService()
        result = await service.get_available_sources()

        # Parse result if it's a string
        if isinstance(result, str):
            import json

            result = json.loads(result)

        return result
    except Exception as e:
        safe_logfire_error(f"Failed to get available sources | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.delete("/sources/{source_id}")
async def delete_source(source_id: str) -> dict[str, Any]:
    """Delete a source and all its associated data."""
    try:
        safe_logfire_info(f"Deleting source | source_id={source_id}")

        # Use SourceManagementService directly
        source_service = SourceManagementService()

        success, result_data = source_service.delete_source(source_id)

        if success:
            safe_logfire_info(f"Source deleted successfully | source_id={source_id}")

            return {
                "success": True,
                "message": f"Successfully deleted source {source_id}",
                **result_data,
            }
        else:
            safe_logfire_error(f"Source deletion failed | source_id={source_id} | error={result_data.get('error')}")
            raise HTTPException(status_code=500, detail={"error": result_data.get("error", "Deletion failed")})
    except HTTPException:
        raise
    except Exception as e:
        safe_logfire_error(f"Failed to delete source | error={str(e)} | source_id={source_id}")
        raise HTTPException(status_code=500, detail={"error": str(e)})
