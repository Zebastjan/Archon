"""Registry for language support plugins.

Manages language support implementations and provides lookup by file extension
or language ID. Uses lazy loading to avoid importing unused language modules.
"""

import logging
from pathlib import Path

from .language_support import LanguageSupport

logger = logging.getLogger(__name__)


class LanguageSupportRegistry:
    """Registry for language support plugins.
    
    Maintains mappings from file extensions and language IDs to their
    corresponding LanguageSupport implementations. Supports lazy loading
    to minimize startup time and memory usage.
    
    Example:
        >>> registry = LanguageSupportRegistry()
        >>> registry.register(PythonLanguageSupport())
        >>> support = registry.get_for_file("main.py")
        >>> support.language_id
        'python'
    """
    
    def __init__(self):
        """Initialize empty registry."""
        self._languages: dict[str, LanguageSupport] = {}
        self._by_extension: dict[str, LanguageSupport] = {}
        self._logger = logger
        self._logger.debug("language_registry_initialized")
    
    def register(self, support: LanguageSupport) -> None:
        """Register a language support implementation.
        
        Args:
            support: LanguageSupport instance to register
            
        Raises:
            ValueError: If language_id is already registered
            
        Example:
            >>> registry = LanguageSupportRegistry()
            >>> registry.register(PythonLanguageSupport())
        """
        if support.language_id in self._languages:
            raise ValueError(f"Language '{support.language_id}' is already registered")
        
        self._languages[support.language_id] = support
        
        for ext in support.file_extensions:
            self._by_extension[ext.lower()] = support
        
        self._logger.info(
            f"Language registered: {support.language_id} "
            f"with extensions {support.file_extensions}"
        )
    
    def get_for_file(self, file_path: str) -> LanguageSupport | None:
        """Get language support for a given file path.
        
        Args:
            file_path: Path to the file (relative or absolute)
            
        Returns:
            LanguageSupport instance if found, None otherwise
            
        Example:
            >>> registry = LanguageSupportRegistry()
            >>> support = registry.get_for_file("src/main.py")
            >>> support.language_id if support else None
            'python'
        """
        ext = Path(file_path).suffix.lower()
        return self._by_extension.get(ext)
    
    def get(self, language_id: str) -> LanguageSupport | None:
        """Get language support by language ID.
        
        Args:
            language_id: Language identifier (e.g., 'python', 'typescript')
            
        Returns:
            LanguageSupport instance if found, None otherwise
            
        Example:
            >>> registry = LanguageSupportRegistry()
            >>> support = registry.get("python")
            >>> support.language_id if support else None
            'python'
        """
        return self._languages.get(language_id)
    
    def list_languages(self) -> list[str]:
        """Get list of all registered language IDs.
        
        Returns:
            Sorted list of registered language IDs
        """
        return sorted(self._languages.keys())
    
    def list_extensions(self) -> list[str]:
        """Get list of all registered file extensions.
        
        Returns:
            Sorted list of registered file extensions
        """
        return sorted(self._by_extension.keys())
    
    def is_supported(self, file_path: str) -> bool:
        """Check if a file type is supported.
        
        Args:
            file_path: Path to check
            
        Returns:
            True if the file extension is registered
        """
        return self.get_for_file(file_path) is not None


# Global registry instance
_language_registry: LanguageSupportRegistry | None = None


def get_language_registry() -> LanguageSupportRegistry:
    """Get or create the global language registry.
    
    Lazily initializes the registry on first call and registers
    built-in language supports.
    
    Returns:
        Global LanguageSupportRegistry instance
    """
    global _language_registry
    
    if _language_registry is None:
        _language_registry = LanguageSupportRegistry()
        _register_builtin_languages(_language_registry)
    
    return _language_registry


def _register_builtin_languages(registry: LanguageSupportRegistry) -> None:
    """Register built-in language supports.

    Called once during registry initialization. Imports language modules
    here to avoid circular imports at module load time.
    """
    logger.debug("Registering builtin languages")

    try:
        from .python_support import PythonLanguageSupport
        registry.register(PythonLanguageSupport())
        logger.debug("Python language support registered")
    except ImportError as e:
        logger.warning(f"Python language import failed: {e}")

    try:
        from .typescript_support import TypeScriptLanguageSupport
        registry.register(TypeScriptLanguageSupport())
        logger.debug("TypeScript language support registered")
    except ImportError as e:
        logger.warning(f"TypeScript language import failed: {e}")

    try:
        from .nim_support import NimLanguageSupport
        registry.register(NimLanguageSupport())
        logger.debug("Nim language support registered")
    except ImportError as e:
        logger.warning(f"Nim language import failed: {e}")

    logger.info(
        f"Builtin languages registered: {len(registry.list_languages())} "
        f"({', '.join(registry.list_languages())})"
    )


# Convenience function for direct access
def get_language_for_file(file_path: str) -> LanguageSupport | None:
    """Get language support for a file path using the global registry.
    
    This is a convenience wrapper around get_language_registry().get_for_file()
    
    Args:
        file_path: Path to the file
        
    Returns:
        LanguageSupport instance if found, None otherwise
        
    Example:
        >>> support = get_language_for_file("main.py")
        >>> support.language_id if support else None
        'python'
    """
    return get_language_registry().get_for_file(file_path)


# Global registry accessor for import
language_registry = get_language_registry()
