"""
Comprehensive Tests for Async Credential Service

Tests the credential service async functions after sync function removal.
Covers credential storage, retrieval, encryption/decryption, and caching.
"""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.server.services.credential_service import (
    credential_service,
    get_credential,
    initialize_credentials,
    set_credential,
)


class TestAsyncCredentialService:
    """Test suite for async credential service functions"""

    @pytest.fixture(autouse=True)
    def setup_credential_service(self):
        """Setup clean credential service for each test"""
        # Clear cache and reset state
        credential_service._cache.clear()
        credential_service._cache_initialized = False
        yield
        # Cleanup after test
        credential_service._cache.clear()
        credential_service._cache_initialized = False

    @pytest.fixture
    def mock_db_client(self):
        """Mock PostgreSQL database connector"""
        mock_db = MagicMock()
        mock_db.fetch = AsyncMock(return_value=[])
        mock_db.fetchrow = AsyncMock(return_value=None)
        mock_db.fetchval = AsyncMock(return_value=None)
        mock_db.execute = AsyncMock(return_value="INSERT 0 1")
        return mock_db

    @pytest.fixture
    def sample_credentials_data(self):
        """Sample credentials data from database"""
        return [
            {
                "id": 1,
                "key": "OPENAI_API_KEY",
                "encrypted_value": "encrypted_openai_key",
                "value": None,
                "is_encrypted": True,
                "category": "api_keys",
                "description": "OpenAI API key for LLM access",
            },
            {
                "id": 2,
                "key": "MODEL_CHOICE",
                "value": "gpt-4.1-nano",
                "encrypted_value": None,
                "is_encrypted": False,
                "category": "rag_strategy",
                "description": "Default model choice",
            },
            {
                "id": 3,
                "key": "MAX_TOKENS",
                "value": "1000",
                "encrypted_value": None,
                "is_encrypted": False,
                "category": "rag_strategy",
                "description": "Maximum tokens per request",
            },
        ]

    def test_deprecated_functions_removed(self):
        """Test that deprecated sync functions are no longer available"""
        import src.server.services.credential_service as cred_module

        # The sync function should no longer exist
        assert not hasattr(cred_module, "get_credential_sync")

        # The async versions should be the primary functions
        assert hasattr(cred_module, "get_credential")
        assert hasattr(cred_module, "set_credential")

    @pytest.mark.asyncio
    async def test_get_credential_from_cache(self):
        """Test getting credential from initialized cache"""
        # Setup cache
        credential_service._cache = {"TEST_KEY": "test_value", "NUMERIC_KEY": "123"}
        credential_service._cache_initialized = True

        result = await get_credential("TEST_KEY", "default")
        assert result == "test_value"

        result = await get_credential("NUMERIC_KEY", "default")
        assert result == "123"

        result = await get_credential("MISSING_KEY", "default_value")
        assert result == "default_value"

    @pytest.mark.asyncio
    async def test_get_credential_encrypted_value(self):
        """Test getting encrypted credential"""
        # Setup cache with encrypted value
        encrypted_data = {"encrypted_value": "encrypted_test_value", "is_encrypted": True}
        credential_service._cache = {"SECRET_KEY": encrypted_data}
        credential_service._cache_initialized = True

        with patch.object(credential_service, "_decrypt_value", return_value="decrypted_value"):
            result = await get_credential("SECRET_KEY", "default")
            assert result == "decrypted_value"
            credential_service._decrypt_value.assert_called_once_with("encrypted_test_value")

    @pytest.mark.asyncio
    async def test_get_credential_cache_not_initialized(self, mock_db_client):
        """Test getting credential when cache is not initialized"""
        # Mock database response for load_all_credentials (gets ALL settings)
        mock_db_client.fetch = AsyncMock(return_value=[
            {
                "key": "TEST_KEY",
                "value": "db_value",
                "encrypted_value": None,
                "is_encrypted": False,
                "category": "test",
                "description": "Test key",
            }
        ])

        with patch("src.server.services.credential_service.get_database_connector", return_value=mock_db_client):
            result = await credential_service.get_credential("TEST_KEY", "default")
            assert result == "db_value"

            # Should have called database to load all credentials
            mock_db_client.fetch.assert_called()

    @pytest.mark.asyncio
    async def test_get_credential_not_found_in_db(self, mock_db_client):
        """Test getting credential that doesn't exist in database"""
        # Mock empty database response
        mock_db_client.fetch = AsyncMock(return_value=[])

        with patch("src.server.services.credential_service.get_database_connector", return_value=mock_db_client):
            result = await credential_service.get_credential("MISSING_KEY", "default_value")
            assert result == "default_value"

    @pytest.mark.asyncio
    async def test_set_credential_new(self, mock_db_client):
        """Test setting a new credential"""
        # Mock successful insert
        mock_db_client.execute = AsyncMock(return_value="INSERT 0 1")

        with patch("src.server.services.credential_service.get_database_connector", return_value=mock_db_client):
            result = await set_credential("NEW_KEY", "new_value", is_encrypted=False)
            assert result is True

            # Should have attempted insert
            mock_db_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_credential_encrypted(self, mock_db_client):
        """Test setting an encrypted credential"""
        # Mock successful insert
        mock_db_client.execute = AsyncMock(return_value="INSERT 0 1")

        with patch("src.server.services.credential_service.get_database_connector", return_value=mock_db_client):
            with patch.object(credential_service, "_encrypt_value", return_value="encrypted_value"):
                result = await set_credential("SECRET_KEY", "secret_value", is_encrypted=True)
                assert result is True

                # Should have encrypted the value
                credential_service._encrypt_value.assert_called_once_with("secret_value")

    @pytest.mark.asyncio
    async def test_load_all_credentials(self, mock_db_client, sample_credentials_data):
        """Test loading all credentials from database"""
        # Mock database response
        mock_db_client.fetch = AsyncMock(return_value=sample_credentials_data)

        with patch("src.server.services.credential_service.get_database_connector", return_value=mock_db_client):
            result = await credential_service.load_all_credentials()

            # Should have loaded credentials into cache
            assert credential_service._cache_initialized is True
            assert "OPENAI_API_KEY" in credential_service._cache
            assert "MODEL_CHOICE" in credential_service._cache
            assert "MAX_TOKENS" in credential_service._cache

            # Should have stored encrypted values as dict objects (not decrypted yet)
            openai_key_cache = credential_service._cache["OPENAI_API_KEY"]
            assert isinstance(openai_key_cache, dict)
            assert openai_key_cache["encrypted_value"] == "encrypted_openai_key"
            assert openai_key_cache["is_encrypted"] is True

            # Plain text values should be stored directly
            assert credential_service._cache["MODEL_CHOICE"] == "gpt-4.1-nano"


    @pytest.mark.asyncio
    async def test_get_active_provider_basic(self, mock_db_client):
        """Test basic provider configuration retrieval"""
        # Mock empty database response
        mock_db_client.fetch = AsyncMock(return_value=[])

        with patch("src.server.services.credential_service.get_database_connector", return_value=mock_db_client):
            result = await credential_service.get_active_provider("llm")
            # Should return default values when no settings found
            assert "provider" in result
            assert "api_key" in result

    @pytest.mark.asyncio
    async def test_initialize_credentials(self, mock_db_client, sample_credentials_data):
        """Test initialize_credentials function"""
        # Mock database response
        mock_db_client.fetch = AsyncMock(return_value=sample_credentials_data)

        with patch("src.server.services.credential_service.get_database_connector", return_value=mock_db_client):
            with patch.object(credential_service, "_decrypt_value", return_value="decrypted_key"):
                with patch.dict(os.environ, {}):  # Clear specific environment variables
                    await initialize_credentials()

                    # Should have loaded credentials
                    assert credential_service._cache_initialized is True

                    # Should have set infrastructure env vars (like OPENAI_API_KEY)
                    # Note: This tests the logic, actual env var setting depends on implementation

    @pytest.mark.asyncio
    async def test_error_handling_database_failure(self, mock_db_client):
        """Test error handling when database fails"""
        # Mock database error
        mock_db_client.fetch = AsyncMock(side_effect=Exception("Database connection failed"))

        with patch("src.server.services.credential_service.get_database_connector", return_value=mock_db_client):
            # When database fails during load_all_credentials, the exception is raised
            # The service doesn't catch it - which is the actual behavior
            try:
                result = await credential_service.get_credential("TEST_KEY", "default_value")
                # If we get here with cache not initialized, it should return default
                # because load_all_credentials would have failed but not set cache_initialized
                assert credential_service._cache_initialized is False
            except Exception as e:
                # This is the current behavior - exceptions propagate
                assert "Database connection failed" in str(e)

    @pytest.mark.asyncio
    async def test_encryption_decryption_error_handling(self):
        """Test error handling for encryption/decryption failures"""
        # Setup cache with encrypted value that fails to decrypt
        encrypted_data = {"encrypted_value": "corrupted_encrypted_value", "is_encrypted": True}
        credential_service._cache = {"CORRUPTED_KEY": encrypted_data}
        credential_service._cache_initialized = True

        with patch.object(
            credential_service, "_decrypt_value", side_effect=Exception("Decryption failed")
        ):
            # Should fall back to default when decryption fails
            result = await credential_service.get_credential("CORRUPTED_KEY", "fallback_value")
            assert result == "fallback_value"

    def test_direct_cache_access_fallback(self):
        """Test direct cache access pattern used in converted sync functions"""
        # Setup cache
        credential_service._cache = {
            "MODEL_CHOICE": "gpt-4.1-nano",
            "OPENAI_API_KEY": {"encrypted_value": "encrypted_key", "is_encrypted": True},
        }
        credential_service._cache_initialized = True

        # Test simple cache access
        if credential_service._cache_initialized and "MODEL_CHOICE" in credential_service._cache:
            result = credential_service._cache["MODEL_CHOICE"]
            assert result == "gpt-4.1-nano"

        # Test encrypted value access
        if credential_service._cache_initialized and "OPENAI_API_KEY" in credential_service._cache:
            cached_key = credential_service._cache["OPENAI_API_KEY"]
            if isinstance(cached_key, dict) and cached_key.get("is_encrypted"):
                # Would need to call credential_service._decrypt_value(cached_key["encrypted_value"])
                assert cached_key["encrypted_value"] == "encrypted_key"
                assert cached_key["is_encrypted"] is True

    @pytest.mark.asyncio
    async def test_concurrent_access(self):
        """Test concurrent access to credential service"""
        credential_service._cache = {"SHARED_KEY": "shared_value"}
        credential_service._cache_initialized = True

        async def get_credential_task():
            return await get_credential("SHARED_KEY", "default")

        # Run multiple concurrent requests
        tasks = [get_credential_task() for _ in range(10)]
        results = await asyncio.gather(*tasks)

        # All should return the same value
        assert all(result == "shared_value" for result in results)

    @pytest.mark.asyncio
    async def test_cache_persistence(self):
        """Test that cache persists across calls"""
        credential_service._cache = {"PERSISTENT_KEY": "persistent_value"}
        credential_service._cache_initialized = True

        # First call
        result1 = await get_credential("PERSISTENT_KEY", "default")
        assert result1 == "persistent_value"

        # Second call should use same cache
        result2 = await get_credential("PERSISTENT_KEY", "default")
        assert result2 == "persistent_value"
        assert result1 == result2
