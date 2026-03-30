"""Cache management for model discovery service.

Provides caching utilities for models, capabilities, and health status
to reduce redundant API calls to Ollama instances.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Optional

from ...config.logfire_config import get_logger

if TYPE_CHECKING:
    from .models import OllamaModel, InstanceHealthStatus, ModelCapabilities

logger = get_logger(__name__)


class ModelCache:
    """Cache for model discovery results with TTL support."""

    def __init__(self, ttl: int = 300):
        """Initialize cache with specified TTL.

        Args:
            ttl: Time-to-live in seconds (default: 300 = 5 minutes)
        """
        self._model_cache: dict[str, list["OllamaModel"]] = {}
        self._capability_cache: dict[str, "ModelCapabilities"] = {}
        self._health_cache: dict[str, "InstanceHealthStatus"] = {}
        self._ttl = ttl

    def get_cached_models(self, instance_url: str) -> Optional[list["OllamaModel"]]:
        """Get cached models if not expired.

        Args:
            instance_url: URL of the Ollama instance

        Returns:
            List of cached models or None if expired/missing
        """
        cache_key = f"models_{instance_url}"
        cached_data = self._model_cache.get(cache_key)
        if cached_data:
            # Check if any model in cache is still valid (simple TTL check)
            first_model = cached_data[0] if cached_data else None
            if first_model and first_model.last_updated:
                cache_time = float(first_model.last_updated)
                if time.time() - cache_time < self._ttl:
                    logger.debug(f"Using cached models for {instance_url}")
                    return cached_data
                else:
                    # Expired, remove from cache
                    del self._model_cache[cache_key]
        return None

    def cache_models(self, instance_url: str, models: list["OllamaModel"]) -> None:
        """Cache models with current timestamp.

        Args:
            instance_url: URL of the Ollama instance
            models: List of models to cache
        """
        cache_key = f"models_{instance_url}"
        # Set timestamp for cache expiry
        current_time = str(time.time())
        for model in models:
            model.last_updated = current_time
        self._model_cache[cache_key] = models
        logger.debug(f"Cached {len(models)} models for {instance_url}")

    def get_cached_capabilities(self, model_name: str, instance_url: str) -> Optional["ModelCapabilities"]:
        """Get cached capabilities if available.

        Args:
            model_name: Name of the model
            instance_url: URL of the Ollama instance

        Returns:
            Cached capabilities or None
        """
        cache_key = f"{model_name}@{instance_url}"
        return self._capability_cache.get(cache_key)

    def cache_capabilities(self, model_name: str, instance_url: str, capabilities: "ModelCapabilities") -> None:
        """Cache model capabilities.

        Args:
            model_name: Name of the model
            instance_url: URL of the Ollama instance
            capabilities: Capabilities to cache
        """
        cache_key = f"{model_name}@{instance_url}"
        self._capability_cache[cache_key] = capabilities

    def get_cached_health(self, instance_url: str) -> Optional["InstanceHealthStatus"]:
        """Get cached health status if not expired.

        Args:
            instance_url: URL of the Ollama instance

        Returns:
            Cached health status or None if expired/missing
        """
        cache_key = f"health_{instance_url}"
        cached_health = self._health_cache.get(cache_key)
        if cached_health and cached_health.last_checked:
            cache_time = float(cached_health.last_checked)
            # Use shorter cache for health (30 seconds)
            if time.time() - cache_time < 30:
                return cached_health
        return None

    def cache_health(self, instance_url: str, status: "InstanceHealthStatus") -> None:
        """Cache health status.

        Args:
            instance_url: URL of the Ollama instance
            status: Health status to cache
        """
        cache_key = f"health_{instance_url}"
        self._health_cache[cache_key] = status

    def clear(self) -> None:
        """Clear all cached data."""
        self._model_cache.clear()
        self._capability_cache.clear()
        self._health_cache.clear()
        logger.debug("Model cache cleared")
