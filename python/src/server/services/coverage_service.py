"""Coverage Integration Service

Ingests coverage data from pytest-cov (Python) and c8 (TypeScript/JavaScript)
and stores findings in archon_semgrep_findings with source='pytest-cov' or 'c8'.
"""

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg2
from psycopg2.extras import RealDictCursor

from src.server.config.logfire_config import get_logger

logger = get_logger(__name__)


@dataclass
class CoverageFinding:
    """A coverage finding - stored like Semgrep findings but different source."""
    
    file_path: str
    coverage_pct: float
    lines_covered: int
    lines_total: int
    threshold: float
    source: str  # 'pytest-cov' or 'c8'
    
    def to_db_dict(self, repo_id: UUID) -> dict[str, Any]:
        """Convert to dict for database insertion."""
        return {
            "repo_id": str(repo_id),
            "source": self.source,
            "semgrep_check_id": "coverage/below-threshold",
            "semgrep_rule_url": "",
            "message": f"Code coverage {self.coverage_pct:.1f}% is below threshold {self.threshold}%",
            "severity": "WARNING",
            "confidence": "high",
            "file_path": self.file_path,
            "line_start": 1,
            "line_end": 1,
            "column_start": 0,
            "column_end": 0,
            "code_snippet": f"Coverage: {self.lines_covered}/{self.lines_total} lines ({self.coverage_pct:.1f}%)",
            "metavariables": json.dumps({
                "coverage_pct": self.coverage_pct,
                "threshold": self.threshold,
                "lines_covered": self.lines_covered,
                "lines_total": self.lines_total,
            }),
            "data_flow": json.dumps({}),
        }


class CoverageService:
    """Service for ingesting coverage data from various sources."""
    
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
    
    def _get_coverage_threshold(self, repo_id: UUID) -> int:
        """Get coverage threshold for repo from config."""
        try:
            result = self._execute_query(
                "SELECT coverage_threshold FROM archon_code_repos WHERE id = %s",
                (str(repo_id),)
            )
            if result and result[0].get("coverage_threshold"):
                return result[0]["coverage_threshold"]
        except Exception as e:
            logger.warning(f"Could not get coverage threshold: {e}")
        
        # Default threshold
        return 80
    
    def run_pytest_cov(
        self,
        repo_path: str | Path,
        repo_id: UUID,
        threshold: int | None = None,
    ) -> list[CoverageFinding]:
        """
        Run pytest with coverage and ingest findings.
        
        Args:
            repo_path: Path to Python repository
            repo_id: Repository UUID
            threshold: Coverage threshold (default from repo config)
            
        Returns:
            List of CoverageFinding objects for files below threshold
        """
        repo_path = Path(repo_path)
        threshold = threshold or self._get_coverage_threshold(repo_id)
        
        logger.info(f"Running pytest-cov on {repo_path} with threshold {threshold}%")
        
        # Run pytest with coverage
        coverage_file = repo_path / ".coverage.json"
        try:
            result = subprocess.run(
                [
                    "python", "-m", "pytest",
                    "--cov", str(repo_path),
                    "--cov-report", f"json:{coverage_file}",
                    "-x",  # Stop on first failure (we just want coverage)
                ],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=300,
            )
            
            # pytest returns non-zero if tests fail, but coverage may still be generated
            if not coverage_file.exists():
                logger.error("Coverage file not generated")
                return []
            
            # Parse coverage JSON
            with open(coverage_file) as f:
                coverage_data = json.load(f)
            
            findings = self._parse_pytest_cov(coverage_data, threshold)
            logger.info(f"pytest-cov found {len(findings)} files below {threshold}%")
            
            # Cleanup
            coverage_file.unlink(missing_ok=True)
            
            return findings
            
        except FileNotFoundError:
            logger.error("pytest not found or no tests in repo")
            return []
        except subprocess.TimeoutExpired:
            logger.error("pytest-cov timed out after 5 minutes")
            return []
        except Exception as e:
            logger.exception(f"Failed to run pytest-cov: {e}")
            return []
    
    def _parse_pytest_cov(self, coverage_data: dict, threshold: float) -> list[CoverageFinding]:
        """Parse pytest-cov JSON output."""
        findings = []
        
        files = coverage_data.get("files", {})
        for file_path, file_data in files.items():
            if file_path.startswith("test_") or file_path.endswith("_test.py"):
                continue  # Skip test files
            
            summary = file_data.get("summary", {})
            covered = summary.get("covered_lines", 0)
            total = summary.get("num_statements", 0)
            
            if total == 0:
                continue
            
            pct = (covered / total) * 100
            
            if pct < threshold:
                findings.append(CoverageFinding(
                    file_path=file_path,
                    coverage_pct=pct,
                    lines_covered=covered,
                    lines_total=total,
                    threshold=threshold,
                    source="pytest-cov",
                ))
        
        return findings
    
    def run_c8(
        self,
        repo_path: str | Path,
        repo_id: UUID,
        threshold: int | None = None,
    ) -> list[CoverageFinding]:
        """
        Run c8 coverage for TypeScript/JavaScript and ingest findings.
        
        Args:
            repo_path: Path to TypeScript/JavaScript repository
            repo_id: Repository UUID
            threshold: Coverage threshold (default from repo config)
            
        Returns:
            List of CoverageFinding objects for files below threshold
        """
        repo_path = Path(repo_path)
        threshold = threshold or self._get_coverage_threshold(repo_id)
        
        logger.info(f"Running c8 on {repo_path} with threshold {threshold}%")
        
        # Check for c8 in package.json
        package_json = repo_path / "package.json"
        if not package_json.exists():
            logger.error("No package.json found - not a Node.js project")
            return []
        
        # Check if c8 is available
        try:
            result = subprocess.run(
                ["npx", "c8", "--version"],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                logger.error("c8 not available (try: npm install --save-dev c8)")
                return []
        except FileNotFoundError:
            logger.error("npm/npx not found")
            return []
        
        # Run c8 - must wrap the actual test command
        try:
            # Detect test runner from package.json
            import json
            with open(package_json) as f:
                pkg = json.load(f)
            
            scripts = pkg.get("scripts", {})
            
            # Determine test command - prefer vitest, then jest, then npm test
            if "test:coverage" in scripts:
                test_cmd = ["npm", "run", "test:coverage"]
            elif "test:unit" in scripts:
                test_cmd = ["npm", "run", "test:unit"]
            elif "test" in scripts:
                test_cmd = ["npm", "test"]
            elif "vitest" in str(pkg.get("devDependencies", {})):
                test_cmd = ["npx", "vitest", "run", "--coverage"]
            else:
                test_cmd = ["npx", "vitest", "run"]
            
            # Run c8 wrapping the test command
            result = subprocess.run(
                [
                    "npx", "c8",
                    "--reporter=json-summary",
                    "--report-dir", str(repo_path / "coverage"),
                    "--all",
                ] + test_cmd,
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout for tests
            )
            
            # c8 always "fails" because we ran echo, but coverage should be generated
            summary_file = repo_path / "coverage" / "coverage-summary.json"
            if not summary_file.exists():
                logger.error("c8 coverage summary not generated")
                return []
            
            with open(summary_file) as f:
                coverage_data = json.load(f)
            
            findings = self._parse_c8(coverage_data, threshold, str(repo_path))
            logger.info(f"c8 found {len(findings)} files below {threshold}%")
            
            return findings
            
        except subprocess.TimeoutExpired:
            logger.error("c8 timed out")
            return []
        except Exception as e:
            logger.exception(f"Failed to run c8: {e}")
            return []
    
    def _parse_c8(self, coverage_data: dict, threshold: float, repo_path: str) -> list[CoverageFinding]:
        """Parse c8 JSON output."""
        findings = []
        
        for file_path, file_data in coverage_data.items():
            if file_path == "total":
                continue
            
            # Skip test files
            if "test" in file_path.lower() or "spec" in file_path.lower():
                continue
            
            pct = file_data.get("pct", 0)
            
            if pct < threshold:
                lines = file_data.get("lines", {})
                total = lines.get("total", 0)
                covered = lines.get("covered", 0)
                
                findings.append(CoverageFinding(
                    file_path=file_path.replace(f"{repo_path}/", ""),
                    coverage_pct=pct,
                    lines_covered=covered,
                    lines_total=total,
                    threshold=threshold,
                    source="c8",
                ))
        
        return findings
    
    def save_coverage_findings(
        self,
        findings: list[CoverageFinding],
        repo_id: UUID,
    ) -> int:
        """Save coverage findings to database."""
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
                logger.info(f"Saved {saved_count} coverage findings")
                return saved_count
                
        except Exception as e:
            logger.exception(f"Failed to save coverage findings: {e}")
            conn.rollback()
            return 0
    
    def run_coverage_audit(
        self,
        repo_path: str | Path,
        repo_id: UUID,
    ) -> dict[str, Any]:
        """
        Run appropriate coverage tool based on repo type.
        
        Detects repo type and runs pytest-cov or c8 accordingly.
        """
        repo_path = Path(repo_path)
        
        # Detect repo type
        if (repo_path / "package.json").exists():
            # TypeScript/JavaScript project
            findings = self.run_c8(repo_path, repo_id)
        elif (repo_path / "pyproject.toml").exists() or (repo_path / "setup.py").exists():
            # Python project
            findings = self.run_pytest_cov(repo_path, repo_id)
        else:
            logger.warning(f"Could not detect project type for {repo_path}")
            return {
                "source": "unknown",
                "findings_count": 0,
                "error": "Unknown project type",
            }
        
        # Save findings
        saved = self.save_coverage_findings(findings, repo_id)
        
        return {
            "findings_count": len(findings),
            "saved_count": saved,
            "threshold": self._get_coverage_threshold(repo_id),
        }


# Singleton instance
_coverage_service: CoverageService | None = None


def get_coverage_service(db_connection=None) -> CoverageService:
    """Get or create singleton coverage service."""
    global _coverage_service
    if _coverage_service is None:
        _coverage_service = CoverageService(db_connection)
    return _coverage_service
