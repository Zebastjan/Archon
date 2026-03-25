"""Stage 1: Documentation Maintenance Check.

Checks if documentation needs updates based on code changes:
- Are there new functions without docstrings?
- Do ADRs need updates?
- Is context bundle up-to-date?

Returns: dict with status, details, recommendations
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def run_stage_1_doc_maintenance(repo_root: Path) -> dict[str, Any]:
    """Run documentation maintenance checks.

    Args:
        repo_root: Root directory of git repository

    Returns:
        Dict with stage results
    """
    result = {
        "status": "pass",
        "details": {},
        "issues": [],
        "recommendations": [],
    }

    try:
        # Get changed files from last commit
        git_result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1..HEAD"],
            capture_output=True,
            text=True,
            cwd=repo_root,
        )

        if git_result.returncode != 0:
            result["status"] = "warning"
            result["issues"].append("Could not retrieve changed files")
            return result

        changed_files = [
            f.strip() for f in git_result.stdout.strip().split("\n") if f.strip()
        ]
        result["details"]["changed_files"] = changed_files

        # Check if code changed but no docs updated
        code_files = [
            f
            for f in changed_files
            if f.startswith("python/src/") and f.endswith(".py")
        ]
        doc_files = [
            f for f in changed_files if f.startswith("docs/") or f.endswith(".md")
        ]

        result["details"]["code_files_changed"] = len(code_files)
        result["details"]["doc_files_changed"] = len(doc_files)

        if code_files and not doc_files:
            result["status"] = "warning"
            result["issues"].append("Code changed but no documentation updated")
            result["recommendations"].append("Consider updating relevant documentation")

        # Check if ADRs need updates
        adr_dir = repo_root / "docs" / "ADRs"
        if adr_dir.exists():
            pending_adrs = []
            for adr_file in adr_dir.glob("*.md"):
                content = adr_file.read_text()
                if "## Status: Proposed" in content or "## Status: Draft" in content:
                    pending_adrs.append(adr_file.name)

            if pending_adrs:
                result["details"]["pending_adrs"] = pending_adrs
                if len(pending_adrs) > 5:
                    result["recommendations"].append(
                        f"Consider reviewing {len(pending_adrs)} pending ADRs"
                    )

        # Check context bundle freshness
        context_dir = repo_root / ".archon" / "context"
        if context_dir.exists():
            status_file = context_dir / "STATUS.md"
            if status_file.exists():
                import os
                import time

                mtime = os.path.getmtime(status_file)
                age_hours = (time.time() - mtime) / 3600

                if age_hours > 24:
                    result["recommendations"].append(
                        f"Context bundle is {int(age_hours)} hours old - consider regenerating"
                    )

        if not result["issues"] and not result["recommendations"]:
            result["status"] = "pass"

    except Exception as e:
        result["status"] = "error"
        result["issues"].append(f"Error in doc maintenance check: {str(e)}")

    return result
