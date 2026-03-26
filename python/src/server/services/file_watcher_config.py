"""File Watcher Configuration Loader.

Loads watcher settings from .archon/config.toml or environment variables.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from src.server.config.logfire_config import get_logger
from src.server.services.file_watcher_service import WatcherConfig

logger = get_logger(__name__)

# Default values
DEFAULT_CONFIG = {
    "enabled": True,
    "debounce_ms": 500,
    "max_file_size_kb": 512,
}

WATCHED_EXTENSIONS = frozenset(
    {
        ".py",
        ".ts",
        ".go",
        ".rs",  # code
        ".md",
        ".rst",
        ".org",
        ".norg",  # docs
        ".sql",
        ".yaml",
        ".toml",
        ".json",  # config
    }
)


def load_config_from_toml(config_path: Path | None = None) -> dict:
    """Load watcher configuration from .archon/config.toml.

    Args:
        config_path: Path to config file (default: .archon/config.toml in project root)

    Returns:
        Dictionary with watcher settings
    """
    if config_path is None:
        # Try to find config in project root
        cwd = Path.cwd()
        for parent in [cwd, *cwd.parents]:
            config_file = parent / ".archon" / "config.toml"
            if config_file.exists():
                config_path = config_file
                break

    if config_path is None or not config_path.exists():
        logger.debug("No .archon/config.toml found, using defaults")
        return {}

    try:
        import tomllib

        with open(config_path, "rb") as f:
            config = tomllib.load(f)

        return config.get("watcher", {})

    except ImportError:
        # Python < 3.11
        try:
            import tomli

            with open(config_path, "rb") as f:
                config = tomli.load(f)
            return config.get("watcher", {})
        except ImportError:
            logger.warning("No TOML library available, using defaults")
            return {}
    except Exception as e:
        logger.warning(f"Failed to load config: {e}, using defaults")
        return {}


def load_watcher_config() -> WatcherConfig:
    """Load and merge watcher configuration.

    Priority:
    1. Environment variables (ARCHON_WATCHER_*)
    2. .archon/config.toml
    3. Defaults

    Returns:
        WatcherConfig instance
    """
    # Start with defaults
    config_dict = DEFAULT_CONFIG.copy()

    # Override from TOML
    toml_config = load_config_from_toml()
    if toml_config:
        config_dict.update({k: v for k, v in toml_config.items() if k in DEFAULT_CONFIG})

    # Override from environment variables
    env_enabled = os.environ.get("ARCHON_WATCHER_ENABLED")
    if env_enabled is not None:
        config_dict["enabled"] = env_enabled.lower() in ("true", "1", "yes")

    env_debounce = os.environ.get("ARCHON_WATCHER_DEBOUNCE_MS")
    if env_debounce is not None:
        try:
            config_dict["debounce_ms"] = int(env_debounce)
        except ValueError:
            pass

    env_max_size = os.environ.get("ARCHON_WATCHER_MAX_FILE_SIZE_KB")
    if env_max_size is not None:
        try:
            config_dict["max_file_size_kb"] = int(env_max_size)
        except ValueError:
            pass

    return WatcherConfig(
        enabled=config_dict["enabled"],
        debounce_ms=config_dict["debounce_ms"],
        max_file_size_kb=config_dict["max_file_size_kb"],
        watch_extensions=WATCHED_EXTENSIONS,
    )


# Singleton config instance
_watcher_config: WatcherConfig | None = None


def get_watcher_config() -> WatcherConfig:
    """Get the global watcher configuration (singleton)."""
    global _watcher_config
    if _watcher_config is None:
        _watcher_config = load_watcher_config()
    return _watcher_config


def set_watcher_config(config: WatcherConfig) -> None:
    """Set the global watcher configuration."""
    global _watcher_config
    _watcher_config = config
