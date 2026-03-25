"""MCP Tools for Code Metrics and Audit

Provides MCP tools for:
- Calculating code metrics
- Running audit rules
- Querying audit findings
- Managing audit rules
- Super-tool: repo_health_check (combines all above)
"""

from typing import Any

from mcp.server.fastmcp import FastMCP

from src.server.config.logfire_config import get_logger
from src.server.services.code_metrics_service import (
    get_code_metrics_service,
    CodeMetrics,
    AuditFinding,
)
from src.mcp_server.features.code_audit.repo_health_super_tool import run_repo_health_check
import httpx
import os

logger = get_logger(__name__)

# Orchestrator configuration
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://localhost:8080")


def register_code_audit_tools(mcp: FastMCP) -> None:
    """Register code audit MCP tools."""
    logger.info("registering_code_audit_tools")

    @mcp.tool()
    async def code_audit_calculate_metrics(repo_id: str) -> dict[str, Any]:
        """
        Calculate code quality metrics for a repository.

        Analyzes all code entities in the repository and calculates:
        - Lines of code, comments, blank lines
        - Cyclomatic complexity
        - Function/class counts
        - Code-to-comment ratio
        - Health score (0-100)

        Args:
            repo_id: Repository ID to analyze

        Returns:
            Dict with calculated metrics

        Example:
            >>> await code_audit_calculate_metrics("repo-123")
            {
                "success": True,
                "metrics": {
                    "total_files": 45,
                    "total_lines_of_code": 3200,
                    "avg_cyclomatic_complexity": 4.5,
                    "health_score": 87
                }
            }
        """
        try:
            service = get_code_metrics_service()
            metrics = service.calculate_repo_metrics(repo_id)

            return {
                "success": True,
                "metrics": metrics.to_dict(),
                "message": f"Metrics calculated for {metrics.total_files} files",
            }
        except Exception as e:
            logger.exception("code_audit_calculate_metrics_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
            }

    @mcp.tool()
    async def code_audit_run(repo_id: str, ruleset: list[str] | None = None) -> dict[str, Any]:
        """
        Run audit rules against a repository.

        Executes all active audit rules (or specified ruleset) against
        the code entities in the repository.

        Args:
            repo_id: Repository ID to audit
            ruleset: Optional list of rule IDs (None = all active rules)

        Returns:
            Dict with audit results

        Example:
            >>> await code_audit_run("repo-123", ["complexity-high", "missing-docstring"])
            {
                "success": True,
                "findings_count": 12,
                "audit_run_id": "run-456",
                "message": "Audit completed with 12 findings"
            }
        """
        try:
            service = get_code_metrics_service()
            findings_count, run_id = service.run_audit(repo_id, ruleset)

            severity = "success" if findings_count == 0 else "warning"

            return {
                "success": True,
                "findings_count": findings_count,
                "audit_run_id": str(run_id) if run_id else None,
                "severity": severity,
                "message": f"Audit completed with {findings_count} findings",
            }
        except Exception as e:
            logger.exception("code_audit_run_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
            }

    @mcp.tool()
    async def code_audit_get_findings(
        repo_id: str | None = None, status: str = "open", severity: str | None = None, limit: int = 50
    ) -> dict[str, Any]:
        """
        Get audit findings with optional filters.

        Retrieves audit rule violations and suggestions.

        Args:
            repo_id: Filter by repository (None = all repos)
            status: Filter by status (open, acknowledged, resolved, false_positive)
            severity: Filter by severity (critical, error, warning, info)
            limit: Maximum number of findings to return

        Returns:
            Dict with findings list

        Example:
            >>> await code_audit_get_findings("repo-123", "open", "warning")
            {
                "success": True,
                "findings": [
                    {
                        "rule_id": "complexity-high",
                        "severity": "warning",
                        "message": "Function too complex",
                        "file_path": "src/auth.py",
                        "line_start": 45
                    }
                ]
            }
        """
        try:
            service = get_code_metrics_service()
            findings = service.get_audit_findings(repo_id=repo_id, status=status, severity=severity, limit=limit)

            return {
                "success": True,
                "findings": [f.to_dict() for f in findings],
                "count": len(findings),
            }
        except Exception as e:
            logger.exception("code_audit_get_findings_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
            }

    @mcp.tool()
    async def code_audit_get_summary(repo_id: str | None = None) -> dict[str, Any]:
        """
        Get audit summary statistics.

        Returns aggregated statistics about audit findings.

        Args:
            repo_id: Repository ID (None = all repositories)

        Returns:
            Dict with summary statistics

        Example:
            >>> await code_audit_get_summary("repo-123")
            {
                "success": True,
                "summary": {
                    "total_findings": 42,
                    "critical_count": 2,
                    "error_count": 5,
                    "warning_count": 20,
                    "open_count": 35
                }
            }
        """
        try:
            service = get_code_metrics_service()
            summary = service.get_audit_summary(repo_id)

            return {
                "success": True,
                "summary": summary,
            }
        except Exception as e:
            logger.exception("code_audit_get_summary_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
            }

    @mcp.tool()
    async def code_audit_get_rules(category: str | None = None, is_active: bool = True) -> dict[str, Any]:
        """
        Get audit rules.

        Retrieves audit rule definitions.

        Args:
            category: Filter by category (complexity, style, security, etc.)
            is_active: Only return active rules

        Returns:
            Dict with list of rules

        Example:
            >>> await code_audit_get_rules("complexity")
            {
                "success": True,
                "rules": [
                    {
                        "rule_id": "complexity-high",
                        "name": "High Cyclomatic Complexity",
                        "category": "complexity",
                        "severity": "warning",
                        "threshold_max": 10
                    }
                ]
            }
        """
        try:
            service = get_code_metrics_service()
            rules = service.get_audit_rules(category=category, is_active=is_active)

            return {
                "success": True,
                "rules": [r.to_dict() for r in rules],
                "count": len(rules),
            }
        except Exception as e:
            logger.exception("code_audit_get_rules_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
            }

    @mcp.tool()
    async def code_audit_acknowledge_finding(
        finding_id: str, resolution_note: str = "", mark_resolved: bool = False
    ) -> dict[str, Any]:
        """
        Acknowledge or resolve an audit finding.

        Updates the status of an audit finding.

        Args:
            finding_id: The finding ID to update
            resolution_note: Optional note about the resolution
            mark_resolved: If True, mark as resolved; otherwise acknowledged

        Returns:
            Dict with operation result

        Example:
            >>> await code_audit_acknowledge_finding(
            ...     "finding-123",
            ...     "Refactored function to reduce complexity",
            ...     True
            ... )
            {
                "success": True,
                "status": "resolved",
                "message": "Finding marked as resolved"
            }
        """
        try:
            service = get_code_metrics_service()
            success = service.acknowledge_finding(
                finding_id=finding_id, resolution_note=resolution_note, resolved=mark_resolved
            )

            status = "resolved" if mark_resolved else "acknowledged"

            return {
                "success": success,
                "status": status,
                "message": f"Finding marked as {status}" if success else "Failed to update finding",
            }
        except Exception as e:
            logger.exception("code_audit_acknowledge_finding_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
            }

    @mcp.tool()
    async def code_audit_analyze_entity(entity_id: str) -> dict[str, Any]:
        """
        Analyze a specific code entity for metrics.

        Calculates detailed metrics for a single function, class, or method.

        Args:
            entity_id: Entity ID to analyze

        Returns:
            Dict with entity metrics

        Example:
            >>> await code_audit_analyze_entity("entity-456")
            {
                "success": True,
                "metrics": {
                    "lines_of_code": 25,
                    "cyclomatic_complexity": 3,
                    "todo_count": 1
                }
            }
        """
        try:
            service = get_code_metrics_service()
            metrics = service.calculate_file_metrics(entity_id)

            return {
                "success": True,
                "metrics": metrics,
            }
        except Exception as e:
            logger.exception("code_audit_analyze_entity_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
            }

    @mcp.tool()
    async def repo_health_check(
        repo_id: str,
        focus: str | None = None,
        ruleset: str | None = None,
    ) -> dict[str, Any]:
        """
        Run comprehensive repository health check (SUPER-TOOL).

        This unified tool combines metrics calculation, audit execution,
        and worktree safety validation into a single call.

        Use this tool instead of calling code_audit_calculate_metrics +
        code_audit_run separately. Reduces tool usage and latency.

        Args:
            repo_id: Repository ID to check
            focus: Focus area - "full", "security", "db", "tdd", "docs", "maintainability"
            ruleset: Optional custom ruleset (comma-separated rule IDs)

        Returns:
            Comprehensive health report with:
            - health_score (0-100)
            - per_category_scores
            - highlights (top findings)
            - recommendations
            - run_id for traceability

        Example:
            >>> await repo_health_check(repo_id="abc-123", focus="security")
            {
                "success": True,
                "health_score": 78,
                "per_category_scores": {
                    "overall": 78,
                    "security": 85,
                    "complexity": 72
                },
                "highlights": [...],
                "recommendations": [...],
                "run_id": "run-xyz"
            }

        Note:
            focus="db" runs DB security rules (SQL injection, unsafe queries)
            on Python/TypeScript code that talks to PostgreSQL.
        """
        try:
            # Validate focus parameter
            valid_focus = ["full", "security", "db", "tdd", "docs", "maintainability", None]
            if focus not in valid_focus:
                return {
                    "success": False,
                    "error": f"Invalid focus. Must be one of: {valid_focus}",
                }

            result = await run_repo_health_check(
                repo_id=repo_id,
                focus=focus,
                ruleset=ruleset,
            )

            return result

        except Exception as e:
            logger.exception("repo_health_check_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
            }

    @mcp.tool()
    async def db_security_audit(
        repo_id: str,
        include_tests: bool = False,
    ) -> dict[str, Any]:
        """
        Run DB security audit focused on SQL injection and unsafe queries.

        This is a specialized audit that targets:
        - SQL injection vulnerabilities
        - Unsafe raw SQL string building
        - Hardcoded database credentials
        - Dangerous query patterns in Python and TypeScript/JS code

        Uses custom DB rules + Semgrep official SQL injection rules.
        Excludes test files by default.

        Args:
            repo_id: Repository ID to audit
            include_tests: Include test files in scan (default: False)

        Returns:
            Audit results with DB security findings

        Example:
            >>> await db_security_audit(repo_id="abc-123")
            {
                "success": True,
                "findings_count": 5,
                "findings_by_rule": {...},
                "needs_fix": [...],
                "needs_review": [...]
            }
        """
        try:
            from src.server.services.database import get_database_connector
            from src.server.services.semgrep_service import get_semgrep_service
            from uuid import UUID

            # Get repo info
            db = get_database_connector()
            repo_result = await db.fetchrow("SELECT id, local_path, name FROM archon_code_repos WHERE id = $1", repo_id)

            if not repo_result:
                return {"success": False, "error": f"Repository '{repo_id}' not found"}

            repo_path = repo_result["local_path"]

            # Run DB audit via Semgrep service
            semgrep_service = get_semgrep_service()

            db_rulesets = [
                "p/python",  # Python security patterns
                "p/javascript",  # JS security patterns
                "p/typescript",  # TS security patterns
                "python/src/server/semgrep_rules/db",  # Custom DB rules
            ]

            exclude_patterns = []
            if not include_tests:
                exclude_patterns = [
                    "**/test/**",
                    "**/tests/**",
                    "**/*_test.py",
                    "**/*.test.ts",
                    "**/*.test.js",
                    "**/fixtures/**",
                    "**/mocks/**",
                ]

            findings = semgrep_service.run_audit(
                repo_path=repo_path,
                repo_id=UUID(repo_id),
                rulesets=db_rulesets,
                exclude_patterns=exclude_patterns,
            )

            # Filter to DB-related findings
            db_keywords = [
                "sql",
                "injection",
                "query",
                "execute",
                "cursor",
                "psycopg",
                "asyncpg",
                "postgres",
                "sqlite",
                "mysql",
                "connection",
                "credential",
                "password",
            ]

            db_findings = [
                f
                for f in findings
                if any(kw in f.check_id.lower() for kw in db_keywords)
                or any(kw in f.message.lower() for kw in db_keywords)
            ]

            # Group by severity/rule
            findings_by_rule = {}
            needs_fix = []
            needs_review = []

            for finding in db_findings:
                rule_id = finding.check_id
                if rule_id not in findings_by_rule:
                    findings_by_rule[rule_id] = {
                        "count": 0,
                        "severity": finding.severity,
                        "message": finding.message,
                        "samples": [],
                    }
                findings_by_rule[rule_id]["count"] += 1

                # Collect samples (up to 3 per rule)
                if len(findings_by_rule[rule_id]["samples"]) < 3:
                    findings_by_rule[rule_id]["samples"].append(
                        {
                            "file": finding.path,
                            "line": finding.line_start,
                            "snippet": finding.code_snippet[:150] if finding.code_snippet else None,
                        }
                    )

                # Categorize
                if finding.severity == "ERROR":
                    needs_fix.append(
                        {"rule": rule_id, "file": finding.path, "line": finding.line_start, "message": finding.message}
                    )
                else:
                    needs_review.append(
                        {"rule": rule_id, "file": finding.path, "line": finding.line_start, "message": finding.message}
                    )

            # Save findings to database
            saved_count = semgrep_service.save_findings(findings=db_findings, repo_id=UUID(repo_id))

            return {
                "success": True,
                "repo_id": repo_id,
                "repo_name": repo_result["name"],
                "findings_count": len(db_findings),
                "saved_count": saved_count,
                "findings_by_rule": findings_by_rule,
                "needs_fix_count": len(needs_fix),
                "needs_review_count": len(needs_review),
                "needs_fix": needs_fix[:10],  # Limit output
                "needs_review": needs_review[:10],
            }

        except Exception as e:
            logger.exception("db_security_audit_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
            }

    @mcp.tool()
    async def orchestrated_repo_health_check(
        repo_id: str,
        focus: str | None = None,
    ) -> dict[str, Any]:
        """
        Orchestrated repository health check with LLM-powered insights (RECOMMENDED).

        This is the PREFERRED tool for code audits. It combines:
        - Standard repo_health_check execution
        - Local LLM-powered summarization
        - Human-friendly executive summary
        - Detailed analysis and recommendations

        Uses a 7-14B local model running on RTX 3060 for intelligent post-processing.

        Args:
            repo_id: Repository ID to check
            focus: Focus area - "full", "security", "tdd", "docs", "maintainability"

        Returns:
            Comprehensive health report with LLM-generated insights:
            - All standard repo_health_check fields
            - executive_summary: Human-friendly 2-3 sentence summary
            - detailed_analysis: Bullet-pointed recommendations
            - orchestrated: True (indicates LLM-enhanced)

        Example:
            >>> await orchestrated_repo_health_check(repo_id="abc-123", focus="security")
            {
                "success": True,
                "health_score": 78,
                "executive_summary": "Repository has good overall health with 2 critical...",
                "detailed_analysis": "• Address hardcoded secrets in config.py\n• Refactor...",
                "orchestrated": True,
                ...
            }

        Note:
            Requires orchestrator service running (port 8080 by default).
            Falls back to standard repo_health_check if orchestrator unavailable.

            focus="db" runs DB security rules (SQL injection, unsafe queries)
            on Python/TypeScript code that talks to PostgreSQL.
        """
        try:
            # Validate focus parameter
            valid_focus = ["full", "security", "db", "tdd", "docs", "maintainability", None]
            if focus not in valid_focus:
                return {
                    "success": False,
                    "error": f"Invalid focus. Must be one of: {valid_focus}",
                }

            logger.info(f"Calling orchestrator for repo {repo_id}, focus={focus}")

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{ORCHESTRATOR_URL}/orchestrator/repo_health_check",
                    params={"repo_id": repo_id, "focus": focus},
                )

                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"Orchestrator returned score: {result.get('health_score')}")
                    return {
                        "success": True,
                        "message": "Orchestrated audit complete with LLM insights",
                        **result,
                    }
                else:
                    logger.warning(f"Orchestrator error {response.status_code}, falling back")
                    # Fall back to standard repo_health_check
                    return await repo_health_check(repo_id=repo_id, focus=focus)

        except httpx.ConnectError as e:
            logger.warning(f"Orchestrator unavailable: {e}, using fallback")
            # Orchestrator not running, use standard tool
            return await repo_health_check(repo_id=repo_id, focus=focus)
        except Exception as e:
            logger.exception("orchestrated_repo_health_check_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
            }

    @mcp.tool()
    async def audit_get_context(repo_name: str) -> dict[str, Any]:
        """
        Get batched audit context for a repository.

        Returns repo_id, findings grouped by source and check_id, with sample snippets.
        This is the recommended tool for audit triage and analysis - it eliminates
        the need for multiple discovery calls.

        Args:
            repo_name: Repository name to look up

        Returns:
            Dict with:
            - repo_id: Repository UUID
            - findings_by_source: Findings grouped by source, with counts and samples
            - summary: Overall statistics (total_open, by severity)

        Example:
            >>> await audit_get_context("archon")
            {
                "success": True,
                "repo_id": "abc-123",
                "findings_by_source": {
                    "semgrep": [
                        {
                            "check_id": "hardcoded-secrets",
                            "count": 5,
                            "severity": "critical",
                            "samples": [
                                {"file_path": "config.py", "line": 42, "snippet": "API_KEY = 'sk-...'"}
                            ]
                        }
                    ],
                    "audit_rules": [
                        {
                            "check_id": "complexity-high",
                            "count": 12,
                            "severity": "warning",
                            "samples": [...]
                        }
                    ]
                },
                "summary": {
                    "total_open": 17,
                    "critical": 5,
                    "error": 0,
                    "warning": 12
                }
            }
        """
        try:
            from src.server.services.database import get_database_connector

            db = get_database_connector()

            # Get repo_id from name
            repo_result = await db.fetchrow("SELECT id FROM archon_code_repos WHERE name = $1", repo_name)

            if not repo_result:
                return {"success": False, "error": f"Repository '{repo_name}' not found"}

            repo_id = str(repo_result["id"])

            # Get findings grouped by source (check_id) with severity and count
            findings_query = """
                SELECT 
                    rule_id,
                    severity,
                    COUNT(*) as count,
                    MIN(id) as sample_id
                FROM archon_audit_findings
                WHERE repo_id = $1 AND status = 'open'
                GROUP BY rule_id, severity
                ORDER BY 
                    CASE severity 
                        WHEN 'critical' THEN 1 
                        WHEN 'error' THEN 2 
                        WHEN 'warning' THEN 3 
                        ELSE 4 
                    END,
                    count DESC
            """

            findings_groups = await db.fetch(findings_query, repo_result["id"])

            # Get sample snippets for each group (3-5 samples per group)
            findings_by_source = {}
            summary = {"total_open": 0, "critical": 0, "error": 0, "warning": 0, "info": 0}

            for group in findings_groups:
                rule_id = group["rule_id"]
                severity = group["severity"]
                count = group["count"]

                summary["total_open"] += count
                summary[severity] = summary.get(severity, 0) + count

                # Get samples for this rule
                samples_query = """
                    SELECT 
                        file_path,
                        line_start,
                        code_snippet,
                        message
                    FROM archon_audit_findings
                    WHERE repo_id = $1 AND rule_id = $2 AND status = 'open'
                    LIMIT 5
                """

                samples_result = await db.fetch(samples_query, repo_result["id"], rule_id)

                samples = [
                    {
                        "file_path": s["file_path"],
                        "line": s["line_start"],
                        "snippet": s["code_snippet"][:200] if s["code_snippet"] else None,  # Truncate long snippets
                        "message": s["message"][:100] if s["message"] else None,
                    }
                    for s in samples_result
                ]

                # Determine source category based on rule_id prefix or pattern
                source = "audit_rules"  # default
                if any(x in rule_id.lower() for x in ["semgrep", "sg-"]):
                    source = "semgrep"
                elif any(x in rule_id.lower() for x in ["trivy", "cve", "vuln"]):
                    source = "trivy"
                elif any(x in rule_id.lower() for x in ["bandit", "security"]):
                    source = "security"

                if source not in findings_by_source:
                    findings_by_source[source] = []

                findings_by_source[source].append(
                    {"check_id": rule_id, "count": count, "severity": severity, "samples": samples}
                )

            return {"success": True, "repo_id": repo_id, "findings_by_source": findings_by_source, "summary": summary}

        except Exception as e:
            logger.exception(f"audit_get_context failed for repo '{repo_name}': {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def audit_track_outcome(
        finding_id: str,
        outcome_type: str,  # bug_filed, bug_hit_production, validated_correct
        notes: str = "",
        related_issue_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Record the outcome of a dismissed finding.

        When a finding that was marked 'false_positive' or 'wont_fix'
        later results in a real bug, record the correlation to improve
        future audit recommendations.

        Args:
            finding_id: UUID of the audit finding
            outcome_type: Type of outcome (bug_filed, bug_hit_production, validated_correct)
            notes: Additional context about the outcome
            related_issue_id: Optional ID of related issue/ticket

        Returns:
            Dict with outcome tracking result

        Example:
            >>> await audit_track_outcome(
            ...     finding_id="uuid-findings-id",
            ...     outcome_type="bug_filed",
            ...     notes="Same issue found in production",
            ...     related_issue_id="BUG-123"
            ... )
        """
        try:
            from src.server.services.database import get_database_connector
            from uuid import UUID

            # Validate outcome_type
            valid_types = {"bug_filed", "bug_hit_production", "validated_correct"}
            if outcome_type not in valid_types:
                return {
                    "success": False,
                    "error": f"Invalid outcome_type. Must be one of: {', '.join(valid_types)}",
                }

            db = get_database_connector()

            # Check if finding exists
            finding = await db.fetchrow("SELECT id, status FROM archon_audit_findings WHERE id = $1", finding_id)

            if not finding:
                return {"success": False, "error": f"Finding {finding_id} not found"}

            # Create outcome record
            outcome = await db.fetchrow(
                """
                INSERT INTO archon_audit_outcomes
                    (finding_id, outcome_type, notes, related_issue_id)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                finding_id,
                outcome_type,
                notes,
                related_issue_id,
            )

            if not outcome:
                return {"success": False, "error": "Failed to create outcome record"}

            outcome_id = outcome["id"]

            # Create learning event if this is a bug (dismissed finding came back to bite us)
            learning_event = None
            if outcome_type in ("bug_filed", "bug_hit_production"):
                event_type = (
                    "dismissed_then_hit" if finding["status"] in ("false_positive", "wont_fix") else "false_negative"
                )
                correlation_data = {
                    "original_status": finding["status"],
                    "outcome_type": outcome_type,
                    "notes": notes,
                }

                learning_event = await db.fetchrow(
                    """
                    INSERT INTO archon_audit_learning_events
                        (finding_id, outcome_id, event_type, correlation_data)
                    VALUES ($1, $2, $3, $4)
                    RETURNING id
                    """,
                    finding_id,
                    outcome_id,
                    event_type,
                    correlation_data,
                )

            return {
                "success": True,
                "outcome_id": outcome_id,
                "learning_event_id": learning_event["id"] if learning_event else None,
                "message": f"Recorded {outcome_type} outcome for finding",
            }

        except Exception as e:
            logger.exception("audit_track_outcome_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
            }

    @mcp.tool()
    async def audit_get_retrospectives(event_type: str | None = None, limit: int = 50) -> dict[str, Any]:
        """
        Get all learning events where dismissed findings were validated.

        Returns correlation events showing where audit findings were
        dismissed and later proven correct (bugs appeared).

        Args:
            event_type: Optional filter by event type (dismissed_then_hit, false_negative, correct_dismissal)
            limit: Maximum number of events to return

        Returns:
            Dict with learning events and context

        Example:
            >>> await audit_get_retrospectives()
            {
                "success": true,
                "events": [...],
                "count": 5
            }
        """
        try:
            from src.server.services.database import get_database_connector

            db = get_database_connector()

            query = """
                SELECT
                    le.id as event_id,
                    le.event_type,
                    le.correlation_data,
                    le.created_at as event_created_at,
                    le.retrospective_task_id,
                    f.id as finding_id,
                    f.message as finding_message,
                    f.file_path,
                    f.severity as finding_severity,
                    f.status as finding_status,
                    f.rule_id,
                    o.outcome_type,
                    o.notes as outcome_notes,
                    o.related_issue_id
                FROM archon_audit_learning_events le
                JOIN archon_audit_findings f ON le.finding_id = f.id
                LEFT JOIN archon_audit_outcomes o ON le.outcome_id = o.id
            """

            if event_type:
                query += " WHERE le.event_type = $1"
                query += " ORDER BY le.created_at DESC LIMIT $2"
                events = await db.fetch(query, event_type, limit)
            else:
                query += " ORDER BY le.created_at DESC LIMIT $1"
                events = await db.fetch(query, limit)

            results = []
            for event in events:
                correlation = event["correlation_data"] or {}
                if isinstance(correlation, str):
                    import json

                    try:
                        correlation = json.loads(correlation)
                    except:
                        correlation = {}

                results.append(
                    {
                        "event_id": event["event_id"],
                        "event_type": event["event_type"],
                        "created_at": event["event_created_at"].isoformat() if event["event_created_at"] else None,
                        "finding": {
                            "id": event["finding_id"],
                            "message": event["finding_message"],
                            "file_path": event["file_path"],
                            "severity": event["finding_severity"],
                            "status": event["finding_status"],
                        },
                        "outcome": {
                            "type": event["outcome_type"],
                            "notes": event["outcome_notes"],
                            "issue_id": event["related_issue_id"],
                        },
                        "correlation": correlation,
                    }
                )

            return {
                "success": True,
                "events": results,
                "count": len(results),
            }

        except Exception as e:
            logger.exception("audit_get_retrospectives_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
                "events": [],
            }

    @mcp.tool()
    async def audit_check_correlation(file_path: str, function_name: str | None = None) -> dict[str, Any]:
        """
        Check if there are any dismissed findings related to this file/function.

        Call this before marking a new issue as "won't fix" or when a new
        bug is discovered. Returns any previously dismissed findings that
        match the file/function.

        Args:
            file_path: File path to check for previous findings
            function_name: Optional function name to narrow search

        Returns:
            Dict with correlation results and warning if dismissed findings found

        Example:
            >>> await audit_check_correlation(file_path="src/auth.py")
            {
                "success": true,
                "has_correlation": true,
                "warning": "2 previously dismissed findings in this file",
                "dismissed_findings": [...]
            }
        """
        try:
            from src.server.services.database import get_database_connector

            db = get_database_connector()

            # Find dismissed findings for this file
            query = """
                SELECT
                    f.id,
                    f.rule_id,
                    f.message,
                    f.severity,
                    f.status,
                    f.category,
                    f.file_path,
                    f.created_at,
                    COUNT(le.id) as learning_events_count,
                    MAX(o.outcome_type) as last_outcome_type
                FROM archon_audit_findings f
                LEFT JOIN archon_audit_learning_events le ON f.id = le.finding_id
                LEFT JOIN archon_audit_outcomes o ON f.id = o.finding_id
                WHERE f.file_path = $1
                AND f.status IN ('false_positive', 'wont_fix')
            """

            params = [file_path]

            if function_name:
                query += " AND (f.message ILIKE $2 OR f.code_snippet ILIKE $2)"
                params.append(f"%{function_name}%")

            query += " GROUP BY f.id ORDER BY f.created_at DESC"

            findings = await db.fetch(query, *params)

            dismissed = []
            for finding in findings:
                dismissed.append(
                    {
                        "id": finding["id"],
                        "rule_id": finding["rule_id"],
                        "message": finding["message"],
                        "severity": finding["severity"],
                        "status": finding["status"],
                        "category": finding["category"],
                        "created_at": finding["created_at"].isoformat() if finding["created_at"] else None,
                        "learning_events_count": finding["learning_events_count"],
                        "last_outcome_type": finding["last_outcome_type"],
                    }
                )

            has_correlation = len(dismissed) > 0

            return {
                "success": True,
                "has_correlation": has_correlation,
                "dismissed_findings": dismissed,
                "count": len(dismissed),
                "warning": f"{len(dismissed)} previously dismissed finding(s) in this file"
                if has_correlation
                else None,
            }

        except Exception as e:
            logger.exception("audit_check_correlation_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
                "has_correlation": False,
                "dismissed_findings": [],
            }

    logger.info("code_audit_tools_registered")
