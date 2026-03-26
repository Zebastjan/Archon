"""Tests for FileWatcherConfig loader."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.server.services.file_watcher_config import (
    load_config_from_toml,
    load_watcher_config,
    get_watcher_config,
    set_watcher_config,
    WatcherConfig,
)


class TestLoadConfigFromToml:
    """Test TOML config loading."""

    def test_no_config_returns_empty(self):
        """Missing config file returns empty dict."""
        with patch.object(Path, "exists", return_value=False):
            result = load_config_from_toml(Path("/nonexistent/config.toml"))
            assert result == {}

    def test_default_config_used(self):
        """Default config is returned when no file exists."""
        config = load_watcher_config()
        assert config.enabled
        assert config.debounce_ms == 500
        assert config.max_file_size_kb == 512


class TestLoadWatcherConfig:
    """Test watcher config loading."""

    def test_defaults_applied(self):
        """Default configuration values are applied."""
        config = load_watcher_config()
        assert config.enabled is True
        assert config.debounce_ms == 500
        assert config.max_file_size_kb == 512

    def test_env_override_enabled(self):
        """Environment variable overrides enabled setting."""
        with patch.dict(os.environ, {"ARCHON_WATCHER_ENABLED": "false"}):
            config = load_watcher_config()
            assert config.enabled is False

    def test_env_override_debounce(self):
        """Environment variable overrides debounce setting."""
        with patch.dict(os.environ, {"ARCHON_WATCHER_DEBOUNCE_MS": "1000"}):
            config = load_watcher_config()
            assert config.debounce_ms == 1000

    def test_env_override_max_size(self):
        """Environment variable overrides max file size setting."""
        with patch.dict(os.environ, {"ARCHON_WATCHER_MAX_FILE_SIZE_KB": "1024"}):
            config = load_watcher_config()
            assert config.max_file_size_kb == 1024


class TestWatcherConfigSingleton:
    """Test singleton config management."""

    def test_get_config_creates_instance(self):
        """First call to get_watcher_config creates instance."""
        # Reset singleton
        set_watcher_config(None)
        config = get_watcher_config()
        assert config is not None

    def test_set_config_replaces_instance(self):
        """set_watcher_config replaces the singleton."""
        custom_config = WatcherConfig(enabled=False, debounce_ms=2000)
        set_watcher_config(custom_config)
        result = get_watcher_config()
        assert result.enabled is False
        assert result.debounce_ms == 2000


class TestWatcherConfigIntegration:
    """Integration tests for config loading."""

    def test_env_vars_take_precedence(self):
        """Environment variables take precedence over defaults."""
        env = {
            "ARCHON_WATCHER_ENABLED": "false",
            "ARCHON_WATCHER_DEBOUNCE_MS": "750",
            "ARCHON_WATCHER_MAX_FILE_SIZE_KB": "256",
        }
        with patch.dict(os.environ, env):
            config = load_watcher_config()
            assert config.enabled is False
            assert config.debounce_ms == 750
            assert config.max_file_size_kb == 256
