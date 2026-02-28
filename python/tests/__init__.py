"""Simplified test suite for Archon - Essential tests only."""

import sys
import types

if "openai" not in sys.modules:
    sys.modules["openai"] = types.ModuleType("openai")
