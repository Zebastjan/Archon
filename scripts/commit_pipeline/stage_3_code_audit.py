"""Stage 3: Code Audit.

Runs light code audit on changed files:
- Check for common issues
- Report findings count
- Flag critical issues

Returns: dict with status, details, findings
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def run_stage_3_code_audit(repo_root: Path) -> dict[str, Any]:
    """Run code audit on changed files.

    Args:
        repo_root: Root directory of git repository

    Returns:
        Dict with stage results
    """
    result = {
        "status": "pass",
        "details": {},
        "findings": {"critical": 0, "error": 0, "warning": 0, "info": 0},
        "issues": [],
    }

    try:
        # Get changed Python files from last commit
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
        py_files = [
            f for f in changed_files if f.endswith(".py") and "test" not in f.lower()
        ]

        result["details"]["files_audited"] = len(py_files)

        if not py_files:
            result["status"] = "skip"
            result["details"]["reason"] = "No Python files changed"
            return result

        # Run ruff check if available
        try:
            ruff_result = subprocess.run(
                ["ruff", "check", "--output-format", "json"] + py_files,
                capture_output=True,
                text=True,
                cwd=repo_root,
                timeout=60,
            )

            if ruff_result.returncode == 0:
                result["details"]["ruff"] = "No issues found"
            elif ruff_result.stdout:
                import json

                try:
                    ruff_issues = json.loads(ruff_result.stdout)
                    warning_count = len(ruff_issues)
                    result["findings"]["warning"] = warning_count
                    result["details"]["ruff_issues"] = warning_count
                except json.JSONDecodeError:
                    pass

        except (FileNotFoundError, subprocess.TimeoutExpired):
            result["details"]["ruff"] = "Not available or timed out"

        # Check for basic patterns in changed files
        for py_file in py_files:
            file_path = repo_root / py_file
            if file_path.exists():
                content = file_path.read_text()

                # Check for TODO/FIXME
                if "TODO" in content or "FIXME" in content:
                    result["findings"]["info"] += 1

                # Check for broad except
                if "except:" in content or "except Exception:" in content:
                    result["findings"]["warning"] += 1

                # Check for hardcoded secrets patterns
                if any(
                    pattern in content.lower()
                    for pattern in ["password =", "secret =", "api_key ="]
                ):
                    result["findings"]["critical"] += 1

        # Determine overall status
        if result["findings"]["critical"] > 0:
            result["status"] = "critical"
        elif result["findings"]["error"] > 0:
            result["status"] = "error"
        elif result["findings"]["warning"] > 0:
            result["status"] = "warning"
        else:
            result["status"] = "pass"

    except Exception as e:
        result["status"] = "error"
        result["issues"].append(f"Error in code audit: {str(e)}")

    return result
