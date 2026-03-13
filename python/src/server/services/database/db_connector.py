"""
Database Connector for Archon

Provides a unified interface for database operations using asyncpg for direct
PostgreSQL connections. Replaces Supabase client dependency with native async
database access.

Supports both local PostgreSQL and Supabase (as fallback) via configuration.
"""

import os
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import asyncpg
from asyncpg import Pool

from ...config.logfire_config import get_logger

logger = get_logger(__name__)


class DatabaseConfig:
    """Database configuration from environment variables."""
    
    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Load configuration from environment variables."""
        # Primary: Direct DATABASE_URL
        database_url = os.getenv("ARCHON_DATABASE_URL")
        
        # Fallback: Build from components
        if not database_url:
            host = os.getenv("ARCHON_DB_HOST", "localhost")
            port = int(os.getenv("ARCHON_DB_PORT", "5432"))
            user = os.getenv("ARCHON_DB_USER", "archon")
            password = os.getenv("ARCHON_DB_PASSWORD", "archon_local_dev")
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
        if hasattr(self, '_initialized'):
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
                    'jit': 'off',  # Disable JIT for complex queries (pgvector compat)
                }
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
        Acquire a connection from the pool.
        
        Usage:
            >>> async with db.acquire() as conn:
            ...     result = await conn.fetch("SELECT * FROM table")
        """
        if not self._initialized:
            await self.initialize()
            
        async with self._pool.acquire() as connection:
            yield connection
    
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
        """
        columns = list(data.keys())
        values = list(data.values())
        placeholders = [f"${i+1}" for i in range(len(values))]
        
        query = f"""
            INSERT INTO {table} ({', '.join(columns)})
            VALUES ({', '.join(placeholders)})
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
        """
        set_clauses = [f"{k} = ${i+1}" for i, k in enumerate(data.keys())]
        where_clauses = [f"{k} = ${i+len(data)+1}" for i, k in enumerate(where.keys())]
        
        query = f"""
            UPDATE {table}
            SET {', '.join(set_clauses)}
            WHERE {' AND '.join(where_clauses)}
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
        """
        where_clauses = [f"{k} = ${i+1}" for i, k in enumerate(where.keys())]
        
        query = f"""
            DELETE FROM {table}
            WHERE {' AND '.join(where_clauses)}
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
            order_by: ORDER BY clause
            limit: LIMIT
            offset: OFFSET
            
        Returns:
            List of records
        """
        cols = ', '.join(columns) if columns else '*'
        
        query = f"SELECT {cols} FROM {table}"
        values = []
        
        if where:
            where_clauses = []
            for i, (k, v) in enumerate(where.items()):
                if isinstance(v, list):
                    # Handle IN clauses
                    placeholders = [f"${len(values)+j+1}" for j in range(len(v))]
                    where_clauses.append(f"{k} IN ({', '.join(placeholders)})")
                    values.extend(v)
                else:
                    where_clauses.append(f"{k} = ${len(values)+1}")
                    values.append(v)
            
            query += f" WHERE {' AND '.join(where_clauses)}"
        
        if order_by:
            query += f" ORDER BY {order_by}"
        
        if limit:
            query += f" LIMIT {limit}"
        
        if offset:
            query += f" OFFSET {offset}"
        
        records = await self.fetch(query, *values)
        return [dict(r) for r in records]


class DatabaseConnectionError(Exception):
    """Raised when database connection fails."""
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
