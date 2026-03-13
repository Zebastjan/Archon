"""TypeScript and JavaScript language support using Tree-sitter.

Extracts functions, classes, interfaces, methods, imports, and their relationships
from TypeScript and JavaScript source code.
"""

from pathlib import Path

from tree_sitter import Language, Node, Parser

try:
    import tree_sitter_typescript as ts_typescript
    from tree_sitter_typescript import language_tsx, language_typescript
    HAS_TS = True
except ImportError:
    HAS_TS = False

from ...config.logfire_config import get_logger
from .language_support import (
    CodeEntity,
    CodeRelationship,
    LanguageSupportBase,
    ParseError,
)

logger = get_logger(__name__)


class TypeScriptLanguageSupport(LanguageSupportBase):
    """TypeScript and JavaScript language support using Tree-sitter.
    
    Handles both TypeScript (.ts, .tsx) and JavaScript (.js, .jsx, .mjs, .cjs).
    Extracts:
    - Function declarations and expressions
    - Arrow functions
    - Class definitions
    - Interface and type definitions
    - Methods and properties
    - Import/export statements
    - Decorators (@Component, etc.)
    - Generic types
    - Async/await patterns
    
    Example:
        >>> support = TypeScriptLanguageSupport()
        >>> content = '''
        ... interface User {
        ...     name: string;
        ... }
        ... 
        ... class UserService {
        ...     async getUser(id: number): Promise<User> {
        ...         return fetch(`/api/users/${id}`);
        ...     }
        ... }
        ... '''
        >>> entities, relationships = support.extract_entities_and_relationships(
        ...     content, "user.ts"
        ... )
    """
    
    language_id = "typescript"
    file_extensions = [".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"]
    
    def __init__(self):
        """Initialize TypeScript/JavaScript language support.
        
        Raises:
            ImportError: If tree-sitter-typescript or tree-sitter-javascript
                        is not installed
        """
        if not HAS_TS:
            raise ImportError(
                "tree-sitter-typescript and tree-sitter-javascript are required. "
                "Install with: uv pip install tree-sitter-typescript tree-sitter-javascript"
            )
        
        self._ts_language = Language(language_typescript())
        self._js_language = Language(language_tsx())
        # Parser created fresh for each parse since we need different languages
        self._logger = logger
        self._logger.debug("TypeScript language support initialized")
    
    def _get_language(self, file_path: str) -> Language:
        """Select appropriate grammar based on file extension."""
        ext = Path(file_path).suffix.lower()
        if ext in [".ts", ".tsx"]:
            return self._ts_language
        return self._js_language
    
    def extract_entities_and_relationships(
        self,
        content: str,
        file_path: str,
    ) -> tuple[list[CodeEntity], list[CodeRelationship]]:
        """Extract entities and relationships from TypeScript/JavaScript source.
        
        Args:
            content: Source code as a string
            file_path: Path to the file (for determining language variant)
            
        Returns:
            Tuple of (entities, relationships) found in the file
            
        Raises:
            ParseError: If the source code cannot be parsed
        """
        language = self._get_language(file_path)
        # Create new parser with the correct language (tree-sitter 0.25+ API)
        self._parser = Parser(language)
        
        try:
            tree = self._parser.parse(bytes(content, "utf8"))
        except Exception as e:
            raise ParseError(
                f"Failed to parse TypeScript/JavaScript source: {e}",
                file_path=file_path,
            ) from e
        
        entities: list[CodeEntity] = []
        relationships: list[CodeRelationship] = []
        
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
        """Recursively walk the TypeScript/JavaScript AST."""
        
        # Function declarations
        if node.type == "function_declaration":
            self._handle_function_declaration(
                node, content, file_path, entities, relationships,
                parent_entity, scope_stack, is_async=False, is_arrow=False
            )
            return
            
        # Async function declarations
        elif node.type == "async_function_declaration":
            self._handle_function_declaration(
                node, content, file_path, entities, relationships,
                parent_entity, scope_stack, is_async=True, is_arrow=False
            )
            return
            
        # Class declarations
        elif node.type == "class_declaration":
            self._handle_class(
                node, content, file_path, entities, relationships,
                parent_entity, scope_stack
            )
            return
            
        # Interface declarations (TypeScript)
        elif node.type == "interface_declaration":
            self._handle_interface(
                node, content, file_path, entities, relationships,
                parent_entity, scope_stack
            )
            return
            
        # Type alias declarations (TypeScript)
        elif node.type == "type_alias_declaration":
            self._handle_type_alias(
                node, content, file_path, entities, relationships,
                parent_entity, scope_stack
            )
            return
            
        # Method definitions (in classes)
        elif node.type == "method_definition":
            self._handle_method(
                node, content, file_path, entities, relationships,
                parent_entity, scope_stack
            )
            return
            
        # Arrow functions (as variable declarations)
        elif node.type == "variable_declarator":
            self._handle_arrow_function(
                node, content, file_path, entities, relationships,
                parent_entity, scope_stack
            )
            
        # Import statements
        elif node.type == "import_statement":
            self._handle_import(
                node, content, relationships, parent_entity
            )
            
        # Export statements
        elif node.type in ("export_statement", "export_clause"):
            self._handle_export(
                node, content, relationships, parent_entity
            )
            
        # Function calls
        elif node.type == "call_expression":
            self._handle_call(
                node, content, relationships, parent_entity
            )
            
        # Decorators
        elif node.type == "decorator":
            self._handle_decorator(
                node, content, relationships, parent_entity
            )
            
        # Decorated definitions
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
    
    def _handle_function_declaration(
        self,
        node: Node,
        content: str,
        file_path: str,
        entities: list[CodeEntity],
        relationships: list[CodeRelationship],
        parent_entity: CodeEntity | None,
        scope_stack: list[str],
        is_async: bool,
        is_arrow: bool,
    ) -> CodeEntity:
        """Handle function declarations."""
        name_node = node.child_by_field_name("name")
        func_name = "anonymous"
        
        if name_node:
            func_name = content[name_node.start_byte:name_node.end_byte]
        elif is_arrow and parent_entity:
            # Arrow function as variable - try to get variable name
            func_name = parent_entity.name if parent_entity.name != "anonymous" else "anonymous"
        
        qualified_name = ".".join(scope_stack + [func_name]) if scope_stack else func_name
        
        # Build signature
        params_node = node.child_by_field_name("parameters")
        return_type_node = node.child_by_field_name("return_type")
        type_parameters = node.child_by_field_name("type_parameters")
        
        signature_parts = []
        if is_async:
            signature_parts.append("async")
        signature_parts.append("function")
        signature_parts.append(func_name)
        
        if type_parameters:
            type_params_text = content[type_parameters.start_byte:type_parameters.end_byte]
            signature_parts.append(type_params_text)
        
        if params_node:
            params_text = content[params_node.start_byte:params_node.end_byte]
            signature_parts.append(params_text)
        
        if return_type_node:
            return_type_text = content[return_type_node.start_byte:return_type_node.end_byte]
            signature_parts.append(return_type_text)
        
        signature = " ".join(signature_parts)
        
        # Get JSDoc/TSDoc if present (as leading comment)
        docstring = self._extract_jsdoc(node, content)
        
        entity_type = "function"
        if parent_entity and parent_entity.entity_type == "class":
            entity_type = "method"
        
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
                "arrow": is_arrow,
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
        
        # Walk body for nested entities and calls
        body_node = node.child_by_field_name("body")
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
        """Handle class declarations."""
        name_node = node.child_by_field_name("name")
        class_name = "anonymous"
        if name_node:
            class_name = content[name_node.start_byte:name_node.end_byte]
        
        qualified_name = ".".join(scope_stack + [class_name]) if scope_stack else class_name
        
        # Get heritage clause (extends/implements)
        heritage_node = node.child_by_field_name("heritage")
        bases = []
        implements = []
        if heritage_node:
            bases, implements = self._extract_heritage(content, heritage_node)
        
        # Build signature
        type_parameters = node.child_by_field_name("type_parameters")
        signature_parts = ["class", class_name]
        
        if type_parameters:
            type_params_text = content[type_parameters.start_byte:type_parameters.end_byte]
            signature_parts.append(type_params_text)
        
        if bases:
            signature_parts.append(f"extends {', '.join(bases)}")
        if implements:
            signature_parts.append(f"implements {', '.join(implements)}")
        
        signature = " ".join(signature_parts)
        docstring = self._extract_jsdoc(node, content)
        
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
                "implements": implements,
                "local_name": class_name,
            },
        )
        entities.append(entity)
        
        # Add inheritance relationships
        for base in bases:
            relationships.append(CodeRelationship(
                source_name=qualified_name,
                target_name=base,
                relationship_type="INHERITS",
                metadata={"inheritance_type": "extends"},
            ))
        
        for impl in implements:
            relationships.append(CodeRelationship(
                source_name=qualified_name,
                target_name=impl,
                relationship_type="IMPLEMENTS",
                metadata={},
            ))
        
        # Walk class body
        body_node = node.child_by_field_name("body")
        if body_node:
            new_scope = scope_stack + [class_name]
            for child in body_node.children:
                self._walk_tree(
                    child, content, file_path, entities, relationships,
                    entity, new_scope
                )
        
        return entity
    
    def _handle_interface(
        self,
        node: Node,
        content: str,
        file_path: str,
        entities: list[CodeEntity],
        relationships: list[CodeRelationship],
        parent_entity: CodeEntity | None,
        scope_stack: list[str],
    ) -> CodeEntity:
        """Handle interface declarations (TypeScript)."""
        name_node = node.child_by_field_name("name")
        iface_name = "anonymous"
        if name_node:
            iface_name = content[name_node.start_byte:name_node.end_byte]
        
        qualified_name = ".".join(scope_stack + [iface_name]) if scope_stack else iface_name
        
        # Get extends clause
        extends_node = node.child_by_field_name("extends")
        extends = []
        if extends_node:
            extends = self._extract_interface_extends(content, extends_node)
        
        type_parameters = node.child_by_field_name("type_parameters")
        signature_parts = ["interface", iface_name]
        
        if type_parameters:
            type_params_text = content[type_parameters.start_byte:type_parameters.end_byte]
            signature_parts.append(type_params_text)
        
        if extends:
            signature_parts.append(f"extends {', '.join(extends)}")
        
        signature = " ".join(signature_parts)
        docstring = self._extract_jsdoc(node, content)
        
        entity = CodeEntity(
            entity_type="interface",
            name=qualified_name,
            signature=signature,
            docstring=docstring,
            source_code=content[node.start_byte:node.end_byte],
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            metadata={
                "extends": extends,
                "local_name": iface_name,
            },
        )
        entities.append(entity)
        
        # Add EXTENDS relationships
        for ext in extends:
            relationships.append(CodeRelationship(
                source_name=qualified_name,
                target_name=ext,
                relationship_type="INHERITS",
                metadata={"inheritance_type": "interface_extends"},
            ))
        
        # Walk body
        body_node = node.child_by_field_name("body")
        if body_node:
            new_scope = scope_stack + [iface_name]
            for child in body_node.children:
                self._walk_tree(
                    child, content, file_path, entities, relationships,
                    entity, new_scope
                )
        
        return entity
    
    def _handle_type_alias(
        self,
        node: Node,
        content: str,
        file_path: str,
        entities: list[CodeEntity],
        relationships: list[CodeRelationship],
        parent_entity: CodeEntity | None,
        scope_stack: list[str],
    ) -> CodeEntity:
        """Handle type alias declarations."""
        name_node = node.child_by_field_name("name")
        type_name = "anonymous"
        if name_node:
            type_name = content[name_node.start_byte:name_node.end_byte]
        
        qualified_name = ".".join(scope_stack + [type_name]) if scope_stack else type_name
        
        type_parameters = node.child_by_field_name("type_parameters")
        type_value = node.child_by_field_name("type")
        
        signature_parts = ["type", type_name]
        if type_parameters:
            type_params_text = content[type_parameters.start_byte:type_parameters.end_byte]
            signature_parts.append(type_params_text)
        signature_parts.append("=")
        if type_value:
            type_text = content[type_value.start_byte:type_value.end_byte]
            signature_parts.append(type_text)
        
        signature = " ".join(signature_parts)
        
        entity = CodeEntity(
            entity_type="type_alias",
            name=qualified_name,
            signature=signature,
            docstring=None,
            source_code=content[node.start_byte:node.end_byte],
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            metadata={
                "local_name": type_name,
            },
        )
        entities.append(entity)
        
        return entity
    
    def _handle_method(
        self,
        node: Node,
        content: str,
        file_path: str,
        entities: list[CodeEntity],
        relationships: list[CodeRelationship],
        parent_entity: CodeEntity | None,
        scope_stack: list[str],
    ) -> CodeEntity:
        """Handle method definitions in classes."""
        if not parent_entity:
            return parent_entity  # type: ignore[return-value]
        
        name_node = node.child_by_field_name("name")
        method_name = "anonymous"
        if name_node:
            method_name = content[name_node.start_byte:name_node.end_byte]
        
        qualified_name = ".".join(scope_stack + [method_name]) if scope_stack else method_name
        
        # Check if async
        is_async = any(child.type == "async" for child in node.children)
        
        # Build signature
        params_node = node.child_by_field_name("parameters")
        return_type_node = node.child_by_field_name("return_type")
        type_parameters = node.child_by_field_name("type_parameters")
        
        signature_parts = []
        if is_async:
            signature_parts.append("async")
        signature_parts.append(method_name)
        
        if type_parameters:
            type_params_text = content[type_parameters.start_byte:type_parameters.end_byte]
            signature_parts.append(type_params_text)
        
        if params_node:
            params_text = content[params_node.start_byte:params_node.end_byte]
            signature_parts.append(params_text)
        
        if return_type_node:
            return_type_text = content[return_type_node.start_byte:return_type_node.end_byte]
            signature_parts.append(return_type_text)
        
        signature = " ".join(signature_parts)
        docstring = self._extract_jsdoc(node, content)
        
        entity = CodeEntity(
            entity_type="method",
            name=qualified_name,
            signature=signature,
            docstring=docstring,
            source_code=content[node.start_byte:node.end_byte],
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            metadata={
                "async": is_async,
                "local_name": method_name,
                "class": parent_entity.name,
            },
        )
        entities.append(entity)
        
        # Add DEFINES relationship
        relationships.append(CodeRelationship(
            source_name=parent_entity.name,
            target_name=qualified_name,
            relationship_type="DEFINES",
            metadata={"defined_type": "method"},
        ))
        
        # Walk body
        body_node = node.child_by_field_name("body")
        if body_node:
            new_scope = scope_stack + [method_name]
            for child in body_node.children:
                self._walk_tree(
                    child, content, file_path, entities, relationships,
                    entity, new_scope
                )
        
        return entity
    
    def _handle_arrow_function(
        self,
        node: Node,
        content: str,
        file_path: str,
        entities: list[CodeEntity],
        relationships: list[CodeRelationship],
        parent_entity: CodeEntity | None,
        scope_stack: list[str],
    ) -> None:
        """Handle arrow functions assigned to variables."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return
        
        var_name = content[name_node.start_byte:name_node.end_byte]
        
        # Check if value is an arrow function
        value_node = node.child_by_field_name("value")
        if value_node and value_node.type in ("arrow_function", "function"):
            # Treat as function declaration
            self._handle_function_declaration(
                value_node, content, file_path, entities, relationships,
                parent_entity, scope_stack, is_async=False, is_arrow=True
            )
    
    def _handle_import(
        self,
        node: Node,
        content: str,
        relationships: list[CodeRelationship],
        parent_entity: CodeEntity | None,
    ) -> None:
        """Handle import statements."""
        if not parent_entity:
            return
        
        # Find import clause
        for child in node.children:
            if child.type == "import_clause":
                # Get source
                source_node = None
                for c in node.children:
                    if c.type == "string":
                        source_node = c
                        break
                
                if source_node:
                    source = content[source_node.start_byte:source_node.end_byte]
                    source = source.strip('"\'')
                    
                    # Process imported items
                    self._process_import_clause(
                        child, content, relationships, parent_entity, source
                    )
    
    def _process_import_clause(
        self,
        node: Node,
        content: str,
        relationships: list[CodeRelationship],
        parent_entity: CodeEntity,
        source: str,
    ) -> None:
        """Process import clause to extract imported items."""
        for child in node.children:
            if child.type == "identifier":
                # Direct import: import React
                imported_name = content[child.start_byte:child.end_byte]
                relationships.append(CodeRelationship(
                    source_name=parent_entity.name,
                    target_name=source,
                    relationship_type="IMPORTS",
                    metadata={
                        "import_type": "default",
                        "name": imported_name,
                    },
                ))
            elif child.type == "named_imports":
                # Named imports: import { useState, useEffect }
                for named in child.children:
                    if named.type == "import_specifier":
                        name_node = named.child_by_field_name("name")
                        if name_node:
                            imported_name = content[name_node.start_byte:name_node.end_byte]
                            relationships.append(CodeRelationship(
                                source_name=parent_entity.name,
                                target_name=f"{source}.{imported_name}",
                                relationship_type="IMPORTS",
                                metadata={
                                    "import_type": "named",
                                    "source": source,
                                    "name": imported_name,
                                },
                            ))
            elif child.type == "namespace_import":
                # Namespace import: import * as React
                name_node = child.child_by_field_name("name")
                if name_node:
                    alias = content[name_node.start_byte:name_node.end_byte]
                    relationships.append(CodeRelationship(
                        source_name=parent_entity.name,
                        target_name=source,
                        relationship_type="IMPORTS",
                        metadata={
                            "import_type": "namespace",
                            "alias": alias,
                        },
                    ))
    
    def _handle_export(
        self,
        node: Node,
        content: str,
        relationships: list[CodeRelationship],
        parent_entity: CodeEntity | None,
    ) -> None:
        """Handle export statements."""
        # Mark entities as exported - could add metadata
        pass
    
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
        
        func_node = node.child_by_field_name("function")
        if func_node:
            target_name = self._resolve_call_target(func_node, content)
            if target_name:
                relationships.append(CodeRelationship(
                    source_name=parent_entity.name,
                    target_name=target_name,
                    relationship_type="CALLS",
                    metadata={"line": node.start_point[0] + 1},
                ))
    
    def _handle_decorator(
        self,
        node: Node,
        content: str,
        relationships: list[CodeRelationship],
        parent_entity: CodeEntity | None,
    ) -> None:
        """Handle decorators."""
        if not parent_entity:
            return
        
        call_node = node.child_by_field_name("call")
        if call_node:
            decorator_name = self._resolve_call_target(call_node, content)
        else:
            # Simple decorator: @Component
            identifier = node.children[0] if node.children else None
            if identifier:
                decorator_name = content[identifier.start_byte:identifier.end_byte]
            else:
                return
        
        relationships.append(CodeRelationship(
            source_name=parent_entity.name,
            target_name=decorator_name,
            relationship_type="DECORATES",
            metadata={},
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
        """Handle decorated definitions."""
        # Find the decorated item
        definition_node = None
        decorator_nodes = []
        
        for child in node.children:
            if child.type == "decorator":
                decorator_nodes.append(child)
            elif child.type in ("function_declaration", "class_declaration", 
                                 "async_function_declaration", "method_definition"):
                definition_node = child
        
        if not definition_node:
            return
        
        # Process the definition (will create entity and walk children)
        for child in node.children:
            self._walk_tree(
                child, content, file_path, entities, relationships,
                parent_entity, scope_stack
            )
    
    def _extract_heritage(
        self,
        content: str,
        heritage_node: Node,
    ) -> tuple[list[str], list[str]]:
        """Extract extends/implements from heritage clause."""
        bases = []
        implements = []
        
        for child in heritage_node.children:
            if child.type == "extends_clause":
                for type_child in child.children:
                    if type_child.type in ("identifier", "type_identifier", "member_expression"):
                        base_name = content[type_child.start_byte:type_child.end_byte]
                        bases.append(base_name)
            elif child.type == "implements_clause":
                for type_child in child.children:
                    if type_child.type in ("identifier", "type_identifier", "type_reference"):
                        impl_name = content[type_child.start_byte:type_child.end_byte]
                        implements.append(impl_name)
        
        return bases, implements
    
    def _extract_interface_extends(
        self,
        content: str,
        extends_node: Node,
    ) -> list[str]:
        """Extract extended interfaces."""
        extends = []
        for child in extends_node.children:
            if child.type in ("identifier", "type_identifier", "type_reference"):
                ext_name = content[child.start_byte:child.end_byte]
                extends.append(ext_name)
        return extends
    
    def _resolve_call_target(self, node: Node, content: str) -> str | None:
        """Resolve the target of a function/method call."""
        if node.type == "identifier":
            return content[node.start_byte:node.end_byte]
        elif node.type == "member_expression":
            obj = node.child_by_field_name("object")
            prop = node.child_by_field_name("property")
            if obj and prop:
                obj_name = self._resolve_call_target(obj, content)
                prop_name = content[prop.start_byte:prop.end_byte]
                if obj_name:
                    return f"{obj_name}.{prop_name}"
                return prop_name
        elif node.type == "call_expression":
            func_node = node.child_by_field_name("function")
            if func_node:
                return self._resolve_call_target(func_node, content)
        return None
    
    def _extract_jsdoc(self, node: Node, content: str) -> str | None:
        """Extract JSDoc/TSDoc comment if present."""
        # Tree-sitter doesn't expose comments as children by default
        # This would require looking at the preceding sibling or comment nodes
        # For now, return None - can be enhanced with comment parsing
        return None
