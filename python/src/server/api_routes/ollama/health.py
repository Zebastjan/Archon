"""
Ollama Health Monitoring API Routes

Handles instance health checks and monitoring:
- Check health of multiple Ollama instances
- Get health summary statistics
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from ...config.logfire_config import get_logger
from ...services.ollama.model_discovery_service import model_discovery_service

logger = get_logger(__name__)
router = APIRouter()


@router.get("/instances/health")
async def health_check_endpoint(
    instance_urls: list[str] = Query(..., description="Ollama instance URLs to check"),
    include_models: bool = Query(False, description="Include model count in response"),
) -> dict[str, Any]:
    """
    Check health status of multiple Ollama instances.

    Provides real-time health monitoring with response times, model availability,
    and error diagnostics for distributed Ollama deployments.
    """
    try:
        logger.info(f"Checking health for {len(instance_urls)} instances")

        health_results = {}

        # Check health for each instance
        for instance_url in instance_urls:
            try:
                url = instance_url.rstrip("/")
                health_status = await model_discovery_service.check_instance_health(url)

                health_results[url] = {
                    "is_healthy": health_status.is_healthy,
                    "response_time_ms": health_status.response_time_ms,
                    "models_available": health_status.models_available if include_models else None,
                    "error_message": health_status.error_message,
                    "last_checked": health_status.last_checked,
                }

            except Exception as e:
                logger.warning(f"Health check failed for {instance_url}: {e}")
                health_results[instance_url] = {
                    "is_healthy": False,
                    "response_time_ms": None,
                    "models_available": None,
                    "error_message": str(e),
                    "last_checked": None,
                }

        # Calculate summary statistics
        healthy_count = sum(1 for result in health_results.values() if result["is_healthy"])
        avg_response_time = None
        if healthy_count > 0:
            response_times = [
                r["response_time_ms"] for r in health_results.values() if r["response_time_ms"] is not None
            ]
            if response_times:
                avg_response_time = sum(response_times) / len(response_times)

        return {
            "summary": {
                "total_instances": len(instance_urls),
                "healthy_instances": healthy_count,
                "unhealthy_instances": len(instance_urls) - healthy_count,
                "average_response_time_ms": avg_response_time,
            },
            "instance_status": health_results,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error in health check: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


# Import datetime for the timestamp
from datetime import datetime
