"""Nim Audit Adapter Service

Uses existing tree-sitter Nim parser to audit Nim code.
Checks for:
- Missing doc comments (## style)
- Discarded non-trivial return values
- Missing test companions

Stores findings in archon_semgrep_findings with source='nim-tree-sitter-audit'.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg2
from psycopg2.extras import RealDictCursor
from tree_sitter import Language, Parser

from src.server.config.logfire_config import get_logger

logger = get_logger(__name__)


@dataclass
class NimFinding:
    """A Nim audit finding."""
    
    file_path: str
    line_start: int
    line_end: int
    check_id: str
    message: str
    code_snippet: str
    
    def to_db_dict(self, repo_id: UUID) -> dict[str, Any]:
        """Convert to dict for database insertion."""
        return {
            "repo_id": str(repo_id),
            "source": "nim-tree-sitter-audit",
            "semgrep_check_id": self.check_id,
            "semgrep_rule_url": "",
            "message": self.message,
            "severity": "WARNING",
            "confidence": "medium",
            "file_path": self.file_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "column_start": 0,
            "column_end": 0,
            "code_snippet": self.code_snippet,
            "metavariables": json.dumps({
                "language": "nim",
                "check_type": self.check_id,
            }),
            "data_flow": json.dumps({}),
        }


class NimAuditService:
    """Service for auditing Nim code using tree-sitter."""
    
    def __init__(self, db_connection=None):
        self._db = db_connection
        # Use DATABASE_URL from env or default to Docker compose postgres
        import os
        db_url = os.getenv("ARCHON_DATABASE_URL", "postgresql://archon:archon_local_dev@postgres:5432/archon")
        # Convert asyncpg URL to psycopg2 format if needed
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql://", 1)
        self._connection_string = db_url
        self._parser = None
        self._language = None
    
    def _get_db(self):
        """Get database connection."""
        if self._db is None:
            self._db = psycopg2.connect(self._connection_string)
        return self._db
    
    def _execute_query(self, query: str, params: tuple = (), commit: bool = False) -> list[dict]:
        """Execute a query and return results."""
        conn = self._get_db()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            if cur.description:
                result = [dict(row) for row in cur.fetchall()]
                if commit:
                    conn.commit()
                return result
            if commit:
                conn.commit()
            return []
    
    def _get_parser(self) -> Parser:
        """Get or create tree-sitter Nim parser."""
        if self._parser is None:
            try:
                # Try to load Nim language from tree-sitter-language-pack
                from tree_sitter_language_pack import get_language
                self._language = get_language("nim")
                self._parser = Parser(self._language)
            except Exception as e:
                logger.error(f"Could not load Nim language: {e}")
                return None
        return self._parser
    
    def check_missing_doc_comments(
        self,
        repo_path: Path,
        repo_id: UUID,
    ) -> list[NimFinding]:
        """Check for Nim procedures missing doc comments."""
        findings = []
        parser = self._get_parser()
        
        if parser is None:
            logger.warning("Nim parser not available")
            return []
        
        # Find Nim files
        for nim_file in repo_path.rglob("*.nim"):
            if nim_file.name.endswith("_test.nim") or "/tests/" in str(nim_file):
                continue
            
            try:
                with open(nim_file, "rb") as f:
                    source = f.read()
                
                tree = parser.parse(source)
                
                # Find procedures
                query = self._language.query("""
                    (proc_declaration
                        (identifier) @proc_name) @proc
                """)
                
                captures = query.captures(tree.root_node)
                for capture_name, capture_nodes in captures.items():
                    if capture_name != "proc":
                        continue
                    for proc_node in capture_nodes:
                        # Check if previous line is doc comment
                        has_doc = False
                        if proc_node.start_point[0] > 0:
                            lines = source.decode("utf-8", errors="replace").split("\n")
                            prev_line = lines[proc_node.start_point[0] - 1].strip()
                            if prev_line.startswith("##"):
                                has_doc = True
                        
                        if not has_doc:
                            # Get proc name
                            proc_name = source[proc_node.start_byte:proc_node.end_byte].decode("utf-8", errors="replace")
                            
                            findings.append(NimFinding(
                                file_path=str(nim_file.relative_to(repo_path)),
                                line_start=proc_node.start_point[0] + 1,
                                line_end=proc_node.end_point[0] + 1,
                                check_id="nim/missing-doc-comment",
                                message=f"Procedure '{proc_name}' is missing a doc comment (##)",
                                code_snippet=proc_name[:80],
                            ))
                        
            except Exception as e:
                logger.warning(f"Could not parse {nim_file}: {e}")
                continue
        
        logger.info(f"Found {len(findings)} Nim procedures missing doc comments")
        return findings
    
    def check_discard_usage(
        self,
        repo_path: Path,
        repo_id: UUID,
    ) -> list[NimFinding]:
        """Check for suspicious discard usage."""
        findings = []
        
        for nim_file in repo_path.rglob("*.nim"):
            try:
                with open(nim_file, "r") as f:
                    lines = f.readlines()
                
                for i, line in enumerate(lines):
                    # Check for discard on non-trivial expressions
                    if line.strip().startswith("discard") and not line.strip().startswith("discard result"):
                        # Simple heuristic: check if it's discarding a function call
                        if "(" in line and ")" in line:
                            findings.append(NimFinding(
                                file_path=str(nim_file.relative_to(repo_path)),
                                line_start=i + 1,
                                line_end=i + 1,
                                check_id="nim/suspicious-discard",
                                message="Non-trivial return value is being discarded. Consider handling the result.",
                                code_snippet=line.strip()[:80],
                            ))
                            
            except Exception as e:
                logger.warning(f"Could not read {nim_file}: {e}")
                continue
        
        logger.info(f"Found {len(findings)} suspicious discard usages")
        return findings
    
    def check_test_companions(
        self,
        repo_path: Path,
        repo_id: UUID,
    ) -> list[NimFinding]:
        """Check for Nim files missing test companions."""
        findings = []
        
        src_dir = repo_path / "src"
        tests_dir = repo_path / "tests"
        
        if not src_dir.exists() or not tests_dir.exists():
            return []
        
        for nim_file in src_dir.rglob("*.nim"):
            if nim_file.name.startswith("_"):
                continue
            
            # Expected test file
            test_file = tests_dir / f"{nim_file.stem}_test.nim"
            
            if not test_file.exists():
                findings.append(NimFinding(
                    file_path=str(nim_file.relative_to(repo_path)),
                    line_start=1,
                    line_end=1,
                    check_id="nim/missing-test-companion",
                    message=f"Nim module '{nim_file.name}' is missing test companion '{test_file.name}'",
                    code_snippet=f"Expected test: tests/{test_file.name}",
                ))
        
        logger.info(f"Found {len(findings)} Nim files missing test companions")
        return findings
    
    def save_nim_findings(
        self,
        findings: list[NimFinding],
        repo_id: UUID,
    ) -> int:
        """Save Nim audit findings to database."""
        if not findings:
            return 0
        
        conn = self._get_db()
        saved_count = 0
        
        try:
            with conn.cursor() as cur:
                for finding in findings:
                    data = finding.to_db_dict(repo_id)
                    cur.execute("""
                        INSERT INTO archon_semgrep_findings (
                            repo_id, source, semgrep_check_id, semgrep_rule_url,
                            message, severity, confidence, file_path,
                            line_start, line_end, column_start, column_end,
                            code_snippet, metavariables, data_flow
                        ) VALUES (
                            %(repo_id)s, %(source)s, %(semgrep_check_id)s, %(semgrep_rule_url)s,
                            %(message)s, %(severity)s, %(confidence)s, %(file_path)s,
                            %(line_start)s, %(line_end)s, %(column_start)s, %(column_end)s,
                            %(code_snippet)s, %(metavariables)s, %(data_flow)s
                        )
                        ON CONFLICT DO NOTHING
                    """, data)
                    saved_count += 1
                
                conn.commit()
                logger.info(f"Saved {saved_count} Nim audit findings")
                return saved_count
                
        except Exception as e:
            logger.exception(f"Failed to save Nim findings: {e}")
            conn.rollback()
            return 0
    
    def run_nim_audit(
        self,
        repo_path: str | Path,
        repo_id: UUID,
    ) -> dict[str, Any]:
        """Run full Nim audit."""
        repo_path = Path(repo_path)
        
        # Check if this is a Nim project
        if not list(repo_path.rglob("*.nim")):
            return {
                "findings_count": 0,
                "saved_count": 0,
                "message": "No Nim files found",
            }
        
        findings = []
        
        # Run checks
        findings.extend(self.check_missing_doc_comments(repo_path, repo_id))
        findings.extend(self.check_discard_usage(repo_path, repo_id))
        findings.extend(self.check_test_companions(repo_path, repo_id))
        
        # Save findings
        saved = self.save_nim_findings(findings, repo_id)
        
        return {
            "findings_count": len(findings),
            "saved_count": saved,
        }


# Singleton instance
_nim_audit_service: NimAuditService | None = None


def get_nim_audit_service(db_connection=None) -> NimAuditService:
    """Get or create singleton Nim audit service."""
    global _nim_audit_service
    if _nim_audit_service is None:
        _nim_audit_service = NimAuditService(db_connection)
    return _nim_audit_service
