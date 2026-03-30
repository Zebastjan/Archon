"""Base protocol for language-specific code analysis.

Defines the interface that all language support implementations must follow.
This enables a plugin architecture where new languages can be added
by implementing this protocol.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass
class CodeEntity:
    """Represents a code entity (function, class, etc.) extracted from source.

    Attributes:
        entity_type: Type of entity (function, class, interface, etc.)
        name: Name of the entity
        signature: Function signature or class definition
        docstring: Documentation string if present
        source_code: Full source code of the entity
        line_start: Starting line number (1-indexed)
        line_end: Ending line number (1-indexed)
        file_path: Path to the source file (optional, for convenience)
        language: Programming language identifier (optional)
        metadata: Additional language-specific metadata
    """

    entity_type: str
    name: str
    signature: str | None = None
    docstring: str | None = None
    source_code: str = ""
    line_start: int = 0
    line_end: int = 0
    file_path: str | None = None
    language: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class CodeRelationship:
    """Represents a relationship between two code entities.

    Relationships are stored by name initially and resolved to entity IDs
    during the storage phase. This allows cross-file relationships to be
    captured during single-file parsing.

    Attributes:
        source_name: Name of the source entity (fully qualified if possible)
        target_name: Name of the target entity
        relationship_type: Type of relationship (CALLS, INHERITS, IMPORTS, etc.)
        metadata: Additional context (line number, confidence, etc.)
    """

    source_name: str
    target_name: str
    relationship_type: str
    metadata: dict = field(default_factory=dict)


@runtime_checkable
class LanguageSupport(Protocol):
    """Protocol for language-specific code analysis.

    All language support implementations must implement this interface.
    The protocol is checked at runtime using isinstance().

    Example:
        >>> from tree_sitter import Language, Parser
        >>> import tree_sitter_python as ts_python
        >>>
        >>> class PythonLanguageSupport:
        ...     language_id = "python"
        ...     file_extensions = [".py", ".pyw", ".pyi"]
        ...
        ...     def __init__(self):
        ...         self._language = Language(ts_python.language())
        ...         self._parser = Parser(self._language)
        ...
        ...     def extract_entities_and_relationships(self, content, file_path):
        ...         # Parse and extract entities
        ...         return entities, relationships
    """

    language_id: str
    """Unique identifier for the language (e.g., 'python', 'typescript')."""

    file_extensions: list[str]
    """File extensions this language handles (e.g., ['.py'], ['.ts', '.tsx'])."""

    def can_handle(self, file_path: str) -> bool:
        """Check if this language support can handle the given file.

        Args:
            file_path: Path to the file (can be relative or absolute)

        Returns:
            True if this language can parse the file, False otherwise

        Example:
            >>> python = PythonLanguageSupport()
            >>> python.can_handle("src/main.py")
            True
            >>> python.can_handle("src/main.ts")
            False
        """
        ext = Path(file_path).suffix.lower()
        return ext in self.file_extensions

    def extract_entities_and_relationships(
        self,
        content: str,
        file_path: str,
    ) -> tuple[list[CodeEntity], list[CodeRelationship]]:
        """Extract entities and relationships from source code.

        This is the core method that parses source code and extracts
        structural information about code entities and their relationships.

        Args:
            content: Full file content as a string
            file_path: Relative path within the repository (for context)

        Returns:
            Tuple of (entities, relationships) found in the file.
            Entities are fully populated CodeEntity objects.
            Relationships use entity names and are resolved to IDs during storage.

        Raises:
            ParseError: If the source code cannot be parsed

        Example:
            >>> content = '''def greet(name: str) -> str:
            ...     \"\"\"Return a greeting.\"\"\"
            ...     return f"Hello, {name}!"
            ... '''
            >>> entities, relationships = support.extract_entities_and_relationships(
            ...     content, "greeting.py"
            ... )
            >>> entities[0].name
            'greet'
            >>> entities[0].entity_type
            'function'
        """
        ...


class LanguageSupportBase(ABC):
    """Abstract base class for language support implementations.

    Provides common functionality and enforces the interface.
    Language implementations should inherit from this class.
    """

    language_id: str
    file_extensions: list[str]

    def can_handle(self, file_path: str) -> bool:
        """Check if this language support can handle the given file."""
        ext = Path(file_path).suffix.lower()
        return ext in self.file_extensions

    @abstractmethod
    def extract_entities_and_relationships(
        self,
        content: str,
        file_path: str,
    ) -> tuple[list[CodeEntity], list[CodeRelationship]]:
        """Extract entities and relationships from source code."""
        pass


class ParseError(Exception):
    """Raised when source code cannot be parsed."""

    def __init__(self, message: str, file_path: str, line: int | None = None):
        self.file_path = file_path
        self.line = line
        super().__init__(
            f"Parse error in {file_path}:{line}: {message}" if line else f"Parse error in {file_path}: {message}"
        )
