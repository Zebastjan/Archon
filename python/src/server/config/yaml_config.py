"""
Strict YAML Configuration Manager

Validates configuration with no foot-guns allowed.
Fails fast on invalid config rather than running with bad values.
"""

import os
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


class ConfigError(Exception):
    """Configuration validation error."""
    pass


class ServerConfig(BaseModel):
    """Server configuration with strict validation."""
    
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8181, ge=1024, le=65535)
    reload: bool = Field(default=False)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    
    @field_validator("host")
    @classmethod
    def validate_host(cls, v: str) -> str:
        # Prevent binding to all interfaces in production
        allowed = ["127.0.0.1", "localhost", "::1"]
        if v not in allowed and not v.startswith("192.168.") and not v.startswith("10."):
            raise ValueError(f"host must be localhost/private, got {v}")
        return v


class DatabaseConfig(BaseModel):
    """Database configuration - LOCAL PostgreSQL only."""
    
    socket_dir: Path | None = Field(default=None)
    host: str = Field(default="localhost")
    port: int = Field(default=5432, ge=1, le=65535)
    user: str = Field(..., min_length=1)  # Required
    password: str | None = Field(default=None)
    name: str = Field(..., min_length=1, pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$")
    min_connections: int = Field(default=2, ge=1, le=100)
    max_connections: int = Field(default=10, ge=1, le=1000)
    data_dir: Path = Field(default=Path("~/.local/share/archon/postgres"))
    
    @field_validator("name")
    @classmethod
    def validate_db_name(cls, v: str) -> str:
        # Prevent SQL injection via db name
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", v):
            raise ValueError(f"database name must be valid identifier, got {v}")
        return v
    
    @field_validator("max_connections")
    @classmethod
    def validate_pool_size(cls, v: int, info) -> int:
        # Ensure max >= min
        min_conn = info.data.get("min_connections", 1)
        if v < min_conn:
            raise ValueError(f"max_connections ({v}) must be >= min_connections ({min_conn})")
        return v
    
    @property
    def dsn(self) -> str:
        """Build connection string."""
        # Prefer Unix socket if available (no password needed for peer auth)
        if self.socket_dir and self.socket_dir.exists():
            return f"postgresql://{self.user}@/{self.name}?host={self.socket_dir}"
        
        # Fallback to TCP
        if self.password:
            return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"
        return f"postgresql://{self.user}@{self.host}:{self.port}/{self.name}"
    
    @property
    def is_local(self) -> bool:
        """Check if database is local."""
        return self.host in ("localhost", "127.0.0.1", "::1")


class OllamaConfig(BaseModel):
    """Ollama (local LLM) configuration."""
    
    url: str = Field(default="http://localhost:11434")
    embedding_model: str = Field(default="bge-large")
    chat_model: str = Field(default="llama3.2")
    
    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        # Only allow localhost URLs for security
        if not v.startswith("http://localhost") and not v.startswith("http://127.0.0.1"):
            raise ValueError(f"ollama URL must be localhost, got {v}")
        return v


class ExternalConfig(BaseModel):
    """External service configuration."""
    
    openai_api_key: str | None = Field(default=None)
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)


class CodeIntelligenceConfig(BaseModel):
    """Code intelligence feature configuration."""
    
    enabled: bool = Field(default=True)
    languages: list[str] = Field(
        default_factory=lambda: ["python", "typescript", "javascript"]
    )


class RAGConfig(BaseModel):
    """RAG feature configuration."""
    
    enabled: bool = Field(default=True)
    use_hybrid_search: bool = Field(default=True)
    use_reranking: bool = Field(default=True)


class AuditingConfig(BaseModel):
    """Code auditing configuration."""
    
    enabled: bool = Field(default=True)
    semgrep_enabled: bool = Field(default=True)


class WorktreeConfig(BaseModel):
    """Worktree safety configuration."""
    
    enabled: bool = Field(default=True)


class FeaturesConfig(BaseModel):
    """Feature flags."""
    
    code_intelligence: CodeIntelligenceConfig = Field(default_factory=CodeIntelligenceConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)
    auditing: AuditingConfig = Field(default_factory=AuditingConfig)
    worktree: WorktreeConfig = Field(default_factory=WorktreeConfig)


class MCPConfig(BaseModel):
    """MCP server configuration."""
    
    enabled: bool = Field(default=True)
    path: str = Field(default="/mcp")


class PathsConfig(BaseModel):
    """Path configuration with expansion."""
    
    repos: Path = Field(default=Path("~/.local/share/archon/repos"))
    temp: Path = Field(default=Path("~/.cache/archon"))
    logs: Path = Field(default=Path("~/.local/share/archon/logs"))
    
    @model_validator(mode="after")
    def expand_paths(self) -> "PathsConfig":
        """Expand home directory (~) in paths."""
        self.repos = self.repos.expanduser()
        self.temp = self.temp.expanduser()
        self.logs = self.logs.expanduser()
        return self


class ArchonConfig(BaseModel):
    """Root configuration with strict validation."""
    
    server: ServerConfig = Field(default_factory=ServerConfig)
    database: DatabaseConfig  # Required
    external: ExternalConfig = Field(default_factory=ExternalConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    features: FeaturesConfig = Field(default_factory=FeaturesConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    
    @model_validator(mode="after")
    def validate_local_only(self) -> "ArchonConfig":
        """Ensure all services are local (no external dependencies)."""
        if not self.database.is_local:
            raise ConfigError(
                f"Database must be local (localhost), got {self.database.host}. "
                "Archon is designed for local-only operation."
            )
        return self
    
    def ensure_dirs(self) -> None:
        """Create necessary directories."""
        self.paths.repos.mkdir(parents=True, exist_ok=True)
        self.paths.temp.mkdir(parents=True, exist_ok=True)
        self.paths.logs.mkdir(parents=True, exist_ok=True)


# Global config instance
_config: ArchonConfig | None = None


def find_config_file() -> Path | None:
    """Find config file in standard locations."""
    candidates = []
    
    env_config = os.getenv("ARCHON_CONFIG")
    if env_config:
        candidates.append(Path(env_config))
    
    # Get the python directory (parent of src)
    python_dir = Path(__file__).parent.parent.parent.parent
    
    candidates.extend([
        Path.cwd() / "config.yaml",
        Path.cwd() / "archon.yaml",
        python_dir / "config.yaml",  # python/config.yaml
        Path(__file__).parent.parent.parent / "config.yaml",
        Path.home() / ".config" / "archon" / "config.yaml",
    ])
    
    for path in candidates:
        if path and path.exists() and path.is_file():
            return path
    
    return None


def load_config(config_path: str | None = None) -> ArchonConfig:
    """
    Load and validate configuration.
    
    Args:
        config_path: Explicit config file path (optional)
    
    Returns:
        Validated ArchonConfig instance
    
    Raises:
        ConfigError: If config is invalid or missing required fields
    """
    global _config
    
    if _config is not None:
        return _config
    
    # Find config file
    if config_path:
        path = Path(config_path)
    else:
        path = find_config_file()
    
    # Load YAML
    if path and path.exists():
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        print(f"✓ Loaded config from {path}")
    else:
        data = {}
        print("⚠ No config file found, using defaults with required values from environment")
    
    # Apply environment overrides
    if os.getenv("ARCHON_DB_NAME"):
        data.setdefault("database", {})["name"] = os.getenv("ARCHON_DB_NAME")
    if os.getenv("ARCHON_DB_USER"):
        data.setdefault("database", {})["user"] = os.getenv("ARCHON_DB_USER")
    if os.getenv("ARCHON_DB_PASSWORD"):
        data.setdefault("database", {})["password"] = os.getenv("ARCHON_DB_PASSWORD")
    if os.getenv("ARCHON_DB_PORT"):
        data.setdefault("database", {})["port"] = int(os.getenv("ARCHON_DB_PORT"))
    if os.getenv("OPENAI_API_KEY"):
        data.setdefault("external", {})["openai_api_key"] = os.getenv("OPENAI_API_KEY")
    
    # Validate
    try:
        _config = ArchonConfig(**data)
        _config.ensure_dirs()
    except Exception as e:
        raise ConfigError(f"Configuration error: {e}") from e
    
    return _config


def get_config() -> ArchonConfig:
    """Get current configuration."""
    if _config is None:
        return load_config()
    return _config


def reload_config() -> ArchonConfig:
    """Reload configuration from disk."""
    global _config
    _config = None
    return load_config()


# Convenience accessors
def get_db_dsn() -> str:
    """Get database connection string."""
    return get_config().database.dsn


def get_db_name() -> str:
    """Get database name."""
    return get_config().database.name


def get_server_port() -> int:
    """Get server port."""
    return get_config().server.port


def get_openai_key() -> str | None:
    """Get OpenAI API key."""
    return get_config().external.openai_api_key
