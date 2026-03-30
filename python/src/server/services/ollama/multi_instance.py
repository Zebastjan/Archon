"""Multi-instance model discovery.

Provides concurrent discovery of models across multiple Ollama instances.
"""

import asyncio
from typing import TYPE_CHECKING, Any, cast

from ...config.logfire_config import get_logger
from .discovery import DiscoveryService
from .models import OllamaModel

if TYPE_CHECKING:
    from .caching import ModelCache

logger = get_logger(__name__)


class MultiInstanceDiscovery:
    """Discovers models from multiple Ollama instances concurrently."""

    def __init__(self, cache: "ModelCache", discovery_service: DiscoveryService):
        """Initialize multi-instance discovery.

        Args:
            cache: Cache instance for storing results
            discovery_service: Discovery service for single-instance operations
        """
        self._cache = cache
        self._discovery_service = discovery_service

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
        if not instance_urls:
            return {
                "total_models": 0,
                "chat_models": [],
                "embedding_models": [],
                "host_status": {},
                "discovery_errors": [],
            }

        logger.info(
            f"Discovering models from {len(instance_urls)} Ollama instances with fetch_details={fetch_details}"
        )

        # Discover models from all instances concurrently
        tasks = [
            self._discovery_service.discover_models(url, fetch_details=fetch_details)
            for url in instance_urls
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Aggregate results
        all_models: list[OllamaModel] = []
        chat_models = []
        embedding_models = []
        host_status = {}
        discovery_errors = []

        for url, result in zip(instance_urls, results, strict=False):
            if isinstance(result, Exception):
                error_msg = f"Failed to discover models from {url}: {str(result)}"
                discovery_errors.append(error_msg)
                host_status[url] = {"status": "error", "error": str(result)}
                logger.error(error_msg)
            else:
                # Use cast to tell type checker this is list[OllamaModel]
                models = cast(list[OllamaModel], result)
                all_models.extend(models)
                host_status[url] = {
                    "status": "online",
                    "models_count": str(len(models)),
                    "instance_url": url,
                }

                # Categorize models
                for model in models:
                    model_dict = self._model_to_dict(model)

                    if "chat" in model.capabilities:
                        chat_models.append(model_dict)

                    if "embedding" in model.capabilities:
                        embedding_models.append(
                            {
                                **model_dict,
                                "dimensions": model.embedding_dimensions,
                            }
                        )

        # Remove duplicates (same model on multiple instances)
        unique_models = {}
        for model in all_models:
            key = f"{model.name}@{model.instance_url}"
            unique_models[key] = model

        discovery_result = {
            "total_models": len(unique_models),
            "chat_models": chat_models,
            "embedding_models": embedding_models,
            "host_status": host_status,
            "discovery_errors": discovery_errors,
            "unique_model_names": list({model.name for model in unique_models.values()}),
        }

        logger.info(
            f"Discovery complete: {discovery_result['total_models']} total models, "
            f"{len(chat_models)} chat, {len(embedding_models)} embedding"
        )

        return discovery_result

    def _model_to_dict(self, model: OllamaModel) -> dict[str, Any]:
        """Convert OllamaModel to dictionary for API response.

        Args:
            model: OllamaModel instance

        Returns:
            Dictionary representation of the model
        """
        return {
            "name": model.name,
            "instance_url": model.instance_url,
            "size": model.size,
            "parameters": model.parameters,
            "context_window": model.context_window,
            "max_context_length": model.max_context_length,
            "base_context_length": model.base_context_length,
            "custom_context_length": model.custom_context_length,
            "architecture": model.architecture,
            "format": model.format,
            "parent_model": model.parent_model,
            "capabilities": model.capabilities,
        }
