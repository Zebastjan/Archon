"""Health API Routes

Provides endpoints for health monitoring and alerting.
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config.logfire_config import get_logger
from ..services.health_monitoring_service import (
    HealthAlert,
    get_health_monitor,
    start_health_monitoring,
    stop_health_monitoring,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/api/health", tags=["health"])


class AlertAcknowledgeRequest(BaseModel):
    """Request to acknowledge an alert."""

    alert_index: int


@router.get("/status")
async def get_health_status() -> dict[str, Any]:
    """Get current health monitoring status.

    Returns:
        Dictionary with monitoring status and failure counts
    """
    monitor = get_health_monitor()
    return monitor.get_status()


@router.get("/alerts")
async def get_alerts(acknowledged: bool | None = None, severity: str | None = None, limit: int = 100) -> dict[str, Any]:
    """Get health alerts.

    Args:
        acknowledged: Filter by acknowledged status
        severity: Filter by severity (critical, warning, info)
        limit: Maximum number of alerts to return

    Returns:
        Dictionary with alerts list
    """
    monitor = get_health_monitor()
    alerts = monitor.get_alerts(acknowledged=acknowledged, severity=severity, limit=limit)

    return {
        "success": True,
        "alerts": [
            {
                "timestamp": a.timestamp.isoformat(),
                "check_name": a.check_name,
                "severity": a.severity,
                "message": a.message,
                "details": a.details,
                "acknowledged": a.acknowledged,
            }
            for a in alerts
        ],
        "count": len(alerts),
    }


@router.post("/alerts/acknowledge")
async def acknowledge_alert(request: AlertAcknowledgeRequest) -> dict[str, Any]:
    """Acknowledge a health alert.

    Args:
        request: AlertAcknowledgeRequest with alert_index

    Returns:
        Dictionary with success status
    """
    monitor = get_health_monitor()
    success = monitor.acknowledge_alert(request.alert_index)

    if success:
        return {"success": True, "message": "Alert acknowledged"}
    else:
        raise HTTPException(status_code=404, detail="Alert not found")


@router.post("/monitoring/start")
async def start_monitoring() -> dict[str, Any]:
    """Start health monitoring service.

    Returns:
        Dictionary with success status
    """
    try:
        await start_health_monitoring()
        return {"success": True, "message": "Health monitoring started"}
    except Exception as e:
        logger.error(f"Failed to start health monitoring: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start: {e}")


@router.post("/monitoring/stop")
async def stop_monitoring() -> dict[str, Any]:
    """Stop health monitoring service.

    Returns:
        Dictionary with success status
    """
    try:
        await stop_health_monitoring()
        return {"success": True, "message": "Health monitoring stopped"}
    except Exception as e:
        logger.error(f"Failed to stop health monitoring: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop: {e}")


@router.get("/check")
async def run_health_check() -> dict[str, Any]:
    """Run immediate health check and return results.

    Returns:
        Dictionary with health check results
    """
    # Quick health check using database
    try:
        from ..services.database import get_database_connector

        db = get_database_connector()

        # Check database connection
        result = await db.fetch("SELECT COUNT(*) as count FROM archon_code_repos")
        repo_count = result[0]["count"] if result else 0

        result = await db.fetch("SELECT COUNT(*) as count FROM archon_code_entities")
        entity_count = result[0]["count"] if result else 0

        return {
            "success": True,
            "status": "healthy",
            "database": {"connected": True, "repos": repo_count, "entities": entity_count},
            "api": {"status": "responding"},
        }
    except Exception as e:
        return {
            "success": False,
            "status": "error",
            "error": str(e),
        }
