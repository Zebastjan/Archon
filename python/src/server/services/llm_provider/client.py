"""
LLM Provider Client Module

Handles client creation and provider validation.
"""

from contextlib import asynccontextmanager
from typing import Any

import openai

from ...config.logfire_config import get_logger
from ..credential_service import credential_service
from .cache import _get_cached_settings, _sanitize_for_log, _set_cached_settings
from .ollama_utils import _get_optimal_ollama_instance

logger = get_logger(__name__)


def _is_valid_provider(provider: str) -> bool:
    """Basic provider validation."""
    if not provider or not isinstance(provider, str):
        return False
    return provider.lower() in {"openai", "ollama", "google", "openrouter", "anthropic", "grok"}


@asynccontextmanager
async def get_llm_client(
    provider: str | None = None,
    use_embedding_provider: bool = False,
    instance_type: str | None = None,
    base_url: str | None = None,
):
    """
    Create an async OpenAI-compatible client based on the configured provider.

    This context manager handles client creation for different LLM providers
    that support the OpenAI API format, with enhanced support for multi-instance
    Ollama configurations and intelligent instance routing.

    Args:
        provider: Override provider selection
        use_embedding_provider: Use the embedding-specific provider if different
        instance_type: For Ollama multi-instance: 'chat', 'embedding', or None for auto-select
        base_url: Override base URL for specific instance routing

    Yields:
        openai.AsyncOpenAI: An OpenAI-compatible client configured for the selected provider
    """
    client = None
    provider_name: str | None = None
    api_key = None

    try:
        # Get provider configuration from database settings
        if provider:
            # Explicit provider requested - get minimal config
            provider_name = provider
            api_key = await credential_service._get_provider_api_key(provider)

            # Check cache for rag_settings
            cache_key = "rag_strategy_settings"
            rag_settings = _get_cached_settings(cache_key)
            if rag_settings is None:
                rag_settings = await credential_service.get_credentials_by_category("rag_strategy")
                _set_cached_settings(cache_key, rag_settings)

            # For Ollama, don't use the base_url from config - let _get_optimal_ollama_instance decide
            base_url = (
                credential_service._get_provider_base_url(provider, rag_settings) if provider != "ollama" else None
            )
        else:
            # Get configured provider from database
            service_type = "embedding" if use_embedding_provider else "llm"

            # Check cache for provider config
            cache_key = f"provider_config_{service_type}"
            provider_config = _get_cached_settings(cache_key)
            if provider_config is None:
                provider_config = await credential_service.get_active_provider(service_type)
                _set_cached_settings(cache_key, provider_config)

            provider_name = provider_config["provider"]
            api_key = provider_config["api_key"]
            # For Ollama, don't use the base_url from config - let _get_optimal_ollama_instance decide
            base_url = provider_config["base_url"] if provider_name != "ollama" else None

        # Comprehensive provider validation with security checks
        if not _is_valid_provider(provider_name):
            raise ValueError(f"Unsupported LLM provider: {provider_name}")

        # Validate API key format for security
        if api_key:
            if len(api_key.strip()) == 0:
                api_key = None  # Treat empty strings as None
            elif len(api_key) > 500:  # Reasonable API key length limit
                raise ValueError("API key length exceeds security limits")
            # Additional security: check for suspicious patterns
            if any(char in api_key for char in ["\n", "\r", "\t", "\0"]):
                raise ValueError("API key contains invalid characters")

        # Sanitize provider name for logging
        safe_provider_name = _sanitize_for_log(provider_name) if provider_name else "unknown"
        logger.info(f"Creating LLM client for provider: {safe_provider_name}")

        if provider_name == "openai":
            if api_key:
                client = openai.AsyncOpenAI(api_key=api_key)
                logger.info("OpenAI client created successfully")
            else:
                raise ValueError("OpenAI API key is required")

        elif provider_name == "ollama":
            # Get optimal Ollama instance with intelligent routing
            ollama_base_url = await _get_optimal_ollama_instance(
                instance_type=instance_type,
                use_embedding_provider=use_embedding_provider,
                base_url_override=base_url,
            )

            if not ollama_base_url:
                raise ValueError("No healthy Ollama instances available")

            client = openai.AsyncOpenAI(
                base_url=f"{ollama_base_url}/v1",
                api_key="ollama",  # Ollama doesn't require a real API key
            )
            logger.info(f"Ollama client created for instance: {ollama_base_url}")

        elif provider_name == "google":
            if api_key:
                client = openai.AsyncOpenAI(
                    base_url="https://generativelanguage.googleapis.com/v1beta",
                    api_key=api_key,
                )
                logger.info("Google Gemini client created successfully")
            else:
                raise ValueError("Google API key is required")

        elif provider_name == "openrouter":
            if api_key:
                client = openai.AsyncOpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=api_key,
                )
                logger.info("OpenRouter client created successfully")
            else:
                raise ValueError("OpenRouter API key is required")

        elif provider_name == "anthropic":
            if api_key:
                client = openai.AsyncOpenAI(
                    base_url="https://api.anthropic.com/v1",
                    api_key=api_key,
                )
                logger.info("Anthropic client created successfully")
            else:
                raise ValueError("Anthropic API key is required")

        elif provider_name == "grok":
            if api_key:
                client = openai.AsyncOpenAI(
                    base_url="https://api.x.ai/v1",
                    api_key=api_key,
                )
                logger.info("Grok client created successfully")
            else:
                raise ValueError("Grok API key is required")

        else:
            raise ValueError(f"Unsupported LLM provider: {provider_name}")

        yield client

    except Exception as e:
        logger.error(f"Failed to create LLM client for provider '{provider_name}': {e}")
        raise

    finally:
        if client:
            # Note: AsyncOpenAI client doesn't need explicit cleanup
            pass


async def validate_provider_instance(provider: str, instance_url: str | None = None) -> dict[str, any]:
    """
    Validate an LLM provider instance.

    Args:
        provider: The provider name (e.g., "ollama", "openai")
        instance_url: Specific instance URL to validate (for Ollama)

    Returns:
        dict: Validation result with is_available, response_time_ms, error_message, etc.
    """
    import time

    start_time = time.time()

    try:
        if not _is_valid_provider(provider):
            return {
                "is_available": False,
                "error_message": f"Invalid provider: {provider}",
                "response_time_ms": None,
                "models_available": 0,
            }

        # For Ollama, validate the specific instance
        if provider == "ollama":
            if not instance_url:
                return {
                    "is_available": False,
                    "error_message": "Instance URL required for Ollama validation",
                    "response_time_ms": None,
                    "models_available": 0,
                }

            # Test connection to Ollama instance
            from ..ollama.model_discovery_service import model_discovery_service

            health_status = await model_discovery_service.check_instance_health(instance_url.rstrip("/"))

            response_time = (time.time() - start_time) * 1000

            return {
                "is_available": health_status.is_healthy,
                "response_time_ms": response_time,
                "models_available": health_status.models_available,
                "error_message": health_status.error_message,
            }

        # For other providers, basic validation only
        response_time = (time.time() - start_time) * 1000

        return {
            "is_available": True,
            "response_time_ms": response_time,
            "models_available": 0,  # Would need provider-specific implementation
            "error_message": None,
        }

    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        return {
            "is_available": False,
            "response_time_ms": response_time,
            "models_available": 0,
            "error_message": str(e),
        }
