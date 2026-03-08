from __future__ import annotations

import os
from collections.abc import Generator

import pytest

from src.server.services.git.git_repository_service import GitRepositoryService
from tests.git_integration.test_git_repository_integration import (
    FakeSupabaseClient,
)


@pytest.fixture(autouse=True)
def configure_test_environment() -> Generator[None, None, None]:
    """Ensure environment variables expected by Git services are present."""
    original_env = {key: os.environ.get(key) for key in ("TEST_MODE", "TESTING")}
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
