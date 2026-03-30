"""Generate HEALTH.md for context bundle.

Creates a human-readable health report from audit findings.
"""

import subprocess
from pathlib import Path
from typing import Any


def get_audit_summary(repo_root: Path) -> dict[str, Any]:
    """Get audit summary from database via MCP or direct query."""
    # For now, use the last pipeline results
    hooks_dir = repo_root / ".archon" / "hooks"
    last_run = hooks_dir / "last-run.json"

    if last_run.exists():
        import json

        data = json.loads(last_run.read_text())
        return {
            "last_audit": data.get("generated_at", "unknown"),
            "stage_results": data.get("stages", {}),
        }

    return {"last_audit": "never", "stage_results": {}}


def generate_health_md(repo_root: Path) -> str:
    """Generate HEALTH.md content."""
    summary = get_audit_summary(repo_root)

    # Get repo stats
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%h %s (%cr)"],
            capture_output=True,
            text=True,
            cwd=repo_root,
        )
        last_commit = result.stdout.strip() if result.returncode == 0 else "unknown"
    except (subprocess.CalledProcessError, OSError):
        last_commit = "unknown"

    # Get branch
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            cwd=repo_root,
        )
        branch = result.stdout.strip() if result.returncode == 0 else "unknown"
    except (subprocess.CalledProcessError, OSError):
        branch = "unknown"

    stages = summary.get("stage_results", {})

    # Build content
    lines = [
        "# Archon Health Report",
        "",
        f"**Branch**: {branch}",
        f"**Last Commit**: {last_commit}",
        f"**Generated**: {summary.get('last_audit', 'unknown')}",
        "",
        "## Pipeline Status",
        "",
    ]

    # Stage statuses
    for stage_name, stage_data in stages.items():
        status = stage_data.get("status", "unknown")
        icon = (
            "✅"
            if status == "pass"
            else "⚠️"
            if status == "warning"
            else "❌"
            if status in ["error", "critical"]
            else "⏭️"
        )
        lines.append(f"{icon} **{stage_name}**: {status}")

        # Add details for non-pass statuses
        if status != "pass":
            issues = stage_data.get("issues", [])
            if issues:
                lines.append(f"   - Issues: {', '.join(issues[:2])}")

    lines.extend(
        [
            "",
            "## Quick Actions",
            "",
            "- Run full health check: `mcp0_repo_health_check`",
            "- View all audit findings: `mcp0_code_audit_get_findings`",
            "- Check context status: `cat .archon/context/STATUS.md`",
            "",
            "## Documentation",
            "",
            "- [Architecture](ARCHITECTURE.md)",
            "- [Current Status](STATUS.md)",
            "- [Recent Changes](CHANGES.md)",
            "- [Known Issues](KNOWN_ISSUES.md)",
            "",
        ]
    )

    return "\n".join(lines)


def write_health_md(repo_root: Path) -> Path:
    """Write HEALTH.md to context directory."""
    context_dir = repo_root / ".archon" / "context"
    context_dir.mkdir(parents=True, exist_ok=True)

    health_path = context_dir / "HEALTH.md"
    content = generate_health_md(repo_root)
    health_path.write_text(content)

    return health_path


if __name__ == "__main__":
    repo_root = Path.cwd()
    health_path = write_health_md(repo_root)
    print(f"Generated: {health_path}")
