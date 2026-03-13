"""
Real-world Python code for testing tree-sitter extraction.
This file contains diverse Python constructs to validate parsing.
"""

import os
from typing import Dict, List, Optional
from dataclasses import dataclass
from abc import ABC, abstractmethod


# Global constant
MAX_RETRIES = 3


@dataclass
class User:
    """User data class."""
    id: int
    name: str
    email: Optional[str] = None


class Repository(ABC):
    """Abstract base class for repositories."""
    
    def __init__(self, db_url: str):
        self.db_url = db_url
        self._connection = None
    
    @abstractmethod
    def connect(self) -> None:
        """Establish database connection."""
        pass
    
    @abstractmethod
    def find_by_id(self, id: int) -> Optional[Dict]:
        """Find entity by ID."""
        pass
    
    def close(self) -> None:
        """Close connection."""
        if self._connection:
            self._connection.close()


class UserRepository(Repository):
    """Concrete repository for users."""
    
    def __init__(self, db_url: str, table_name: str = "users"):
        super().__init__(db_url)
        self.table_name = table_name
    
    def connect(self) -> None:
        """Connect to database."""
        import sqlite3
        self._connection = sqlite3.connect(self.db_url)
    
    def find_by_id(self, id: int) -> Optional[Dict]:
        """Find user by ID."""
        cursor = self._connection.cursor()
        cursor.execute(f"SELECT * FROM {self.table_name} WHERE id = ?", (id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def find_all(self, limit: int = 100) -> List[Dict]:
        """Find all users with limit."""
        cursor = self._connection.cursor()
        cursor.execute(f"SELECT * FROM {self.table_name} LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()]


def create_user(name: str, email: str, **kwargs) -> User:
    """Factory function to create users."""
    return User(id=kwargs.get('id', 0), name=name, email=email)


def process_users(users: List[User]) -> Dict[int, str]:
    """Process list of users into dict."""
    return {user.id: user.name for user in users}


# Lambda and comprehension examples
squares = [x**2 for x in range(10)]
evens = list(filter(lambda x: x % 2 == 0, squares))


class DecoratorExample:
    """Class with decorated methods."""
    
    @property
    def full_name(self) -> str:
        """Property example."""
        return "Test User"
    
    @staticmethod
    def static_method() -> str:
        """Static method."""
        return "static"
    
    @classmethod
    def class_method(cls) -> str:
        """Class method."""
        return cls.__name__


# Exception handling
class ValidationError(Exception):
    """Custom exception."""
    pass


def validate_email(email: str) -> bool:
    """Validate email format."""
    if "@" not in email:
        raise ValidationError(f"Invalid email: {email}")
    return True


# Async example
import asyncio


async def fetch_data(url: str) -> Dict:
    """Async function example."""
    await asyncio.sleep(0.1)
    return {"url": url, "data": "test"}


async def process_async(items: List[str]) -> List[Dict]:
    """Process items asynchronously."""
    tasks = [fetch_data(item) for item in items]
    return await asyncio.gather(*tasks)


# Nested classes and closures
class Outer:
    """Outer class."""
    
    class Inner:
        """Inner class."""
        
        def method(self) -> None:
            """Inner method."""
            pass
    
    def outer_method(self) -> None:
        """Outer method with closure."""
        x = 10
        
        def inner() -> int:
            """Closure function."""
            return x + 1
        
        return inner()


# Generator example
def fibonacci(n: int):
    """Generate fibonacci sequence."""
    a, b = 0, 1
    for _ in range(n):
        yield a
        a, b = b, a + b


# Context manager
class DatabaseContext:
    """Context manager example."""
    
    def __enter__(self):
        """Enter context."""
        self.conn = "connection"
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context."""
        self.conn = None


# Type hints with generics
from typing import TypeVar, Generic

T = TypeVar('T')


class Container(Generic[T]):
    """Generic class."""
    
    def __init__(self, value: T):
        self.value = value
    
    def get(self) -> T:
        """Get value."""
        return self.value
