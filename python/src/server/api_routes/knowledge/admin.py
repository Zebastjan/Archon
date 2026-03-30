"""
Knowledge Admin API Routes

Administrative endpoints for knowledge management:
- Health checks
- Database metrics
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException

from ...config.logfire_config import get_logger, safe_logfire_error
from ...services.knowledge import DatabaseMetricsService

logger = get_logger(__name__)
router = APIRouter()


@router.get("/database/metrics")
async def get_database_metrics() -> dict[str, Any]:
    """Get database metrics and statistics."""
    try:
        # Use DatabaseMetricsService
        service = DatabaseMetricsService()
        metrics = await service.get_metrics()
        return metrics
    except Exception as e:
        safe_logfire_error(f"Failed to get database metrics | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.get("/health")
async def knowledge_health() -> dict[str, Any]:
    """Knowledge API health check with migration detection."""
    # Check for database migration needs
    from ...main import _check_database_schema

    schema_status = await _check_database_schema()
    if not schema_status["valid"]:
        return {
            "status": "migration_required",
            "service": "knowledge-api",
            "timestamp": datetime.now().isoformat(),
            "ready": False,
            "migration_required": True,
            "message": schema_status["message"],
            "migration_instructions": "Open Supabase Dashboard → SQL Editor → Run: migration/add_source_url_display_name.sql",
        }

    # Removed health check logging to reduce console noise
    result = {
        "status": "healthy",
        "service": "knowledge-api",
        "timestamp": datetime.now().isoformat(),
    }

    return result
