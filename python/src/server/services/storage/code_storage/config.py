"""Configuration and settings for code storage service.

Handles credential retrieval with fallback to environment variables.
"""

import os
from typing import Any

from ....config.logfire_config import search_logger
from ...credential_service import credential_service


class CodeStorageConfig:
    """Configuration resolver for code storage operations.

    Provides centralized access to settings with proper fallback chain:
    1. Credential service (database-stored settings)
    2. Environment variables
    3. Default values
    """

    # Default configuration values
    DEFAULTS = {
        "CODE_SUMMARY_BATCH_SIZE": "10",
        "CODE_SUMMARY_MAX_WORKERS": "3",
        "CODE_SUMMARY_LLM_TIMEOUT": "60.0",
        "CODE_SUMMARY_MAX_RETRIES": "2",
        "USE_CONTEXTUAL_EMBEDDINGS": "false",
        "CONTEXTUAL_EMBEDDING_BATCH_SIZE": "50",
        "EMBEDDING_BATCH_SIZE": "100",
    }

    @classmethod
    async def get_setting(cls, key: str, default: str | None = None) -> str:
        """Get a setting value with proper fallback chain.

        Args:
            key: The setting key to retrieve
            default: Default value if not found in credential service or env

        Returns:
            The setting value as a string
        """
        # Try credential service first (async)
        try:
            value = await credential_service.get_credential(key, default, decrypt=True)
            if value is not None and str(value).strip():
                return str(value).strip()
        except Exception as e:
            search_logger.debug(f"Could not get {key} from credential service: {e}")

        # Fall back to environment variable
        env_value = os.getenv(key)
        if env_value and env_value.strip():
            return env_value.strip()

        # Use provided default or class default
        if default is not None:
            return default

        return cls.DEFAULTS.get(key, "")

    @classmethod
    async def get_int_setting(cls, key: str, default: int = 0) -> int:
        """Get a setting value as an integer.

        Args:
            key: The setting key to retrieve
            default: Default integer value if conversion fails

        Returns:
            The setting value as an integer
        """
        str_value = await cls.get_setting(key, str(default))
        try:
            return int(str_value)
        except (ValueError, TypeError):
            search_logger.warning(f"Could not parse {key} as int, using default: {default}")
            return default

    @classmethod
    async def get_float_setting(cls, key: str, default: float = 0.0) -> float:
        """Get a setting value as a float.

        Args:
            key: The setting key to retrieve
            default: Default float value if conversion fails

        Returns:
            The setting value as a float
        """
        str_value = await cls.get_setting(key, str(default))
        try:
            return float(str_value)
        except (ValueError, TypeError):
            search_logger.warning(f"Could not parse {key} as float, using default: {default}")
            return default

    @classmethod
    async def get_bool_setting(cls, key: str, default: bool = False) -> bool:
        """Get a setting value as a boolean.

        Args:
            key: The setting key to retrieve
            default: Default boolean value if conversion fails

        Returns:
            The setting value as a boolean
        """
        str_value = await cls.get_setting(key, str(default).lower())
        if str_value:
            return str_value.lower() in ("true", "1", "yes", "on")
        return default


# Convenience functions for common settings
async def get_batch_size() -> int:
    """Get code summary batch size."""
    return await CodeStorageConfig.get_int_setting("CODE_SUMMARY_BATCH_SIZE", 10)


async def get_max_workers() -> int:
    """Get maximum parallel workers for code summarization."""
    return await CodeStorageConfig.get_int_setting("CODE_SUMMARY_MAX_WORKERS", 3)


async def get_llm_timeout() -> float:
    """Get LLM request timeout in seconds."""
    return await CodeStorageConfig.get_float_setting("CODE_SUMMARY_LLM_TIMEOUT", 60.0)


async def get_max_retries() -> int:
    """Get maximum retry attempts for LLM calls."""
    return await CodeStorageConfig.get_int_setting("CODE_SUMMARY_MAX_RETRIES", 2)


async def use_contextual_embeddings() -> bool:
    """Check if contextual embeddings are enabled."""
    return await CodeStorageConfig.get_bool_setting("USE_CONTEXTUAL_EMBEDDINGS", False)


async def get_embedding_batch_size() -> int:
    """Get batch size for embedding generation."""
    return await CodeStorageConfig.get_int_setting("EMBEDDING_BATCH_SIZE", 100)


async def get_contextual_embedding_batch_size() -> int:
    """Get batch size for contextual embedding generation."""
    return await CodeStorageConfig.get_int_setting("CONTEXTUAL_EMBEDDING_BATCH_SIZE", 50)
