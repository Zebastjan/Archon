from __future__ import annotations

import os
from collections.abc import Generator
from unittest.mock import MagicMock

import httpx
import pytest
import pytest_asyncio

from src.server.services.git.git_repository_service import GitRepositoryService
from tests.git_integration.test_git_repository_integration import (
    FakeSupabaseClient,
)


@pytest.fixture(autouse=True)
def configure_test_environment() -> Generator[None, None, None]:
    """Ensure environment variables expected by Git services are present."""
    original_env = {key: os.environ.get(key) for key in ("TEST_MODE", "TESTING", "OLLAMA_TEST_URL")}
    os.environ.setdefault("TEST_MODE", "true")
    os.environ.setdefault("TESTING", "true")
    try:
        yield
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@pytest.fixture
def supabase_client() -> FakeSupabaseClient:
    """Provide a fake Supabase client for testing."""
    return FakeSupabaseClient()


@pytest.fixture
def git_service(supabase_client: FakeSupabaseClient) -> GitRepositoryService:
    """Provide a GitRepositoryService with fake Supabase client."""
    return GitRepositoryService(supabase_client=supabase_client)


# Ollama Test Infrastructure


def _check_ollama_available(url: str) -> bool:
    """Check if Ollama is available at the given URL."""
    try:
        response = httpx.get(f"{url}/api/tags", timeout=2.0)
        return response.status_code == 200
    except Exception:
        return False


@pytest.fixture(scope="session")
def ollama_url() -> str:
    """Get Ollama URL from environment or use default."""
    return os.environ.get("OLLAMA_TEST_URL", "http://localhost:11434")


@pytest.fixture(scope="session")
def ollama_available(ollama_url: str) -> bool:
    """Check if Ollama instance is available for testing."""
    return _check_ollama_available(ollama_url)


@pytest.fixture
def embedding_provider(ollama_available: bool) -> str:
    """Return embedding provider based on Ollama availability."""
    return "ollama" if ollama_available else "mock"


@pytest.fixture
def mock_embedding_result():
    """Provide a mock embedding result for tests without Ollama."""
    return MagicMock(
        embeddings=[[0.1] * 1536],
        has_failures=False,
        failed_items=[],
        success_count=1,
        failure_count=0,
        texts_processed=["test text"],
    )


@pytest.fixture
def mock_supabase_client():
    """Provide a mocked Supabase client with chainable methods."""
    client = MagicMock()
    
    # Setup table method chain
    table_mock = MagicMock()
    table_mock.select.return_value = table_mock
    table_mock.eq.return_value = table_mock
    table_mock.in_.return_value = table_mock
    table_mock.contains.return_value = table_mock
    table_mock.gte.return_value = table_mock
    table_mock.lte.return_value = table_mock
    table_mock.or_.return_value = table_mock
    table_mock.not_.return_value = table_mock
    table_mock.is_.return_value = table_mock
    table_mock.limit.return_value = table_mock
    table_mock.execute.return_value = MagicMock(data=[])
    client.table.return_value = table_mock
    
    # Setup RPC method
    rpc_mock = MagicMock()
    rpc_mock.execute.return_value = MagicMock(data=[])
    client.rpc.return_value = rpc_mock
    
    return client
