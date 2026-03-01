from __future__ import annotations

import os
from typing import Generator

import pytest


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
