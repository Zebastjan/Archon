"""Code Metrics and Audit Service

Provides code quality metrics calculation and audit rule enforcement
for the Archon code auditing platform.

This service is part of Phase 2: Metrics Tracking and Audit Rules
"""

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg2
from psycopg2.extras import RealDictCursor

from src.server.config.logfire_config import get_logger

logger = get_logger(__name__)


@dataclass
class CodeMetrics:
    """Code quality metrics for a repository or file."""
    
    # Size metrics
    total_files: int = 0
    total_lines_of_code: int = 0
    total_lines_of_comments: int = 0
    total_blank_lines: int = 0
    
    # Entity counts
    total_functions: int = 0
    total_classes: int = 0
    total_modules: int = 0
    total_interfaces: int = 0
    total_enums: int = 0
    total_variables: int = 0
    total_imports: int = 0
    
    # Complexity metrics
    avg_cyclomatic_complexity: float = 0.0
    max_cyclomatic_complexity: int = 0
    avg_function_length: int = 0
    max_function_length: int = 0
    
    # Quality metrics
    code_to_comment_ratio: float = 0.0
    duplicate_lines: int = 0
    todo_count: int = 0
    fixme_count: int = 0
    deprecated_count: int = 0
    
    # Health score (0-100)
    health_score: int = 100
    
    # Raw metrics for extensibility
    raw_metrics: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "total_files": self.total_files,
            "total_lines_of_code": self.total_lines_of_code,
            "total_lines_of_comments": self.total_lines_of_comments,
            "total_blank_lines": self.total_blank_lines,
            "total_functions": self.total_functions,
            "total_classes": self.total_classes,
            "total_modules": self.total_modules,
            "total_interfaces": self.total_interfaces,
            "total_enums": self.total_enums,
            "total_variables": self.total_variables,
            "total_imports": self.total_imports,
            "avg_cyclomatic_complexity": self.avg_cyclomatic_complexity,
            "max_cyclomatic_complexity": self.max_cyclomatic_complexity,
            "avg_function_length": self.avg_function_length,
            "max_function_length": self.max_function_length,
            "code_to_comment_ratio": self.code_to_comment_ratio,
            "duplicate_lines": self.duplicate_lines,
            "todo_count": self.todo_count,
            "fixme_count": self.fixme_count,
            "deprecated_count": self.deprecated_count,
            "health_score": self.health_score,
            "raw_metrics": self.raw_metrics,
        }


@dataclass
class AuditFinding:
    """An audit rule finding/violation."""
    
    rule_id: str
    entity_id: UUID | None = None
    finding_type: str = "violation"  # violation, suggestion, info
    severity: str = "warning"  # critical, error, warning, info
    message: str = ""
    description: str = ""
    file_path: str = ""
    line_start: int = 0
    line_end: int = 0
    code_snippet: str = ""
    suggested_fix: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "entity_id": str(self.entity_id) if self.entity_id else None,
            "finding_type": self.finding_type,
            "severity": self.severity,
            "message": self.message,
            "description": self.description,
            "file_path": self.file_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "code_snippet": self.code_snippet,
            "suggested_fix": self.suggested_fix,
        }


@dataclass
class AuditRule:
    """An audit rule definition."""
    
    id: UUID | None = None
    rule_id: str = ""
    name: str = ""
    description: str = ""
    category: str = ""  # complexity, style, security, performance, maintainability
    severity: str = "warning"
    rule_type: str = "threshold"  # threshold, pattern, custom
    configuration: dict[str, Any] = field(default_factory=dict)
    threshold_min: float | None = None
    threshold_max: float | None = None
    pattern: str | None = None
    applies_to: list[str] = field(default_factory=list)
    languages: list[str] | None = None
    file_patterns: list[str] | None = None
    is_active: bool = True
    is_builtin: bool = False
    
    # Enhanced metadata (Phase 2)
    implementation_type: str = "threshold"
    rationale: str = ""
    remediation_guidance: str = ""
    example_violation: str = ""
    example_fix: str = ""
    references: list[str] = field(default_factory=list)
    methodology_tags: list[str] = field(default_factory=list)
    applies_to_tdd: bool = False
    applies_to_doc_driven: bool = False
    applies_to_security_first: bool = False
    owasp_category: str = ""
    cwe_id: str = ""
    estimated_fix_time_minutes: int = 0
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id) if self.id else None,
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "severity": self.severity,
            "rule_type": self.rule_type,
            "configuration": self.configuration,
            "threshold_min": self.threshold_min,
            "threshold_max": self.threshold_max,
            "pattern": self.pattern,
            "applies_to": self.applies_to,
            "languages": self.languages,
            "file_patterns": self.file_patterns,
            "is_active": self.is_active,
            "is_builtin": self.is_builtin,
            "implementation_type": self.implementation_type,
            "rationale": self.rationale,
            "remediation_guidance": self.remediation_guidance,
            "example_violation": self.example_violation,
            "example_fix": self.example_fix,
            "references": self.references,
            "methodology_tags": self.methodology_tags,
            "applies_to_tdd": self.applies_to_tdd,
            "applies_to_doc_driven": self.applies_to_doc_driven,
            "applies_to_security_first": self.applies_to_security_first,
            "owasp_category": self.owasp_category,
            "cwe_id": self.cwe_id,
            "estimated_fix_time_minutes": self.estimated_fix_time_minutes,
        }


class CodeMetricsService:
    """Service for calculating code metrics and running audits."""
    
    # Complexity patterns for different languages
    COMPLEXITY_PATTERNS = {
        "python": [
            (r'\bif\b', 1),
            (r'\belif\b', 1),
            (r'\belse\s*:', 1),
            (r'\bfor\b', 1),
            (r'\bwhile\b', 1),
            (r'\bexcept', 1),
            (r'\bwith\b', 0),  # Context managers don't add complexity
            (r'\band\b', 0),   # Logical operators handled separately
            (r'\bor\b', 0),
        ],
        "javascript": [
            (r'\bif\b', 1),
            (r'\belse\b', 1),
            (r'\bfor\b', 1),
            (r'\bwhile\b', 1),
            (r'\bcatch\b', 1),
            (r'\bswitch\b', 1),
            (r'\?\s*[^:]\s*:', 1),  # Ternary operators
        ],
        "typescript": [
            (r'\bif\b', 1),
            (r'\belse\b', 1),
            (r'\bfor\b', 1),
            (r'\bwhile\b', 1),
            (r'\bcatch\b', 1),
            (r'\bswitch\b', 1),
            (r'\?\s*[^:]\s*:', 1),
        ],
    }
    
    def __init__(self, db_connection=None):
        """Initialize with optional database connection."""
        self._db = db_connection
        self._connection_string = os.getenv(
            "ARCHON_DATABASE_URL",
            "postgresql://archon:archon_local_dev@localhost:5434/archon"
        )
    
    def _get_db(self):
        """Get database connection."""
        if self._db is None:
            self._db = psycopg2.connect(self._connection_string)
        return self._db
    
    def _execute_query(self, query: str, params: tuple = ()) -> list[dict]:
        """Execute a query and return results."""
        conn = self._get_db()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            if cur.description:
                return [dict(row) for row in cur.fetchall()]
            conn.commit()
            return []
    
    def _execute_single(self, query: str, params: tuple = ()) -> dict | None:
        """Execute a query and return single result."""
        results = self._execute_query(query, params)
        return results[0] if results else None
    
    def calculate_cyclomatic_complexity(
        self, 
        source_code: str, 
        language: str = "python"
    ) -> int:
        """
        Calculate cyclomatic complexity for source code.
        
        Args:
            source_code: The source code to analyze
            language: Programming language
            
        Returns:
            Cyclomatic complexity score (1 = minimum)
        """
        if not source_code:
            return 1
        
        patterns = self.COMPLEXITY_PATTERNS.get(language, self.COMPLEXITY_PATTERNS["python"])
        complexity = 1  # Base complexity
        
        for pattern, weight in patterns:
            matches = len(re.findall(pattern, source_code, re.IGNORECASE))
            complexity += matches * weight
        
        # Count logical operators
        complexity += len(re.findall(r'\band\b|\bor\b', source_code))
        
        return max(1, complexity)
    
    def count_lines(self, source_code: str) -> tuple[int, int, int]:
        """
        Count lines of code, comments, and blank lines.
        
        Returns:
            Tuple of (code_lines, comment_lines, blank_lines)
        """
        if not source_code:
            return 0, 0, 0
        
        lines = source_code.split('\n')
        code_lines = 0
        comment_lines = 0
        blank_lines = 0
        in_multiline_comment = False
        
        for line in lines:
            stripped = line.strip()
            
            if not stripped:
                blank_lines += 1
                continue
            
            # Handle Python-style comments
            if stripped.startswith('#'):
                comment_lines += 1
                continue
            
            # Handle docstrings
            if stripped.startswith('"""') or stripped.startswith("'''"):
                if stripped.count('"""') == 2 or stripped.count("'''") == 2:
                    # Single line docstring
                    comment_lines += 1
                else:
                    in_multiline_comment = not in_multiline_comment
                    comment_lines += 1
                continue
            
            if in_multiline_comment:
                comment_lines += 1
                if stripped.endswith('"""') or stripped.endswith("'''"):
                    in_multiline_comment = False
                continue
            
            code_lines += 1
        
        return code_lines, comment_lines, blank_lines
    
    def count_todos_and_fixmes(self, source_code: str) -> tuple[int, int]:
        """Count TODO and FIXME comments in code."""
        if not source_code:
            return 0, 0
        
        todos = len(re.findall(r'#\s*TODO', source_code, re.IGNORECASE))
        todos += len(re.findall(r'""".*?TODO.*?"""', source_code, re.IGNORECASE | re.DOTALL))
        
        fixmes = len(re.findall(r'#\s*FIXME', source_code, re.IGNORECASE))
        fixmes += len(re.findall(r'""".*?FIXME.*?"""', source_code, re.IGNORECASE | re.DOTALL))
        
        return todos, fixmes
    
    def calculate_file_metrics(
        self, 
        entity_id: str | UUID,
        source_code: str | None = None,
        language: str = "python"
    ) -> dict[str, Any]:
        """
        Calculate metrics for a single file/entity.
        
        Args:
            entity_id: The entity ID
            source_code: Optional source code (fetched from DB if not provided)
            language: Programming language
            
        Returns:
            Dictionary of metrics
        """
        # Fetch source code if not provided
        if source_code is None:
            result = self._execute_single(
                """SELECT source_code, entity_type, name, file_path, line_start, line_end 
                   FROM archon_code_entities WHERE id = %s""",
                (str(entity_id),)
            )
            
            if not result:
                logger.warning(f"Entity {entity_id} not found")
                return {}
            
            source_code = result.get("source_code", "")
            language = self._detect_language(result.get("file_path", ""))
        
        # Calculate metrics
        code_lines, comment_lines, blank_lines = self.count_lines(source_code)
        complexity = self.calculate_cyclomatic_complexity(source_code, language)
        todos, fixmes = self.count_todos_and_fixmes(source_code)
        
        metrics = {
            "lines_of_code": code_lines,
            "lines_of_comments": comment_lines,
            "blank_lines": blank_lines,
            "cyclomatic_complexity": complexity,
            "function_length": code_lines,
            "todo_count": todos,
            "fixme_count": fixmes,
        }
        
        return metrics
    
    def calculate_repo_metrics(self, repo_id: str | UUID) -> CodeMetrics:
        """
        Calculate comprehensive metrics for a repository.
        
        Args:
            repo_id: The repository ID
            
        Returns:
            CodeMetrics object with all calculated metrics
        """
        logger.info(f"Calculating metrics for repo {repo_id}")
        
        # Fetch all entities for this repo
        entities = self._execute_query(
            """SELECT id, entity_type, source_code, file_path, line_start, line_end 
               FROM archon_code_entities WHERE repo_id = %s""",
            (str(repo_id),)
        )
        
        if not entities:
            logger.warning(f"No entities found for repo {repo_id}")
            return CodeMetrics()
        metrics = CodeMetrics()
        
        # Track file-level metrics
        file_metrics_list: list[dict[str, Any]] = []
        complexity_values: list[int] = []
        function_lengths: list[int] = []
        total_comment_lines = 0
        total_code_lines = 0
        
        # Process each entity
        for entity in entities:
            entity_type = entity.get("entity_type", "")
            source_code = entity.get("source_code", "")
            file_path = entity.get("file_path", "")
            language = self._detect_language(file_path)
            
            # Count entity types
            if entity_type == "function":
                metrics.total_functions += 1
            elif entity_type == "class":
                metrics.total_classes += 1
            elif entity_type == "module":
                metrics.total_modules += 1
            elif entity_type == "interface":
                metrics.total_interfaces += 1
            elif entity_type == "enum":
                metrics.total_enums += 1
            elif entity_type == "variable":
                metrics.total_variables += 1
            elif entity_type == "import":
                metrics.total_imports += 1
            
            # Calculate file metrics for functions and classes
            if entity_type in ["function", "method", "class"] and source_code:
                file_metrics = self.calculate_file_metrics(
                    entity["id"], source_code, language
                )
                file_metrics_list.append({
                    "entity_id": entity["id"],
                    "file_path": file_path,
                    **file_metrics
                })
                
                complexity_values.append(file_metrics["cyclomatic_complexity"])
                function_lengths.append(file_metrics["lines_of_code"])
                total_code_lines += file_metrics["lines_of_code"]
                total_comment_lines += file_metrics["lines_of_comments"]
                metrics.todo_count += file_metrics["todo_count"]
                metrics.fixme_count += file_metrics["fixme_count"]
        
        # Calculate aggregates
        metrics.total_files = len(set(e.get("file_path", "") for e in entities if e.get("file_path")))
        metrics.total_lines_of_code = total_code_lines
        metrics.total_lines_of_comments = total_comment_lines
        
        if complexity_values:
            metrics.avg_cyclomatic_complexity = round(sum(complexity_values) / len(complexity_values), 2)
            metrics.max_cyclomatic_complexity = max(complexity_values)
        
        if function_lengths:
            metrics.avg_function_length = sum(function_lengths) // len(function_lengths)
            metrics.max_function_length = max(function_lengths)
        
        # Calculate code-to-comment ratio
        if total_comment_lines > 0:
            metrics.code_to_comment_ratio = round(total_code_lines / total_comment_lines, 2)
        
        # Fetch exception findings for health score calculation
        exception_findings = []
        assertion_findings = []
        try:
            exception_query = """
                SELECT r.rule_id, f.severity 
                FROM archon_audit_findings f
                JOIN archon_audit_rules r ON f.rule_id = r.id
                WHERE f.repo_id = %s 
                AND f.status = 'open'
                AND (r.rule_id LIKE 'broad-except%%'
                   OR r.rule_id LIKE 'exception-not-logged%%'
                   OR r.rule_id LIKE 'async-exception-swallowed%%')
            """
            exception_results = self._execute_query(exception_query, (str(repo_id),))
            for row in exception_results:
                exception_findings.append(AuditFinding(
                    rule_id=row.get('rule_id', ''),
                    severity=row.get('severity', 'warning'),
                ))
            
            # Fetch assertion findings
            assertion_query = """
                SELECT r.rule_id, f.severity 
                FROM archon_audit_findings f
                JOIN archon_audit_rules r ON f.rule_id = r.id
                WHERE f.repo_id = %s 
                AND f.status = 'open'
                AND r.rule_id LIKE 'assert-%%'
            """
            assertion_results = self._execute_query(assertion_query, (str(repo_id),))
            for row in assertion_results:
                assertion_findings.append(AuditFinding(
                    rule_id=row.get('rule_id', ''),
                    severity=row.get('severity', 'warning'),
                ))
        except Exception as e:
            logger.warning(f"Could not fetch findings for health score: {e}")
        
        # Calculate health score with findings
        metrics.health_score = self._calculate_health_score(metrics, exception_findings, assertion_findings)
        
        # Save metrics to database
        self._save_repo_metrics(repo_id, metrics)
        self._save_file_metrics(repo_id, file_metrics_list)
        
        logger.info(f"Metrics calculated for repo {repo_id}: health_score={metrics.health_score}")
        return metrics
    
    def _calculate_health_score(
        self,
        metrics: CodeMetrics,
        exception_findings: list[AuditFinding] | None = None,
        assertion_findings: list[AuditFinding] | None = None,
    ) -> int:
        """
        Calculate an overall health score (0-100) based on metrics and findings.
        
        Higher score = better code health.
        Exception handling violations carry extra weight, especially for security focus.
        Assertion quality issues affect test reliability.
        """
        score = 100
        
        # Penalize high complexity
        if metrics.avg_cyclomatic_complexity > 10:
            score -= min(30, int((metrics.avg_cyclomatic_complexity - 10) * 3))
        
        # Penalize large functions
        if metrics.avg_function_length > 50:
            score -= min(20, int((metrics.avg_function_length - 50) / 5))
        
        # Penalize poor comment ratio
        if metrics.code_to_comment_ratio > 20:  # Very little commenting
            score -= 10
        
        # Penalize TODO/FIXME items
        todo_penalty = (metrics.todo_count + metrics.fixme_count) * 2
        score -= min(20, todo_penalty)
        
        # Penalize max complexity
        if metrics.max_cyclomatic_complexity > 20:
            score -= min(20, int((metrics.max_cyclomatic_complexity - 20) / 2))
        
        # Extra penalty for exception handling violations (P0)
        if exception_findings:
            for finding in exception_findings:
                if finding.rule_id == 'broad-except':
                    score -= 15  # Critical security risk
                elif finding.rule_id == 'async-exception-swallowed':
                    score -= 15  # Critical async issue
                elif finding.rule_id == 'exception-not-logged':
                    score -= 5   # Warning level
        
        # Penalty for assertion quality violations (P1) - capped at 20 total
        assertion_penalty = 0
        if assertion_findings:
            for finding in assertion_findings:
                if finding.rule_id == 'assert-missing-in-test':
                    assertion_penalty += 3
                elif finding.rule_id == 'assert-mock-not-verified':
                    assertion_penalty += 2
                elif finding.rule_id == 'assert-exception-not-tested':
                    assertion_penalty += 4
                elif finding.rule_id == 'assert-weak-boolean':
                    assertion_penalty += 1
                elif finding.rule_id == 'assert-equality-on-floats':
                    assertion_penalty += 2
        
        # Cap assertion penalty at 20 points
        score -= min(20, assertion_penalty)
        
        return max(0, min(100, score))
    
    def _save_repo_metrics(
        self, 
        repo_id: str | UUID, 
        metrics: CodeMetrics,
        branch_name: str = "main"
    ):
        """Save repository-level metrics to database."""
        try:
            data = metrics.to_dict()
            self._execute_query(
                """INSERT INTO archon_code_metrics 
                   (repo_id, branch_name, total_files, total_lines_of_code, 
                    total_lines_of_comments, total_blank_lines, total_functions,
                    total_classes, total_modules, total_interfaces, total_enums,
                    total_variables, total_imports, avg_cyclomatic_complexity,
                    max_cyclomatic_complexity, avg_function_length, max_function_length,
                    code_to_comment_ratio, duplicate_lines, todo_count, fixme_count,
                    deprecated_count, health_score, raw_metrics)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (str(repo_id), branch_name, data['total_files'], data['total_lines_of_code'],
                 data['total_lines_of_comments'], data['total_blank_lines'], data['total_functions'],
                 data['total_classes'], data['total_modules'], data['total_interfaces'], data['total_enums'],
                 data['total_variables'], data['total_imports'], data['avg_cyclomatic_complexity'],
                 data['max_cyclomatic_complexity'], data['avg_function_length'], data['max_function_length'],
                 data['code_to_comment_ratio'], data['duplicate_lines'], data['todo_count'], data['fixme_count'],
                 data['deprecated_count'], data['health_score'], json.dumps(data['raw_metrics']))
            )
            logger.debug(f"Saved metrics for repo {repo_id}")
        except Exception as e:
            logger.exception("Failed to save repo metrics: %s", str(e))
    
    def _save_file_metrics(
        self, 
        repo_id: str | UUID, 
        file_metrics: list[dict[str, Any]]
    ):
        """Save file-level metrics to database."""
        if not file_metrics:
            return
        
        try:
            # Insert in batches
            batch_size = 100
            for i in range(0, len(file_metrics), batch_size):
                batch = file_metrics[i:i + batch_size]
                for fm in batch:
                    self._execute_query(
                        """INSERT INTO archon_file_metrics 
                           (repo_id, entity_id, file_path, lines_of_code, lines_of_comments,
                            blank_lines, cyclomatic_complexity, todo_count, fixme_count)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (str(repo_id), fm["entity_id"], fm["file_path"],
                         fm.get("lines_of_code", 0), fm.get("lines_of_comments", 0),
                         fm.get("blank_lines", 0), fm.get("cyclomatic_complexity", 0),
                         fm.get("todo_count", 0), fm.get("fixme_count", 0))
                    )
            
            logger.debug(f"Saved {len(file_metrics)} file metrics for repo {repo_id}")
        except Exception as e:
            logger.exception("Failed to save file metrics: %s", str(e))
    
    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension."""
        if not file_path:
            return "unknown"
        
        extension = file_path.split('.')[-1].lower() if '.' in file_path else ""
        
        language_map = {
            "py": "python",
            "js": "javascript",
            "ts": "typescript",
            "tsx": "typescript",
            "jsx": "javascript",
            "java": "java",
            "go": "go",
            "rs": "rust",
            "cpp": "cpp",
            "c": "c",
            "h": "c",
            "hpp": "cpp",
            "cs": "csharp",
            "rb": "ruby",
            "php": "php",
            "swift": "swift",
            "kt": "kotlin",
            "scala": "scala",
        }
        
        return language_map.get(extension, "unknown")
    
    # =================================================================
    # EXCEPTION HANDLING RULES (P0)
    # =================================================================
    
    def check_exception_handling_rules(
        self,
        source_code: str,
        file_path: str,
        entity_id: str | None = None,
    ) -> list[AuditFinding]:
        """
        Check source code for exception handling violations.
        
        Args:
            source_code: The source code to analyze
            file_path: Path to the file
            entity_id: Optional entity ID
            
        Returns:
            List of AuditFinding objects for exception violations
        """
        if not source_code:
            return []
        
        findings = []
        lines = source_code.split('\n')
        
        # Track state
        in_try_block = False
        try_start_line = 0
        has_specific_except = False
        has_logging = False
        is_async = False
        current_except_line = 0
        
        # First pass: detect if this is async
        for i, line in enumerate(lines):
            if re.match(r'^\s*async\s+def\s+', line):
                is_async = True
                break
        
        # Second pass: analyze exception handling
        for i, line in enumerate(lines):
            line_num = i + 1
            
            # Detect try block
            if re.match(r'^\s*try\s*:', line):
                in_try_block = True
                try_start_line = line_num
                has_specific_except = False
                has_logging = False
                current_except_line = 0
            
            # Detect except block
            elif in_try_block and re.match(r'^\s*except\s*', line):
                current_except_line = line_num
                # Check if it's broad except
                if re.match(r'^\s*except\s*:\s*$', line):
                    # No specific exception type
                    findings.append(AuditFinding(
                        rule_id='broad-except',
                        severity='error',
                        message=f'Broad exception handler at line {line_num}: use specific exceptions',
                        file_path=file_path,
                        line_start=line_num,
                        line_end=line_num,
                    ))
                else:
                    # Check if it has specific exception
                    has_specific_except = bool(re.match(r'^\s*except\s+\w+', line))
                
                # Look ahead for logging
                has_logging = False
                for j in range(i + 1, min(i + 6, len(lines))):
                    next_line = lines[j]
                    # Stop if we hit another except or block end
                    if re.match(r'^\s*(except|finally|class|def)\s*', next_line):
                        break
                    # Check for logging
                    if re.search(r'(log|print|logger)', next_line, re.IGNORECASE):
                        has_logging = True
                        break
                
                # If no logging found, report
                if not has_logging:
                    findings.append(AuditFinding(
                        rule_id='exception-not-logged',
                        severity='warning',
                        message=f'Exception handler at line {line_num} does not log the error',
                        file_path=file_path,
                        line_start=line_num,
                        line_end=line_num,
                    ))
                
                # Check for async exception swallowing
                if is_async and re.search(r'pass', line):
                    # Check if this is a bare pass in except
                    for j in range(i + 1, min(i + 3, len(lines))):
                        if lines[j].strip() == 'pass':
                            findings.append(AuditFinding(
                                rule_id='async-exception-swallowed',
                                severity='error',
                                message=f'Async function at line {try_start_line} swallows exceptions - security risk',
                                file_path=file_path,
                                line_start=try_start_line,
                                line_end=line_num,
                            ))
                            break
            
            # Detect end of try/except block
            elif in_try_block and line.strip() and not line.startswith(' ') and not line.startswith('\t'):
                # Block ended
                in_try_block = False
        
        return findings

    def run_exception_rules_on_repo(
        self,
        repo_id: str | UUID,
    ) -> list[AuditFinding]:
        """
        Run exception handling rules on all entities in a repository.
        
        Args:
            repo_id: Repository ID
            
        Returns:
            List of exception-related findings
        """
        logger.info(f"Running exception handling rules on repo {repo_id}")
        
        # Get all entities for this repo
        entities = self._execute_query(
            """SELECT id, entity_type, source_code, file_path, line_start, line_end 
               FROM archon_code_entities 
               WHERE repo_id = %s 
               AND (entity_type IN ('function', 'method') OR source_code LIKE '%%try:%%')""",
            (str(repo_id),)
        )
        
        all_findings = []
        
        for entity in entities:
            source_code = entity.get('source_code', '')
            if source_code and ('try:' in source_code or 'except' in source_code):
                findings = self.check_exception_handling_rules(
                    source_code=source_code,
                    file_path=entity.get('file_path', ''),
                    entity_id=entity.get('id'),
                )
                
                # Adjust line numbers relative to entity
                for finding in findings:
                    finding.entity_id = entity.get('id')
                    finding.line_start += entity.get('line_start', 0) - 1
                    finding.line_end += entity.get('line_start', 0) - 1
                    
                    # Save to database
                    self._save_finding(repo_id, finding)
                
                all_findings.extend(findings)
        
        logger.info(f"Exception rules complete: {len(all_findings)} findings")
        return all_findings

    def _save_finding(
        self,
        repo_id: str | UUID,
        finding: AuditFinding,
    ):
        """Save a finding to the database."""
        try:
            # Get rule ID from database
            rule_result = self._execute_single(
                "SELECT id FROM archon_audit_rules WHERE rule_id = %s",
                (finding.rule_id,)
            )
            
            if not rule_result:
                logger.warning(f"Rule {finding.rule_id} not found in database")
                return
            
            rule_uuid = rule_result['id']
            
            # Check if finding already exists
            existing = self._execute_single(
                """SELECT id FROM archon_audit_findings 
                   WHERE repo_id = %s AND rule_id = %s AND file_path = %s 
                   AND line_start = %s AND status = 'open'""",
                (str(repo_id), rule_uuid, finding.file_path, finding.line_start)
            )
            
            if not existing:
                # Insert new finding
                self._execute_query(
                    """INSERT INTO archon_audit_findings 
                       (rule_id, entity_id, repo_id, finding_type, severity, 
                        message, file_path, line_start, line_end, status)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'open')""",
                    (rule_uuid, finding.entity_id, str(repo_id), finding.finding_type,
                     finding.severity, finding.message, finding.file_path,
                     finding.line_start, finding.line_end)
                )
        except Exception as e:
            logger.exception(f"Failed to save finding: {e}")

    # =================================================================
    # ASSERTION QUALITY RULES (P1)
    # =================================================================

    def check_assertion_quality_rules(
        self,
        source_code: str,
        file_path: str,
        entity_id: str | None = None,
    ) -> list[AuditFinding]:
        """
        Check test source code for assertion quality violations.

        Args:
            source_code: The source code to analyze
            file_path: Path to the file
            entity_id: Optional entity ID

        Returns:
            List of AuditFinding objects for assertion violations
        """
        if not source_code:
            return []

        findings = []

        # Skip if not a test file
        is_test_file = bool(
            re.search(r'[\._-]test', file_path, re.IGNORECASE) or
            re.search(r'tests?[/\\]', file_path, re.IGNORECASE) or
            re.search(r'__tests__', file_path) or
            file_path.endswith('.spec.py') or
            file_path.endswith('.test.py')
        )

        if not is_test_file:
            return findings

        lines = source_code.split('\n')

        # Rule: assert-missing-in-test - Check test functions missing assertions
        # Find test functions
        test_func_pattern = r'^\s*(async\s+)?def\s+(test_\w+|\w+_test)\s*\('
        assertion_pattern = r'\b(assert\w*|expect|should|fail|assert_called)'

        in_test_function = False
        test_start_line = 0
        test_has_assertion = False
        test_indent = 0

        for i, line in enumerate(lines):
            line_num = i + 1

            # Detect test function start
            test_match = re.match(test_func_pattern, line)
            if test_match:
                # Check previous test function
                if in_test_function and not test_has_assertion:
                    findings.append(AuditFinding(
                        rule_id='assert-missing-in-test',
                        severity='warning',
                        message=f'Test function at line {test_start_line} has no assertions',
                        file_path=file_path,
                        line_start=test_start_line,
                        line_end=i,
                    ))

                in_test_function = True
                test_start_line = line_num
                test_has_assertion = False
                test_indent = len(line) - len(line.lstrip())
                continue

            # Check for assertions within test function
            if in_test_function:
                current_indent = len(line) - len(line.lstrip())

                # End of test function (dedented)
                if line.strip() and current_indent <= test_indent:
                    if not test_has_assertion:
                        findings.append(AuditFinding(
                            rule_id='assert-missing-in-test',
                            severity='warning',
                            message=f'Test function at line {test_start_line} has no assertions',
                            file_path=file_path,
                            line_start=test_start_line,
                            line_end=line_num - 1,
                        ))
                    in_test_function = False
                    continue

                # Check for assertion patterns
                if re.search(assertion_pattern, line, re.IGNORECASE):
                    test_has_assertion = True

        # Check last function if file ends
        if in_test_function and not test_has_assertion:
            findings.append(AuditFinding(
                rule_id='assert-missing-in-test',
                severity='warning',
                message=f'Test function at line {test_start_line} has no assertions',
                file_path=file_path,
                line_start=test_start_line,
                line_end=len(lines),
            ))

        # Rule: assert-weak-boolean - Check weak boolean assertions
        weak_bool_pattern = r'\.assertTrue\s*\(\s*\w+\s*\)'
        for i, line in enumerate(lines):
            if re.search(weak_bool_pattern, line):
                findings.append(AuditFinding(
                    rule_id='assert-weak-boolean',
                    severity='info',
                    message=f'Weak boolean assertion at line {i + 1}: use assertEqual with expected/actual',
                    file_path=file_path,
                    line_start=i + 1,
                    line_end=i + 1,
                ))

        # Rule: assert-equality-on-floats - Check float equality assertions
        float_equal_pattern = r'\.assertEqual\s*\([^,]+,\s*[0-9]+\.[0-9]+\s*\)'
        for i, line in enumerate(lines):
            if re.search(float_equal_pattern, line):
                findings.append(AuditFinding(
                    rule_id='assert-equality-on-floats',
                    severity='warning',
                    message=f'Float equality assertion at line {i + 1}: use assertAlmostEqual',
                    file_path=file_path,
                    line_start=i + 1,
                    line_end=i + 1,
                ))

        # Rule: assert-mock-not-verified - Check mock objects not verified
        mock_pattern = r'\bMock\s*\(|MagicMock|mock\.\w+'
        mock_verify_pattern = r'assert_called|assert_called_with|assert_called_once'

        has_mock = False
        mock_line = 0
        has_mock_verify = False

        for i, line in enumerate(lines):
            if re.search(mock_pattern, line):
                has_mock = True
                mock_line = i + 1

            if re.search(mock_verify_pattern, line):
                has_mock_verify = True

        if has_mock and not has_mock_verify:
            findings.append(AuditFinding(
                rule_id='assert-mock-not-verified',
                severity='warning',
                message=f'Mock created at line {mock_line} but not verified: add assert_called',
                file_path=file_path,
                line_start=mock_line,
                line_end=mock_line,
            ))

        return findings

    def run_assertion_rules_on_repo(
        self,
        repo_id: str | UUID,
    ) -> list[AuditFinding]:
        """
        Run assertion quality rules on all test entities in a repository.

        Args:
            repo_id: Repository ID

        Returns:
            List of assertion-related findings
        """
        logger.info(f"Running assertion quality rules on repo {repo_id}")

        # Get all test-related entities for this repo
        entities = self._execute_query(
            """SELECT id, entity_type, source_code, file_path, line_start, line_end
               FROM archon_code_entities
               WHERE repo_id = %s
               AND (
                   file_path LIKE '%%test%%'
                   OR file_path LIKE '%%_test.%%'
                   OR file_path LIKE '%%.test.%%'
                   OR file_path LIKE '%%/tests/%%'
                   OR file_path LIKE '%%__tests__%%'
               )""",
            (str(repo_id),)
        )

        all_findings = []

        for entity in entities:
            source_code = entity.get('source_code', '')
            if source_code:
                findings = self.check_assertion_quality_rules(
                    source_code=source_code,
                    file_path=entity.get('file_path', ''),
                    entity_id=entity.get('id'),
                )

                # Adjust line numbers relative to entity
                for finding in findings:
                    finding.entity_id = entity.get('id')
                    finding.line_start += entity.get('line_start', 0) - 1
                    finding.line_end += entity.get('line_start', 0) - 1

                    # Save to database
                    self._save_finding(repo_id, finding)

                all_findings.extend(findings)

        logger.info(f"Assertion rules complete: {len(all_findings)} findings")
        return all_findings

    # =================================================================
    # AUDIT RULES METHODS
    # =================================================================
    
    def get_audit_rules(
        self, 
        category: str | None = None,
        is_active: bool = True
    ) -> list[AuditRule]:
        """Get audit rules, optionally filtered by category."""
        query = "SELECT * FROM archon_audit_rules"
        conditions = []
        params = []
        
        if is_active:
            conditions.append("is_active = %s")
            params.append(True)
        
        if category:
            conditions.append("category = %s")
            params.append(category)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        result = self._execute_query(query, tuple(params))
        
        rules = []
        for row in result:
            methodology_tags = row.get("methodology_tags", [])
            if isinstance(methodology_tags, str):
                try:
                    methodology_tags = json.loads(methodology_tags)
                except json.JSONDecodeError:
                    methodology_tags = []
            
            configuration = row.get("configuration", {})
            if isinstance(configuration, str):
                try:
                    configuration = json.loads(configuration)
                except json.JSONDecodeError:
                    configuration = {}
            
            references = row.get("references", [])
            if references is None:
                references = []
            
            rules.append(AuditRule(
                id=row.get("id"),
                rule_id=row.get("rule_id"),
                name=row.get("name"),
                description=row.get("description"),
                category=row.get("category"),
                severity=row.get("severity"),
                rule_type=row.get("rule_type"),
                configuration=configuration,
                threshold_min=row.get("threshold_min"),
                threshold_max=row.get("threshold_max"),
                pattern=row.get("pattern"),
                applies_to=row.get("applies_to", []),
                languages=row.get("languages"),
                file_patterns=row.get("file_patterns"),
                is_active=row.get("is_active", True),
                is_builtin=row.get("is_builtin", False),
                implementation_type=row.get("implementation_type", "threshold"),
                rationale=row.get("rationale", ""),
                remediation_guidance=row.get("remediation_guidance", ""),
                example_violation=row.get("example_violation", ""),
                example_fix=row.get("example_fix", ""),
                references=references,
                methodology_tags=methodology_tags,
                applies_to_tdd=row.get("applies_to_tdd", False),
                applies_to_doc_driven=row.get("applies_to_doc_driven", False),
                applies_to_security_first=row.get("applies_to_security_first", False),
                owasp_category=row.get("owasp_category", ""),
                cwe_id=row.get("cwe_id", ""),
                estimated_fix_time_minutes=row.get("estimated_fix_time_minutes", 0) or 0,
            ))
        
        return rules

    def run_audit(
        self, 
        repo_id: str | UUID,
        ruleset: list[str] | None = None
    ) -> tuple[int, str]:
        """Run audit on a repository."""
        logger.info(f"Starting audit for repo {repo_id}")
        
        # Run exception handling rules first
        exception_findings = self.run_exception_rules_on_repo(repo_id)
        
        # Create audit run record
        run_id = self._execute_single(
            """INSERT INTO archon_audit_runs 
               (repo_id, name, status, started_at, total_entities)
               VALUES (%s, %s, %s, NOW(), 
                       (SELECT COUNT(*) FROM archon_code_entities WHERE repo_id = %s))
               RETURNING id""",
            (str(repo_id), f"Audit run for repo {repo_id}", "running", str(repo_id))
        )
        
        if not run_id:
            logger.error("Failed to create audit run")
            return 0, None
        
        run_id = run_id["id"]
        
        # Get rules to check
        if ruleset:
            rules_query = "SELECT * FROM archon_audit_rules WHERE rule_id = ANY(%s) AND is_active = TRUE"
            rules = self._execute_query(rules_query, (ruleset,))
        else:
            rules = self._execute_query(
                "SELECT * FROM archon_audit_rules WHERE is_active = TRUE"
            )
        
        findings_count = len(exception_findings)
        
        # Check each entity against rules
        entities = self._execute_query(
            "SELECT id, entity_type, name, file_path, line_start, line_end, source_code FROM archon_code_entities WHERE repo_id = %s",
            (str(repo_id),)
        )
        
        for entity in entities:
            for rule in rules:
                # Simple threshold check for complexity
                if rule["rule_type"] == "threshold":
                    if rule["configuration"].get("metric") == "cyclomatic_complexity":
                        # Calculate complexity
                        complexity = self.calculate_cyclomatic_complexity(
                            entity.get("source_code", ""),
                            self._detect_language(entity.get("file_path", ""))
                        )
                        
                        threshold_max = rule.get("threshold_max")
                        if threshold_max and complexity > threshold_max:
                            self._execute_query(
                                """INSERT INTO archon_audit_findings
                                   (rule_id, entity_id, repo_id, finding_type, severity, message,
                                    file_path, line_start, line_end, audit_run_id)
                                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                                (str(rule["id"]), str(entity["id"]), str(repo_id), "violation",
                                 rule["severity"], 
                                 f"{rule['name']}: complexity {complexity} exceeds threshold {threshold_max}",
                                 entity.get("file_path", ""), entity.get("line_start", 0),
                                 entity.get("line_end", 0), run_id)
                            )
                            findings_count += 1
        
        # Update audit run
        self._execute_query(
            """UPDATE archon_audit_runs 
               SET status = %s, completed_at = NOW(), findings_count = %s
               WHERE id = %s""",
            ("completed", findings_count, run_id)
        )
        
        logger.info(f"Audit completed: {findings_count} findings, run_id={run_id}")
        return findings_count, run_id

    def get_audit_findings(
        self,
        repo_id: str | UUID | None = None,
        status: str = "open",
        severity: str | None = None,
        limit: int = 100
    ) -> list[AuditFinding]:
        """Get audit findings with optional filters."""
        query = """SELECT f.*, r.rule_id as rule_rule_id, r.name as rule_name, r.category as rule_category 
                   FROM archon_audit_findings f
                   LEFT JOIN archon_audit_rules r ON r.id = f.rule_id
                   WHERE 1=1"""
        params = []
        
        if repo_id:
            query += " AND f.repo_id = %s"
            params.append(str(repo_id))
        
        if status:
            query += " AND f.status = %s"
            params.append(status)
        
        if severity:
            query += " AND f.severity = %s"
            params.append(severity)
        
        query += " ORDER BY f.created_at DESC LIMIT %s"
        params.append(limit)
        
        result = self._execute_query(query, tuple(params))
        
        findings = []
        for row in result:
            rule_id = row.get("rule_rule_id") or row.get("rule_id")
            findings.append(AuditFinding(
                rule_id=rule_id,
                entity_id=row.get("entity_id"),
                finding_type=row.get("finding_type", "violation"),
                severity=row.get("severity", "warning"),
                message=row.get("message", ""),
                description=row.get("description", ""),
                file_path=row.get("file_path", ""),
                line_start=row.get("line_start", 0),
                line_end=row.get("line_end", 0),
                code_snippet=row.get("code_snippet", ""),
                suggested_fix=row.get("suggested_fix", ""),
            ))
        
        return findings

    def get_audit_summary(self, repo_id: str | UUID | None = None) -> dict[str, Any]:
        """Get audit summary statistics."""
        if repo_id:
            result = self._execute_single(
                "SELECT * FROM archon_audit_summary WHERE repo_id = %s",
                (str(repo_id),)
            )
        else:
            result = self._execute_single("SELECT * FROM archon_audit_summary LIMIT 1")
        
        return dict(result) if result else {}

    def acknowledge_finding(
        self, 
        finding_id: str | UUID,
        resolution_note: str = "",
        resolved: bool = False
    ) -> bool:
        """Acknowledge or resolve an audit finding."""
        try:
            status = "resolved" if resolved else "acknowledged"
            now = datetime.now().isoformat()
            
            if resolved:
                self._execute_query(
                    """UPDATE archon_audit_findings 
                       SET status = %s, resolution_note = %s, 
                           resolved_at = %s, resolved_by = %s
                       WHERE id = %s""",
                    (status, resolution_note, now, "system", str(finding_id))
                )
            else:
                self._execute_query(
                    """UPDATE archon_audit_findings 
                       SET status = %s, resolution_note = %s, 
                           acknowledged_at = %s, acknowledged_by = %s
                       WHERE id = %s""",
                    (status, resolution_note, now, "system", str(finding_id))
                )
            
            return True
        except Exception as e:
            logger.exception("Failed to acknowledge finding: %s", str(e))
            return False


# Singleton instance
_code_metrics_service: CodeMetricsService | None = None


def get_code_metrics_service(db_connection=None) -> CodeMetricsService:
    """Get or create singleton metrics service."""
    global _code_metrics_service
    if _code_metrics_service is None:
        _code_metrics_service = CodeMetricsService(db_connection)
    return _code_metrics_service
