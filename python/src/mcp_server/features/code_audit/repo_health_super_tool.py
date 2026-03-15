"""Repository Health Check Super-Tool

A unified tool that combines metrics calculation, audit execution, and worktree safety
into a single call. Reduces tool usage by orchestrating multiple operations internally.
"""

from typing import Any, Literal
from uuid import UUID

from src.server.config.logfire_config import get_logger
from src.server.services.code_metrics_service import (
    get_code_metrics_service,
    CodeMetrics,
)
from src.server.services.worktree_service import get_worktree_service

logger = get_logger(__name__)

# Focus modes and their corresponding rulesets
FOCUS_RULESETS = {
    "full": None,  # All active rules
    "security": [
        "hardcoded-secrets",
        "sql-injection",
        "unsafe-eval",
        "insecure-deserialization",
        "weak-crypto",
        "subprocess-shell-true",
    ],
    "tdd": [
        "untested-production-code",
        "missing-tests-for-public-api",
        "test-assert-quality",
    ],
    "docs": [
        "public-api-missing-docs",
        "missing-docstring",
        "missing-type-hints",
    ],
    "maintainability": [
        "complexity-high",
        "complexity-critical",
        "function-too-long",
        "function-critically-long",
        "too-many-params",
        "deeply-nested",
        "cognitive-complexity",
        "duplicate-code",
        "broad-except",
    ],
}


def run_repo_health_check(
    repo_id: str,
    focus: Literal["full", "security", "tdd", "docs", "maintainability"] | None = None,
    ruleset: str | None = None,
    skip_worktree_validation: bool = False,
) -> dict[str, Any]:
    """
    Run comprehensive repository health check.
    
    This super-tool orchestrates multiple operations internally:
    - Worktree safety validation (before any writes)
    - Code metrics calculation
    - Audit execution with appropriate ruleset
    - Results aggregation and summarization
    
    Args:
        repo_id: Repository UUID to check
        focus: Focus area - determines which ruleset to use
        ruleset: Optional custom ruleset (comma-separated rule IDs)
        skip_worktree_validation: Skip worktree safety check (not recommended)
        
    Returns:
        Comprehensive health report with scores, findings, and recommendations
    """
    logger.info(f"Starting repo_health_check for {repo_id}, focus={focus}")
    
    try:
        # Step 1: Worktree safety validation (internal, not exposed to model)
        if not skip_worktree_validation:
            worktree_service = get_worktree_service()
            validation = worktree_service.validate_safe_to_work(
                file_paths=["*"],  # Generic check for repo-wide operations
            )
            
            if not validation.is_safe:
                logger.warning(f"Worktree safety issues detected: {validation.issues}")
                return {
                    "success": False,
                    "error": "Worktree safety validation failed",
                    "safety_issues": validation.issues,
                    "safety_warnings": validation.warnings,
                    "context": validation.context.to_dict() if validation.context else None,
                }
        
        # Step 2: Get metrics service
        metrics_service = get_code_metrics_service()
        
        # Step 3: Calculate metrics
        logger.debug("Calculating code metrics...")
        metrics = metrics_service.calculate_repo_metrics(repo_id)
        
        # Step 4: Determine ruleset based on focus
        selected_ruleset = None
        if ruleset:
            # Custom ruleset provided
            selected_ruleset = ruleset.split(",")
        elif focus and focus in FOCUS_RULESETS:
            # Use predefined ruleset for focus area
            selected_ruleset = FOCUS_RULESETS[focus]
        
        # Step 5: Run audit
        logger.debug(f"Running audit with ruleset: {selected_ruleset}")
        findings_count, run_id = metrics_service.run_audit(repo_id, selected_ruleset)
        
        # Step 6: Get findings
        findings = metrics_service.get_audit_findings(
            repo_id=repo_id,
            status="open",
            limit=50,
        )
        
        # Step 7: Calculate per-category scores
        category_scores = _calculate_category_scores(metrics, findings)
        
        # Step 8: Generate highlights (top findings)
        highlights = _generate_highlights(findings)
        
        # Step 9: Generate recommendations
        recommendations = _generate_recommendations(metrics, findings, focus)
        
        # Step 10: Build response
        result = {
            "success": True,
            "health_score": metrics.health_score,
            "per_category_scores": category_scores,
            "highlights": highlights,
            "recommendations": recommendations,
            "run_id": str(run_id) if run_id else None,
            "metrics_summary": {
                "total_files": metrics.total_files,
                "total_lines_of_code": metrics.total_lines_of_code,
                "total_lines_of_comments": metrics.total_lines_of_comments,
                "code_to_comment_ratio": metrics.code_to_comment_ratio,
                "total_functions": metrics.total_functions,
                "total_classes": metrics.total_classes,
                "avg_cyclomatic_complexity": metrics.avg_cyclomatic_complexity,
                "max_cyclomatic_complexity": metrics.max_cyclomatic_complexity,
            },
            "findings_summary": {
                "total": findings_count,
                "critical": sum(1 for f in findings if f.severity == "critical"),
                "error": sum(1 for f in findings if f.severity == "error"),
                "warning": sum(1 for f in findings if f.severity == "warning"),
                "info": sum(1 for f in findings if f.severity == "info"),
            },
            "focus": focus or "full",
            "safety_validated": not skip_worktree_validation,
        }
        
        logger.info(f"Repo health check complete: score={metrics.health_score}, findings={findings_count}")
        return result
        
    except Exception as e:
        logger.exception(f"Repo health check failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }


def _calculate_category_scores(
    metrics: CodeMetrics,
    findings: list,
) -> dict[str, int]:
    """Calculate per-category health scores."""
    
    # Base scores start at health_score
    base_score = metrics.health_score
    
    # Adjust based on findings in each category
    scores = {
        "overall": base_score,
        "security": base_score,
        "complexity": base_score,
        "maintainability": base_score,
        "documentation": base_score,
    }
    
    # Count findings by category
    category_findings = {
        "security": [],
        "complexity": [],
        "maintainability": [],
        "documentation": [],
    }
    
    for finding in findings:
        # Map rule_id to category (simplified)
        if "security" in finding.rule_id or finding.rule_id in [
            "hardcoded-secrets", "sql-injection", "unsafe-eval",
            "insecure-deserialization", "weak-crypto", "subprocess-shell-true"
        ]:
            category_findings["security"].append(finding)
        elif "complexity" in finding.rule_id or "function-too" in finding.rule_id:
            category_findings["complexity"].append(finding)
        elif "doc" in finding.rule_id or "test" in finding.rule_id:
            category_findings["documentation"].append(finding)
        else:
            category_findings["maintainability"].append(finding)
    
    # Penalize scores based on finding severity
    for category, cat_findings in category_findings.items():
        if cat_findings:
            penalty = 0
            for f in cat_findings:
                if f.severity == "critical":
                    penalty += 15
                elif f.severity == "error":
                    penalty += 10
                elif f.severity == "warning":
                    penalty += 5
                else:
                    penalty += 1
            
            scores[category] = max(0, scores[category] - min(penalty, 50))
    
    return scores


def _generate_highlights(findings: list) -> list[dict[str, Any]]:
    """Generate top finding highlights."""
    
    # Sort by severity
    severity_order = {"critical": 0, "error": 1, "warning": 2, "info": 3}
    sorted_findings = sorted(
        findings,
        key=lambda f: (severity_order.get(f.severity, 4), f.message)
    )
    
    highlights = []
    for finding in sorted_findings[:10]:  # Top 10
        highlight = {
            "rule_id": finding.rule_id,
            "severity": finding.severity,
            "description": finding.message[:200],  # Truncate long messages
            "file": finding.file_path,
            "line": finding.line_start,
            "fix_summary": _generate_fix_summary(finding),
        }
        highlights.append(highlight)
    
    return highlights


def _generate_fix_summary(finding) -> str:
    """Generate a brief fix summary for a finding."""
    
    fix_summaries = {
        "complexity-high": "Refactor into smaller functions",
        "complexity-critical": "Split into multiple functions immediately",
        "function-too-long": "Extract sections into helper functions",
        "function-critically-long": "Major refactoring required",
        "hardcoded-secrets": "Move to environment variables",
        "sql-injection": "Use parameterized queries",
        "unsafe-eval": "Replace with safer alternatives",
        "insecure-deserialization": "Use safe_load or json.loads",
        "weak-crypto": "Use SHA-256 or stronger algorithms",
        "public-api-missing-docs": "Add docstrings",
        "missing-type-hints": "Add type annotations",
        "too-many-params": "Use configuration object pattern",
        "deeply-nested": "Extract nested blocks into functions",
    }
    
    return fix_summaries.get(finding.rule_id, "Review and refactor")


def _generate_recommendations(
    metrics: CodeMetrics,
    findings: list,
    focus: str | None,
) -> list[str]:
    """Generate actionable recommendations."""
    
    recommendations = []
    
    # Critical/Error findings
    critical_error_count = sum(1 for f in findings if f.severity in ["critical", "error"])
    if critical_error_count > 0:
        recommendations.append(
            f"Address {critical_error_count} critical/error findings before next release"
        )
    
    # Complexity issues
    if metrics.max_cyclomatic_complexity > 20:
        recommendations.append(
            f"Refactor highest complexity function (complexity: {metrics.max_cyclomatic_complexity})"
        )
    
    # Comment ratio
    if metrics.code_to_comment_ratio > 20:
        recommendations.append(
            f"Add more comments (current ratio {metrics.code_to_comment_ratio:.1f}:1, target 4-10:1)"
        )
    
    # Focus-specific recommendations
    if focus == "security":
        security_findings = [f for f in findings if "security" in f.rule_id]
        if security_findings:
            recommendations.append(
                f"Review {len(security_findings)} security findings immediately"
            )
    elif focus == "tdd":
        recommendations.append("Add tests for untested production code")
    elif focus == "docs":
        recommendations.append("Add docstrings to public APIs")
    
    return recommendations[:5]  # Limit to top 5
