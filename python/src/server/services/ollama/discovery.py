"""Core model discovery and enrichment logic.

Handles discovery of models from Ollama instances and enrichment with
capability information using pattern-based detection and API testing.
"""

import time
from typing import TYPE_CHECKING, Any

import httpx

from ...config.logfire_config import get_logger
from .capability_testing import CapabilityTester
from .details import ModelDetailsFetcher
from .models import ModelCapabilities, OllamaModel

if TYPE_CHECKING:
    from .caching import ModelCache

logger = get_logger(__name__)

# Pattern definitions for model classification
EMBEDDING_PATTERNS = [
    "embed", "embedding", "bge-", "e5-", "sentence-",
    "arctic-embed", "nomic-embed", "mxbai-embed",
    "snowflake-arctic-embed", "gte-", "stella-",
]

CHAT_PATTERNS = [
    "phi", "qwen", "llama", "mistral", "gemma", "deepseek",
    "codellama", "orca", "vicuna", "wizardlm", "solar",
    "mixtral", "chatglm", "baichuan", "yi", "zephyr",
    "openchat", "starling", "nous-hermes",
]

# Model families supporting advanced features
FUNCTION_CALLING_FAMILIES = ["qwen", "llama3", "phi3", "mistral"]
STRUCTURED_OUTPUT_FAMILIES = ["llama", "phi", "gemma"]


class DiscoveryService:
    """Service for discovering and enriching Ollama models."""

    def __init__(self, cache: "ModelCache", discovery_timeout: int = 30):
        """Initialize discovery service.

        Args:
            cache: Cache instance for storing results
            discovery_timeout: Timeout for discovery operations in seconds
        """
        self._cache = cache
        self._discovery_timeout = discovery_timeout
        self._capability_tester = CapabilityTester()
        self._details_fetcher = ModelDetailsFetcher()

    async def discover_models(
        self, instance_url: str, fetch_details: bool = False
    ) -> list[OllamaModel]:
        """Discover all available models from an Ollama instance.

        Args:
            instance_url: Base URL of the Ollama instance
            fetch_details: If True, fetch comprehensive model details via /api/show

        Returns:
            List of OllamaModel objects with discovered capabilities
        """
        # Check cache first (but skip if we need detailed info)
        if not fetch_details:
            cached_models = self._cache.get_cached_models(instance_url)
            if cached_models:
                return cached_models

        try:
            logger.info(f"Discovering models from Ollama instance: {instance_url}")

            # Use direct HTTP client for /api/tags endpoint (not OpenAI-compatible)
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self._discovery_timeout)
            ) as client:
                # Remove /v1 suffix if present (OpenAI compatibility layer)
                base_url = instance_url.rstrip("/").replace("/v1", "")
                # Ollama API endpoint for listing models
                tags_url = f"{base_url}/api/tags"

                response = await client.get(tags_url)
                response.raise_for_status()
                data = response.json()

                models = []
                if "models" in data:
                    for model_data in data["models"]:
                        # Extract basic model information
                        model = OllamaModel(
                            name=model_data.get("name", "unknown"),
                            tag=model_data.get("name", "unknown"),  # Ollama uses name as tag
                            size=model_data.get("size", 0),
                            digest=model_data.get("digest", ""),
                            capabilities=[],  # Will be filled by capability detection
                            instance_url=instance_url,
                        )

                        # Extract additional model details if available
                        details = model_data.get("details", {})
                        if details:
                            model.parameters = {
                                "family": details.get("family", ""),
                                "parameter_size": details.get("parameter_size", ""),
                                "quantization": details.get("quantization_level", ""),
                            }

                        models.append(model)

                logger.info(f"Discovered {len(models)} models from {instance_url}")

                # Enrich models with capability information
                enriched_models = await self._enrich_model_capabilities(
                    models, instance_url, fetch_details=fetch_details
                )

                # Cache the results
                self._cache.cache_models(instance_url, enriched_models)

                return enriched_models

        except httpx.TimeoutException as e:
            logger.error(f"Timeout discovering models from {instance_url}")
            raise Exception(f"Timeout connecting to Ollama instance at {instance_url}") from e
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error discovering models from {instance_url}: {e.response.status_code}")
            raise Exception(f"HTTP {e.response.status_code} error from {instance_url}") from e
        except Exception as e:
            logger.error(f"Error discovering models from {instance_url}: {e}")
            raise Exception(f"Failed to discover models: {str(e)}") from e

    async def get_model_info(self, model_name: str, instance_url: str) -> OllamaModel | None:
        """Get comprehensive information about a specific model.

        Args:
            model_name: Name of the model
            instance_url: Ollama instance URL

        Returns:
            OllamaModel object with complete information or None if not found
        """
        try:
            models = await self.discover_models(instance_url)

            for model in models:
                if model.name == model_name:
                    return model

            logger.warning(f"Model {model_name} not found on instance {instance_url}")
            return None

        except Exception as e:
            logger.error(f"Error getting model info for {model_name}: {e}")
            return None

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
        try:
            capabilities = await self._detect_model_capabilities(model_name, instance_url)

            if required_capability == "chat":
                return capabilities.supports_chat
            elif required_capability == "embedding":
                return capabilities.supports_embedding
            elif required_capability == "function_calling":
                return capabilities.supports_function_calling
            elif required_capability == "structured_output":
                return capabilities.supports_structured_output
            else:
                logger.warning(f"Unknown capability requirement: {required_capability}")
                return False

        except Exception as e:
            logger.error(f"Error validating model {model_name} for {required_capability}: {e}")
            return False

    async def _enrich_model_capabilities(
        self, models: list[OllamaModel], instance_url: str, fetch_details: bool = False
    ) -> list[OllamaModel]:
        """Enrich models with capability information using optimized pattern-based detection.

        Args:
            models: List of basic model information
            instance_url: Ollama instance URL
            fetch_details: If True, fetch comprehensive model details via /api/show

        Returns:
            Models enriched with capability information
        """
        start_time = time.time()
        logger.info(f"Starting capability enrichment for {len(models)} models from {instance_url}")

        enriched_models = []
        unknown_models = []

        # First pass: Use pattern-based detection for known models
        for model in models:
            model_name_lower = model.name.lower()

            # Check if model matches embedding patterns
            is_embedding_model = any(pattern in model_name_lower for pattern in EMBEDDING_PATTERNS)

            if is_embedding_model:
                # Set embedding capabilities immediately
                model.capabilities = ["embedding"]
                model.embedding_dimensions = self._get_embedding_dimensions(model_name_lower)

                logger.debug(f"Pattern-matched embedding model {model.name} with {model.embedding_dimensions}D")
                enriched_models.append(model)
            else:
                # Check if model matches chat patterns
                is_known_chat_model = any(pattern in model_name_lower for pattern in CHAT_PATTERNS)

                if is_known_chat_model:
                    # Set chat capabilities based on model patterns
                    model.capabilities = ["chat"]

                    # Advanced capability detection based on model families
                    if any(pattern in model_name_lower for pattern in FUNCTION_CALLING_FAMILIES):
                        model.capabilities.extend(["function_calling", "structured_output"])
                    elif any(pattern in model_name_lower for pattern in STRUCTURED_OUTPUT_FAMILIES):
                        model.capabilities.append("structured_output")

                    # Get comprehensive information from /api/show endpoint if requested
                    if fetch_details:
                        await self._details_fetcher.fetch_model_details(model, instance_url)

                    logger.debug(f"Pattern-matched chat model {model.name} with capabilities: {model.capabilities}")
                    enriched_models.append(model)
                else:
                    # Unknown model - needs testing
                    unknown_models.append(model)

        # Log pattern matching results for debugging
        pattern_matched_count = len(enriched_models)
        unknown_count = len(unknown_models)
        logger.info(
            f"Pattern matching results: {pattern_matched_count} models matched patterns, "
            f"{unknown_count} models require API testing"
        )

        if pattern_matched_count > 0:
            matched_names = [m.name for m in enriched_models]
            logger.info(
                f"Pattern-matched models: {', '.join(matched_names[:10])}"
                f"{'...' if len(matched_names) > 10 else ''}"
            )

        if unknown_models:
            unknown_names = [m.name for m in unknown_models]
            logger.info(
                f"Unknown models requiring API testing: {', '.join(unknown_names[:10])}"
                f"{'...' if len(unknown_names) > 10 else ''}"
            )

        # PERFORMANCE MODE: Skip slow API testing entirely
        # Instead of testing unknown models (which takes 30+ minutes), assign reasonable defaults
        if unknown_models:
            logger.info(
                f"PERFORMANCE MODE: Skipping API testing for {len(unknown_models)} unknown models, "
                f"assigning fast defaults"
            )

            for model in unknown_models:
                # Assign capability based on name hints
                model_name_lower = model.name.lower()
                if any(hint in model_name_lower for hint in ["embed", "embedding", "vector"]):
                    model.capabilities = ["embedding"]
                    model.embedding_dimensions = 768  # Safe default
                    logger.debug(f"Fast-assigned embedding capability to {model.name} based on name hints")
                else:
                    model.capabilities = ["chat"]
                    logger.debug(f"Fast-assigned chat capability to {model.name}")

                enriched_models.append(model)

            logger.info(
                f"PERFORMANCE MODE: Fast assignment completed for {len(unknown_models)} models in <1s"
            )

        # Log final timing and results
        end_time = time.time()
        total_duration = end_time - start_time

        logger.info(
            f"Model capability enrichment complete: {len(enriched_models)} total models, "
            f"pattern-matched {pattern_matched_count}, fast-assigned {len(unknown_models)}"
        )
        logger.info(f"Total enrichment time: {total_duration:.2f}s for {instance_url}")

        if pattern_matched_count > 0:
            logger.info(f"Pattern matching saved ~{pattern_matched_count * 10:.1f}s (estimated 10s per model API test)")

        return enriched_models

    def _get_embedding_dimensions(self, model_name_lower: str) -> int:
        """Get embedding dimensions based on model name patterns.

        Args:
            model_name_lower: Lowercase model name

        Returns:
            Estimated embedding dimensions
        """
        if "nomic" in model_name_lower:
            return 768
        elif "bge" in model_name_lower:
            return 1024 if "large" in model_name_lower else 768
        elif "e5" in model_name_lower:
            return 1024 if "large" in model_name_lower else 768
        elif "arctic" in model_name_lower:
            return 1024
        else:
            return 768  # Conservative default

    async def _detect_model_capabilities(
        self, model_name: str, instance_url: str
    ) -> ModelCapabilities:
        """Detect capabilities of a specific model by testing its endpoints.

        Args:
            model_name: Name of the model to test
            instance_url: Ollama instance URL

        Returns:
            ModelCapabilities object with detected capabilities
        """
        # Check cache first
        cached_caps = self._cache.get_cached_capabilities(model_name, instance_url)
        if cached_caps:
            logger.debug(f"Using cached capabilities for {model_name}")
            return cached_caps

        # Use the capability tester
        capabilities = await self._capability_tester.detect_capabilities(model_name, instance_url)

        # Cache the results
        self._cache.cache_capabilities(model_name, instance_url, capabilities)

        return capabilities
