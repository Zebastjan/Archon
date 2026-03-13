"""Python language support using Tree-sitter.

Extracts functions, classes, methods, imports, and their relationships
from Python source code using the tree-sitter-python parser.
"""

from pathlib import Path

from tree_sitter import Language, Node, Parser, Tree

import logging

try:
    import tree_sitter_python as ts_python
    HAS_TS_PYTHON = True
except ImportError:
    HAS_TS_PYTHON = False

from .language_support import (
    CodeEntity,
    CodeRelationship,
    LanguageSupportBase,
    ParseError,
)

logger = logging.getLogger(__name__)


class PythonLanguageSupport(LanguageSupportBase):
    """Python language support using Tree-sitter.
    
    Extracts entities and relationships from Python source code.
    Handles:
    - Function definitions (def, async def)
    - Class definitions
    - Methods and properties
    - Import statements (import, from ... import)
    - Decorators
    - Type hints
    - Docstrings
    - Nested entities (functions within classes, etc.)
    
    Example:
        >>> support = PythonLanguageSupport()
        >>> content = '''
        ... class Calculator:
        ...     \"\"\"A simple calculator.\"\"\"
        ...     
        ...     def add(self, a: int, b: int) -> int:
        ...         \"\"\"Add two numbers.\"\"\"
        ...         return a + b
        ... '''
        >>> entities, relationships = support.extract_entities_and_relationships(
        ...     content, "calculator.py"
        ... )
        >>> len(entities)
        2  # class Calculator and method add
    """
    
    language_id = "python"
    file_extensions = [".py", ".pyw", ".pyi"]
    
    def __init__(self):
        """Initialize Python language support.
        
        Raises:
            ImportError: If tree-sitter-python is not installed
        """
        if not HAS_TS_PYTHON:
            raise ImportError(
                "tree-sitter-python is required. "
                "Install with: uv pip install tree-sitter-python"
            )
        
        self._language = Language(ts_python.language())
        self._parser = Parser(self._language)  # Language passed to constructor
        self._logger = logger
        self._logger.debug("Python language support initialized")
    
    def extract_entities_and_relationships(
        self,
        content: str,
        file_path: str,
    ) -> tuple[list[CodeEntity], list[CodeRelationship]]:
        """Extract entities and relationships from Python source code.
        
        Args:
            content: Python source code as a string
            file_path: Path to the file (for context and logging)
            
        Returns:
            Tuple of (entities, relationships) found in the file
            
        Raises:
            ParseError: If the source code cannot be parsed
        """
        try:
            tree = self._parser.parse(bytes(content, "utf8"))
        except Exception as e:
            raise ParseError(
                f"Failed to parse Python source: {e}",
                file_path=file_path,
            ) from e
        
        entities: list[CodeEntity] = []
        relationships: list[CodeRelationship] = []
        
        # Walk the AST and extract entities/relationships
        self._walk_tree(
            tree.root_node,
            content,
            file_path,
            entities,
            relationships,
            parent_entity=None,
            scope_stack=[],
        )
        
        self._logger.debug(
            f"Extraction complete: {file_path} - "
            f"{len(entities)} entities, {len(relationships)} relationships"
        )
        
        return entities, relationships
    
    def _walk_tree(
        self,
        node: Node,
        content: str,
        file_path: str,
        entities: list[CodeEntity],
        relationships: list[CodeRelationship],
        parent_entity: CodeEntity | None,
        scope_stack: list[str],
    ) -> None:
        """Recursively walk the Python AST.
        
        Args:
            node: Current AST node
            content: Full source content
            file_path: Path to the file
            entities: List to collect entities
            relationships: List to collect relationships
            parent_entity: Parent entity (e.g., class containing a method)
            scope_stack: Stack of scope names for building qualified names
        """
        # Handle different node types
        if node.type == "function_definition":
            # Check if async (tree-sitter 0.25+ has 'async' as child node)
            is_async = any(child.type == "async" for child in node.children)
            self._handle_function(
                node, content, file_path, entities, relationships,
                parent_entity, scope_stack, is_async=is_async
            )
            return  # Don't recurse into handled nodes
            
        elif node.type == "class_definition":
            self._handle_class(
                node, content, file_path, entities, relationships,
                parent_entity, scope_stack
            )
            return
            
        elif node.type in ("call", "attribute"):
            self._handle_call(
                node, content, relationships, parent_entity
            )
            
        elif node.type == "import_statement":
            self._handle_import(
                node, content, relationships, parent_entity
            )
            
        elif node.type == "import_from_statement":
            self._handle_import_from(
                node, content, relationships, parent_entity
            )
            
        elif node.type == "decorated_definition":
            self._handle_decorated(
                node, content, file_path, entities, relationships,
                parent_entity, scope_stack
            )
            return
        
        # Continue walking children
        for child in node.children:
            self._walk_tree(
                child, content, file_path, entities, relationships,
                parent_entity, scope_stack
            )
    
    def _handle_function(
        self,
        node: Node,
        content: str,
        file_path: str,
        entities: list[CodeEntity],
        relationships: list[CodeRelationship],
        parent_entity: CodeEntity | None,
        scope_stack: list[str],
        is_async: bool = False,
    ) -> CodeEntity:
        """Handle function definition nodes."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return parent_entity  # type: ignore[return-value]
        
        func_name = content[name_node.start_byte:name_node.end_byte]
        qualified_name = ".".join(scope_stack + [func_name]) if scope_stack else func_name
        
        # Build signature
        params_node = node.child_by_field_name("parameters")
        return_type_node = node.child_by_field_name("return_type")
        
        signature_parts = []
        if is_async:
            signature_parts.append("async")
        signature_parts.append("def")
        signature_parts.append(func_name)
        
        if params_node:
            params_text = content[params_node.start_byte:params_node.end_byte]
            signature_parts.append(params_text)
        
        if return_type_node:
            return_type_text = content[return_type_node.start_byte:return_type_node.end_byte]
            signature_parts.append(f"-> {return_type_text}")
        
        signature = " ".join(signature_parts)
        
        # Get docstring
        body_node = node.child_by_field_name("body")
        docstring = self._extract_docstring(content, body_node)
        
        # Determine entity type
        entity_type = "method" if parent_entity and parent_entity.entity_type == "class" else "function"
        
        # Create entity
        entity = CodeEntity(
            entity_type=entity_type,
            name=qualified_name,
            signature=signature,
            docstring=docstring,
            source_code=content[node.start_byte:node.end_byte],
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            metadata={
                "async": is_async,
                "local_name": func_name,
            },
        )
        entities.append(entity)
        
        # Add DEFINES relationship if inside a class
        if parent_entity and parent_entity.entity_type == "class":
            relationships.append(CodeRelationship(
                source_name=parent_entity.name,
                target_name=qualified_name,
                relationship_type="DEFINES",
                metadata={"defined_type": entity_type},
            ))
        
        # Walk the body for nested entities and calls
        if body_node:
            new_scope = scope_stack + [func_name]
            for child in body_node.children:
                self._walk_tree(
                    child, content, file_path, entities, relationships,
                    entity, new_scope
                )
        
        return entity
    
    def _handle_class(
        self,
        node: Node,
        content: str,
        file_path: str,
        entities: list[CodeEntity],
        relationships: list[CodeRelationship],
        parent_entity: CodeEntity | None,
        scope_stack: list[str],
    ) -> CodeEntity:
        """Handle class definition nodes."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return parent_entity  # type: ignore[return-value]
        
        class_name = content[name_node.start_byte:name_node.end_byte]
        qualified_name = ".".join(scope_stack + [class_name]) if scope_stack else class_name
        
        # Get inheritance
        superclasses_node = node.child_by_field_name("superclasses")
        bases = []
        if superclasses_node:
            bases = self._extract_bases(content, superclasses_node)
        
        # Build signature
        signature_parts = ["class", class_name]
        if bases:
            signature_parts.append(f"({', '.join(bases)})")
        signature = " ".join(signature_parts)
        
        # Get docstring
        body_node = node.child_by_field_name("body")
        docstring = self._extract_docstring(content, body_node)
        
        # Create entity
        entity = CodeEntity(
            entity_type="class",
            name=qualified_name,
            signature=signature,
            docstring=docstring,
            source_code=content[node.start_byte:node.end_byte],
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            metadata={
                "bases": bases,
                "local_name": class_name,
            },
        )
        entities.append(entity)
        
        # Add INHERITS relationships
        for base in bases:
            relationships.append(CodeRelationship(
                source_name=qualified_name,
                target_name=base,
                relationship_type="INHERITS",
                metadata={},
            ))
        
        # Walk the body for nested entities
        if body_node:
            new_scope = scope_stack + [class_name]
            for child in body_node.children:
                self._walk_tree(
                    child, content, file_path, entities, relationships,
                    entity, new_scope
                )
        
        return entity
    
    def _handle_call(
        self,
        node: Node,
        content: str,
        relationships: list[CodeRelationship],
        parent_entity: CodeEntity | None,
    ) -> None:
        """Handle function/method calls."""
        if not parent_entity:
            return
        
        target_name = self._resolve_call_target(node, content)
        if target_name:
            relationships.append(CodeRelationship(
                source_name=parent_entity.name,
                target_name=target_name,
                relationship_type="CALLS",
                metadata={"line": node.start_point[0] + 1},
            ))
    
    def _handle_import(
        self,
        node: Node,
        content: str,
        relationships: list[CodeRelationship],
        parent_entity: CodeEntity | None,
    ) -> None:
        """Handle 'import x' statements."""
        if not parent_entity:
            return
        
        # Find dotted_name nodes (module paths)
        for child in node.children:
            if child.type == "dotted_name":
                module_name = content[child.start_byte:child.end_byte]
                relationships.append(CodeRelationship(
                    source_name=parent_entity.name,
                    target_name=module_name,
                    relationship_type="IMPORTS",
                    metadata={"import_type": "module"},
                ))
            elif child.type == "identifier":
                # Simple import
                module_name = content[child.start_byte:child.end_byte]
                relationships.append(CodeRelationship(
                    source_name=parent_entity.name,
                    target_name=module_name,
                    relationship_type="IMPORTS",
                    metadata={"import_type": "module"},
                ))
    
    def _handle_import_from(
        self,
        node: Node,
        content: str,
        relationships: list[CodeRelationship],
        parent_entity: CodeEntity | None,
    ) -> None:
        """Handle 'from x import y' statements."""
        if not parent_entity:
            return
        
        module_node = node.child_by_field_name("module_name")
        if module_node:
            module_name = content[module_node.start_byte:module_node.end_byte]
            
            # Find imported names
            for child in node.children:
                if child.type == "import_from_statement":
                    continue  # Skip the module_name which is also child_by_field_name
                if child.type in ("identifier", "dotted_name"):
                    imported_name = content[child.start_byte:child.end_byte]
                    relationships.append(CodeRelationship(
                        source_name=parent_entity.name,
                        target_name=f"{module_name}.{imported_name}",
                        relationship_type="IMPORTS",
                        metadata={
                            "import_type": "from",
                            "module": module_name,
                            "name": imported_name,
                        },
                    ))
    
    def _handle_decorated(
        self,
        node: Node,
        content: str,
        file_path: str,
        entities: list[CodeEntity],
        relationships: list[CodeRelationship],
        parent_entity: CodeEntity | None,
        scope_stack: list[str],
    ) -> None:
        """Handle decorated definitions (e.g., @app.route)."""
        # Find the decorated function/class
        definition_node = None
        decorator_nodes = []
        
        for child in node.children:
            if child.type == "decorator":
                decorator_nodes.append(child)
            elif child.type in ("function_definition", "class_definition", "async_function_definition"):
                definition_node = child
        
        if not definition_node:
            return
        
        # Process the definition (will create the entity)
        if definition_node.type == "function_definition":
            is_async = any(child.type == "async" for child in definition_node.children)
            entity = self._handle_function(
                definition_node, content, file_path, entities, relationships,
                parent_entity, scope_stack, is_async=is_async
            )
        elif definition_node.type == "class_definition":
            entity = self._handle_class(
                definition_node, content, file_path, entities, relationships,
                parent_entity, scope_stack
            )
        else:
            return
        
        # Add DECORATES relationships
        for decorator_node in decorator_nodes:
            decorator_name = self._extract_decorator_name(decorator_node, content)
            if decorator_name:
                relationships.append(CodeRelationship(
                    source_name=entity.name,
                    target_name=decorator_name,
                    relationship_type="DECORATES",
                    metadata={},
                ))
    
    def _extract_docstring(self, content: str, body_node: Node | None) -> str | None:
        """Extract docstring from function/class body."""
        if not body_node:
            return None
        
        # Look for expression_statement containing a string
        for child in body_node.children:
            if child.type == "expression_statement":
                expr_child = child.children[0] if child.children else None
                if expr_child and expr_child.type in ("string", "concatenated_string"):
                    docstring = content[expr_child.start_byte:expr_child.end_byte]
                    # Strip quotes
                    docstring = docstring.strip('"\'')
                    return docstring
        return None
    
    def _extract_bases(self, content: str, superclasses_node: Node) -> list[str]:
        """Extract base class names from superclasses node."""
        bases = []
        for child in superclasses_node.children:
            if child.type in ("identifier", "attribute", "dotted_name"):
                base_name = content[child.start_byte:child.end_byte]
                bases.append(base_name)
        return bases
    
    def _resolve_call_target(self, node: Node, content: str) -> str | None:
        """Resolve the target of a function/method call."""
        if node.type == "identifier":
            return content[node.start_byte:node.end_byte]
        elif node.type == "attribute":
            obj = node.child_by_field_name("object")
            attr = node.child_by_field_name("attribute")
            if obj and attr:
                obj_name = self._resolve_call_target(obj, content)
                attr_name = content[attr.start_byte:attr.end_byte]
                if obj_name:
                    return f"{obj_name}.{attr_name}"
                return attr_name
        elif node.type == "call":
            # Get the function being called
            func_node = node.child_by_field_name("function")
            if func_node:
                return self._resolve_call_target(func_node, content)
        return None
    
    def _extract_decorator_name(self, node: Node, content: str) -> str | None:
        """Extract decorator name from decorator node."""
        for child in node.children:
            if child.type in ("identifier", "attribute", "call"):
                return content[child.start_byte:child.end_byte]
        return None
