"""Database services module.

Provides database connectivity and operations for Archon.
Uses asyncpg for direct PostgreSQL connections (replacing Supabase dependency).
"""

from .db_connector import (
    DatabaseConfig,
    DatabaseConnector,
    DatabaseConnectionError,
    close_database,
    get_database_connector,
    initialize_database,
)

__all__ = [
    "DatabaseConfig",
    "DatabaseConnector",
    "DatabaseConnectionError",
    "get_database_connector",
    "initialize_database",
    "close_database",
]
