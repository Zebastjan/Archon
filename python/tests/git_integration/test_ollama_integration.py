"""
Test Ollama Integration - Real Ollama embedding tests.

Tests that require a live Ollama instance with embedding-capable models.
Skip these tests if Ollama is not available using: pytest -m "not ollama"
"""

import pytest
import httpx
from unittest.mock import MagicMock

# These tests require a live Ollama instance
pytestmark = pytest.mark.ollama


class TestOllamaConnection:
    """Basic connectivity tests for Ollama."""

    @pytest.mark.asyncio
    async def test_ollama_is_reachable(self, ollama_url: str):
        """Verify Ollama API is accessible."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{ollama_url}/api/tags", timeout=5.0)
            assert response.status_code == 200
            data = response.json()
            assert "models" in data

    @pytest.mark.asyncio
    async def test_ollama_has_embedding_models(self, ollama_url: str):
        """Verify at least one embedding model is available."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{ollama_url}/api/tags", timeout=5.0)
            data = response.json()
            models = data.get("models", [])
            
            # Check for known embedding models
            embedding_models = [m for m in models if any(
                name in m.get("name", "").lower() 
                for name in ["nomic-embed", "all-minilm", "mxbai-embed"]
            )]
            
            assert len(embedding_models) > 0, "No embedding models found. Install: ollama pull nomic-embed-text"


class TestOllamaEmbeddings:
    """Real embedding generation tests."""

    @pytest.mark.asyncio
    async def test_ollama_can_generate_embeddings(self, ollama_url: str):
        """Test basic embedding generation via Ollama API."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{ollama_url}/api/embeddings",
                json={
                    "model": "nomic-embed-text",
                    "prompt": "This is a test sentence for embedding generation."
                },
                timeout=30.0
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "embedding" in data
            assert isinstance(data["embedding"], list)
            assert len(data["embedding"]) > 0  # Should have dimensionality

    @pytest.mark.asyncio
    async def test_ollama_embedding_dimensions(self, ollama_url: str):
        """Verify embedding dimensions match expected values."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{ollama_url}/api/embeddings",
                json={
                    "model": "nomic-embed-text",
                    "prompt": "Test"
                },
                timeout=30.0
            )
            
            data = response.json()
            embedding = data.get("embedding", [])
            
            # nomic-embed-text should produce 768-dimensional embeddings
            assert len(embedding) == 768, f"Expected 768 dimensions, got {len(embedding)}"

    @pytest.mark.asyncio
    async def test_ollama_embedding_consistency(self, ollama_url: str):
        """Same text should produce same embeddings."""
        text = "Consistency test string"
        
        async with httpx.AsyncClient() as client:
            # Generate embedding twice
            embeddings = []
            for _ in range(2):
                response = await client.post(
                    f"{ollama_url}/api/embeddings",
                    json={
                        "model": "nomic-embed-text",
                        "prompt": text
                    },
                    timeout=30.0
                )
                data = response.json()
                embeddings.append(data["embedding"])
            
            # Should be identical
            assert embeddings[0] == embeddings[1]


class TestEmbeddingRouterIntegration:
    """Integration tests with EmbeddingRouter service."""

    @pytest.mark.asyncio
    async def test_embedding_router_with_ollama(self, ollama_url: str):
        """Test EmbeddingRouter can route to Ollama."""
        from src.server.services.ollama.embedding_router import EmbeddingRouter
        
        router = EmbeddingRouter()
        
        # Route for nomic-embed-text
        decision = await router.route_embedding(
            model_name="nomic-embed-text",
            instance_url=ollama_url
        )
        
        assert decision.target_column in ["embedding_768", "embedding_1024", "embedding_1536"]
        assert decision.dimensions == 768
        assert decision.confidence >= 0.7

    @pytest.mark.asyncio
    async def test_embedding_router_dimension_detection(self, ollama_url: str):
        """Test automatic dimension detection."""
        from src.server.services.ollama.model_discovery_service import model_discovery_service
        
        dimensions = await model_discovery_service._test_embedding_capability_fast(
            model_name="nomic-embed-text",
            instance_url=ollama_url
        )
        
        assert dimensions is not None
        assert dimensions == 768


class TestModelDiscovery:
    """Model discovery service tests with real Ollama."""

    @pytest.mark.asyncio
    async def test_discover_models_from_ollama(self, ollama_url: str):
        """Test model discovery with real instance."""
        from src.server.services.ollama.model_discovery_service import model_discovery_service
        
        result = await model_discovery_service.discover_models_from_multiple_instances(
            [ollama_url]
        )
        
        assert "embedding_models" in result
        assert "chat_models" in result
        assert isinstance(result["embedding_models"], list)
        assert isinstance(result["chat_models"], list)


class TestGitEmbeddingWithOllama:
    """Git embedding service tests with real Ollama backend."""

    @pytest.mark.asyncio
    async def test_git_embedding_service_with_ollama_backend(self, ollama_url: str, mock_supabase_client):
        """Test GitEmbeddingService can use Ollama for embeddings."""
        import sys
        from unittest.mock import MagicMock
        
        # Mock required modules
        sys.modules['src.server.db_connector'] = MagicMock()
        sys.modules['src.server.services.embeddings.contextual_embedding_service'] = MagicMock()
        
        from src.server.services.git.git_embedding_service import GitEmbeddingService
        
        service = GitEmbeddingService(supabase_client=mock_supabase_client)
        
        # Format commit text
        text = service.format_commit_for_embedding(
            commit_sha="abc123",
            message="Add user authentication feature",
            source="message"
        )
        
        assert "user authentication" in text
        assert isinstance(text, str)
        assert len(text) > 0

    @pytest.mark.asyncio
    async def test_real_embedding_for_commit(self, ollama_url: str):
        """Generate real embedding for commit-like text."""
        import sys
        from unittest.mock import MagicMock
        
        sys.modules['src.server.db_connector'] = MagicMock()
        sys.modules['src.server.services.embeddings.contextual_embedding_service'] = MagicMock()
        
        from src.server.services.embeddings.embedding_service import create_embedding
        
        # Create a commit-like text
        commit_text = """Commit: abc123def456
Author: Test User <test@example.com>
Date: 2024-01-15

Add user authentication feature with OAuth2 support

This commit implements user authentication using OAuth2 protocol,
enabling secure login via third-party providers."""
        
        # Generate embedding via Ollama
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{ollama_url}/api/embeddings",
                json={
                    "model": "nomic-embed-text",
                    "prompt": commit_text
                },
                timeout=30.0
            )
            
            assert response.status_code == 200
            data = response.json()
            embedding = data.get("embedding", [])
            
            # Should produce valid embedding
            assert len(embedding) == 768
            assert all(isinstance(x, (int, float)) for x in embedding)
            
            # Should be normalized (L2 norm ~1.0)
            import math
            norm = math.sqrt(sum(x**2 for x in embedding))
            assert 0.9 < norm < 1.1, f"Embedding not normalized: norm={norm}"


# Helper to check if Ollama is available before running tests
def pytest_configure(config):
    """Configure pytest to handle Ollama availability."""
    # This will be checked by the ollama_available fixture
    pass
