"""Nimalyzer Integration Service

Layer 1 of Nim audit: Pragma enforcement via Nimalyzer.
Wraps the Nimalyzer tool for pragma checks (raises, noSideEffect).
"""

import json
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg2
from psycopg2.extras import RealDictCursor

from src.server.config.logfire_config import get_logger

logger = get_logger(__name__)


@dataclass
class NimalyzerFinding:
    """A Nimalyzer finding."""

    check_id: str
    file_path: str
    line: int
    message: str
    severity: str = "WARNING"
    rule_type: str = "pragma"

    def to_db_dict(self, repo_id: UUID) -> dict[str, Any]:
        """Convert to dict for database insertion."""
        return {
            "repo_id": str(repo_id),
            "source": "nimalyzer",
            "semgrep_check_id": f"nimalyzer/{self.check_id}",
            "semgrep_rule_url": "",
            "message": self.message,
            "severity": self.severity,
            "confidence": "medium",
            "file_path": self.file_path,
            "line_start": self.line,
            "line_end": self.line,
            "column_start": 0,
            "column_end": 0,
            "code_snippet": "",
            "metavariables": json.dumps({"rule_type": self.rule_type}),
            "data_flow": json.dumps({}),
        }


class NimalyzerService:
    """Service for running Nimalyzer pragma checks on Nim code."""

    def __init__(self, db_connection=None):
        self._db = db_connection
        self._connection_string = (
            "postgresql://archon:archon_local_dev@localhost:5434/archon"
        )
        self._nimalyzer_path = self._find_nimalyzer()

    def _find_nimalyzer(self) -> str:
        """Find Nimalyzer executable."""
        # Check common locations
        paths = [
            "/home/zebastjan/.nimble/bin/nimalyzer",
            "/usr/local/bin/nimalyzer",
            "/usr/bin/nimalyzer",
            "nimalyzer",
        ]
        for path in paths:
            try:
                result = subprocess.run(
                    [path, "--version"],
                    capture_output=True,
                    timeout=5,
                )
                if result.returncode == 0 or b"Starting nimalyzer" in result.stderr:
                    logger.info(f"Found Nimalyzer at: {path}")
                    return path
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue

        logger.warning("Nimalyzer not found, pragma checks will be unavailable")
        return "nimalyzer"

    def _get_db(self):
        """Get database connection."""
        if self._db is None:
            self._db = psycopg2.connect(self._connection_string)
        return self._db

    def _execute_query(
        self, query: str, params: tuple = (), commit: bool = False
    ) -> list[dict]:
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

    def _create_config_file(self, source_files: list[str]) -> Path:
        """Create a temporary Nimalyzer config file."""
        config_content = """# Nimalyzer configuration for pragma enforcement
check hasPragma procedures "raises: [*"
check hasPragma procedures noSideEffect
"""
        # Add source files
        for src in source_files:
            config_content += f"{src}\n"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".cfg", delete=False
        ) as f:
            f.write(config_content)
            return Path(f.name)

    def run_pragma_check(
        self,
        repo_path: str | Path,
        repo_id: UUID,
        source_files: list[str] | None = None,
    ) -> list[NimalyzerFinding]:
        """
        Run Nimalyzer pragma checks on Nim source files.

        Args:
            repo_path: Path to the repository
            repo_id: Repository UUID
            source_files: List of Nim files to check (relative to repo_path)

        Returns:
            List of NimalyzerFinding objects
        """
        repo_path = Path(repo_path)

        if source_files is None:
            # Find all .nim files
            source_files = [
                str(f.relative_to(repo_path))
                for f in repo_path.rglob("*.nim")
                if ".git" not in str(f) and "node_modules" not in str(f)
            ]

        if not source_files:
            logger.info("No Nim files to check")
            return []

        # Create config file
        config_file = self._create_config_file(source_files)

        try:
            # Run Nimalyzer
            cmd = [self._nimalyzer_path, str(config_file)]
            result = subprocess.run(
                cmd,
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=300,
            )

            # Nimalyzer exits with code 1 when findings exist
            findings = self._parse_output(result.stderr or result.stdout, repo_path)

            logger.info(f"Nimalyzer found {len(findings)} pragma issues")
            return findings

        except subprocess.TimeoutExpired:
            logger.error("Nimalyzer timed out after 5 minutes")
            return []
        except FileNotFoundError:
            logger.error(f"Nimalyzer not found at {self._nimalyzer_path}")
            return []
        finally:
            config_file.unlink(missing_ok=True)

    def _parse_output(
        self, output: str, repo_path: Path
    ) -> list[NimalyzerFinding]:
        """Parse Nimalyzer output into finding objects."""
        findings = []

        # Nimalyzer outputs findings in format like:
        # [HH:MM:SS] ERROR  The procedure myProc doesn't have declared the pragma raises.
        # [HH:MM:SS] ERROR  The procedure myProc doesn't have declared the pragma noSideEffect.
        # Or with file info:
        # src/main.nim(42, 1) Error: ...

        # Pattern for file:line output
        file_pattern = re.compile(
            r"^(.*?\.nim)\((\d+),\s*\d+\)\s*Error:\s*(.+)$", re.MULTILINE
        )
        # Pattern for general output
        general_pattern = re.compile(
            r"\[.*?\]\s*ERROR\s+The procedure (.+?) doesn't have declared the pragma (.+?)\."
        )

        # Try file pattern first
        for match in file_pattern.finditer(output):
            file_path = match.group(1)
            line = int(match.group(2))
            message = match.group(3).strip()

            # Extract pragma from message
            pragma = "unknown"
            if "raises" in message.lower():
                pragma = "raises"
            elif "noSideEffect" in message.lower() or "side effect" in message.lower():
                pragma = "noSideEffect"

            findings.append(
                NimalyzerFinding(
                    check_id=f"missing-pragma-{pragma}",
                    file_path=file_path,
                    line=line,
                    message=f"Procedure missing required pragma: {pragma}",
                    severity="WARNING",
                    rule_type="pragma",
                )
            )

        # Try general pattern for additional context
        for match in general_pattern.finditer(output):
            proc_name = match.group(1)
            pragma = match.group(2).strip()

            # Only add if we don't already have a finding for this
            existing = [
                f
                for f in findings
                if proc_name in f.message and pragma in f.message
            ]
            if not existing:
                findings.append(
                    NimalyzerFinding(
                        check_id=f"missing-pragma-{pragma}",
                        file_path="unknown.nim",
                        line=0,
                        message=f"Procedure '{proc_name}' missing required pragma: {pragma}",
                        severity="WARNING",
                        rule_type="pragma",
                    )
                )

        return findings

    def save_findings(
        self,
        findings: list[NimalyzerFinding],
        repo_id: UUID,
    ) -> int:
        """Save findings to database."""
        if not findings:
            return 0

        conn = self._get_db()
        saved_count = 0

        try:
            with conn.cursor() as cur:
                for finding in findings:
                    data = finding.to_db_dict(repo_id)
                    cur.execute(
                        """
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
                    """,
                        data,
                    )
                    saved_count += 1

                conn.commit()
                logger.info(f"Saved {saved_count} Nimalyzer findings")
                return saved_count

        except Exception as e:
            logger.exception(f"Failed to save Nimalyzer findings: {e}")
            conn.rollback()
            return 0


# Singleton instance
_nimalyzer_service: NimalyzerService | None = None


def get_nimalyzer_service(db_connection=None) -> NimalyzerService:
    """Get or create singleton Nimalyzer service."""
    global _nimalyzer_service
    if _nimalyzer_service is None:
        _nimalyzer_service = NimalyzerService(db_connection)
    return _nimalyzer_service
