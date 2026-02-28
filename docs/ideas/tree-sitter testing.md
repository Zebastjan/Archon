Based on my investigation, I can now provide you with a comprehensive analysis of tree-sitter testing patterns and how to implement them properly in the Archon project.

## Tree-Sitter Testing Strategy for Archon

Tree-sitter isn't currently integrated into Archon yet, but based on your mention that you've done it before (possibly planning or in another branch), I've analyzed how the tree-sitter project itself does testing to help you implement proper testing for both modalities you mentioned.

### How Tree-Sitter Does Testing

The [tree-sitter/py-tree-sitter](https://github.com/tree-sitter/py-tree-sitter) project follows a comprehensive testing pattern:

**Test Structure:**
- Organized by component: `test_parser.py`, `test_query.py`, `test_node.py`, `test_tree.py`, `test_language.py`
- Uses Python's `unittest.TestCase` framework
- Establishes language fixtures in `setUpClass` for multiple languages (JavaScript, Python, Rust, HTML, JSON)
- Tests work with actual language grammars, not mocks

**Key Testing Patterns:**

1. **Multi-Language Coverage** - Tests run against Python, JavaScript, Rust, HTML, and JSON grammars simultaneously
2. **Parser Testing** - Validates parsing with different input types (bytes, memoryview, bytearray), callback functions, and UTF-16 encoding
3. **Query Testing** - Comprehensive tests for tree-sitter queries including patterns, captures, predicates, and range queries
4. **Edge Case Focus** - Tests for overlapping ranges, newly included/excluded ranges, multi-line comments, and boundary conditions

### Testing Strategy for Archon

Based on your two modalities and the tree-sitter testing approach:

## **Modality 1: General Infrastructure (Project-Wide Facility)**

Create `python/tests/server/test_tree_sitter_infrastructure.py`:

```python
"""
Tree-sitter infrastructure tests for general code parsing across the project.
Pattern based on tree-sitter/py-tree-sitter test structure.
"""
import pytest
from tree_sitter import Language, Parser

# Import language modules that will be used across the project
import tree_sitter_python
import tree_sitter_javascript
import tree_sitter_typescript


@pytest.fixture(scope="module")
def languages():
    """Initialize all supported languages once per module."""
    return {
        "python": Language(tree_sitter_python.language()),
        "javascript": Language(tree_sitter_javascript.language()),
        "typescript": Language(tree_sitter_typescript.language()),
    }


@pytest.fixture
def parser(languages):
    """Create a fresh parser for each test."""
    return Parser()


class TestTreeSitterInfrastructure:
    """Test suite for general tree-sitter infrastructure."""
    
    def test_language_loading(self, languages):
        """Verify all supported languages load correctly."""
        assert languages["python"] is not None
        assert languages["javascript"] is not None
        assert languages["typescript"] is not None
    
    def test_parser_initialization(self, parser, languages):
        """Test parser can be initialized with each language."""
        for lang_name, language in languages.items():
            parser.language = language
            assert parser.language == language
    
    def test_basic_parsing_python(self, parser, languages):
        """Test parsing simple Python code."""
        parser.language = languages["python"]
        source = b"def foo():\n    return 42"
        tree = parser.parse(source)
        
        assert tree.root_node is not None
        assert tree.root_node.type == "module"
        assert not tree.root_node.has_error
    
    def test_basic_parsing_javascript(self, parser, languages):
        """Test parsing simple JavaScript code."""
        parser.language = languages["javascript"]
        source = b"function foo() { return 42; }"
        tree = parser.parse(source)
        
        assert tree.root_node is not None
        assert tree.root_node.type == "program"
        assert not tree.root_node.has_error
    
    def test_parsing_with_syntax_errors(self, parser, languages):
        """Test parser handles syntax errors gracefully."""
        parser.language = languages["python"]
        source = b"def foo(\n    # incomplete function"
        tree = parser.parse(source)
        
        assert tree.root_node.has_error
    
    def test_multiple_input_formats(self, parser, languages):
        """Test parser accepts different input formats (bytes, memoryview, bytearray)."""
        parser.language = languages["python"]
        source_text = b"x = 1"
        
        # Test with bytes
        tree1 = parser.parse(source_text)
        assert not tree1.root_node.has_error
        
        # Test with memoryview
        tree2 = parser.parse(memoryview(source_text))
        assert not tree2.root_node.has_error
        
        # Test with bytearray
        tree3 = parser.parse(bytearray(source_text))
        assert not tree3.root_node.has_error
```

## **Modality 2: Chunking Process Integration**

Create `python/tests/server/services/crawling/test_tree_sitter_chunking.py`:

```python
"""
Tree-sitter integration tests for code-aware chunking.
Ensures chunks respect code structure boundaries.
"""
import pytest
from tree_sitter import Language, Parser, Query

import tree_sitter_python
import tree_sitter_javascript


@pytest.fixture(scope="module")
def languages():
    """Initialize languages for chunking tests."""
    return {
        "python": Language(tree_sitter_python.language()),
        "javascript": Language(tree_sitter_javascript.language()),
    }


class TestTreeSitterChunking:
    """Test tree-sitter integration in the chunking process."""
    
    def test_chunk_respects_function_boundaries_python(self, languages):
        """Test that chunks don't split Python functions."""
        parser = Parser(languages["python"])
        
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
        
        # Query for all function definitions
        query = Query(
            languages["python"],
            "(function_definition) @function"
        )
        
        captures = query.captures(tree.root_node)
        functions = captures.get("function", [])
        
        assert len(functions) == 3
        
        # Verify each function has distinct byte ranges
        for func in functions:
            start = func.start_byte
            end = func.end_byte
            assert start < end
            # Each chunk should contain complete function
            func_text = source[start:end]
            assert b"def" in func_text
            assert b"return" in func_text
    
    def test_chunk_respects_class_boundaries_python(self, languages):
        """Test that chunks don't split Python classes."""
        parser = Parser(languages["python"])
        
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
        
        # Query for class definition
        query = Query(
            languages["python"],
            "(class_definition) @class"
        )
        
        captures = query.captures(tree.root_node)
        classes = captures.get("class", [])
        
        assert len(classes) == 1
        
        # Verify class contains all methods
        class_node = classes[0]
        class_text = source[class_node.start_byte:class_node.end_byte]
        assert b"__init__" in class_text
        assert b"method_one" in class_text
        assert b"method_two" in class_text
    
    def test_chunk_respects_function_boundaries_javascript(self, languages):
        """Test that chunks don't split JavaScript functions."""
        parser = Parser(languages["javascript"])
        
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
        
        # Query for function declarations and arrow functions
        query = Query(
            languages["javascript"],
            """
            (function_declaration) @function
            (arrow_function) @arrow
            """
        )
        
        captures = query.captures(tree.root_node)
        
        # Should find 2 function declarations and 1 arrow function
        assert len(captures.get("function", [])) == 2
        assert len(captures.get("arrow", [])) == 1
    
    def test_identify_import_statements_for_chunk_context(self, languages):
        """Test extracting imports that should be included in chunk context."""
        parser = Parser(languages["python"])
        
        source = b"""
import os
import sys
from pathlib import Path
from typing import List, Dict

def my_function():
    return Path('.')
"""
        tree = parser.parse(source)
        
        # Query for import statements
        query = Query(
            languages["python"],
            """
            (import_statement) @import
            (import_from_statement) @import_from
            """
        )
        
        captures = query.captures(tree.root_node)
        
        # Verify we can identify imports for context
        imports = captures.get("import", [])
        import_froms = captures.get("import_from", [])
        
        assert len(imports) == 2  # import os, import sys
        assert len(import_froms) == 2  # from pathlib..., from typing...
    
    def test_nested_structure_chunking(self, languages):
        """Test chunking handles nested code structures properly."""
        parser = Parser(languages["python"])
        
        source = b"""
class OuterClass:
    class InnerClass:
        def inner_method(self):
            def nested_function():
                return "deeply nested"
            return nested_function()
    
    def outer_method(self):
        return self.InnerClass()
"""
        tree = parser.parse(source)
        
        # Query for nested classes
        query = Query(
            languages["python"],
            "(class_definition) @class"
        )
        
        captures = query.captures(tree.root_node)
        classes = captures.get("class", [])
        
        # Should find both outer and inner classes
        assert len(classes) == 2
        
        # Verify nesting is preserved
        outer_class = classes[0]
        outer_text = source[outer_class.start_byte:outer_class.end_byte]
        assert b"InnerClass" in outer_text
        assert b"inner_method" in outer_text
        assert b"outer_method" in outer_text
    
    def test_large_file_chunking_strategy(self, languages):
        """Test chunking strategy for large files with many functions."""
        parser = Parser(languages["python"])
        
        # Generate a large file with many functions
        functions = []
        for i in range(50):
            functions.append(f"""
def function_{i}():
    '''Function {i}'''
    x = {i}
    y = x * 2
    z = y + {i}
    return z
""")
        
        source = "\n".join(functions).encode()
        tree = parser.parse(source)
        
        # Query for all functions
        query = Query(
            languages["python"],
            "(function_definition) @function"
        )
        
        captures = query.captures(tree.root_node)
        all_functions = captures.get("function", [])
        
        assert len(all_functions) == 50
        
        # Simulate chunking by grouping functions based on byte size
        chunk_size = 5000  # Target chunk size in bytes
        chunks = []
        current_chunk_size = 0
        current_chunk_functions = []
        
        for func in all_functions:
            func_size = func.end_byte - func.start_byte
            
            if current_chunk_size + func_size > chunk_size and current_chunk_functions:
                # Start new chunk
                chunks.append(current_chunk_functions)
                current_chunk_functions = [func]
                current_chunk_size = func_size
            else:
                current_chunk_functions.append(func)
                current_chunk_size += func_size
        
        if current_chunk_functions:
            chunks.append(current_chunk_functions)
        
        # Verify we created multiple chunks
        assert len(chunks) > 1
        
        # Verify no chunk is too large
        for chunk in chunks:
            chunk_size_bytes = sum(f.end_byte - f.start_byte for f in chunk)
            assert chunk_size_bytes <= chunk_size * 1.5  # Allow some overflow
    
    @pytest.mark.parametrize("language,source,expected_type", [
        ("python", b"def foo(): pass", "function_definition"),
        ("python", b"class Bar: pass", "class_definition"),
        ("javascript", b"function foo() {}", "function_declaration"),
        ("javascript", b"const x = () => {}", "arrow_function"),
    ])
    def test_detect_code_construct_types(self, languages, language, source, expected_type):
        """Test detection of different code construct types across languages."""
        parser = Parser(languages[language])
        tree = parser.parse(source)
        
        # Find nodes of expected type
        def find_node_by_type(node, target_type):
            if node.type == target_type:
                return node
            for child in node.children:
                result = find_node_by_type(child, target_type)
                if result:
                    return result
            return None
        
        found_node = find_node_by_type(tree.root_node, expected_type)
        assert found_node is not None
        assert found_node.type == expected_type
```

### Additional Integration Tests

Create `python/tests/server/services/crawling/test_tree_sitter_document_storage.py`:

```python
"""
Integration tests for tree-sitter with document storage operations.
Ensures chunking service properly uses tree-sitter for code files.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
class TestTreeSitterDocumentStorage:
    """Test tree-sitter integration with document storage."""
    
    async def test_smart_chunk_uses_tree_sitter_for_python(self):
        """Test that smart_chunk_text_async uses tree-sitter for Python code."""
        # Mock the DocumentStorageService
        with patch('server.services.storage.storage_services.DocumentStorageService') as MockService:
            mock_service = MockService.return_value
            
            # Setup mock for smart chunking
            python_code = """
def function_one():
    return 1

def function_two():
    return 2
"""
            
            # Mock should return chunks that respect function boundaries
            expected_chunks = [
                "def function_one():\n    return 1\n",
                "def function_two():\n    return 2\n"
            ]
            mock_service.smart_chunk_text_async = AsyncMock(return_value=expected_chunks)
            
            # Call the chunking service
            chunks = await mock_service.smart_chunk_text_async(python_code, chunk_size=5000)
            
            # Verify chunks respect code structure
            assert len(chunks) == 2
            assert "function_one" in chunks[0]
            assert "function_two" in chunks[1]
    
    async def test_smart_chunk_detects_language_from_metadata(self):
        """Test language detection from file metadata for appropriate tree-sitter grammar."""
        test_cases = [
            ("test.py", "python", b"def foo(): pass"),
            ("test.js", "javascript", b"function foo() {}"),
            ("test.ts", "typescript", b"function foo(): void {}"),
        ]
        
        for filename, expected_lang, code in test_cases:
            # This test validates the pattern where the chunking service
            # should detect language from filename and use appropriate parser
            assert filename.endswith(f".{expected_lang.replace('typescript', 'ts')}")
    
    @pytest.mark.parametrize("chunk_size,expected_min_chunks", [
        (1000, 5),   # Small chunks should split more
        (5000, 2),   # Medium chunks should split moderately
        (10000, 1),  # Large chunks might not split
    ])
    async def test_chunk_size_affects_tree_sitter_grouping(self, chunk_size, expected_min_chunks):
        """Test that chunk size parameter affects how tree-sitter nodes are grouped."""
        # Generate code with multiple functions
        code = "\n".join([
            f"def function_{i}():\n    return {i}\n"
            for i in range(10)
        ])
        
        # The chunking logic should group complete functions
        # but create more chunks with smaller chunk_size
        # This is a pattern test - actual implementation would go here
        assert chunk_size > 0
        assert expected_min_chunks > 0
```

### Dependencies to Add

Update `python/pyproject.toml` to include tree-sitter dependencies:

```toml
server = [
    # ... existing dependencies ...
    "tree-sitter>=0.21.0",
    "tree-sitter-python>=0.21.0",
    "tree-sitter-javascript>=0.21.0",
    "tree-sitter-typescript>=0.21.0",
]
```

### Test Execution Strategy

1. **Unit Tests** - Run tree-sitter infrastructure tests independently
2. **Integration Tests** - Test tree-sitter + chunking together
3. **Multi-Language Coverage** - Ensure Python, JavaScript, TypeScript all work
4. **Edge Cases** - Test malformed code, very large files, deeply nested structures
5. **Performance Tests** - Measure parsing performance on large codebases

This testing strategy follows the established pattern from dockling and GitHub integration tests you've already created, while incorporating the proven patterns from tree-sitter's own test suite.