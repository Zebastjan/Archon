"""Health checking for Ollama instances.

Provides health monitoring for Ollama instances with caching support.
"""

import time

import httpx

from ...config.logfire_config import get_logger
from .models import InstanceHealthStatus

logger = get_logger(__name__)


class HealthChecker:
    """Health checker for Ollama instances."""

    def __init__(self, cache: "ModelCache"):
        """Initialize health checker.

        Args:
            cache: Cache instance for storing health results
        """
        self._cache = cache

    async def check_instance_health(self, instance_url: str) -> InstanceHealthStatus:
        """Check the health status of an Ollama instance.

        Args:
            instance_url: Base URL of the Ollama instance

        Returns:
            InstanceHealthStatus with current health information
        """
        # Check cache first (shorter TTL for health checks)
        cached_health = self._cache.get_cached_health(instance_url)
        if cached_health:
            return cached_health

        start_time = time.time()
        status = InstanceHealthStatus(is_healthy=False)

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10)) as client:
                # Try to ping the Ollama API
                ping_url = f"{instance_url.rstrip('/')}/api/tags"

                response = await client.get(ping_url)
                response.raise_for_status()

                data = response.json()
                models_count = len(data.get("models", []))

                status.is_healthy = True
                status.response_time_ms = (time.time() - start_time) * 1000
                status.models_available = models_count
                status.last_checked = str(time.time())

                logger.debug(
                    f"Instance {instance_url} is healthy: {models_count} models, "
                    f"{status.response_time_ms:.0f}ms"
                )

        except httpx.TimeoutException:
            status.error_message = "Connection timeout"
            logger.warning(f"Health check timeout for {instance_url}")
        except httpx.HTTPStatusError as e:
            status.error_message = f"HTTP {e.response.status_code}"
            logger.warning(f"Health check HTTP error for {instance_url}: {e.response.status_code}")
        except Exception as e:
            status.error_message = str(e)
            logger.warning(f"Health check failed for {instance_url}: {e}")

        # Cache the result
        self._cache.cache_health(instance_url, status)

        return status
