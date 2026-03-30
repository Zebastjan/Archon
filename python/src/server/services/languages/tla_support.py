"""TLA+ language support using Tree-sitter.

Extracts TLA+ specifications including:
- Operators and functions
- State variables
- Invariants and properties
- PlusCal algorithms
- Theorems and proofs
- Constants and assumptions

Useful for linking formal specifications to implementations
and tracking spec drift.
"""

from tree_sitter import Language, Node, Parser
import logging

# Try to import TLA+ grammar
try:
    import tree_sitter_tlaplus as ts_tla

    HAS_TS_TLA = True
except ImportError:
    HAS_TS_TLA = False
    ts_tla = None

from ...config.logfire_config import get_logger
from .language_support import CodeEntity, CodeRelationship, LanguageSupport

logger = get_logger(__name__)


class TlaLanguageSupport(LanguageSupport):
    """TLA+ language support for specification extraction."""

    def __init__(self):
        """Initialize TLA+ language support."""
        self._logger = logger
        self._has_ts_tla = HAS_TS_TLA and ts_tla is not None
        self._language = None
        self._parser = None

        if self._has_ts_tla and ts_tla is not None:
            try:
                self._language = Language(ts_tla.language())
                self._parser = Parser(self._language)
                self._logger.debug("TLA+ language support initialized with tree-sitter-tlaplus")
            except Exception as e:
                self._logger.warning(f"Failed to initialize tree-sitter TLA+: {e}")
                self._has_ts_tla = False

        if not self._has_ts_tla:
            self._logger.warning("TLA+ tree-sitter grammar not available - specifications will not be parsed")

    @property
    def name(self) -> str:
        return "tla"

    @property
    def language_id(self) -> str:
        return "tla"

    @property
    def file_extensions(self) -> list[str]:
        return [".tla", ".cfg"]

    def extract_entities_and_relationships(
        self, content: str, file_path: str
    ) -> tuple[list[CodeEntity], list[CodeRelationship]]:
        """Extract TLA+ specification entities.

        Returns operators, variables, invariants, theorems, and PlusCal algorithms
        as entities that can be linked to implementations.
        """
        if not self._has_ts_tla or not self._parser:
            # No tree-sitter support - create a basic entity for the file
            self._logger.debug(f"No TLA+ parser available for {file_path}")
            entity = CodeEntity(
                entity_type="specification_file",
                name=file_path.split("/")[-1].replace(".tla", ""),
                signature=f"MODULE {file_path.split('/')[-1].replace('.tla', '')}",
                docstring=None,
                source_code=content[:1000],  # First 1000 chars
                line_start=1,
                line_end=content.count("\n") + 1,
                file_path=file_path,
                language="tla+",
                metadata={
                    "unparsed": True,
                    "reason": "tree-sitter-tlaplus not available",
                },
            )
            return [entity], []

        try:
            tree = self._parser.parse(bytes(content, "utf-8"))
        except Exception as e:
            self._logger.warning(f"Failed to parse TLA+ file {file_path}: {e}")
            return [], []

        entities: list[CodeEntity] = []
        relationships: list[CodeRelationship] = []

        # Walk the AST
        self._walk_tree(
            tree.root_node,
            content,
            file_path,
            entities,
            relationships,
            parent_entity=None,
        )

        self._logger.debug(f"TLA+ extraction complete: {file_path} - {len(entities)} entities")

        return entities, relationships

    def _walk_tree(
        self,
        node: Node,
        content: str,
        file_path: str,
        entities: list[CodeEntity],
        relationships: list[CodeRelationship],
        parent_entity: CodeEntity | None,
    ) -> None:
        """Recursively walk the TLA+ AST."""
        node_type = node.type

        # Handle operator definitions
        if node_type in ("operator_definition", "function_definition"):
            self._handle_operator(node, content, file_path, entities, relationships, parent_entity)
            return

        # Handle variable declarations
        elif node_type in ("variable_declaration", "constant_declaration"):
            self._handle_variable(node, content, file_path, entities, relationships, parent_entity)
            return

        # Handle theorems and proofs
        elif node_type in ("theorem", "axiom", "assumption"):
            self._handle_theorem(node, content, file_path, entities, relationships, parent_entity)
            return

        # Handle invariants and properties
        elif node_type == "invariant":
            self._handle_invariant(node, content, file_path, entities, relationships, parent_entity)
            return

        # Handle PlusCal algorithms
        elif node_type in ("pcal_algorithm", "algorithm"):
            self._handle_pluscal(node, content, file_path, entities, relationships)
            return

        # Handle module definition
        elif node_type == "module":
            self._handle_module(node, content, file_path, entities, relationships)

        # Continue walking children
        for child in node.children:
            self._walk_tree(child, content, file_path, entities, relationships, parent_entity)

    def _handle_module(
        self,
        node: Node,
        content: str,
        file_path: str,
        entities: list[CodeEntity],
        relationships: list[CodeRelationship],
    ) -> None:
        """Handle TLA+ MODULE definition."""
        # Find module name
        module_name = None
        for child in node.children:
            if child.type == "identifier":
                module_name = content[child.start_byte : child.end_byte]
                break

        if not module_name:
            module_name = file_path.split("/")[-1].replace(".tla", "")

        entity = CodeEntity(
            entity_type="specification_module",
            name=module_name,
            signature=f"MODULE {module_name}",
            docstring=self._extract_module_docstring(node, content),
            source_code=self._get_source_code(node, content),
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            file_path=file_path,
            language="tla+",
            metadata={
                "is_module": True,
            },
        )
        entities.append(entity)

    def _handle_operator(
        self,
        node: Node,
        content: str,
        file_path: str,
        entities: list[CodeEntity],
        relationships: list[CodeRelationship],
        parent_entity: CodeEntity | None,
    ) -> None:
        """Handle operator/function definition."""
        # Find operator name
        op_name = self._find_identifier(node, content)
        if not op_name:
            return

        # Determine if it's a temporal property, invariant, or regular operator
        is_temporal = self._is_temporal_operator(node, content)
        is_invariant = "inv" in op_name.lower() or "invariant" in op_name.lower()

        entity_type = "operator"
        if is_temporal:
            entity_type = "temporal_property"
        elif is_invariant:
            entity_type = "invariant"

        entity = CodeEntity(
            entity_type=entity_type,
            name=op_name,
            signature=self._build_operator_signature(node, content, op_name),
            docstring=self._extract_docstring(node, content),
            source_code=self._get_source_code(node, content),
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            file_path=file_path,
            language="tla+",
            metadata={
                "is_temporal": is_temporal,
                "is_invariant": is_invariant,
                "operator_kind": self._classify_operator(node, content),
            },
        )
        entities.append(entity)

    def _handle_variable(
        self,
        node: Node,
        content: str,
        file_path: str,
        entities: list[CodeEntity],
        relationships: list[CodeRelationship],
        parent_entity: CodeEntity | None,
    ) -> None:
        """Handle variable/constant declaration."""
        # TLA+ can declare multiple variables at once
        var_names = self._find_identifiers(node, content)

        for var_name in var_names:
            entity = CodeEntity(
                entity_type="state_variable" if "variable" in node.type else "constant",
                name=var_name,
                signature=f"{var_name}",
                docstring=None,
                source_code=self._get_source_code(node, content),
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                file_path=file_path,
                language="tla+",
                metadata={
                    "declaration_type": node.type,
                },
            )
            entities.append(entity)

    def _handle_theorem(
        self,
        node: Node,
        content: str,
        file_path: str,
        entities: list[CodeEntity],
        relationships: list[CodeRelationship],
        parent_entity: CodeEntity | None,
    ) -> None:
        """Handle theorem/axiom/assumption."""
        # Find name if present
        thm_name = self._find_identifier(node, content)
        if not thm_name:
            thm_name = f"{node.type}_{len([e for e in entities if node.type in e.entity_type])}"

        entity_type_map = {
            "theorem": "theorem",
            "axiom": "axiom",
            "assumption": "assumption",
        }

        entity = CodeEntity(
            entity_type=entity_type_map.get(node.type, "property"),
            name=thm_name,
            signature=f"{node.type.upper()} {thm_name}",
            docstring=self._extract_docstring(node, content),
            source_code=self._get_source_code(node, content),
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            file_path=file_path,
            language="tla+",
            metadata={
                "theorem_type": node.type,
            },
        )
        entities.append(entity)

    def _handle_invariant(
        self,
        node: Node,
        content: str,
        file_path: str,
        entities: list[CodeEntity],
        relationships: list[CodeRelationship],
        parent_entity: CodeEntity | None,
    ) -> None:
        """Handle invariant definition."""
        inv_name = self._find_identifier(node, content)
        if not inv_name:
            inv_name = f"invariant_{len([e for e in entities if e.entity_type == 'invariant'])}"

        entity = CodeEntity(
            entity_type="invariant",
            name=inv_name,
            signature=f"INVARIANT {inv_name}",
            docstring=None,
            source_code=self._get_source_code(node, content),
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            file_path=file_path,
            language="tla+",
            metadata={
                "is_safety_property": True,
            },
        )
        entities.append(entity)

    def _handle_pluscal(
        self,
        node: Node,
        content: str,
        file_path: str,
        entities: list[CodeEntity],
        relationships: list[CodeRelationship],
    ) -> None:
        """Handle PlusCal algorithm."""
        algo_name = self._find_identifier(node, content)
        if not algo_name:
            algo_name = "PlusCalAlgorithm"

        entity = CodeEntity(
            entity_type="pluscal_algorithm",
            name=algo_name,
            signature=f"--algorithm {algo_name}",
            docstring=self._extract_docstring(node, content),
            source_code=self._get_source_code(node, content),
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            file_path=file_path,
            language="tla+",
            metadata={
                "is_pluscal": True,
                "algorithm_name": algo_name,
            },
        )
        entities.append(entity)

    # Helper methods
    def _find_identifier(self, node: Node, content: str) -> str | None:
        """Find first identifier in node."""
        for child in node.children:
            if child.type == "identifier":
                return content[child.start_byte : child.end_byte]
            result = self._find_identifier(child, content)
            if result:
                return result
        return None

    def _find_identifiers(self, node: Node, content: str) -> list[str]:
        """Find all identifiers in node."""
        identifiers = []
        for child in node.children:
            if child.type == "identifier":
                identifiers.append(content[child.start_byte : child.end_byte])
            identifiers.extend(self._find_identifiers(child, content))
        return identifiers

    def _build_operator_signature(self, node: Node, content: str, name: str) -> str:
        """Build operator signature."""
        # Get parameters if it's a function
        params = ""
        params_node = None
        for child in node.children:
            if child.type in ("parameter_list", "quantifier_bound"):
                params_node = child
                break

        if params_node:
            params = content[params_node.start_byte : params_node.end_byte]

        if params:
            return f"{name}{params}"
        return name

    def _extract_docstring(self, node: Node, content: str) -> str | None:
        """Extract documentation comment."""
        # Look for preceding comment
        # TLA+ uses (* ... *) or \* for comments
        # This is a simplified version
        return None

    def _extract_module_docstring(self, node: Node, content: str) -> str | None:
        """Extract module-level documentation."""
        # Look for comments before EXTENDS or after MODULE
        return None

    def _get_source_code(self, node: Node, content: str, max_length: int = 500) -> str:
        """Get source code for a node."""
        source = content[node.start_byte : node.end_byte]
        if len(source) > max_length:
            source = source[:max_length] + "..."
        return source

    def _is_temporal_operator(self, node: Node, content: str) -> bool:
        """Check if operator uses temporal logic."""
        source = content[node.start_byte : node.end_byte].upper()
        temporal_keywords = ["[]", "<>", "WF_", "SF_", "~>", "-+-", "-+->"]
        return any(kw in source for kw in temporal_keywords)

    def _classify_operator(self, node: Node, content: str) -> str:
        """Classify operator by its usage pattern."""
        source = content[node.start_byte : node.end_byte].upper()

        if "NEXT" in source or "'" in source:
            return "action"
        elif any(kw in source for kw in ["[]", "<>", "WF_", "SF_"]):
            return "temporal"
        elif "CHOOSE" in source:
            return "choice"
        elif "CASE" in source:
            return "case"
        else:
            return "definition"
