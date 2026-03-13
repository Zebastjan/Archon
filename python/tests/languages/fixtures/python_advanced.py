"""
Advanced Python patterns for testing edge cases.
Includes metaclasses, descriptors, complex decorators, and tricky syntax.
"""

import functools
import contextlib
from typing import TypeVar, Generic, Protocol, runtime_checkable
from dataclasses import dataclass, field
from enum import Enum, auto
from collections.abc import Iterator, AsyncIterator


# ============================================================================
# Metaclasses
# ============================================================================

class SingletonMeta(type):
    """Metaclass that creates singleton classes."""
    _instances: dict = {}
    
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class DatabaseMeta(type):
    """Metaclass that registers database models."""
    registry: list = []
    
    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        if name != 'BaseModel':
            mcs.registry.append(cls)
        return cls


class BaseModel(metaclass=DatabaseMeta):
    """Base class using custom metaclass."""
    
    def save(self) -> None:
        """Save to database."""
        pass


class UserModel(BaseModel):
    """User model with metaclass inheritance."""
    
    def __init__(self, name: str) -> None:
        self.name = name


# ============================================================================
# Complex Decorators
# ============================================================================

def retry(max_attempts: int = 3, exceptions: tuple = (Exception,)):
    """Decorator factory with parameters."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts - 1:
                        raise
        return wrapper
    return decorator


class CachedProperty:
    """Custom descriptor implementing cached property."""
    
    def __init__(self, func):
        self.func = func
        self.name = func.__name__
        functools.update_wrapper(self, func)
    
    def __get__(self, instance, owner):
        if instance is None:
            return self
        value = self.func(instance)
        setattr(instance, self.name, value)
        return value


def class_decorator(cls):
    """Decorator that modifies a class."""
    cls.decorated = True
    return cls


# ============================================================================
# Protocols and Structural Subtyping
# ============================================================================

@runtime_checkable
class Drawable(Protocol):
    """Protocol for drawable objects."""
    
    def draw(self) -> None:
        ...
    
    @property
    def bounds(self) -> tuple[float, float, float, float]:
        ...


class Shape:
    """Regular class that happens to match protocol."""
    
    def draw(self) -> None:
        """Draw the shape."""
        pass
    
    @property
    def bounds(self) -> tuple[float, float, float, float]:
        return (0.0, 0.0, 1.0, 1.0)


# ============================================================================
# Generics and TypeVars
# ============================================================================

T = TypeVar('T')
K = TypeVar('K')
V = TypeVar('V')
Number = TypeVar('Number', int, float)


class Container(Generic[T]):
    """Generic container class."""
    
    def __init__(self, value: T) -> None:
        self._value = value
    
    def get(self) -> T:
        """Get value."""
        return self._value
    
    def set(self, value: T) -> None:
        """Set value."""
        self._value = value


class NumberContainer(Container[Number]):
    """Constrained generic."""
    
    def add(self, other: Number) -> Number:
        return self._value + other  # type: ignore


# ============================================================================
# Context Managers and Context Decorators
# ============================================================================

class Transaction:
    """Context manager for database transactions."""
    
    def __init__(self, db: str) -> None:
        self.db = db
        self.committed = False
    
    def __enter__(self) -> 'Transaction':
        """Begin transaction."""
        self.committed = False
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """End transaction."""
        if not exc_type and not self.committed:
            self.commit()
    
    def commit(self) -> None:
        """Commit transaction."""
        self.committed = True


@contextlib.contextmanager
def temporary_context():
    """Context manager using decorator syntax."""
    try:
        yield "context_value"
    finally:
        pass


# ============================================================================
# Complex Class Hierarchies
# ============================================================================

class MixinA:
    """Mixin providing A functionality."""
    
    def method_a(self) -> str:
        return "A"


class MixinB:
    """Mixin providing B functionality."""
    
    def method_b(self) -> str:
        return "B"


class Combined(MixinA, MixinB):
    """Class using multiple inheritance."""
    
    def method_combined(self) -> str:
        return self.method_a() + self.method_b()


# Diamond inheritance
class Base:
    """Base class."""
    
    def method(self) -> str:
        return "base"


class Left(Base):
    """Left branch."""
    
    def method(self) -> str:
        return "left"


class Right(Base):
    """Right branch."""
    
    def method(self) -> str:
        return "right"


class Diamond(Left, Right):
    """Diamond inheritance - MRO is tricky."""
    pass


# ============================================================================
# Enums and Data Classes
# ============================================================================

class Color(Enum):
    """Color enumeration."""
    RED = auto()
    GREEN = auto()
    BLUE = auto()


class Status(Enum):
    """Status with values."""
    PENDING = "pending"
    ACTIVE = "active"
    CLOSED = "closed"


@dataclass(frozen=True)
class Point:
    """Immutable point."""
    x: float
    y: float


@dataclass
class Config:
    """Configuration with defaults."""
    name: str
    debug: bool = False
    options: dict = field(default_factory=dict)


# ============================================================================
# Async Patterns
# ============================================================================

async def async_generator() -> AsyncIterator[int]:
    """Async generator."""
    for i in range(10):
        yield i


class AsyncContext:
    """Async context manager."""
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


async def use_async_context():
    """Use async context manager."""
    async with AsyncContext() as ctx:
        pass


# ============================================================================
# Exception Hierarchy
# ============================================================================

class ApplicationError(Exception):
    """Base application error."""
    pass


class ValidationError(ApplicationError):
    """Validation failed."""
    pass


class NotFoundError(ApplicationError):
    """Resource not found."""
    
    def __init__(self, resource_type: str, resource_id: str) -> None:
        super().__init__(f"{resource_type} {resource_id} not found")
        self.resource_type = resource_type
        self.resource_id = resource_id


# ============================================================================
# Properties with Complex Logic
# ============================================================================

class Temperature:
    """Class with computed properties."""
    
    def __init__(self, celsius: float = 0) -> None:
        self._celsius = celsius
    
    @property
    def celsius(self) -> float:
        """Get Celsius."""
        return self._celsius
    
    @celsius.setter
    def celsius(self, value: float) -> None:
        """Set Celsius."""
        self._celsius = value
    
    @property
    def fahrenheit(self) -> float:
        """Get Fahrenheit."""
        return (self._celsius * 9/5) + 32
    
    @fahrenheit.setter
    def fahrenheit(self, value: float) -> None:
        """Set Fahrenheit."""
        self._celsius = (value - 32) * 5/9
    
    @property
    def is_freezing(self) -> bool:
        """Check if freezing."""
        return self._celsius <= 0


# ============================================================================
# Complex Function Signatures
# ============================================================================

def complex_function(
    required: str,
    optional: int = 10,
    *args: str,
    keyword_only: bool = False,
    **kwargs: object
) -> dict[str, object]:
    """Function with all parameter types.
    
    Args:
        required: Required positional
        optional: Optional with default
        *args: Variable positional
        keyword_only: Keyword-only
        **kwargs: Variable keyword
    
    Returns:
        Dict of all arguments
    """
    return {
        "required": required,
        "optional": optional,
        "args": args,
        "keyword_only": keyword_only,
        "kwargs": kwargs,
    }


# ============================================================================
# Lambdas and Higher-Order Functions
# ============================================================================

operations = {
    'add': lambda x, y: x + y,
    'subtract': lambda x, y: x - y,
    'multiply': lambda x, y: x * y,
}


def make_multiplier(factor: float):
    """Return a multiplier function."""
    return lambda x: x * factor


# ============================================================================
# Module-Level Execution
# ============================================================================

if __name__ == "__main__":
    # This should not be extracted as it's at module level
    # but inside if __name__ == "__main__"
    def main_function():
        """Main function - should this be extracted?"""
        pass
