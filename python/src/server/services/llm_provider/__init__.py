"""
LLM Provider Service Package

Provides a unified interface for creating OpenAI-compatible clients for different LLM providers.
Supports OpenAI, Ollama, Google Gemini, and other providers.

This package is organized into modules:
- cache: Settings caching with TTL and security
- client: Client creation and management
- embedding: Embedding model utilities
- reasoning: Reasoning model support
- validation: Provider validation
"""

from .cache import (
    clear_provider_cache,
    get_cache_security_report,
    get_cache_stats,
    invalidate_provider_cache,
)
from .client import get_llm_client, validate_provider_instance
from .embedding import (
    get_embedding_model,
    get_embedding_model_with_routing,
    get_supported_embedding_models,
    is_google_embedding_model,
    is_openai_embedding_model,
    is_valid_embedding_model_for_provider,
)
from .reasoning import (
    extract_json_from_reasoning,
    extract_message_text,
    is_reasoning_model,
    prepare_chat_completion_params,
    requires_max_completion_tokens,
    synthesize_json_from_reasoning,
)

__all__ = [
    # Cache
    "clear_provider_cache",
    "get_cache_security_report",
    "get_cache_stats",
    "invalidate_provider_cache",
    # Client
    "get_llm_client",
    "validate_provider_instance",
    # Embedding
    "get_embedding_model",
    "get_embedding_model_with_routing",
    "get_supported_embedding_models",
    "is_google_embedding_model",
    "is_openai_embedding_model",
    "is_valid_embedding_model_for_provider",
    # Reasoning
    "extract_json_from_reasoning",
    "extract_message_text",
    "is_reasoning_model",
    "prepare_chat_completion_params",
    "requires_max_completion_tokens",
    "synthesize_json_from_reasoning",
]
