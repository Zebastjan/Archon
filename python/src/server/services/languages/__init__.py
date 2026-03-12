"""Language support module for multi-language code intelligence.

Provides Tree-sitter-based AST parsing and entity extraction for multiple
programming languages, with a plugin architecture for extensibility.
"""

from .language_support import (
    CodeEntity,
    CodeRelationship,
    LanguageSupport,
)
from .language_registry import (
    LanguageSupportRegistry,
    language_registry,
    get_language_for_file,
)

__all__ = [
    "CodeEntity",
    "CodeRelationship",
    "LanguageSupport",
    "LanguageSupportRegistry",
    "language_registry",
    "get_language_for_file",
]
