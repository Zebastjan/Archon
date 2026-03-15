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
    async def code_audit_run(
        repo_id: str,
        ruleset: list[str] | None = None
    ) -> dict[str, Any]:
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
        repo_id: str | None = None,
        status: str = "open",
        severity: str | None = None,
        limit: int = 50
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
            findings = service.get_audit_findings(
                repo_id=repo_id,
                status=status,
                severity=severity,
                limit=limit
            )
            
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
    async def code_audit_get_rules(
        category: str | None = None,
        is_active: bool = True
    ) -> dict[str, Any]:
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
        finding_id: str,
        resolution_note: str = "",
        mark_resolved: bool = False
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
                finding_id=finding_id,
                resolution_note=resolution_note,
                resolved=mark_resolved
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
            focus: Focus area - "full", "security", "tdd", "docs", "maintainability"
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
        """
        try:
            # Validate focus parameter
            valid_focus = ["full", "security", "tdd", "docs", "maintainability", None]
            if focus not in valid_focus:
                return {
                    "success": False,
                    "error": f"Invalid focus. Must be one of: {valid_focus}",
                }
            
            result = run_repo_health_check(
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
        """
        try:
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

    logger.info("code_audit_tools_registered")
