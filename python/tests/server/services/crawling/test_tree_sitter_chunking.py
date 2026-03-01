"""Tree-sitter integration tests for code-aware chunking."""

from __future__ import annotations

import pytest
from tree_sitter import Language, Parser, Query, QueryCursor

import tree_sitter_javascript
import tree_sitter_python
import tree_sitter_typescript


@pytest.fixture(scope="module")
def languages() -> dict[str, Language]:
    return {
        "python": Language(tree_sitter_python.language()),
        "javascript": Language(tree_sitter_javascript.language()),
        "typescript": Language(tree_sitter_typescript.language_typescript()),
    }


@pytest.fixture
def parser(languages: dict[str, Language]) -> Parser:
    parser = Parser()
    parser.language = languages["python"]
    return parser


@pytest.mark.tree_sitter_integration
class TestTreeSitterChunking:
    """Integration tests that will hook into chunking once available."""

    def test_python_function_captures(self, parser: Parser, languages: dict[str, Language]) -> None:
        language = languages["python"]
        parser.language = language
        source = b"""
        def function_one():
            '''First function'''
            return 1

        def function_two():
            '''Second function'''
            return 2

        def function_three():
            '''Third function'''
            return 3
        """
        tree = parser.parse(source)
        query = Query(language, "(function_definition) @function")
        cursor = QueryCursor(query)
        captures = cursor.captures(tree.root_node)
        assert len(captures.get("function", [])) == 3

    def test_class_structure_capture(self, parser: Parser, languages: dict[str, Language]) -> None:
        language = languages["python"]
        parser.language = language
        source = b"""
        class MyClass:
            def __init__(self):
                self.value = 1

            def method_one(self):
                return self.value

            def method_two(self):
                return self.value * 2
        """
        tree = parser.parse(source)
        query = Query(language, "(class_definition) @class")
        cursor = QueryCursor(query)
        captures = cursor.captures(tree.root_node)
        assert len(captures.get("class", [])) == 1

    def test_javascript_function_captures(self, parser: Parser, languages: dict[str, Language]) -> None:
        language = languages["javascript"]
        parser.language = language
        source = b"""
        function functionOne() {
            return 1;
        }

        function functionTwo() {
            return 2;
        }

        const arrowFunc = () => {
            return 3;
        };
        """
        tree = parser.parse(source)
        query = Query(
            language,
            """
            (function_declaration) @function
            (lexical_declaration (variable_declarator value: (arrow_function))) @arrow
            """,
        )
        cursor = QueryCursor(query)
        captures = cursor.captures(tree.root_node)
        total = sum(len(nodes) for nodes in captures.values())
        assert total == 3

    def test_import_statements(self, parser: Parser, languages: dict[str, Language]) -> None:
        language = languages["python"]
        parser.language = language
        source = b"""
        import os
        import sys
        from pathlib import Path
        from typing import List, Dict

        def my_function():
            return Path('.')
        """
        tree = parser.parse(source)
        query = Query(
            language,
            """
            (import_statement) @import
            (import_from_statement) @import_from
            """,
        )
        cursor = QueryCursor(query)
        captures = cursor.captures(tree.root_node)
        total = sum(len(nodes) for nodes in captures.values())
        assert total == 4

    @pytest.mark.xfail(reason="Chunker integration pending")
    def test_chunker_respects_function_boundaries(self, languages: dict[str, Language]) -> None:
        parser = Parser(languages["python"])
        source = b"""
        def function_one():
            return 1

        def function_two():
            return 2
        """
        tree = parser.parse(source)
        query = Query(languages["python"], "(function_definition) @function")
        functions = QueryCursor(query).captures(tree.root_node).get("function", [])
        assert len(functions) == 2
        # Placeholder assertion until the chunker integration is ready.
        assert functions[0].type == "function_definition"
