"""
LLM Provider Ollama Utilities Module

Provides Ollama-specific utilities for instance selection and management.
"""

from ...config.logfire_config import get_logger
from ..credential_service import credential_service

logger = get_logger(__name__)


async def _get_optimal_ollama_instance(
    instance_type: str | None = None, use_embedding_provider: bool = False, base_url_override: str | None = None
) -> str:
    """
    Get the optimal Ollama instance URL based on configuration and health status.

    Args:
        instance_type: Preferred instance type ('chat', 'embedding', 'both', or None)
        use_embedding_provider: Whether this is for embedding operations
        base_url_override: Override URL if specified

    Returns:
        Best available Ollama instance URL
    """
    # If override URL provided, use it directly
    if base_url_override:
        return base_url_override if base_url_override.endswith("/v1") else f"{base_url_override}/v1"

    try:
        # For now, we don't have multi-instance support, so skip to single instance config
        # TODO: Implement get_ollama_instances() method in CredentialService for multi-instance support
        logger.info("Using single instance Ollama configuration")

        # Get single instance configuration from RAG settings
        rag_settings = await credential_service.get_credentials_by_category("rag_strategy")

        # Check if we need embedding provider and have separate embedding URL
        if use_embedding_provider or instance_type == "embedding":
            embedding_url = rag_settings.get("OLLAMA_EMBEDDING_URL")
            if embedding_url:
                return embedding_url if embedding_url.endswith("/v1") else f"{embedding_url}/v1"

        # Default to LLM base URL for chat operations
        fallback_url = rag_settings.get("LLM_BASE_URL", "http://host.docker.internal:11434")
        return fallback_url if fallback_url.endswith("/v1") else f"{fallback_url}/v1"

    except Exception as e:
        logger.error(f"Error getting Ollama configuration: {e}")
        # Final fallback to localhost only if we can't get RAG settings
        try:
            rag_settings = await credential_service.get_credentials_by_category("rag_strategy")
            fallback_url = rag_settings.get("LLM_BASE_URL", "http://host.docker.internal:11434")
            return fallback_url if fallback_url.endswith("/v1") else f"{fallback_url}/v1"
        except Exception as fallback_error:
            logger.error(f"Could not retrieve fallback configuration: {fallback_error}")
            return "http://host.docker.internal:11434/v1"
