"""Tests for language support module.

Tests the Tree-sitter-based code extraction for Python and TypeScript.
"""

import pytest

from src.server.services.languages import (
    CodeEntity,
    CodeRelationship,
    get_language_for_file,
    language_registry,
)
from src.server.services.languages.language_support import ParseError
from src.server.services.languages.python_support import PythonLanguageSupport
from src.server.services.languages.typescript_support import TypeScriptLanguageSupport


class TestLanguageRegistry:
    """Tests for the language registry."""
    
    def test_get_language_for_python_file(self):
        """Should return Python support for .py files."""
        support = get_language_for_file("src/main.py")
        assert support is not None
        assert support.language_id == "python"
    
    def test_get_language_for_typescript_file(self):
        """Should return TypeScript support for .ts files."""
        support = get_language_for_file("src/main.ts")
        assert support is not None
        assert support.language_id == "typescript"
    
    def test_get_language_for_javascript_file(self):
        """Should return TypeScript support for .js files (shared handler)."""
        support = get_language_for_file("src/main.js")
        assert support is not None
        assert support.language_id == "typescript"
    
    def test_get_language_for_unsupported_file(self):
        """Should return None for unsupported extensions."""
        support = get_language_for_file("src/main.rs")
        assert support is None
    
    def test_language_registry_has_registered_languages(self):
        """Registry should have Python and TypeScript registered."""
        languages = language_registry.list_languages()
        assert "python" in languages
        assert "typescript" in languages


class TestPythonLanguageSupport:
    """Tests for Python language support."""
    
    @pytest.fixture
    def python_support(self):
        """Create Python language support instance."""
        return PythonLanguageSupport()
    
    def test_extract_simple_function(self, python_support):
        """Should extract a simple function."""
        content = '''
def greet(name: str) -> str:
    """Return a greeting."""
    return f"Hello, {name}!"
'''
        entities, relationships = python_support.extract_entities_and_relationships(
            content, "greeting.py"
        )
        
        assert len(entities) == 1
        assert entities[0].entity_type == "function"
        assert entities[0].name == "greet"
        assert "def greet" in entities[0].signature
        assert entities[0].docstring == "Return a greeting."
    
    def test_extract_class_with_method(self, python_support):
        """Should extract class and its methods."""
        content = '''
class Calculator:
    """A simple calculator."""
    
    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b
'''
        entities, relationships = python_support.extract_entities_and_relationships(
            content, "calculator.py"
        )
        
        # Should have Calculator class and add method
        assert len(entities) == 2
        
        class_entity = next(e for e in entities if e.entity_type == "class")
        assert class_entity.name == "Calculator"
        
        method_entity = next(e for e in entities if e.entity_type == "method")
        assert method_entity.name == "Calculator.add"
        assert "Add two numbers." == method_entity.docstring
        
        # Should have DEFINES relationship
        defines_rels = [r for r in relationships if r.relationship_type == "DEFINES"]
        assert len(defines_rels) == 1
        assert defines_rels[0].source_name == "Calculator"
        assert defines_rels[0].target_name == "Calculator.add"
    
    def test_extract_imports(self, python_support):
        """Should extract import relationships."""
        content = '''
import os
from typing import Dict, List

def process():
    pass
'''
        entities, relationships = python_support.extract_entities_and_relationships(
            content, "imports.py"
        )
        
        # Should have process function
        assert len(entities) == 1
        
        # Should have import relationships
        import_rels = [r for r in relationships if r.relationship_type == "IMPORTS"]
        assert len(import_rels) >= 2  # os and typing
    
    def test_extract_class_inheritance(self, python_support):
        """Should extract class inheritance."""
        content = '''
class Animal:
    pass

class Dog(Animal):
    pass
'''
        entities, relationships = python_support.extract_entities_and_relationships(
            content, "inheritance.py"
        )
        
        assert len(entities) == 2
        
        # Should have INHERITS relationship
        inherits_rels = [r for r in relationships if r.relationship_type == "INHERITS"]
        assert len(inherits_rels) == 1
        assert inherits_rels[0].source_name == "Dog"
        assert inherits_rels[0].target_name == "Animal"
    
    def test_extract_nested_functions(self, python_support):
        """Should extract nested functions."""
        content = '''
def outer():
    """Outer function."""
    def inner():
        """Inner function."""
        return 42
    return inner()
'''
        entities, relationships = python_support.extract_entities_and_relationships(
            content, "nested.py"
        )
        
        assert len(entities) == 2
        
        names = [e.name for e in entities]
        assert "outer" in names
        assert any("inner" in name for name in names)


class TestTypeScriptLanguageSupport:
    """Tests for TypeScript/JavaScript language support."""
    
    @pytest.fixture
    def ts_support(self):
        """Create TypeScript language support instance."""
        return TypeScriptLanguageSupport()
    
    def test_extract_function_declaration(self, ts_support):
        """Should extract function declarations."""
        content = '''
function greet(name: string): string {
    return `Hello, ${name}!`;
}
'''
        entities, relationships = ts_support.extract_entities_and_relationships(
            content, "greeting.ts"
        )
        
        assert len(entities) >= 1
        func = next(e for e in entities if e.entity_type == "function")
        assert func.name == "greet"
        assert "function greet" in func.signature
    
    def test_extract_class_with_method(self, ts_support):
        """Should extract classes and methods."""
        content = '''
class UserService {
    async getUser(id: number): Promise<User> {
        return await fetch(`/api/users/${id}`);
    }
}
'''
        entities, relationships = ts_support.extract_entities_and_relationships(
            content, "service.ts"
        )
        
        # Should have UserService class and getUser method
        class_entity = next((e for e in entities if e.entity_type == "class"), None)
        assert class_entity is not None
        assert class_entity.name == "UserService"
        
        method_entity = next((e for e in entities if e.entity_type == "method"), None)
        assert method_entity is not None
        assert "UserService.getUser" in method_entity.name or "getUser" in method_entity.name
    
    def test_extract_interface(self, ts_support):
        """Should extract TypeScript interfaces."""
        content = '''
interface User {
    id: number;
    name: string;
}
'''
        entities, relationships = ts_support.extract_entities_and_relationships(
            content, "user.ts"
        )
        
        interface = next((e for e in entities if e.entity_type == "interface"), None)
        assert interface is not None
        assert interface.name == "User"
    
    def test_extract_imports(self, ts_support):
        """Should extract ES6 imports."""
        content = '''
import React, { useState, useEffect } from 'react';
import * as utils from './utils';

export function MyComponent() {
    return null;
}
'''
        entities, relationships = ts_support.extract_entities_and_relationships(
            content, "component.tsx"
        )
        
        assert len(entities) >= 1
        
        # Should have IMPORTS relationships
        import_rels = [r for r in relationships if r.relationship_type == "IMPORTS"]
        assert len(import_rels) > 0


class TestCodeEntityDataclass:
    """Tests for CodeEntity dataclass."""
    
    def test_create_entity(self):
        """Should create a CodeEntity."""
        entity = CodeEntity(
            entity_type="function",
            name="test_function",
            signature="def test_function():",
            docstring="Test docstring",
            source_code="def test_function():\n    pass",
            line_start=1,
            line_end=2,
        )
        
        assert entity.entity_type == "function"
        assert entity.name == "test_function"
        assert entity.docstring == "Test docstring"
    
    def test_create_relationship(self):
        """Should create a CodeRelationship."""
        rel = CodeRelationship(
            source_name="caller",
            target_name="callee",
            relationship_type="CALLS",
            metadata={"line": 42},
        )
        
        assert rel.source_name == "caller"
        assert rel.target_name == "callee"
        assert rel.relationship_type == "CALLS"
        assert rel.metadata["line"] == 42


class TestIntegrationWithGitRepository:
    """Integration tests with git repository service."""
    
    @pytest.mark.integration
    def test_extract_from_archon_repo_python(self):
        """Test extraction from Archon's actual Python files."""
        # This would require setting up test fixtures
        # Placeholder for integration test
        pass
