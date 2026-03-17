"""Test Companion Check Service

Checks that source files have corresponding test files.
Stores findings in archon_semgrep_findings with source='companion-check'.
"""

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg2
from psycopg2.extras import RealDictCursor

from src.server.config.logfire_config import get_logger

logger = get_logger(__name__)


@dataclass
class CompanionFinding:
    """A missing test companion finding."""
    
    source_file: str
    expected_test: str
    pattern: str  # e.g., 'test_{module}.py'
    
    def to_db_dict(self, repo_id: UUID) -> dict[str, Any]:
        """Convert to dict for database insertion."""
        return {
            "repo_id": str(repo_id),
            "source": "companion-check",
            "semgrep_check_id": "testing/missing-test-companion",
            "semgrep_rule_url": "",
            "message": f"Source file '{self.source_file}' is missing test companion '{self.expected_test}'",
            "severity": "WARNING",
            "confidence": "high",
            "file_path": self.source_file,
            "line_start": 1,
            "line_end": 1,
            "column_start": 0,
            "column_end": 0,
            "code_snippet": f"Expected test pattern: {self.pattern}",
            "metavariables": json.dumps({
                "source_file": self.source_file,
                "expected_test": self.expected_test,
                "pattern": self.pattern,
            }),
            "data_flow": json.dumps({}),
        }


class CompanionCheckService:
    """Service for checking test companion files."""
    
    # Default patterns by language
    DEFAULT_PATTERNS = {
        "python": {
            "source_dirs": ["src", "."],
            "test_dirs": ["tests", "test"],
            "pattern": "test_{module}.py",
            "source_ext": ".py",
            "test_ext": "_test.py",  # Alternative pattern
        },
        "typescript": {
            "source_dirs": ["src", "app", "."],
            "test_dirs": ["tests", "test", "__tests__"],
            "pattern": "{module}.test.ts",
            "source_ext": ".ts",
            "alt_ext": ".tsx",
        },
        "javascript": {
            "source_dirs": ["src", "app", "."],
            "test_dirs": ["tests", "test", "__tests__"],
            "pattern": "{module}.test.js",
            "source_ext": ".js",
            "alt_ext": ".jsx",
        },
    }
    
    def __init__(self, db_connection=None):
        self._db = db_connection
        self._connection_string = "postgresql://archon:archon_local_dev@localhost:5434/archon"
    
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
    
    def _get_methodology_config(self, repo_id: UUID) -> dict:
        """Get methodology config for repo."""
        try:
            result = self._execute_query(
                "SELECT methodology FROM archon_code_repos WHERE id = %s",
                (str(repo_id),)
            )
            if result and result[0].get("methodology"):
                meth = result[0]["methodology"]
                if isinstance(meth, dict):
                    return meth
                return json.loads(meth)
        except Exception as e:
            logger.warning(f"Could not get methodology: {e}")
        
        # Default config
        return {
            "primary": "tdd",
            "enforce": ["coverage", "docstrings", "test_companions"],
            "test_companion_pattern": "test_{module}.py",
        }
    
    def check_python_companions(
        self,
        repo_path: str | Path,
        repo_id: UUID,
    ) -> list[CompanionFinding]:
        """Check Python source files have test companions."""
        repo_path = Path(repo_path)
        findings = []
        
        config = self._get_methodology_config(repo_id)
        if "test_companions" not in config.get("enforce", []):
            logger.info("Test companion check disabled for this repo")
            return []
        
        pattern_template = config.get("test_companion_pattern", "test_{module}.py")
        
        # Find Python source files - ONLY in src/ directory, not root
        source_dirs = [repo_path / "src"] if (repo_path / "src").exists() else [repo_path]
        test_dirs = [repo_path / d for d in ["tests", "test"] if (repo_path / d).exists()]
        
        # Directories to exclude
        excluded_dirs = {".venv", "__pycache__", ".git", "node_modules", ".pytest_cache", ".mypy_cache", "build", "dist"}
        
        for src_dir in source_dirs:
            if not src_dir.exists():
                continue
            
            for py_file in src_dir.rglob("*.py"):
                # Skip excluded directories
                if any(excluded in str(py_file) for excluded in excluded_dirs):
                    continue
                # Skip test files, __init__.py, etc.
                if py_file.name.startswith("test_") or py_file.name.endswith("_test.py"):
                    continue
                if py_file.name.startswith("__"):
                    continue
                
                # Get module name
                rel_path = py_file.relative_to(repo_path)
                module_name = py_file.stem
                
                # Calculate expected test file
                expected_test = pattern_template.replace("{module}", module_name)
                
                # Check if test exists
                test_found = False
                for test_dir in test_dirs:
                    test_file = test_dir / expected_test
                    if test_file.exists():
                        test_found = True
                        break
                    # Also check _test.py pattern
                    alt_test = f"{module_name}_test.py"
                    if (test_dir / alt_test).exists():
                        test_found = True
                        break
                
                if not test_found:
                    findings.append(CompanionFinding(
                        source_file=str(rel_path),
                        expected_test=expected_test,
                        pattern=pattern_template,
                    ))
        
        logger.info(f"Found {len(findings)} Python files missing test companions")
        return findings
    
    def check_typescript_companions(
        self,
        repo_path: str | Path,
        repo_id: UUID,
    ) -> list[CompanionFinding]:
        """Check TypeScript source files have test companions."""
        repo_path = Path(repo_path)
        findings = []
        
        config = self._get_methodology_config(repo_id)
        if "test_companions" not in config.get("enforce", []):
            return []
        
        # Find TypeScript source files
        source_dirs = [repo_path / d for d in ["src", "app", "."]]
        test_dirs = [repo_path / d for d in ["tests", "test", "__tests__"]]
        
        for src_dir in source_dirs:
            if not src_dir.exists():
                continue
            
            for ts_file in src_dir.rglob("*.ts"):
                if ts_file.name.endswith(".test.ts") or ts_file.name.endswith(".spec.ts"):
                    continue
                
                rel_path = ts_file.relative_to(repo_path)
                module_name = ts_file.stem
                
                # Expected test file
                expected_test = f"{module_name}.test.ts"
                
                # Check if test exists
                test_found = False
                for test_dir in test_dirs:
                    if (test_dir / expected_test).exists():
                        test_found = True
                        break
                
                if not test_found:
                    findings.append(CompanionFinding(
                        source_file=str(rel_path),
                        expected_test=expected_test,
                        pattern="{module}.test.ts",
                    ))
        
        logger.info(f"Found {len(findings)} TypeScript files missing test companions")
        return findings
    
    def save_companion_findings(
        self,
        findings: list[CompanionFinding],
        repo_id: UUID,
    ) -> int:
        """Save companion check findings to database."""
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
                logger.info(f"Saved {saved_count} companion check findings")
                return saved_count
                
        except Exception as e:
            logger.exception(f"Failed to save companion findings: {e}")
            conn.rollback()
            return 0
    
    def run_companion_check(
        self,
        repo_path: str | Path,
        repo_id: UUID,
    ) -> dict[str, Any]:
        """Run appropriate companion check based on repo type."""
        repo_path = Path(repo_path)
        
        all_findings = []
        
        # Check for Python files
        if list(repo_path.rglob("*.py")):
            py_findings = self.check_python_companions(repo_path, repo_id)
            all_findings.extend(py_findings)
        
        # Check for TypeScript files
        if list(repo_path.rglob("*.ts")):
            ts_findings = self.check_typescript_companions(repo_path, repo_id)
            all_findings.extend(ts_findings)
        
        # Save findings
        saved = self.save_companion_findings(all_findings, repo_id)
        
        return {
            "findings_count": len(all_findings),
            "saved_count": saved,
        }


# Singleton instance
_companion_service: CompanionCheckService | None = None


def get_companion_check_service(db_connection=None) -> CompanionCheckService:
    """Get or create singleton companion check service."""
    global _companion_service
    if _companion_service is None:
        _companion_service = CompanionCheckService(db_connection)
    return _companion_service
