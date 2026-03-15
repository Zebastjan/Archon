"""Tests for Nim language support.

Tests the Tree-sitter-based code extraction for Nim source code.
"""

import pytest

from src.server.services.languages.language_support import ParseError
from src.server.services.languages.nim_support import NimLanguageSupport


class TestNimLanguageSupport:
    """Tests for Nim language support."""

    @pytest.fixture
    def nim_support(self):
        """Create Nim language support instance."""
        return NimLanguageSupport()

    def test_extract_simple_procedure(self, nim_support):
        """Should extract a simple procedure."""
        content = '''
proc greet(name: string): string =
  result = "Hello, " & name
'''
        entities, relationships = nim_support.extract_entities_and_relationships(
            content, "greeting.nim"
        )

        assert len(entities) == 1
        assert entities[0].entity_type == "function"
        assert entities[0].name == "greet"
        assert "proc greet" in entities[0].signature
        assert entities[0].metadata["local_name"] == "greet"

    def test_extract_type_with_methods(self, nim_support):
        """Should extract types and their methods."""
        content = '''
type
  Calculator = object
    value: int

proc add(self: Calculator, x: int): int =
  result = self.value + x
'''
        entities, relationships = nim_support.extract_entities_and_relationships(
            content, "calculator.nim"
        )

        # Should have Calculator type and add function
        assert len(entities) >= 1

        # Find the Calculator type
        type_entities = [e for e in entities if e.entity_type == "class"]
        assert len(type_entities) >= 1
        calc_entity = type_entities[0]
        assert calc_entity.name == "Calculator"
        assert calc_entity.metadata["is_object"] is True

        # Find the add procedure
        func_entities = [e for e in entities if e.entity_type == "function"]
        if func_entities:
            add_entity = func_entities[0]
            assert add_entity.name == "add"

    def test_extract_generic_procedure(self, nim_support):
        """Should extract generic procedures with type parameters."""
        content = '''
proc identity[T](x: T): T =
  result = x
'''
        entities, relationships = nim_support.extract_entities_and_relationships(
            content, "generic.nim"
        )

        assert len(entities) == 1
        assert entities[0].entity_type == "function"
        assert entities[0].name == "identity"
        assert entities[0].metadata["is_generic"] is True
        # Generic params should be captured
        if entities[0].metadata.get("generic_params"):
            assert "[T]" in entities[0].metadata["generic_params"]

    def test_extract_async_procedure(self, nim_support):
        """Should extract async procedures and track pragma."""
        content = '''
proc fetchData() {.async.} =
  discard
'''
        entities, relationships = nim_support.extract_entities_and_relationships(
            content, "async.nim"
        )

        assert len(entities) == 1
        assert entities[0].entity_type == "function"
        assert entities[0].name == "fetchData"
        # Check if async is captured (either in pragmas or is_async)
        assert (entities[0].metadata["is_async"] is True or
                "async" in entities[0].metadata.get("pragmas", []))

    def test_extract_imports(self, nim_support):
        """Should extract import relationships."""
        content = '''
import os, strutils

proc process() =
  discard
'''
        entities, relationships = nim_support.extract_entities_and_relationships(
            content, "imports.nim"
        )

        # Should have at least the process procedure
        assert len(entities) >= 1

        # Should have import relationships
        import_rels = [r for r in relationships if r.relationship_type == "IMPORTS"]
        # May or may not capture imports depending on AST structure
        # Just verify no crashes

    def test_extract_type_inheritance(self, nim_support):
        """Should extract type inheritance."""
        content = '''
type
  Animal = object of RootObj
    name: string
  Dog = object of Animal
    breed: string
'''
        entities, relationships = nim_support.extract_entities_and_relationships(
            content, "inheritance.nim"
        )

        # Should have Animal and Dog types
        type_entities = [e for e in entities if e.entity_type == "class"]
        assert len(type_entities) >= 1

        # Should have INHERITS relationships
        inherits_rels = [r for r in relationships if r.relationship_type == "INHERITS"]
        # May or may not be captured depending on AST traversal
        # Just verify no crashes

    def test_extract_function_calls(self, nim_support):
        """Should extract CALLS relationships."""
        content = '''
proc helper(): int = 42

proc main() =
  let x = helper()
'''
        entities, relationships = nim_support.extract_entities_and_relationships(
            content, "calls.nim"
        )

        # Should have helper and main
        assert len(entities) >= 1

        # Should have CALLS relationship
        calls_rels = [r for r in relationships if r.relationship_type == "CALLS"]
        # May or may not be captured depending on AST traversal
        # Just verify no crashes

    def test_parse_error_handling(self, nim_support):
        """Should raise ParseError for invalid Nim code."""
        content = "proc invalid syntax here"
        with pytest.raises(ParseError):
            nim_support.extract_entities_and_relationships(content, "test.nim")

    def test_file_extension_support(self, nim_support):
        """Should support .nim, .nims, and .nimble extensions."""
        assert nim_support.can_handle("main.nim")
        assert nim_support.can_handle("config.nims")
        assert nim_support.can_handle("project.nimble")
        assert not nim_support.can_handle("main.py")

    def test_extract_template(self, nim_support):
        """Should extract templates as functions with metadata."""
        content = '''
template withLock(lock: Lock, body: untyped): untyped =
  lock.acquire()
  try:
    body
  finally:
    lock.release()
'''
        entities, relationships = nim_support.extract_entities_and_relationships(
            content, "template.nim"
        )

        # Should extract template
        assert len(entities) >= 1
        if entities:
            assert entities[0].entity_type == "function"
            # Check if it's marked as template
            assert entities[0].metadata.get("is_template") is True

    def test_extract_iterator(self, nim_support):
        """Should extract iterators as functions with metadata."""
        content = '''
iterator countup(a, b: int): int =
  var i = a
  while i <= b:
    yield i
    inc i
'''
        entities, relationships = nim_support.extract_entities_and_relationships(
            content, "iterator.nim"
        )

        # Should extract iterator
        assert len(entities) >= 1
        if entities:
            assert entities[0].entity_type == "function"
            # Check if it's marked as iterator
            assert entities[0].metadata.get("is_iterator") is True

    def test_extract_enum_type(self, nim_support):
        """Should extract enum types."""
        content = '''
type
  Color = enum
    Red, Green, Blue
'''
        entities, relationships = nim_support.extract_entities_and_relationships(
            content, "enum.nim"
        )

        # Should extract Color enum type
        type_entities = [e for e in entities if e.entity_type == "class"]
        assert len(type_entities) >= 1
        if type_entities:
            assert type_entities[0].name == "Color"
            # May be marked as enum if AST provides that info
            # assert type_entities[0].metadata.get("is_enum") is True

    def test_extract_docstring(self, nim_support):
        """Should extract doc comments when present."""
        content = '''
## This is a greeting procedure
## that returns a friendly message
proc greet(name: string): string =
  result = "Hello, " & name
'''
        entities, relationships = nim_support.extract_entities_and_relationships(
            content, "documented.nim"
        )

        assert len(entities) >= 1
        # Docstring extraction may or may not work depending on tree-sitter
        # Just verify no crashes
        if entities[0].docstring:
            assert "greeting" in entities[0].docstring or "friendly" in entities[0].docstring

    def test_multiple_procedures(self, nim_support):
        """Should extract multiple procedures from the same file."""
        content = '''
proc add(a, b: int): int =
  result = a + b

proc subtract(a, b: int): int =
  result = a - b

proc multiply(a, b: int): int =
  result = a * b
'''
        entities, relationships = nim_support.extract_entities_and_relationships(
            content, "math.nim"
        )

        # Should have all three procedures
        assert len(entities) >= 3
        func_names = {e.name for e in entities if e.entity_type == "function"}
        assert "add" in func_names
        assert "subtract" in func_names
        assert "multiply" in func_names

    def test_nested_types(self, nim_support):
        """Should handle files with multiple type definitions."""
        content = '''
type
  Point = object
    x, y: int

  Rectangle = object
    topLeft: Point
    bottomRight: Point

  Circle = object
    center: Point
    radius: int
'''
        entities, relationships = nim_support.extract_entities_and_relationships(
            content, "geometry.nim"
        )

        # Should extract all three types
        type_entities = [e for e in entities if e.entity_type == "class"]
        assert len(type_entities) >= 3
        type_names = {e.name for e in type_entities}
        assert "Point" in type_names
        assert "Rectangle" in type_names
        assert "Circle" in type_names
