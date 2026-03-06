"""Tree-sitter infrastructure tests for general code parsing across the project."""

from __future__ import annotations

import importlib
import sys

import pytest
import tree_sitter_javascript
import tree_sitter_python
import tree_sitter_typescript
from tree_sitter import Language, Parser, Query, QueryCursor


class _ModuleProxy:
    def __init__(self, name: str):
        self._name = name

    def __getattr__(self, item):
        module = importlib.import_module(self._name)
        return getattr(module, item)

    def __dir__(self):
        module = importlib.import_module(self._name)
        return dir(module)


sys.modules.setdefault("src.server.utils", _ModuleProxy("src.server.utils"))


@pytest.fixture(scope="module")
def languages() -> dict[str, Language]:
    """Load supported Tree-sitter languages once per module."""
    return {
        "python": Language(tree_sitter_python.language()),
        "javascript": Language(tree_sitter_javascript.language()),
        "typescript": Language(tree_sitter_typescript.language_typescript()),
        "tsx": Language(tree_sitter_typescript.language_tsx()),
    }


@pytest.fixture
def parser(languages: dict[str, Language]) -> Parser:
    """Return a fresh parser for each test."""
    parser = Parser()
    parser.language = languages["python"]
    return parser


@pytest.mark.tree_sitter_unit
class TestTreeSitterInfrastructure:
    """Test suite for baseline Tree-sitter functionality."""

    def test_language_loading(self, languages: dict[str, Language]) -> None:
        assert languages["python"] is not None
        assert languages["javascript"] is not None
        assert languages["typescript"] is not None

    def test_parser_initialization(self, parser: Parser, languages: dict[str, Language]) -> None:
        for language in languages.values():
            parser.language = language
            assert parser.language == language

    def test_basic_parsing_python(self, parser: Parser, languages: dict[str, Language]) -> None:
        parser.language = languages["python"]
        tree = parser.parse(b"def foo():\n    return 42")
        assert tree.root_node.type == "module"
        assert not tree.root_node.has_error

    def test_basic_parsing_javascript(self, parser: Parser, languages: dict[str, Language]) -> None:
        parser.language = languages["javascript"]
        tree = parser.parse(b"function foo() { return 42; }")
        assert tree.root_node.type == "program"
        assert not tree.root_node.has_error

    def test_handles_syntax_errors(self, parser: Parser, languages: dict[str, Language]) -> None:
        parser.language = languages["python"]
        tree = parser.parse(b"def foo(\n    # missing body")
        assert tree.root_node.has_error

    def test_supports_memoryview_and_bytearray_inputs(
        self, parser: Parser, languages: dict[str, Language]
    ) -> None:
        parser.language = languages["python"]
        source = b"def foo():\n    return 1\n"
        tree1 = parser.parse(source)
        tree2 = parser.parse(memoryview(source))
        tree3 = parser.parse(bytearray(source))
        assert tree1.root_node.type == tree2.root_node.type == tree3.root_node.type == "module"

    def test_basic_query_execution(self, parser: Parser, languages: dict[str, Language]) -> None:
        language = languages["python"]
        parser.language = language
        source = b"\n".join(
            [
                b"def first():\n    return 1",
                b"",
                b"def second():\n    return 2",
            ]
        )
        tree = parser.parse(source)
        query = Query(language, "(function_definition) @function")
        cursor = QueryCursor(query)
        captures = cursor.captures(tree.root_node)
        function_nodes = captures.get("function", [])
        assert [node.type for node in function_nodes] == ["function_definition", "function_definition"]

    def test_query_with_captures_and_text(self, parser: Parser, languages: dict[str, Language]) -> None:
        language = languages["javascript"]
        parser.language = language
        source = b"const foo = () => 1;\nfunction bar() { return 2; }"
        tree = parser.parse(source)
        query = Query(
            language,
            """
            (arrow_function) @arrow
            (function_declaration name: (identifier) @name)
            """,
        )
        cursor = QueryCursor(query)
        matches = cursor.matches(tree.root_node)
        assert len(matches) == 2
        captured_kinds = set()
        for _, capture_dict in matches:
            captured_kinds.update(capture_dict.keys())
        assert captured_kinds == {"arrow", "name"}
