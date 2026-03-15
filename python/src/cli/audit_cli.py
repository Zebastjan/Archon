"""CLI commands for code audit operations.

Provides commands for running audits and generating reports from the command line.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.server.services.code_metrics_service import get_code_metrics_service
from src.server.config.logfire_config import get_logger

logger = get_logger(__name__)


def generate_markdown_report(
    repo_id: str,
    metrics: dict[str, Any],
    findings: list[dict[str, Any]],
    summary: dict[str, Any],
    output_path: str | None = None,
) -> str:
    """
    Generate a Markdown audit report.
    
    Args:
        repo_id: Repository ID
        metrics: Calculated metrics
        findings: List of findings
        summary: Audit summary
        output_path: Optional path to write report
        
    Returns:
        Markdown report string
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Calculate severity counts
    critical_count = sum(1 for f in findings if f.get("severity") == "critical")
    error_count = sum(1 for f in findings if f.get("severity") == "error")
    warning_count = sum(1 for f in findings if f.get("severity") == "warning")
    info_count = sum(1 for f in findings if f.get("severity") == "info")
    
    # Get health score with color indicator
    health_score = metrics.get("health_score", 0)
    if health_score >= 90:
        health_indicator = "🟢 Excellent"
    elif health_score >= 70:
        health_indicator = "🟡 Good"
    elif health_score >= 50:
        health_indicator = "🟠 Fair"
    else:
        health_indicator = "🔴 Poor"
    
    # Build report
    report = f"""# Code Audit Report

**Generated:** {now}  
**Repository ID:** `{repo_id}`

---

## 📊 Health Score

<div align="center">

### {health_score}/100 - {health_indicator}

</div>

---

## 📈 High-Level Summary

| Metric | Value |
|--------|-------|
| **Total Files** | {metrics.get("total_files", 0):,} |
| **Lines of Code** | {metrics.get("total_lines_of_code", 0):,} |
| **Lines of Comments** | {metrics.get("total_lines_of_comments", 0):,} |
| **Code-to-Comment Ratio** | {metrics.get("code_to_comment_ratio", 0):.1f}:1 |
| **Functions** | {metrics.get("total_functions", 0):,} |
| **Classes** | {metrics.get("total_classes", 0):,} |

### Complexity Metrics

| Metric | Value | Target |
|--------|-------|--------|
| **Avg Cyclomatic Complexity** | {metrics.get("avg_cyclomatic_complexity", 0):.1f} | < 8 |
| **Max Cyclomatic Complexity** | {metrics.get("max_cyclomatic_complexity", 0)} | < 15 |
| **Avg Function Length** | {metrics.get("avg_function_length", 0)} lines | < 25 |
| **Max Function Length** | {metrics.get("max_function_length", 0)} lines | < 100 |

### Quality Indicators

| Metric | Count | Status |
|--------|-------|--------|
| **TODO Comments** | {metrics.get("todo_count", 0)} | { "⚠️" if metrics.get("todo_count", 0) > 5 else "✅" } |
| **FIXME Comments** | {metrics.get("fixme_count", 0)} | { "⚠️" if metrics.get("fixme_count", 0) > 0 else "✅" } |
| **Deprecated Items** | {metrics.get("deprecated_count", 0)} | { "⚠️" if metrics.get("deprecated_count", 0) > 0 else "✅" } |

---

## 🔍 Findings Summary

| Severity | Count | Status |
|----------|-------|--------|
| 🔴 Critical | {critical_count} | { "❌ Action Required" if critical_count > 0 else "✅ None" } |
| 🟠 Error | {error_count} | { "❌ Fix Before Release" if error_count > 0 else "✅ None" } |
| 🟡 Warning | {warning_count} | { "⚠️ Review Recommended" if warning_count > 10 else "✅ Acceptable" } |
| 🔵 Info | {info_count} | ℹ️ Optional |

**Total Findings:** {len(findings)}

---

## 🚨 Top Findings

"""
    
    # Add top findings by severity
    if findings:
        # Sort by severity (critical first)
        severity_order = {"critical": 0, "error": 1, "warning": 2, "info": 3}
        sorted_findings = sorted(
            findings,
            key=lambda f: severity_order.get(f.get("severity", "info"), 4)
        )
        
        # Add top 10 findings
        for i, finding in enumerate(sorted_findings[:10], 1):
            severity = finding.get("severity", "info")
            severity_emoji = {
                "critical": "🔴",
                "error": "🟠",
                "warning": "🟡",
                "info": "🔵",
            }.get(severity, "⚪")
            
            report += f"""### {i}. {severity_emoji} {finding.get('message', 'Unknown Issue')}

**Rule:** `{finding.get('rule_id', 'unknown')}`  
**Severity:** {severity.upper()}  
**File:** `{finding.get('file_path', 'unknown')}`  
**Location:** Lines {finding.get('line_start', 0)}-{finding.get('line_end', 0)}

{finding.get('description', '')}

"""
            
            if finding.get("suggested_fix"):
                report += f"""**Suggested Fix:**
```
{finding.get('suggested_fix')}
```

"""
            
            report += "---\n\n"
    else:
        report += "✅ No issues found! Great job!\n\n"
    
    # Add recommendations
    report += """## 📋 Recommendations

"""
    
    if critical_count > 0:
        report += """### 🔴 Critical Actions Required

1. **Address security vulnerabilities immediately**
2. **Review and fix critical complexity issues**
3. **Remove hardcoded secrets if present**

"""
    
    if error_count > 0:
        report += """### 🟠 High Priority Fixes

1. **Refactor high-complexity functions** (> 20 cyclomatic complexity)
2. **Split long functions** (> 100 lines)
3. **Add missing documentation** for public APIs

"""
    
    if warning_count > 10:
        report += f"""### 🟡 Medium Priority ({warning_count} warnings)

1. **Add docstrings** to undocumented functions
2. **Reduce function complexity** where possible
3. **Address TODO/FIXME comments**

"""
    
    report += f"""### 📈 Health Score Improvement

Current Score: **{health_score}/100** ({health_indicator.split()[1]})

To improve:
- Reduce average cyclomatic complexity (current: {metrics.get("avg_cyclomatic_complexity", 0):.1f}, target: < 8)
- Add more comments (current ratio: {metrics.get("code_to_comment_ratio", 0):.1f}:1, target: 4-10:1)
- Clear TODO/FIXME items (current: {metrics.get("todo_count", 0) + metrics.get("fixme_count", 0)})

"""
    
    report += f"""---

## 📊 Detailed Metrics

```json
{json.dumps(metrics, indent=2)}
```

---

*Report generated by Archon Code Audit CLI*  
*For more information: https://github.com/archon/archon*
"""
    
    # Write to file if path provided
    if output_path:
        output_file = Path(output_path)
        output_file.write_text(report)
        print(f"📄 Report written to: {output_file.absolute()}")
    
    return report


def audit_repo_command(args: argparse.Namespace) -> int:
    """
    Run audit on a repository and generate report.
    
    Args:
        args: Command line arguments
        
    Returns:
        Exit code (0 for success, 1 for error)
    """
    repo_id = args.repo_id
    ruleset = args.ruleset
    output = args.output
    
    print(f"🔍 Running audit on repository: {repo_id}")
    print()
    
    try:
        service = get_code_metrics_service()
        
        # Step 1: Calculate metrics
        print("📊 Calculating code metrics...")
        metrics_obj = service.calculate_repo_metrics(repo_id)
        metrics = metrics_obj.to_dict()
        print(f"   ✓ Health Score: {metrics['health_score']}/100")
        print(f"   ✓ Files: {metrics['total_files']}")
        print(f"   ✓ LOC: {metrics['total_lines_of_code']:,}")
        print()
        
        # Step 2: Run audit
        print("🔎 Running audit rules...")
        ruleset_list = None if ruleset == "default" else ruleset.split(",")
        findings_count, audit_run_id = service.run_audit(repo_id, ruleset_list)
        print(f"   ✓ Findings: {findings_count}")
        print(f"   ✓ Audit Run ID: {audit_run_id}")
        print()
        
        # Step 3: Get findings
        print("📋 Retrieving findings...")
        findings = service.get_audit_findings(
            repo_id=repo_id,
            status="open",
            limit=100
        )
        findings_data = [f.to_dict() for f in findings]
        print(f"   ✓ Retrieved {len(findings_data)} findings")
        print()
        
        # Step 4: Get summary
        summary = service.get_audit_summary(repo_id)
        
        # Step 5: Generate report
        print("📝 Generating report...")
        report = generate_markdown_report(
            repo_id=repo_id,
            metrics=metrics,
            findings=findings_data,
            summary=summary,
            output_path=output,
        )
        
        # Print summary to console
        print()
        print("=" * 60)
        print("AUDIT COMPLETE")
        print("=" * 60)
        print()
        print(f"Health Score: {metrics['health_score']}/100")
        print(f"Total Findings: {findings_count}")
        print()
        
        severity_counts = {}
        for f in findings_data:
            sev = f.get("severity", "unknown")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
        
        for sev in ["critical", "error", "warning", "info"]:
            if sev in severity_counts:
                print(f"  {sev.upper()}: {severity_counts[sev]}")
        
        print()
        
        if output:
            print(f"Full report written to: {output}")
        else:
            print("Use --output to save report to file")
        
        return 0
        
    except Exception as e:
        logger.exception("Audit failed: %s", str(e))
        print(f"❌ Audit failed: {e}", file=sys.stderr)
        return 1


def list_rules_command(args: argparse.Namespace) -> int:
    """List available audit rules."""
    try:
        service = get_code_metrics_service()
        rules = service.get_audit_rules(
            category=args.category,
            is_active=not args.include_inactive
        )
        
        print()
        print("=" * 80)
        print("AUDIT RULES")
        print("=" * 80)
        print()
        
        if args.category:
            print(f"Category: {args.category}")
            print()
        
        for rule in rules:
            status = "✅ Active" if rule.is_active else "❌ Inactive"
            builtin = " (Built-in)" if rule.is_builtin else ""
            
            print(f"  {rule.rule_id}{builtin}")
            print(f"    Name: {rule.name}")
            print(f"    Category: {rule.category}")
            print(f"    Severity: {rule.severity}")
            print(f"    Status: {status}")
            
            if rule.threshold_min is not None or rule.threshold_max is not None:
                print(f"    Threshold: ", end="")
                if rule.threshold_min is not None:
                    print(f"> {rule.threshold_min}", end="")
                if rule.threshold_min is not None and rule.threshold_max is not None:
                    print(" and ", end="")
                if rule.threshold_max is not None:
                    print(f"< {rule.threshold_max}", end="")
                print()
            
            print(f"    Applies to: {', '.join(rule.applies_to)}")
            print()
        
        print(f"Total: {len(rules)} rules")
        print()
        
        return 0
        
    except Exception as e:
        logger.exception("Failed to list rules: %s", str(e))
        print(f"❌ Error: {e}", file=sys.stderr)
        return 1


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="archon-audit",
        description="Code audit CLI for Archon",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s audit-repo --repo-id=abc-123
  %(prog)s audit-repo --repo-id=abc-123 --ruleset=complexity-high,missing-docstring
  %(prog)s audit-repo --repo-id=abc-123 --output=audit-report.md
  %(prog)s list-rules --category=security
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Audit repo command
    audit_parser = subparsers.add_parser(
        "audit-repo",
        help="Run audit on a repository"
    )
    audit_parser.add_argument(
        "--repo-id",
        required=True,
        help="Repository ID to audit"
    )
    audit_parser.add_argument(
        "--ruleset",
        default="default",
        help="Comma-separated list of rule IDs (default: all active rules)"
    )
    audit_parser.add_argument(
        "--output",
        "-o",
        help="Output file path for Markdown report"
    )
    
    # List rules command
    rules_parser = subparsers.add_parser(
        "list-rules",
        help="List available audit rules"
    )
    rules_parser.add_argument(
        "--category",
        help="Filter by category (security, complexity, maintainability, style)"
    )
    rules_parser.add_argument(
        "--include-inactive",
        action="store_true",
        help="Include inactive rules"
    )
    
    args = parser.parse_args()
    
    if args.command == "audit-repo":
        return audit_repo_command(args)
    elif args.command == "list-rules":
        return list_rules_command(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
