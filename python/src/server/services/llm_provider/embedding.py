"""
LLM Provider Embedding Module

Provides embedding model utilities and validation.
"""

from typing import Any

from ...config.logfire_config import get_logger
from ..credential_service import credential_service
from .cache import _get_cached_settings, _sanitize_for_log, _set_cached_settings

logger = get_logger(__name__)


def _is_valid_provider(provider: str) -> bool:
    """Basic provider validation."""
    if not provider or not isinstance(provider, str):
        return False
    return provider.lower() in {"openai", "ollama", "google", "openrouter", "anthropic", "grok"}


async def get_embedding_model(provider: str | None = None) -> str:
    """
    Get the configured embedding model based on the provider.

    Args:
        provider: Override provider selection

    Returns:
        str: The embedding model to use
    """
    try:
        # Get provider configuration
        if provider:
            # Explicit provider requested
            provider_name = provider
            # Get custom model from settings if any
            cache_key = "rag_strategy_settings"
            rag_settings = _get_cached_settings(cache_key)
            if rag_settings is None:
                rag_settings = await credential_service.get_credentials_by_category("rag_strategy")
                _set_cached_settings(cache_key, rag_settings)
            custom_model = rag_settings.get("EMBEDDING_MODEL", "")
        else:
            # Get configured provider from database
            cache_key = "provider_config_embedding"
            provider_config = _get_cached_settings(cache_key)
            if provider_config is None:
                provider_config = await credential_service.get_active_provider("embedding")
                _set_cached_settings(cache_key, provider_config)
            provider_name = provider_config["provider"]
            custom_model = provider_config["embedding_model"]

        # Comprehensive provider validation for embeddings
        if not _is_valid_provider(provider_name):
            safe_provider = _sanitize_for_log(provider_name)
            logger.warning(f"Invalid embedding provider: {safe_provider}, falling back to OpenAI")
            provider_name = "openai"

        # Use custom model if specified (with validation)
        if custom_model and len(custom_model.strip()) > 0:
            custom_model = custom_model.strip()
            # Basic model name validation
            if len(custom_model) <= 100 and not any(char in custom_model for char in ["\n", "\r", "\t", "\0"]):
                return custom_model
            else:
                safe_model = _sanitize_for_log(custom_model)
                logger.warning(
                    f"Invalid custom embedding model '{safe_model}' for provider '{provider_name}', using default"
                )

        # Return provider-specific defaults
        if provider_name == "openai":
            return "text-embedding-3-small"
        elif provider_name == "ollama":
            return "nomic-embed-text"
        elif provider_name == "google":
            return "text-embedding-004"
        elif provider_name == "openrouter":
            return "openai/text-embedding-3-small"
        elif provider_name == "anthropic":
            return "text-embedding-3-small"
        elif provider_name == "grok":
            return "text-embedding-3-small"
        else:
            return "text-embedding-3-small"

    except Exception as e:
        logger.error(f"Error getting embedding model: {e}")
        return "text-embedding-3-small"


def is_openai_embedding_model(model: str) -> bool:
    """Check if a model is an OpenAI embedding model."""
    openai_models = {
        "text-embedding-ada-002",
        "text-embedding-3-small",
        "text-embedding-3-large",
    }
    return model in openai_models


def is_google_embedding_model(model: str) -> bool:
    """Check if a model is a Google embedding model."""
    google_models = {
        "textembedding-gecko@001",
        "textembedding-gecko-multilingual@001",
        "text-embedding-004",
        "text-multilingual-embedding-002",
    }
    return model in google_models


def is_valid_embedding_model_for_provider(model: str, provider: str) -> bool:
    """
    Validate that an embedding model is compatible with the specified provider.

    Args:
        model: The embedding model name
        provider: The provider name

    Returns:
        bool: True if the model is valid for the provider
    """
    if not model or not provider:
        return False

    provider = provider.lower()
    model = model.lower()

    # Provider-specific validation
    if provider == "openai":
        return is_openai_embedding_model(model)
    elif provider == "google":
        return is_google_embedding_model(model)
    elif provider == "ollama":
        # Ollama supports many embedding models via its registry
        # Common Ollama embedding models
        ollama_models = {
            "nomic-embed-text",
            "mxbai-embed-large",
            "all-minilm",
            "snowflake-arctic-embed",
        }
        return model in ollama_models or "embed" in model
    elif provider in ["openrouter", "anthropic", "grok"]:
        # These providers support OpenAI models
        return is_openai_embedding_model(model) or is_google_embedding_model(model)

    return False


def get_supported_embedding_models(provider: str) -> list[str]:
    """
    Get the list of supported embedding models for a provider.

    Args:
        provider: The provider name

    Returns:
        list[str]: List of supported model names
    """
    provider = provider.lower()

    if provider == "openai":
        return ["text-embedding-3-small", "text-embedding-3-large", "text-embedding-ada-002"]
    elif provider == "google":
        return ["text-embedding-004", "text-multilingual-embedding-002"]
    elif provider == "ollama":
        return ["nomic-embed-text", "mxbai-embed-large", "all-minilm", "snowflake-arctic-embed"]
    elif provider in ["openrouter", "anthropic", "grok"]:
        return ["text-embedding-3-small", "text-embedding-004"]

    return []


async def get_embedding_model_with_routing(
    provider: str | None = None, instance_url: str | None = None
) -> tuple[str, str]:
    """
    Get embedding model with routing information for Ollama multi-instance support.

    Args:
        provider: Override provider selection
        instance_url: Specific Ollama instance URL for routing

    Returns:
        tuple[str, str]: (model_name, routing_info)
    """
    model = await get_embedding_model(provider)

    routing_info = ""
    if provider == "ollama" or (provider is None and instance_url):
        routing_info = instance_url or "default"

    return model, routing_info
