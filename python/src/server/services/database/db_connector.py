"""
Database Connector for Archon

Provides a unified interface for database operations using asyncpg for direct
PostgreSQL connections. Replaces Supabase client dependency with native async
database access.

Supports both local PostgreSQL and Supabase (as fallback) via configuration.
"""

import os
import re
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import asyncpg
from asyncpg import Pool

import logging

logger = logging.getLogger(__name__)

# Allowed Archon tables for SQL injection protection
ALLOWED_TABLES = frozenset(
    [
        "archon_settings",
        "archon_sources",
        "archon_crawled_pages",
        "archon_code_examples",
        "archon_page_metadata",
        "archon_projects",
        "archon_tasks",
        "archon_project_sources",
        "archon_document_versions",
        "archon_migrations",
        "archon_prompts",
        "archon_code_repos",
        "archon_code_entities",
        "archon_code_relationships",
        "archon_operation_progress",
        "archon_document_blobs",
        "archon_chunks",
        "archon_embedding_sets",
        "archon_embeddings",
        "archon_summaries",
        "archon_crawl_url_state",
        "archon_git_repositories",
        "archon_git_commits",
        "archon_git_files",
        "archon_code_metrics",
        "archon_file_metrics",
        "archon_audit_rules",
        "archon_audit_findings",
        "archon_audit_runs",
        "archon_semgrep_findings",
        "archon_audit_triage_memory",
        "archon_audit_false_negatives",
        "archon_audit_rule_quality",
        "archon_semgrep_config",
        "archon_audit_config",
        "archon_audit_finding_tasks",
        "archon_documents",
        "archon_agent_work_orders",
        "archon_agent_work_order_steps",
        "archon_configured_repositories",
    ]
)

# Valid identifier pattern: alphanumeric + underscore, must start with letter or underscore
VALID_IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


class SQLInjectionError(Exception):
    """Raised when a potential SQL injection is detected in table/column names."""

    pass


def _validate_identifier(name: str, context: str = "identifier") -> None:
    """
    Validate that an identifier (table/column name) is safe.

    Args:
        name: The identifier to validate
        context: Description of what this identifier represents (for error messages)

    Raises:
        SQLInjectionError: If the identifier contains unsafe characters
    """
    if not isinstance(name, str):
        raise SQLInjectionError(f"{context} must be a string, got {type(name).__name__}")

    if not name:
        raise SQLInjectionError(f"{context} cannot be empty")

    if not VALID_IDENTIFIER_PATTERN.match(name):
        raise SQLInjectionError(
            f"Invalid {context} '{name}'. Identifiers must start with a letter or underscore "
            f"and contain only alphanumeric characters and underscores."
        )


def _validate_table_name(table: str) -> None:
    """
    Validate table name against allowlist.

    Args:
        table: Table name to validate

    Raises:
        SQLInjectionError: If table name is not in allowlist or contains unsafe characters
    """
    _validate_identifier(table, "table name")

    if table not in ALLOWED_TABLES:
        raise SQLInjectionError(
            f"Table '{table}' is not in the allowed tables list. Allowed tables: {', '.join(sorted(ALLOWED_TABLES))}"
        )


class DatabaseConfig:
    """Database configuration from YAML config or environment variables."""

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Load configuration from YAML config (preferred) or environment variables."""
        # Primary: YAML config (lazy import to avoid circular deps)
        try:
            import sys

            if "src.server.config.yaml_config" in sys.modules:
                from ...config.yaml_config import get_config

                config = get_config()
                return cls(
                    database_url=config.database.dsn,
                    min_connections=config.database.min_connections,
                    max_connections=config.database.max_connections,
                )
        except Exception as e:
            logger.debug(f"YAML config not available, falling back to env vars: {e}")

        # Fallback: Direct DATABASE_URL
        database_url = os.getenv("ARCHON_DATABASE_URL")

        # Fallback: Build from components
        if not database_url:
            host = os.getenv("ARCHON_DB_HOST", "127.0.0.1")
            port = int(os.getenv("ARCHON_DB_PORT", "5433"))
            user = os.getenv("ARCHON_DB_USER", "archon")
            password = os.getenv("ARCHON_DB_PASSWORD", "")
            database = os.getenv("ARCHON_DB_NAME", "archon")

            database_url = f"postgresql://{user}:{password}@{host}:{port}/{database}"

        return cls(
            database_url=database_url,
            min_connections=int(os.getenv("ARCHON_DB_MIN_CONNECTIONS", "5")),
            max_connections=int(os.getenv("ARCHON_DB_MAX_CONNECTIONS", "20")),
        )

    def __init__(
        self,
        database_url: str,
        min_connections: int = 5,
        max_connections: int = 20,
    ):
        self.database_url = database_url
        self.min_connections = min_connections
        self.max_connections = max_connections


class DatabaseConnector:
    """
    Async PostgreSQL database connector using asyncpg.

    Provides connection pooling and CRUD operations for Archon services.
    Designed as a drop-in replacement for Supabase client in most use cases.

    Example:
        db = DatabaseConnector()
        await db.initialize()

        # Simple query
        result = await db.fetch("SELECT * FROM archon_projects WHERE id = $1", project_id)

        # Insert with returning
        record = await db.fetchrow(
            "INSERT INTO archon_code_entities (repo_id, name, entity_type) VALUES ($1, $2, $3) RETURNING *",
            repo_id, name, entity_type
        )

        await db.close()
    """

    _instance: "DatabaseConnector | None" = None
    _pool: Pool | None = None

    def __new__(cls, *args, **kwargs):
        """Singleton pattern to ensure single connection pool."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config: DatabaseConfig | None = None):
        """
        Initialize database connector.

        Args:
            config: Database configuration. Loads from env if not provided.
        """
        if hasattr(self, "_initialized"):
            return

        self.config = config or DatabaseConfig.from_env()
        self._logger = logger
        self._initialized = False

    async def initialize(self) -> None:
        """
        Initialize connection pool.

        Must be called before any database operations.
        """
        if self._initialized:
            return

        try:
            self._pool = await asyncpg.create_pool(
                self.config.database_url,
                min_size=self.config.min_connections,
                max_size=self.config.max_connections,
                command_timeout=60,
                server_settings={
                    "jit": "off",  # Disable JIT for complex queries (pgvector compat)
                },
            )
            self._initialized = True
            self._logger.info(
                f"database_pool_initialized min_connections={self.config.min_connections} max_connections={self.config.max_connections}"
            )
        except Exception as e:
            self._logger.exception(f"failed_to_initialize_database_pool error={e}")
            raise DatabaseConnectionError(f"Failed to initialize database: {e}") from e

    async def close(self) -> None:
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            self._initialized = False
            self._logger.info("database_pool_closed")

    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """
        Acquire a connection from the pool with automatic rollback on error.

        This ensures that if a query fails, the connection is rolled back
        and won't be left in an aborted transaction state.

        Usage:
            >>> async with db.acquire() as conn:
            ...     result = await conn.fetch("SELECT * FROM table")
        """
        if not self._initialized:
            await self.initialize()

        async with self._pool.acquire() as connection:
            try:
                yield connection
            except Exception:
                # Rollback any failed transaction to prevent "aborted transaction" errors
                # on subsequent queries using this connection
                try:
                    await connection.execute("ROLLBACK")
                except Exception as e:
                    # If rollback fails, connection is likely already clean
                    logger.debug(f"Rollback failed (connection likely clean): {e}")
                raise

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """
        Start a database transaction with automatic commit/rollback.

        This context manager provides atomic database operations. All queries
        executed within the transaction block are committed together on success,
        or rolled back together on failure.

        Usage:
            >>> async with db.transaction() as conn:
            ...     await conn.execute("INSERT INTO archon_sources ...")
            ...     await conn.execute("INSERT INTO archon_embeddings ...")
            ... # Commits automatically if no exception

            >>> async with db.transaction() as conn:
            ...     await conn.execute("INSERT INTO archon_sources ...")
            ...     raise ValueError("Something went wrong")
            ... # Automatically rolled back on exception

        Raises:
            TransactionError: If transaction cannot be started or committed
        """
        if not self._initialized:
            await self.initialize()

        async with self._pool.acquire() as connection:
            # Start transaction
            try:
                await connection.execute("BEGIN")
                self._logger.debug("transaction_started")
            except Exception as e:
                raise TransactionError(f"Failed to start transaction: {e}") from e

            try:
                yield connection
                # Success - commit the transaction
                await connection.execute("COMMIT")
                self._logger.debug("transaction_committed")
            except Exception:
                # Failure - rollback the transaction
                try:
                    await connection.execute("ROLLBACK")
                    self._logger.debug("transaction_rolled_back")
                except Exception as rollback_error:
                    self._logger.error(f"transaction_rollback_failed error={rollback_error}")
                raise

    # Convenience methods matching Supabase-like interface

    async def fetch(
        self,
        query: str,
        *args,
    ) -> list[asyncpg.Record]:
        """
        Execute SELECT query and return all rows.

        Args:
            query: SQL query with positional parameters ($1, $2, ...)
            *args: Query parameters

        Returns:
            List of records
        """
        async with self.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(
        self,
        query: str,
        *args,
    ) -> asyncpg.Record | None:
        """
        Execute SELECT query and return first row.

        Args:
            query: SQL query with positional parameters
            *args: Query parameters

        Returns:
            First record or None
        """
        async with self.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetchval(
        self,
        query: str,
        *args,
    ) -> Any:
        """
        Execute SELECT query and return single value.

        Args:
            query: SQL query
            *args: Query parameters

        Returns:
            Single value or None
        """
        async with self.acquire() as conn:
            return await conn.fetchval(query, *args)

    async def execute(
        self,
        query: str,
        *args,
    ) -> str:
        """
        Execute INSERT, UPDATE, DELETE query.

        Args:
            query: SQL query
            *args: Query parameters

        Returns:
            Query status message
        """
        async with self.acquire() as conn:
            return await conn.execute(query, *args)

    async def executemany(
        self,
        query: str,
        args: list[tuple],
    ) -> None:
        """
        Execute query multiple times with different parameters.

        Args:
            query: SQL query
            args: List of parameter tuples
        """
        async with self.acquire() as conn:
            await conn.executemany(query, args)

    # Table-specific helpers (migration from Supabase-style)

    async def insert(
        self,
        table: str,
        data: dict[str, Any],
        returning: bool = True,
    ) -> dict[str, Any] | None:
        """
        Insert a record into a table.

        Args:
            table: Table name
            data: Column values
            returning: Whether to return inserted record

        Returns:
            Inserted record if returning=True

        Raises:
            SQLInjectionError: If table or column names contain unsafe characters
        """
        # Validate table name
        _validate_table_name(table)

        columns = list(data.keys())
        values = list(data.values())

        # Validate all column names
        for col in columns:
            _validate_identifier(col, "column name")

        placeholders = [f"${i + 1}" for i in range(len(values))]

        # Now safe to interpolate validated identifiers
        query = f"""
            INSERT INTO {table} ({", ".join(columns)})
            VALUES ({", ".join(placeholders)})
        """

        if returning:
            query += " RETURNING *"
            record = await self.fetchrow(query, *values)
            return dict(record) if record else None
        else:
            await self.execute(query, *values)
            return None

    async def update(
        self,
        table: str,
        data: dict[str, Any],
        where: dict[str, Any],
        returning: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Update records in a table.

        Args:
            table: Table name
            data: Columns to update
            where: WHERE conditions
            returning: Whether to return updated records

        Returns:
            Updated records if returning=True

        Raises:
            SQLInjectionError: If table or column names contain unsafe characters
        """
        # Validate table name
        _validate_table_name(table)

        # Validate all column names in SET and WHERE clauses
        for col in data.keys():
            _validate_identifier(col, "SET column name")
        for col in where.keys():
            _validate_identifier(col, "WHERE column name")

        set_clauses = [f"{k} = ${i + 1}" for i, k in enumerate(data.keys())]
        where_clauses = [f"{k} = ${i + len(data) + 1}" for i, k in enumerate(where.keys())]

        # Now safe to interpolate validated identifiers
        query = f"""
            UPDATE {table}
            SET {", ".join(set_clauses)}
            WHERE {" AND ".join(where_clauses)}
        """

        values = list(data.values()) + list(where.values())

        if returning:
            query += " RETURNING *"
            records = await self.fetch(query, *values)
            return [dict(r) for r in records]
        else:
            await self.execute(query, *values)
            return []

    async def delete(
        self,
        table: str,
        where: dict[str, Any],
        returning: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Delete records from a table.

        Args:
            table: Table name
            where: WHERE conditions
            returning: Whether to return deleted records

        Returns:
            Deleted records if returning=True

        Raises:
            SQLInjectionError: If table or column names contain unsafe characters
        """
        # Validate table name
        _validate_table_name(table)

        # Validate all column names in WHERE clause
        for col in where.keys():
            _validate_identifier(col, "WHERE column name")

        where_clauses = [f"{k} = ${i + 1}" for i, k in enumerate(where.keys())]

        # Now safe to interpolate validated identifiers
        query = f"""
            DELETE FROM {table}
            WHERE {" AND ".join(where_clauses)}
        """

        values = list(where.values())

        if returning:
            query += " RETURNING *"
            records = await self.fetch(query, *values)
            return [dict(r) for r in records]
        else:
            await self.execute(query, *values)
            return []

    async def select(
        self,
        table: str,
        columns: list[str] | None = None,
        where: dict[str, Any] | None = None,
        order_by: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Select records from a table.

        Args:
            table: Table name
            columns: Columns to select (default: all)
            where: WHERE conditions
            order_by: ORDER BY clause (column name, optionally with ASC/DESC)
            limit: LIMIT (must be int)
            offset: OFFSET (must be int)

        Returns:
            List of records

        Raises:
            SQLInjectionError: If table or column names contain unsafe characters
            ValueError: If limit or offset are not valid integers
        """
        # Validate table name
        _validate_table_name(table)

        # Validate column names
        if columns:
            for col in columns:
                _validate_identifier(col, "column name")
            cols = ", ".join(columns)
        else:
            cols = "*"

        query = f"SELECT {cols} FROM {table}"
        values = []
        param_idx = 1

        if where:
            # Validate WHERE column names
            for col in where.keys():
                _validate_identifier(col, "WHERE column name")

            where_clauses = []
            for k, v in where.items():
                if isinstance(v, list):
                    # Handle IN clauses
                    placeholders = [f"${param_idx + j}" for j in range(len(v))]
                    where_clauses.append(f"{k} IN ({', '.join(placeholders)})")
                    values.extend(v)
                    param_idx += len(v)
                else:
                    where_clauses.append(f"{k} = ${param_idx}")
                    values.append(v)
                    param_idx += 1

            query += f" WHERE {' AND '.join(where_clauses)}"

        if order_by:
            # ORDER BY can be "column_name" or "column_name ASC/DESC"
            # Split and validate each part
            order_parts = order_by.split()
            if len(order_parts) > 2:
                raise SQLInjectionError(f"Invalid ORDER BY clause: '{order_by}'")

            col_name = order_parts[0]
            _validate_identifier(col_name, "ORDER BY column")

            # Validate sort direction if provided
            if len(order_parts) == 2:
                sort_dir = order_parts[1].upper()
                if sort_dir not in ("ASC", "DESC"):
                    raise SQLInjectionError(f"Invalid sort direction: '{order_parts[1]}'. Must be ASC or DESC.")
                validated_order = f"{col_name} {sort_dir}"
            else:
                validated_order = col_name

            query += f" ORDER BY {validated_order}"

        if limit is not None:
            if not isinstance(limit, int) or limit < 0:
                raise ValueError(f"limit must be a non-negative integer, got {limit}")
            query += f" LIMIT ${param_idx}"
            values.append(limit)
            param_idx += 1

        if offset is not None:
            if not isinstance(offset, int) or offset < 0:
                raise ValueError(f"offset must be a non-negative integer, got {offset}")
            query += f" OFFSET ${param_idx}"
            values.append(offset)
            param_idx += 1

        records = await self.fetch(query, *values)
        return [dict(r) for r in records]


class DatabaseConnectionError(Exception):
    """Raised when database connection fails."""

    pass


class TransactionError(Exception):
    """Raised when a database transaction operation fails."""

    pass


# Global connector instance
_db_connector: DatabaseConnector | None = None


def get_database_connector() -> DatabaseConnector:
    """
    Get or create the global database connector instance.

    Returns:
        DatabaseConnector singleton instance
    """
    global _db_connector

    if _db_connector is None:
        _db_connector = DatabaseConnector()

    return _db_connector


async def initialize_database() -> None:
    """Initialize the global database connection pool."""
    db = get_database_connector()
    await db.initialize()


async def close_database() -> None:
    """Close the global database connection pool."""
    global _db_connector

    if _db_connector:
        await _db_connector.close()
        _db_connector = None
