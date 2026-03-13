"""
Second tranche of tests for advanced language patterns.

Tests extraction of complex features that are common in real-world code
but may not be handled by basic extraction logic.
"""

from pathlib import Path

import pytest

from src.server.services.languages import get_language_for_file
from src.server.services.languages.python_support import PythonLanguageSupport
from src.server.services.languages.typescript_support import TypeScriptLanguageSupport


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestPythonAdvancedExtraction:
    """Test Python extraction against advanced patterns."""
    
    @pytest.fixture(scope="class")
    def python_file_content(self):
        """Load the advanced Python fixture."""
        fixture_path = FIXTURES_DIR / "python_advanced.py"
        if not fixture_path.exists():
            pytest.skip("Python advanced fixture not found")
        return fixture_path.read_text()
    
    @pytest.fixture(scope="class")
    def extraction_result(self, python_file_content):
        """Run extraction on the fixture."""
        support = PythonLanguageSupport()
        entities, relationships = support.extract_entities_and_relationships(
            python_file_content, "python_advanced.py"
        )
        return {"entities": entities, "relationships": relationships}
    
    def test_extraction_completes(self, extraction_result):
        """Extraction should complete without errors."""
        assert extraction_result is not None
        assert len(extraction_result["entities"]) > 0
    
    def test_extracts_dataclasses(self, extraction_result):
        """Should extract dataclass definitions."""
        entities = extraction_result["entities"]
        class_names = [e.name for e in entities if e.entity_type == "class"]
        
        # Point and Config are dataclasses
        assert "Point" in class_names, f"Dataclass Point not found in {class_names}"
        assert "Config" in class_names, f"Dataclass Config not found in {class_names}"
    
    def test_extracts_enums(self, extraction_result):
        """Should extract Enum classes."""
        entities = extraction_result["entities"]
        class_names = [e.name for e in entities if e.entity_type == "class"]
        
        assert "Color" in class_names, f"Enum Color not found"
        assert "Status" in class_names, f"Enum Status not found"
    
    def test_extracts_generic_classes(self, extraction_result):
        """Should extract classes with Generic[T]."""
        entities = extraction_result["entities"]
        class_names = [e.name for e in entities if e.entity_type == "class"]
        
        assert "Container" in class_names, f"Generic class Container not found"
        assert "NumberContainer" in class_names, f"Constrained generic NumberContainer not found"
    
    def test_extracts_properties(self, extraction_result):
        """Should extract properties with getters/setters."""
        entities = extraction_result["entities"]
        method_names = [e.name for e in entities if e.entity_type == "method"]
        
        # Temperature has properties celsius, fahrenheit, is_freezing
        temp_methods = [m for m in method_names if "Temperature." in m]
        assert len(temp_methods) >= 3, f"Expected Temperature methods, got {temp_methods}"
    
    def test_extracts_context_managers(self, extraction_result):
        """Should extract context manager classes."""
        entities = extraction_result["entities"]
        class_names = [e.name for e in entities if e.entity_type == "class"]
        
        assert "Transaction" in class_names, f"Context manager Transaction not found"
    
    def test_extracts_exception_hierarchy(self, extraction_result):
        """Should extract exception classes."""
        entities = extraction_result["entities"]
        class_names = [e.name for e in entities if e.entity_type == "class"]
        
        exceptions = [c for c in class_names if "Error" in c]
        assert "ApplicationError" in exceptions or any("ApplicationError" in c for c in class_names), \
            f"ApplicationError not found in {class_names}"
    
    def test_extracts_multiple_inheritance(self, extraction_result):
        """Should extract classes with multiple inheritance."""
        entities = extraction_result["entities"]
        class_names = [e.name for e in entities if e.entity_type == "class"]
        
        assert "Combined" in class_names, f"Combined (mixins) not found"
        assert "Diamond" in class_names, f"Diamond (diamond inheritance) not found"
    
    def test_extracts_complex_decorators(self, extraction_result):
        """Should extract decorated functions (decorator factories)."""
        entities = extraction_result["entities"]
        func_names = [e.name for e in entities if e.entity_type == "function"]
        
        # retry is a decorator factory
        assert "retry" in func_names, f"Decorator factory retry not found in {func_names}"
    
    def test_extracts_protocols(self, extraction_result):
        """Should extract Protocol classes."""
        entities = extraction_result["entities"]
        class_names = [e.name for e in entities if e.entity_type == "class"]
        
        assert "Drawable" in class_names or any("Drawable" in c for c in class_names), \
            f"Protocol Drawable not found"
    
    def test_extracts_complex_signatures(self, extraction_result):
        """Should extract functions with complex signatures (*args, **kwargs, defaults)."""
        entities = extraction_result["entities"]
        funcs = [e for e in entities if e.entity_type == "function"]
        
        complex_func = next((f for f in funcs if f.name == "complex_function"), None)
        assert complex_func is not None, "complex_function not found"
        # Check signature contains *args and **kwargs
        assert "args" in complex_func.signature or "kwargs" in complex_func.signature, \
            f"complex_function signature missing variadic params: {complex_func.signature}"


class TestTypeScriptAdvancedExtraction:
    """Test TypeScript extraction against advanced patterns."""
    
    @pytest.fixture(scope="class")
    def ts_file_content(self):
        """Load the advanced TypeScript fixture."""
        fixture_path = FIXTURES_DIR / "typescript_advanced.ts"
        if not fixture_path.exists():
            pytest.skip("TypeScript advanced fixture not found")
        return fixture_path.read_text()
    
    @pytest.fixture(scope="class")
    def extraction_result(self, ts_file_content):
        """Run extraction on the fixture."""
        support = TypeScriptLanguageSupport()
        entities, relationships = support.extract_entities_and_relationships(
            ts_file_content, "typescript_advanced.ts"
        )
        return {"entities": entities, "relationships": relationships}
    
    def test_extraction_completes(self, extraction_result):
        """Extraction should complete without errors."""
        assert extraction_result is not None
        assert len(extraction_result["entities"]) > 0
    
    def test_extracts_generic_classes(self, extraction_result):
        """Should extract classes with generics."""
        entities = extraction_result["entities"]
        class_names = [e.name for e in entities if e.entity_type == "class"]
        
        assert "Repository" in class_names, f"Generic Repository not found in {class_names}"
        assert "Service" in class_names, f"Generic Service not found"
    
    def test_extracts_type_aliases(self, extraction_result):
        """Should extract type aliases."""
        entities = extraction_result["entities"]
        type_aliases = [e for e in entities if e.entity_type == "type_alias"]
        
        # Should have some type aliases
        assert len(type_aliases) > 0, "No type aliases extracted"
        
        type_names = [e.name for e in type_aliases]
        print(f"Type aliases found: {type_names}")
    
    def test_extracts_discriminated_union_functions(self, extraction_result):
        """Should extract functions handling discriminated unions."""
        entities = extraction_result["entities"]
        func_names = [e.name for e in entities if e.entity_type == "function"]
        
        assert "calculateArea" in func_names, f"calculateArea not found in {func_names}"
    
    def test_extracts_decorated_classes(self, extraction_result):
        """Should extract classes with decorators."""
        entities = extraction_result["entities"]
        class_names = [e.name for e in entities if e.entity_type == "class"]
        
        assert "DatabaseService" in class_names, f"Decorated DatabaseService not found"
    
    def test_extracts_decorated_methods(self, extraction_result):
        """Should extract methods with decorators."""
        entities = extraction_result["entities"]
        method_names = [e.name for e in entities if e.entity_type == "method"]
        
        # DatabaseService has @Inject decorator on constructor parameter
        db_service_methods = [m for m in method_names if "DatabaseService." in m]
        assert len(db_service_methods) >= 1, \
            f"DatabaseService methods not found: {method_names}"
    
    def test_extracts_abstract_classes(self, extraction_result):
        """Should extract abstract classes."""
        entities = extraction_result["entities"]
        class_names = [e.name for e in entities if e.entity_type == "class"]
        
        assert "BaseController" in class_names, f"Abstract BaseController not found"
        assert "CRUDController" in class_names, f"Abstract CRUDController not found"
    
    def test_extracts_namespace_members(self, extraction_result):
        """Should extract classes within namespaces."""
        entities = extraction_result["entities"]
        
        # Validation namespace has StringSchema and ObjectSchema
        interfaces = [e.name for e in entities if e.entity_type == "interface"]
        classes = [e.name for e in entities if e.entity_type == "class"]
        
        # Schema interface should be extracted
        schema_entity = next((e for e in entities if "Schema" in e.name), None)
        assert schema_entity is not None, f"Schema interface/type not found in {interfaces + classes}"
    
    def test_extracts_function_overloads(self, extraction_result):
        """Should extract overloaded functions."""
        entities = extraction_result["entities"]
        func_names = [e.name for e in entities if e.entity_type == "function"]
        
        assert "parse" in func_names, f"Overloaded function parse not found in {func_names}"
    
    def test_extracts_react_hooks(self, extraction_result):
        """Should extract React hook functions."""
        entities = extraction_result["entities"]
        func_names = [e.name for e in entities if e.entity_type == "function"]
        
        assert "useApi" in func_names, f"Custom hook useApi not found in {func_names}"
    
    def test_extracts_forward_ref_components(self, extraction_result):
        """Should extract forwardRef components."""
        entities = extraction_result["entities"]
        func_names = [e.name for e in entities if e.entity_type == "function"]
        
        assert "FancyInput" in func_names, f"FancyInput forwardRef component not found"
    
    def test_extracts_generic_components(self, extraction_result):
        """Should extract generic React components."""
        entities = extraction_result["entities"]
        func_names = [e.name for e in entities if e.entity_type == "function"]
        
        assert "List" in func_names, f"Generic List component not found in {func_names}"
    
    def test_extracts_async_generators(self, extraction_result):
        """Should extract async generator functions."""
        entities = extraction_result["entities"]
        funcs = [e for e in entities if e.entity_type == "function"]
        
        async_gen = next((f for f in funcs if f.name == "paginatedAPI"), None)
        assert async_gen is not None, "paginatedAPI async generator not found"
        assert async_gen.metadata.get("async") == True, \
            f"paginatedAPI should be marked async"
    
    def test_extracts_mixin_factory_functions(self, extraction_result):
        """Should extract mixin factory functions (Timestamped, Activatable)."""
        entities = extraction_result["entities"]
        func_names = [e.name for e in entities if e.entity_type == "function"]
        
        # These are decorator-like functions that return classes
        assert "Timestamped" in func_names, f"Timestamped mixin not found in {func_names}"
        assert "Activatable" in func_names, f"Activatable mixin not found"


class TestExtractionEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_python_empty_string(self):
        """Should handle empty string."""
        support = PythonLanguageSupport()
        entities, relationships = support.extract_entities_and_relationships("", "empty.py")
        assert entities == []
        assert relationships == []
    
    def test_typescript_empty_string(self):
        """Should handle empty TypeScript."""
        support = TypeScriptLanguageSupport()
        entities, relationships = support.extract_entities_and_relationships("", "empty.ts")
        assert entities == []
        assert relationships == []
    
    def test_python_unicode_content(self):
        """Should handle unicode in code."""
        support = PythonLanguageSupport()
        content = '''
# Unicode comments: 日本語
class 日本語クラス:
    def メソッド(self):
        """日本語 docstring"""
        pass
'''
        entities, _ = support.extract_entities_and_relationships(content, "unicode.py")
        # Should extract without error
        assert len(entities) >= 1
    
    def test_typescript_unicode_content(self):
        """Should handle unicode in TypeScript."""
        support = TypeScriptLanguageSupport()
        content = '''
// Unicode: 日本語
interface 日本語インターフェース {
    プロパティ: string;
}
'''
        entities, _ = support.extract_entities_and_relationships(content, "unicode.ts")
        # Should extract without error
        assert len(entities) >= 1
    
    def test_python_nested_function_depth(self):
        """Should handle deeply nested functions."""
        support = PythonLanguageSupport()
        content = '''
def level1():
    def level2():
        def level3():
            def level4():
                def level5():
                    pass
'''
        entities, _ = support.extract_entities_and_relationships(content, "nested.py")
        # All levels should be extracted
        names = [e.name for e in entities]
        assert "level1" in names
        # Nested functions should be qualified
        nested = [n for n in names if "level2" in n or "level3" in n]
        assert len(nested) >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
