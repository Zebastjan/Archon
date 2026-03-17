"""Semgrep Integration Service

Replaces regex-based audit rules with Semgrep's AST-aware pattern matching.
Provides triage memory and false negative tracking for continuous improvement.
"""

import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg2
from psycopg2.extras import RealDictCursor

from src.server.config.logfire_config import get_logger
from src.server.services.embedding_service import get_embedding_service

logger = get_logger(__name__)


@dataclass
class SemgrepFinding:
    """A Semgrep finding parsed from JSON output."""
    
    # Identification
    check_id: str
    path: str
    line_start: int
    line_end: int
    
    # Content
    message: str
    severity: str = "WARNING"
    
    # Optional fields with defaults
    column_start: int = 0
    column_end: int = 0
    code_snippet: str = ""
    
    # Extra data
    metadata: dict[str, Any] = field(default_factory=dict)
    metavariables: dict[str, Any] = field(default_factory=dict)
    
    # URLs
    rule_url: str = ""
    
    def to_db_dict(self, repo_id: UUID, run_id: UUID | None = None) -> dict[str, Any]:
        """Convert to dict for database insertion."""
        return {
            "repo_id": str(repo_id),
            "audit_run_id": str(run_id) if run_id else None,
            "semgrep_check_id": self.check_id,
            "semgrep_rule_url": self.rule_url,
            "message": self.message,
            "severity": self.severity,
            "confidence": self.metadata.get("confidence", "medium"),
            "file_path": self.path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "column_start": self.column_start,
            "column_end": self.column_end,
            "code_snippet": self.code_snippet,
            "metavariables": json.dumps(self.metavariables),
            "data_flow": json.dumps(self.metadata.get("data_flow", {})),
        }


class SemgrepService:
    """Service for running Semgrep audits and managing findings."""
    
    # Default rulesets to use
    DEFAULT_RULESETS = [
        "p/security-audit",      # Security issues
        "p/owasp-top-ten",       # OWASP top 10
        "p/cwe-top-25",          # CWE top 25
        "p/python",              # Python best practices
        "p/typescript",          # TypeScript best practices
        "p/javascript",          # JavaScript best practices
    ]
    
    def __init__(self, db_connection=None):
        self._db = db_connection
        self._connection_string = "postgresql://archon:archon_local_dev@localhost:5434/archon"
        self._embedding_service = None  # Lazy init
    
    def _get_embedding_service(self):
        """Lazy initialization of embedding service."""
        if self._embedding_service is None:
            self._embedding_service = get_embedding_service()
        return self._embedding_service
    
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
    
    def run_audit(
        self,
        repo_path: str | Path,
        repo_id: UUID,
        rulesets: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> list[SemgrepFinding]:
        """
        Run Semgrep audit on a repository.
        
        Args:
            repo_path: Path to the repository
            repo_id: Repository UUID for database storage
            rulesets: List of rulesets to use (defaults to DEFAULT_RULESETS)
            exclude_patterns: Patterns to exclude from scanning
            
        Returns:
            List of SemgrepFinding objects
        """
        repo_path = Path(repo_path)
        rulesets = rulesets or self.DEFAULT_RULESETS
        exclude_patterns = exclude_patterns or ["tests/", "test/", "*_test.py", "*.test.ts", ".venv/", "node_modules/"]
        
        logger.info(f"Running Semgrep audit on {repo_path} with {len(rulesets)} rulesets")
        
        # Build command
        cmd = [
            "semgrep",
            "--config", ",".join(rulesets),
            "--json",
            "--quiet",  # Suppress progress output
        ]
        
        # Add excludes
        for pattern in exclude_patterns:
            cmd.extend(["--exclude", pattern])
        
        cmd.append(str(repo_path))
        
        # Run Semgrep
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )
            
            # Semgrep returns 1 when findings exist, 0 when no findings
            if result.returncode not in (0, 1):
                logger.error(f"Semgrep failed with code {result.returncode}: {result.stderr}")
                return []
            
            if result.stderr:
                logger.warning(f"Semgrep stderr: {result.stderr}")
            
            # Parse JSON output
            findings = self._parse_semgrep_output(result.stdout, repo_path)
            logger.info(f"Semgrep found {len(findings)} issues")
            
            return findings
            
        except subprocess.TimeoutExpired:
            logger.error("Semgrep timed out after 5 minutes")
            return []
        except FileNotFoundError:
            logger.error("Semgrep not installed. Run: pip install semgrep")
            return []
    
    def _parse_semgrep_output(self, json_output: str, repo_path: Path) -> list[SemgrepFinding]:
        """Parse Semgrep JSON output into SemgrepFinding objects."""
        findings = []
        
        if not json_output.strip():
            return findings
        
        try:
            data = json.loads(json_output)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Semgrep JSON output: {e}")
            return []
        
        errors = data.get("errors", [])
        if errors:
            for error in errors:
                logger.warning(f"Semgrep error: {error}")
        
        for result in data.get("results", []):
            try:
                # Extract location info
                path = result.get("path", "")
                start = result.get("start", {})
                end = result.get("end", {})
                
                # Get code snippet
                extra = result.get("extra", {})
                lines = extra.get("lines", "")
                
                # Get metadata
                metadata = extra.get("metadata", {})
                
                # Make path relative to repo
                try:
                    rel_path = str(Path(path).relative_to(repo_path))
                except ValueError:
                    rel_path = path
                
                finding = SemgrepFinding(
                    check_id=result.get("check_id", ""),
                    path=rel_path,
                    line_start=start.get("line", 0),
                    line_end=end.get("line", 0),
                    column_start=start.get("col", 0),
                    column_end=end.get("col", 0),
                    message=extra.get("message", ""),
                    severity=extra.get("severity", "WARNING").upper(),
                    code_snippet=lines,
                    metadata=metadata,
                    metavariables=extra.get("metavars", {}),
                    rule_url=metadata.get("source", result.get("extra", {}).get("metadata", {}).get("source", "")),
                )
                
                findings.append(finding)
            except Exception as e:
                logger.warning(f"Failed to parse Semgrep result: {e}")
                continue
        
        return findings
    
    def save_findings(
        self,
        findings: list[SemgrepFinding],
        repo_id: UUID,
        run_id: UUID | None = None,
    ) -> int:
        """Save findings to database."""
        if not findings:
            return 0
        
        conn = self._get_db()
        saved_count = 0
        
        try:
            with conn.cursor() as cur:
                # Insert findings
                for finding in findings:
                    data = finding.to_db_dict(repo_id, run_id)
                    cur.execute("""
                        INSERT INTO archon_semgrep_findings (
                            repo_id, audit_run_id, semgrep_check_id, semgrep_rule_url,
                            message, severity, confidence, file_path,
                            line_start, line_end, column_start, column_end,
                            code_snippet, metavariables, data_flow
                        ) VALUES (
                            %(repo_id)s, %(audit_run_id)s, %(semgrep_check_id)s, %(semgrep_rule_url)s,
                            %(message)s, %(severity)s, %(confidence)s, %(file_path)s,
                            %(line_start)s, %(line_end)s, %(column_start)s, %(column_end)s,
                            %(code_snippet)s, %(metavariables)s, %(data_flow)s
                        )
                        ON CONFLICT DO NOTHING
                    """, data)
                    saved_count += 1
                
                conn.commit()
                logger.info(f"Saved {saved_count} findings to database")
                return saved_count
                
        except Exception as e:
            logger.exception(f"Failed to save findings: {e}")
            conn.rollback()
            return 0
    
    def get_findings_for_review(
        self,
        repo_id: UUID | None = None,
        status: str = "open",
        limit: int = 50,
        severity: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get findings ready for review."""
        query = """
            SELECT 
                sf.*,
                repo.name as repo_name
            FROM archon_semgrep_findings sf
            JOIN archon_code_repos repo ON sf.repo_id = repo.id
            WHERE sf.status = %s
        """
        params = [status]
        
        if repo_id:
            query += " AND sf.repo_id = %s"
            params.append(str(repo_id))
        
        if severity:
            query += " AND sf.severity = %s"
            params.append(severity)
        
        query += " ORDER BY sf.severity DESC, sf.created_at LIMIT %s"
        params.append(limit)
        
        return self._execute_query(query, tuple(params))
    
    def get_finding_by_id(self, finding_id: UUID) -> dict[str, Any] | None:
        """Get a specific finding by ID."""
        result = self._execute_query(
            "SELECT * FROM archon_semgrep_findings WHERE id = %s",
            (str(finding_id),)
        )
        return result[0] if result else None
    
    async def triage_finding(
        self,
        finding_id: UUID,
        decision: str,  # confirmed_issue, intentional, false_positive, wont_fix
        rationale: str,
        reviewer: str,
        store_in_memory: bool = True,
    ) -> bool:
        """
        Triage a finding and optionally store the decision in triage memory.
        
        This is the core of the "meta-audit" - learning from decisions.
        """
        if decision not in ("confirmed_issue", "intentional", "false_positive", "wont_fix"):
            raise ValueError(f"Invalid decision: {decision}")
        
        # Get finding details
        finding = self.get_finding_by_id(finding_id)
        
        if not finding:
            logger.error(f"Finding {finding_id} not found")
            return False
        
        # Update finding status
        self._execute_query(
            "UPDATE archon_semgrep_findings SET status = 'triaged', updated_at = NOW() WHERE id = %s",
            (str(finding_id),),
            commit=True,
        )
        
        if store_in_memory:
            # Store in triage memory for future pattern matching
            await self._store_triage_memory(finding, decision, rationale, reviewer)
        
        # Update rule quality metrics
        try:
            self._execute_query(
                "SELECT update_rule_quality_metrics(%s)",
                (finding["semgrep_check_id"],),
                commit=True,
            )
        except Exception as e:
            logger.warning(f"Failed to update rule quality metrics: {e}")
        
        logger.info(f"Triaged finding {finding_id}: {decision}")
        return True
    
    async def _store_triage_memory(
        self,
        finding: dict[str, Any],
        decision: str,
        rationale: str,
        reviewer: str,
    ):
        """Store triage decision in memory for future pattern matching."""
        try:
            # Generate embedding for the code snippet
            code_snippet = finding.get("code_snippet", "")
            if not code_snippet:
                # Fallback to message if no code snippet
                code_snippet = finding.get("message", "")
            
            # Get embedding service and generate embedding
            embedding_service = self._get_embedding_service()
            embedding = await embedding_service.generate_for_code_entity(
                name=f"{finding['semgrep_check_id']}:{finding['file_path']}",
                signature=None,
                docstring=None,
                source_code=code_snippet,
            )
            
            if embedding is None:
                logger.warning("Failed to generate embedding for triage memory")
                return
            
            # Store in triage memory
            self._execute_query(
                """
                INSERT INTO archon_audit_triage_memory (
                    check_id,
                    repo_id,
                    pattern_type,
                    pattern_value,
                    pattern_embedding,
                    decision,
                    decision_rationale,
                    surrounding_code,
                    confidence_score,
                    reviewer_experience,
                    original_finding_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    finding["semgrep_check_id"],
                    finding["repo_id"],
                    "semantic_hash",  # Using semantic similarity
                    f"{finding['file_path']}:{finding['line_start']}",
                    embedding,
                    decision,
                    rationale,
                    code_snippet,
                    0.9 if decision == "false_positive" else 0.8,
                    reviewer,
                    finding["id"],
                ),
                commit=True,
            )
            logger.debug(f"Stored triage memory for {finding['semgrep_check_id']}")
        except Exception as e:
            logger.warning(f"Failed to store triage memory: {e}")
    
    async def suggest_triage_decision(
        self,
        finding_id: UUID,
    ) -> dict[str, Any] | None:
        """
        Suggest a triage decision based on similar past decisions.
        
        This is where the "meta-audit" magic happens - using past decisions
        to inform future ones.
        """
        # Get finding details
        finding = self.get_finding_by_id(finding_id)
        
        if not finding:
            return None
        
        # Try semantic search first
        try:
            code_snippet = finding.get("code_snippet", "")
            if code_snippet:
                embedding_service = self._get_embedding_service()
                embedding = await embedding_service.generate_for_code_entity(
                    name=f"{finding['semgrep_check_id']}:{finding['file_path']}",
                    signature=None,
                    docstring=None,
                    source_code=code_snippet,
                )
                
                if embedding is None:
                    logger.warning("Failed to generate embedding for triage suggestion")
                    return None
                
                # Find similar decisions
                similar = self._execute_query(
                    """
                    SELECT * FROM find_similar_triage_decisions(%s, %s, 0.80)
                    LIMIT 3
                    """,
                    (finding["semgrep_check_id"], embedding),
                )
                
                if similar:
                    # Return the most common decision among similar patterns
                    decisions = [s["decision"] for s in similar]
                    most_common = max(set(decisions), key=decisions.count)
                    avg_confidence = sum(s["confidence_score"] for s in similar) / len(similar)
                    avg_similarity = sum(s["similarity"] for s in similar) / len(similar)
                    
                    return {
                        "suggested_decision": most_common,
                        "confidence": avg_confidence,
                        "similarity": avg_similarity,
                        "similar_cases": len(similar),
                        "rationale": f"Based on {len(similar)} similar patterns previously triaged",
                    }
        except Exception as e:
            logger.warning(f"Failed to suggest triage via semantic search: {e}")
        
        # Fallback: check for exact check_id matches
        try:
            check_matches = self._execute_query(
                """
                SELECT decision, COUNT(*) as count
                FROM archon_audit_triage_memory
                WHERE check_id = %s
                GROUP BY decision
                ORDER BY count DESC
                LIMIT 1
                """,
                (finding["semgrep_check_id"],),
            )
            
            if check_matches:
                return {
                    "suggested_decision": check_matches[0]["decision"],
                    "confidence": 0.6,  # Lower confidence for check-level match
                    "similar_cases": check_matches[0]["count"],
                    "rationale": f"Based on {check_matches[0]['count']} previous findings with same rule",
                }
        except Exception as e:
            logger.warning(f"Failed to suggest triage via check match: {e}")
        
        return None
    
    def record_false_negative(
        self,
        repo_id: UUID,
        bug_type: str,
        bug_description: str,
        file_path: str,
        line_start: int | None = None,
        line_end: int | None = None,
        code_snippet: str = "",
        discovered_by: str = "manual",
        root_cause: str = "",
    ) -> UUID | None:
        """
        Record a bug that slipped past the audit.
        
        This is critical for the meta-audit - tracking what we missed.
        """
        result = self._execute_query(
            """
            INSERT INTO archon_audit_false_negatives (
                repo_id, bug_type, bug_description, file_path,
                line_start, line_end, code_snippet,
                discovered_by, discovery_method, root_cause
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                str(repo_id),
                bug_type,
                bug_description,
                file_path,
                line_start,
                line_end,
                code_snippet,
                discovered_by,
                "manual_review",
                root_cause,
            ),
            commit=True,
        )
        
        if result:
            fn_id = result[0]["id"]
            logger.info(f"Recorded false negative: {fn_id}")
            return UUID(fn_id)
        
        return None
    
    def analyze_false_negative(
        self,
        false_negative_id: UUID,
        repo_path: str | Path,
    ) -> dict[str, Any]:
        """
        Analyze if Semgrep would catch a false negative now.
        
        Re-runs Semgrep on the specific file to see if current rules would catch it.
        """
        fn = self._execute_query(
            "SELECT * FROM archon_audit_false_negatives WHERE id = %s",
            (str(false_negative_id),)
        )
        
        if not fn:
            return {"error": "False negative not found"}
        
        fn = fn[0]
        file_path = Path(repo_path) / fn["file_path"]
        
        if not file_path.exists():
            return {"error": f"File not found: {file_path}"}
        
        # Run Semgrep on just this file
        try:
            cmd = [
                "semgrep",
                "--config", "p/security-audit",
                "--config", "p/owasp-top-ten",
                "--config", "p/cwe-top-25",
                "--json",
                "--quiet",
                str(file_path),
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )
            
            if result.returncode not in (0, 1):
                return {"error": f"Semgrep failed: {result.stderr}"}
            
            data = json.loads(result.stdout)
            findings = data.get("results", [])
            
            # Update false negative record
            would_catch = len(findings) > 0
            rule_ids = [f["check_id"] for f in findings]
            
            self._execute_query(
                """
                UPDATE archon_audit_false_negatives
                SET would_semgrep_catch = %s,
                    semgrep_rules_that_would_catch = %s
                WHERE id = %s
                """,
                (would_catch, rule_ids, str(false_negative_id)),
                commit=True,
            )
            
            return {
                "would_catch": would_catch,
                "rules_that_would_catch": rule_ids,
                "findings_count": len(findings),
            }
            
        except Exception as e:
            logger.exception(f"Failed to analyze false negative: {e}")
            return {"error": str(e)}
    
    def get_rule_quality_report(self) -> list[dict[str, Any]]:
        """Get quality metrics for all rules."""
        return self._execute_query(
            """
            SELECT 
                check_id,
                total_findings,
                confirmed_issues,
                false_positives,
                precision,
                false_positive_rate,
                should_disable,
                disable_reason,
                ROUND(precision * 100, 2) as precision_pct,
                ROUND(false_positive_rate * 100, 2) as fp_rate_pct
            FROM archon_audit_rule_quality
            ORDER BY false_positive_rate DESC
            """
        )
    
    def get_rules_to_disable(self, fp_threshold: float = 0.5, min_findings: int = 5) -> list[str]:
        """Get list of rules that should be disabled due to high false positive rate."""
        result = self._execute_query(
            """
            SELECT check_id
            FROM archon_audit_rule_quality
            WHERE false_positive_rate > %s
            AND total_findings >= %s
            ORDER BY false_positive_rate DESC
            """,
            (fp_threshold, min_findings)
        )
        return [r["check_id"] for r in result]
    
    def get_audit_summary(self, repo_id: UUID | None = None) -> dict[str, Any]:
        """Get summary of audit findings."""
        base_query = """
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE status = 'open') as open_count,
                COUNT(*) FILTER (WHERE status = 'triaged') as triaged_count,
                COUNT(*) FILTER (WHERE severity = 'ERROR') as error_count,
                COUNT(*) FILTER (WHERE severity = 'WARNING') as warning_count,
                COUNT(*) FILTER (WHERE severity = 'INFO') as info_count
            FROM archon_semgrep_findings
        """
        
        if repo_id:
            base_query += " WHERE repo_id = %s"
            result = self._execute_query(base_query, (str(repo_id),))
        else:
            result = self._execute_query(base_query)
        
        return result[0] if result else {}
    
    def get_findings_by_check_id(self, check_id: str, limit: int = 100) -> list[dict[str, Any]]:
        """Get all findings for a specific check/rule."""
        return self._execute_query(
            """
            SELECT * FROM archon_semgrep_findings
            WHERE semgrep_check_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (check_id, limit)
        )
    
    async def check_semantic_drift(
        self,
        repo_id: str,
        entity_id: str,
    ) -> list[dict[str, Any]]:
        """
        Placeholder: compare entity docstring/spec against implementation
        using knowledge graph embeddings.
        
        Not implemented yet — returns empty list.
        Will be implemented when knowledge graph integration matures.
        
        This is the hook where the knowledge graph layer plugs in later.
        """
        logger.debug(f"Semantic drift check called for entity {entity_id} in repo {repo_id}")
        logger.debug("Semantic drift detection not yet implemented — returning empty list")
        return []


# Singleton instance
_semgrep_service: SemgrepService | None = None


def get_semgrep_service(db_connection=None) -> SemgrepService:
    """Get or create singleton Semgrep service."""
    global _semgrep_service
    if _semgrep_service is None:
        _semgrep_service = SemgrepService(db_connection)
    return _semgrep_service
