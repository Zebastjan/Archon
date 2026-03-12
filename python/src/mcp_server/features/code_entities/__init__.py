"""Code entity MCP tools for structural code understanding.

Provides tools for querying code entities (functions, classes, etc.) and
 their relationships extracted via Tree-sitter parsing.
"""

from .tools import register_code_entity_tools

__all__ = ["register_code_entity_tools"]
