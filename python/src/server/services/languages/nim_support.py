"""Nim language support using Tree-sitter.

Extracts procedures, types, methods, imports, and their relationships
from Nim source code using tree-sitter-language-pack.
"""

from tree_sitter import Node, Parser
import logging

try:
    from tree_sitter_language_pack import get_language  # type: ignore[import-untyped]

    HAS_TS_NIM = True
except ImportError:
    HAS_TS_NIM = False
    get_language = None  # type: ignore[assignment]

from .language_support import (
    CodeEntity,
    CodeRelationship,
    LanguageSupportBase,
    ParseError,
)

logger = logging.getLogger(__name__)


class NimLanguageSupport(LanguageSupportBase):
    """Nim language support using Tree-sitter.

    Extracts entities and relationships from Nim source code.
    Handles:
    - Procedure definitions (proc, func, method)
    - Type definitions (object, enum, tuple)
    - Templates and macros
    - Iterators
    - Import/include statements
    - Generic procedures and types
    - Pragmas (async, inline, etc.)
    - Type inheritance (object of X)

    Example:
        >>> support = NimLanguageSupport()
        >>> content = '''
        ... type
        ...   Person = object
        ...     name: string
        ...     age: int
        ...
        ... proc greet(p: Person): string =
        ...   result = "Hello, " & p.name
        ... '''
        >>> entities, relationships = support.extract_entities_and_relationships(
        ...     content, "person.nim"
        ... )
        >>> len(entities)
        2  # type Person and proc greet
    """

    language_id = "nim"
    file_extensions = [".nim", ".nims", ".nimble"]

    def __init__(self):
        """Initialize Nim language support.

        Raises:
            ImportError: If tree-sitter-language-pack is not installed
        """
        if not HAS_TS_NIM or get_language is None:
            raise ImportError(
                "tree-sitter-language-pack is required. Install with: uv pip install tree-sitter-language-pack"
            )

        self._language = get_language("nim")  # type: ignore[misc]
        self._parser = Parser(self._language)
        self._logger = logger
        self._logger.debug("Nim language support initialized")

    def extract_entities_and_relationships(
        self,
        content: str,
        file_path: str,
    ) -> tuple[list[CodeEntity], list[CodeRelationship]]:
        """Extract entities and relationships from Nim source code.

        Args:
            content: Nim source code as a string
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
                f"Failed to parse Nim source: {e}",
                file_path=file_path,
            ) from e

        # Check for parse errors
        if tree.root_node.has_error:
            self._logger.warning(f"Parse tree has errors for {file_path}")
            raise ParseError(
                "Nim source contains syntax errors",
                file_path=file_path,
            )

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
            f"Extraction complete: {file_path} - {len(entities)} entities, {len(relationships)} relationships"
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
        """Recursively walk the Nim AST.

        Args:
            node: Current AST node
            content: Full source content
            file_path: Path to the file
            entities: List to collect entities
            relationships: List to collect relationships
            parent_entity: Parent entity (e.g., type containing a method)
            scope_stack: Stack of scope names for building qualified names
        """
        node_type = node.type

        # Handle procedure/function/method declarations
        # Check for both declaration types and direct proc/type keywords
        if node_type in (
            "proc_declaration",
            "proc",
            "func_declaration",
            "func",
            "method_declaration",
            "method",
            "iterator_declaration",
            "iterator",
            "template_declaration",
            "template",
            "macro_declaration",
            "macro",
        ):
            self._handle_procedure(node, content, file_path, entities, relationships, parent_entity, scope_stack)
            return

        elif node_type in ("type_section", "type"):
            self._handle_type_section(node, content, file_path, entities, relationships, parent_entity, scope_stack)
            return

        elif node_type in ("type_declaration", "type_definition"):
            self._handle_type_def(node, content, file_path, entities, relationships, parent_entity, scope_stack)
            return

        elif node_type in ("call", "command"):
            self._handle_call(node, content, relationships, parent_entity)

        elif node_type in ("import_statement", "import_from_statement", "include_statement", "import", "include"):
            self._handle_import(node, content, relationships, parent_entity)

        elif node_type == "export_statement":
            self._handle_export(node, content, relationships, parent_entity)

        # Continue walking children
        for child in node.children:
            self._walk_tree(child, content, file_path, entities, relationships, parent_entity, scope_stack)

    def _handle_procedure(
        self,
        node: Node,
        content: str,
        file_path: str,
        entities: list[CodeEntity],
        relationships: list[CodeRelationship],
        parent_entity: CodeEntity | None,
        scope_stack: list[str],
    ) -> CodeEntity:
        """Handle procedure/function/method declarations."""
        # Get procedure name using the helper that handles exported symbols
        proc_name = self._find_identifier(node, content)
        if not proc_name:
            # Anonymous procedure - skip
            return parent_entity  # type: ignore[return-value]

        qualified_name = ".".join(scope_stack + [proc_name]) if scope_stack else proc_name

        # Determine procedure type
        is_async = False
        is_generic = False
        node_type = node.type
        is_template = node_type in ("template_declaration", "template")
        is_macro = node_type in ("macro_declaration", "macro")
        is_iterator = node_type in ("iterator_declaration", "iterator")

        # Extract pragmas
        pragmas = self._extract_pragmas(node, content)
        if "async" in pragmas:
            is_async = True

        # Extract generic parameters
        generic_params = self._extract_generic_params(node, content)
        if generic_params:
            is_generic = True

        # Build signature
        signature = self._build_procedure_signature(node, content, proc_name, generic_params, pragmas)

        # Extract return type
        return_type = self._extract_return_type(node, content)

        # Get docstring (Nim uses ## for doc comments)
        docstring = self._extract_docstring(node, content)

        # Determine entity type
        entity_type = self._resolve_procedure_type(node, parent_entity)

        # Create entity
        entity = CodeEntity(
            entity_type=entity_type,
            name=qualified_name,
            signature=signature,
            docstring=docstring,
            source_code=self._get_source_code(node, content),
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            metadata={
                "local_name": proc_name,
                "is_async": is_async,
                "is_generic": is_generic,
                "is_template": is_template,
                "is_macro": is_macro,
                "is_iterator": is_iterator,
                "pragmas": pragmas,
                "return_type": return_type,
                "generic_params": generic_params,
            },
        )
        entities.append(entity)

        # Add DEFINES relationship if inside a type
        if parent_entity and parent_entity.entity_type == "class":
            relationships.append(
                CodeRelationship(
                    source_name=parent_entity.name,
                    target_name=qualified_name,
                    relationship_type="DEFINES",
                    metadata={"defined_type": entity_type},
                )
            )

        # Walk procedure body for nested entities and calls
        body_node = self._find_child_by_type(node, "statement_list")
        if body_node:
            new_scope = scope_stack + [proc_name]
            for child in body_node.children:
                self._walk_tree(child, content, file_path, entities, relationships, entity, new_scope)

        return entity

    def _handle_type_section(
        self,
        node: Node,
        content: str,
        file_path: str,
        entities: list[CodeEntity],
        relationships: list[CodeRelationship],
        parent_entity: CodeEntity | None,
        scope_stack: list[str],
    ) -> None:
        """Handle type section containing type definitions."""
        # Type sections contain multiple type definitions
        for child in node.children:
            if child.type == "type_declaration":
                self._handle_type_def(child, content, file_path, entities, relationships, parent_entity, scope_stack)

    def _handle_type_def(
        self,
        node: Node,
        content: str,
        file_path: str,
        entities: list[CodeEntity],
        relationships: list[CodeRelationship],
        parent_entity: CodeEntity | None,
        scope_stack: list[str],
    ) -> CodeEntity:
        """Handle individual type definition."""
        # Get type name - use helper that handles exported symbols
        type_name = self._find_identifier(node, content)
        if not type_name:
            # Try directly inside type_symbol_declaration
            type_symbol = self._find_child_by_type(node, "type_symbol_declaration")
            if type_symbol:
                type_name = self._find_identifier(type_symbol, content)

        if not type_name:
            return parent_entity  # type: ignore[return-value]

        qualified_name = ".".join(scope_stack + [type_name]) if scope_stack else type_name

        # Determine type kind
        is_object = False
        is_enum = False
        is_tuple = False
        parent_type = None

        # Look for object_declaration, enum, tuple, etc.
        obj_node = self._find_child_by_type(node, "object_declaration")
        enum_node = self._find_child_by_type(node, "enum_declaration")
        tuple_node = self._find_child_by_type(node, "tuple_type")

        if obj_node:
            is_object = True
            # Check for inheritance (object of ParentType)
            parent_type = self._extract_object_parent(obj_node, content)
        elif enum_node:
            is_enum = True
        elif tuple_node:
            is_tuple = True

        # Extract generic parameters
        generic_params = self._extract_generic_params(node, content)

        # Build signature
        signature = self._build_type_signature(node, content, type_name, generic_params, parent_type)

        # Get docstring
        docstring = self._extract_docstring(node, content)

        # Create entity - use "type" for Nim type declarations
        entity = CodeEntity(
            entity_type="type",
            name=qualified_name,
            signature=signature,
            docstring=docstring,
            source_code=self._get_source_code(node, content),
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            metadata={
                "local_name": type_name,
                "is_object": is_object,
                "is_enum": is_enum,
                "is_tuple": is_tuple,
                "is_generic": bool(generic_params),
                "generic_params": generic_params,
                "parent_type": parent_type,
            },
        )
        entities.append(entity)

        # Add INHERITS relationship if there's a parent type
        if parent_type:
            relationships.append(
                CodeRelationship(
                    source_name=qualified_name,
                    target_name=parent_type,
                    relationship_type="INHERITS",
                    metadata={},
                )
            )

        # Walk type body for nested procedures (methods)
        if obj_node:
            new_scope = scope_stack + [type_name]
            for child in obj_node.children:
                self._walk_tree(child, content, file_path, entities, relationships, entity, new_scope)

        return entity

    def _handle_call(
        self,
        node: Node,
        content: str,
        relationships: list[CodeRelationship],
        parent_entity: CodeEntity | None,
    ) -> None:
        """Handle function/procedure calls."""
        if not parent_entity:
            return

        # Get the function being called
        target_name = self._resolve_call_target(node, content)
        if target_name:
            relationships.append(
                CodeRelationship(
                    source_name=parent_entity.name,
                    target_name=target_name,
                    relationship_type="CALLS",
                    metadata={"line": node.start_point[0] + 1},
                )
            )

    def _handle_import(
        self,
        node: Node,
        content: str,
        relationships: list[CodeRelationship],
        parent_entity: CodeEntity | None,
    ) -> None:
        """Handle import/include statements."""
        if not parent_entity:
            return

        # Determine if it's include or import
        import_type = "include"
        if node.type in ("import_statement", "import_from_statement", "import"):
            import_type = "import"

        # Extract imported module names
        for child in node.children:
            if child.type == "identifier" or child.type == "dotted_name":
                module_name = content[child.start_byte : child.end_byte]
                relationships.append(
                    CodeRelationship(
                        source_name=parent_entity.name,
                        target_name=module_name,
                        relationship_type="IMPORTS",
                        metadata={"import_type": import_type},
                    )
                )

    def _handle_export(
        self,
        node: Node,
        content: str,
        relationships: list[CodeRelationship],
        parent_entity: CodeEntity | None,
    ) -> None:
        """Handle export statements (for building dependency graphs)."""
        if not parent_entity:
            return

        for child in node.children:
            if child.type == "identifier" or child.type == "dotted_name":
                exported_name = content[child.start_byte : child.end_byte]
                relationships.append(
                    CodeRelationship(
                        source_name=parent_entity.name,
                        target_name=exported_name,
                        relationship_type="EXPORTS",
                        metadata={},
                    )
                )

    # Helper methods

    def _find_child_by_type(self, node: Node, child_type: str) -> Node | None:
        """Find first child of given type, including inside exported_symbol."""
        for child in node.children:
            if child.type == child_type:
                return child
            # Also check inside exported_symbol
            if child.type == "exported_symbol":
                for sub in child.children:
                    if sub.type == child_type:
                        return sub
        return None

    def _find_identifier(self, node, content: str) -> str | None:
        """Find the identifier name from a proc/type declaration.

        Recursively searches for identifier, handling:
        - Direct identifier children
        - Exported symbols (with trailing *)
        - Nested structures like type_symbol_declaration

        Note: tree-sitter-nim has a bug where node.start_byte can be off by 2 bytes
        for proc declarations (missing 'pr' from 'proc'). We compensate for this.
        """
        node_type = node.type

        # For type_symbol_declaration nodes, look for identifier inside
        if node_type == "type_symbol_declaration":
            # Look in direct children and nested exported_symbol
            for child in node.children:
                if child.type == "identifier":
                    return content[child.start_byte : child.end_byte]
                if child.type == "exported_symbol":
                    for sub in child.children:
                        if sub.type == "identifier":
                            name = content[sub.start_byte : sub.end_byte]
                            if name.endswith("*"):
                                name = name[:-1]
                            return name
            return None

        # For type_declaration nodes, look inside type_symbol_declaration
        if node_type == "type_declaration":
            for child in node.children:
                if child.type == "type_symbol_declaration":
                    # Recursively look inside
                    result = self._find_identifier(child, content)
                    if result:
                        return result
            return None

        # First try direct identifier
        for child in node.children:
            if child.type == "identifier":
                name = content[child.start_byte : child.end_byte]
                # Handle case where identifier includes trailing characters (grammar bug)
                # Find the actual identifier by looking for the first space or paren
                for i, c in enumerate(name):
                    if c in " (":
                        name = name[:i]
                        break
                # Remove trailing * if present
                if name.endswith("*"):
                    name = name[:-1]
                return name

        # Then try inside exported_symbol
        for child in node.children:
            if child.type == "exported_symbol":
                for sub in child.children:
                    if sub.type == "identifier":
                        name = content[sub.start_byte : sub.end_byte]
                        # Handle case where identifier includes trailing characters
                        for i, c in enumerate(name):
                            if c in " (":
                                name = name[:i]
                                break
                        # Remove trailing * if present
                        if name.endswith("*"):
                            name = name[:-1]
                        return name

        return None

    def _get_source_code(self, node: Node, content: str) -> str:
        """Extract source code for a node, handling tree-sitter-nim bugs.

        tree-sitter-nim has a bug where proc/func/method declarations have
        incorrect start_byte (off by 2 bytes - missing 'pr' from 'proc').
        We compensate by finding the correct start position.
        """
        node_start = node.start_byte
        node_end = node.end_byte

        # Check if this looks like a proc/func with wrong start byte
        # The missing 'pr' would leave 'oc ' at the start
        # Or for func it would be 'unc ' (missing 'fu')
        # Check for partial keywords that should start the declaration
        possible_start = content[node_start : node_start + 4]

        # Fix: check if first char is missing (e.g., 'proc ' -> 'oc ')
        # Look for incomplete keywords at start
        if possible_start.startswith("oc ") or possible_start.startswith("oc\n"):
            # Missing 'pr' from 'proc'
            search_start = max(0, node_start - 2)
            search_text = content[search_start : node_start + 5]
            if "proc " in search_text:
                pos = search_text.find("proc ")
                return content[search_start + pos : node_end]

        return content[node_start:node_end]

    def _extract_pragmas(self, node: Node, content: str) -> list[str]:
        """Extract pragma list from procedure/type."""
        pragmas = []
        pragma_node = self._find_child_by_type(node, "pragma_list")
        if pragma_node:
            for child in pragma_node.children:
                if child.type == "identifier":
                    pragma_name = content[child.start_byte : child.end_byte]
                    pragmas.append(pragma_name)
        return pragmas

    def _extract_generic_params(self, node: Node, content: str) -> str | None:
        """Extract generic type parameters [T, U] from procedure/type."""
        generic_node = self._find_child_by_type(node, "generic_parameter_list")
        if generic_node:
            return content[generic_node.start_byte : generic_node.end_byte]
        return None

    def _extract_return_type(self, node: Node, content: str) -> str | None:
        """Extract return type from procedure."""
        # Look for type_expression that comes after parameter list
        params_node = self._find_child_by_type(node, "parameter_declaration_list")
        for child in node.children:
            if child.type == "type_expression" and child.start_byte > (params_node.end_byte if params_node else 0):
                return content[child.start_byte : child.end_byte]
        return None

    def _extract_object_parent(self, obj_node: Node, content: str) -> str | None:
        """Extract parent type from 'object of ParentType' syntax."""
        # The first child is a type_expression containing the parent type
        for child in obj_node.children:
            if child.type == "type_expression":
                # Get the identifier from the type expression
                id_node = self._find_child_by_type(child, "identifier")
                if id_node:
                    return content[id_node.start_byte : id_node.end_byte]
                break
        return None

    def _build_procedure_signature(
        self,
        node: Node,
        content: str,
        proc_name: str,
        generic_params: str | None,
        pragmas: list[str],
    ) -> str:
        """Build signature for procedure definition."""
        # Determine procedure keyword
        keyword_map = {
            "proc_declaration": "proc",
            "func_declaration": "func",
            "method_declaration": "method",
            "iterator_declaration": "iterator",
            "template_declaration": "template",
            "macro_declaration": "macro",
        }
        keyword = keyword_map.get(node.type, "proc")

        signature_parts = [keyword, proc_name]

        # Add generic parameters (already includes brackets)
        if generic_params:
            signature_parts.append(generic_params)

        # Add parameters
        params_node = self._find_child_by_type(node, "parameter_declaration_list")
        if params_node:
            params_text = content[params_node.start_byte : params_node.end_byte]
            signature_parts.append(params_text)

        # Add return type - look for type_expression child (return type)
        return_type_node = None
        # Find type_expression that's not part of parameter list
        for child in node.children:
            if child.type == "type_expression" and child.start_byte > (params_node.end_byte if params_node else 0):
                return_type_node = child
                break

        if return_type_node:
            return_type_text = content[return_type_node.start_byte : return_type_node.end_byte]
            signature_parts.append(f": {return_type_text}")

        # Add pragmas
        if pragmas:
            pragma_str = "{." + ", ".join(pragmas) + ".}"
            signature_parts.append(pragma_str)

        return " ".join(signature_parts)

    def _build_type_signature(
        self,
        node: Node,
        content: str,
        type_name: str,
        generic_params: str | None,
        parent_type: str | None,
    ) -> str:
        """Build signature for type definition."""
        signature_parts = ["type", type_name]

        # Add generic parameters
        if generic_params:
            signature_parts.append(generic_params)

        signature_parts.append("=")

        # Add object keyword and inheritance
        obj_node = self._find_child_by_type(node, "object_declaration")
        if obj_node:
            signature_parts.append("object")
            if parent_type:
                signature_parts.append(f"of {parent_type}")
        else:
            # For enum, tuple, or other types
            enum_node = self._find_child_by_type(node, "enum_declaration")
            if enum_node:
                signature_parts.append("enum")
            else:
                # Get the type expression or other definition
                for child in node.children:
                    if child.type in ("type_expression", "tuple_type", "distinct_type"):
                        type_text = content[child.start_byte : child.end_byte]
                        # Truncate if too long
                        if len(type_text) > 100:
                            type_text = type_text[:97] + "..."
                        signature_parts.append(type_text)
                        break

        return " ".join(signature_parts)

    def _resolve_procedure_type(self, node: Node, parent_entity: CodeEntity | None) -> str:
        """Determine if procedure is proc, func, method, template, macro, iterator, or function."""
        # Check node type first
        if node.type == "method_declaration":
            return "method"
        if node.type == "func_declaration":
            return "func"
        if node.type == "template_declaration":
            return "template"
        if node.type == "macro_declaration":
            return "macro"
        if node.type == "iterator_declaration":
            return "iterator"

        # Check for proc declarations (including with pragmas for templates/iterators)
        if node.type == "proc_declaration":
            # Check metadata flags set earlier
            # These are set in _handle_procedure_declaration
            metadata = getattr(node, "_extracted_metadata", {})

            is_template = metadata.get("is_template", False)
            is_macro = metadata.get("is_macro", False)
            is_iterator = metadata.get("is_iterator", False)

            if is_macro:
                return "macro"
            if is_template:
                return "template"
            if is_iterator:
                return "iterator"

            # Default for proc
            return "proc"

        # If inside a type definition, it's a method
        if parent_entity and parent_entity.entity_type in ("class", "type"):
            return "method"

        # Default fallback
        return "function"

    def _resolve_call_target(self, node: Node, content: str) -> str | None:
        """Resolve the target of a function/procedure call."""
        # Nim calls are represented as (call function: identifier arguments: ...)
        func_node = self._find_child_by_type(node, "identifier")
        if func_node:
            return content[func_node.start_byte : func_node.end_byte]

        # Could be a dotted call (obj.method)
        dot_node = self._find_child_by_type(node, "dot_expression")
        if dot_node:
            return content[dot_node.start_byte : dot_node.end_byte]

        return None

    def _extract_docstring(self, node: Node, content: str) -> str | None:
        """Extract doc comment (##) from procedure/type.

        Nim uses ## for documentation comments. Tree-sitter usually
        doesn't expose comments in the AST, so this is a best-effort
        approach looking at preceding lines.
        """
        # Get the line before this node
        start_line = node.start_point[0]
        if start_line == 0:
            return None

        lines = content.split("\n")
        if start_line >= len(lines):
            return None

        # Check if previous line(s) contain doc comments
        doc_lines = []
        for i in range(start_line - 1, -1, -1):
            line = lines[i].strip()
            if line.startswith("##"):
                doc_lines.insert(0, line[2:].strip())
            elif line:
                # Hit non-comment, non-empty line
                break

        if doc_lines:
            return " ".join(doc_lines)
        return None
