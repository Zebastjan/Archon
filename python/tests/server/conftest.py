from __future__ import annotations

import sys
import types

import pytest


# Prevent pytest from importing the repository-wide tests.conftest module.
sys.modules.setdefault("tests.conftest", types.ModuleType("tests.conftest"))

# Provide a lightweight stub for src.server.utils so that global fixtures do not
# attempt to load heavy optional dependencies (e.g., OpenAI) during collection.
if "src.server.utils" not in sys.modules:
    sys.modules["src.server.utils"] = types.ModuleType("src.server.utils")

# Ensure an openai module is available so optional dependencies don't crash.
if "openai" not in sys.modules:
    class _OpenAIStub(types.ModuleType):
        api_key = None

        class OpenAI:
            def __init__(self, *args, **kwargs):
                pass

        class Embedding:
            def create(self, *args, **kwargs):
                raise RuntimeError("openai stub invoked during tests")

    sys.modules["openai"] = _OpenAIStub("openai")


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "tree_sitter_unit: Tree-sitter parser smoke tests")
    config.addinivalue_line(
        "markers",
        "tree_sitter_integration: Tree-sitter + chunker integration tests",
    )
