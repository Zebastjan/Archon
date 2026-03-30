"""Main service facade for Ollama model discovery.

This module provides a backward-compatible thin wrapper around
the modular discovery services.
"""

from .caching import ModelCache
from .discovery import DiscoveryService
from .health import HealthChecker
from .models import InstanceHealthStatus, ModelCapabilities, OllamaModel
from .multi_instance import MultiInstanceDiscovery
from typing import Any


class ModelDiscoveryService:
    """Service for discovering and validating Ollama models across multiple instances.

    This is the main facade class that coordinates the modular discovery services.
    All functionality is delegated to specialized sub-services for maintainability.
    """

    def __init__(self, cache_ttl: int = 300, discovery_timeout: int = 30):
        """Initialize the model discovery service.

        Args:
            cache_ttl: Cache time-to-live in seconds (default: 300 = 5 minutes)
            discovery_timeout: Timeout for discovery operations in seconds (default: 30)
        """
        self._cache = ModelCache(ttl=cache_ttl)
        self._discovery = DiscoveryService(self._cache, discovery_timeout)
        self._health = HealthChecker(self._cache)
        self._multi = MultiInstanceDiscovery(self._cache, self._discovery)

    async def discover_models(self, instance_url: str, fetch_details: bool = False) -> list[OllamaModel]:
        """Discover all available models from an Ollama instance.

        Args:
            instance_url: Base URL of the Ollama instance
            fetch_details: If True, fetch comprehensive model details via /api/show

        Returns:
            List of OllamaModel objects with discovered capabilities
        """
        return await self._discovery.discover_models(instance_url, fetch_details)

    async def get_model_info(self, model_name: str, instance_url: str) -> OllamaModel | None:
        """Get comprehensive information about a specific model.

        Args:
            model_name: Name of the model
            instance_url: Ollama instance URL

        Returns:
            OllamaModel object with complete information or None if not found
        """
        return await self._discovery.get_model_info(model_name, instance_url)

    async def validate_model_capabilities(
        self, model_name: str, instance_url: str, required_capability: str
    ) -> bool:
        """Validate that a model supports a required capability.

        Args:
            model_name: Name of the model to validate
            instance_url: Ollama instance URL
            required_capability: 'chat' or 'embedding'

        Returns:
            True if model supports the capability, False otherwise
        """
        return await self._discovery.validate_model_capabilities(
            model_name, instance_url, required_capability
        )

    async def check_instance_health(self, instance_url: str) -> InstanceHealthStatus:
        """Check the health status of an Ollama instance.

        Args:
            instance_url: Base URL of the Ollama instance

        Returns:
            InstanceHealthStatus with current health information
        """
        return await self._health.check_instance_health(instance_url)

    async def discover_models_from_multiple_instances(
        self, instance_urls: list[str], fetch_details: bool = False
    ) -> dict[str, Any]:
        """Discover models from multiple Ollama instances concurrently.

        Args:
            instance_urls: List of Ollama instance URLs
            fetch_details: If True, fetch comprehensive model details via /api/show

        Returns:
            Dictionary with discovery results and aggregated information
        """
        return await self._multi.discover_models_from_multiple_instances(
            instance_urls, fetch_details
        )

    def clear_cache(self) -> None:
        """Clear all cached model data."""
        self._cache.clear()


# Global service instance for backward compatibility
model_discovery_service = ModelDiscoveryService()
