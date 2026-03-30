"""Pytest configuration for agent_work_orders tests"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add src to path BEFORE importing anything from src
PYTHON_SRC = Path(__file__).parent.parent.parent / "src"
if str(PYTHON_SRC) not in sys.path:
    sys.path.insert(0, str(PYTHON_SRC))

# Set ENABLE_AGENT_WORK_ORDERS=true for all tests so health endpoint populates dependencies
os.environ.setdefault("ENABLE_AGENT_WORK_ORDERS", "true")


@pytest.fixture(autouse=True)
def mock_supabase_client():
    """Mock Supabase client for all tests to prevent credential validation."""
    mock_client = MagicMock()
    with patch(
        "src.agent_work_orders.state_manager.repository_config_repository.get_supabase_client", return_value=mock_client
    ):
        yield mock_client


@pytest.fixture(autouse=True)
def reset_structlog():
    """Reset structlog configuration for each test"""
    try:
        import structlog

        structlog.reset_defaults()
    except ImportError:
        pass  # structlog not installed, skip
