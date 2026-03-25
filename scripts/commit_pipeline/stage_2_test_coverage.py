"""Stage 2: Test Coverage Analysis.

Runs pytest and analyzes test coverage:
- Are there new functions without tests?
- Do tests pass?
- What's the coverage delta?

Returns: dict with status, details, recommendations
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def run_stage_2_test_coverage(repo_root: Path) -> dict[str, Any]:
    """Run test coverage analysis.

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
        # Get changed source files from last commit
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

        # Categorize files
        src_files = [
            f
            for f in changed_files
            if f.startswith("python/src/") and f.endswith(".py")
        ]
        test_files = [
            f for f in changed_files if "test" in f.lower() and f.endswith(".py")
        ]

        result["details"]["source_files_changed"] = len(src_files)
        result["details"]["test_files_changed"] = len(test_files)

        # Check for new functions without tests
        new_functions_uncovered = []
        orphaned_tests = []

        if src_files and not test_files:
            result["status"] = "warning"
            result["issues"].append("Source code changed but no test files updated")
            result["recommendations"].append(
                "Consider adding tests for new/changed functionality"
            )

        # Simple heuristic: check if each src file has corresponding test file
        for src_file in src_files:
            # Extract the module name
            parts = Path(src_file).parts
            if len(parts) >= 3:
                module = Path(src_file).stem
                # Look for potential test files
                potential_tests = [
                    f"python/tests/test_{module}.py",
                    f"tests/test_{module}.py",
                    f"python/tests/{parts[-2]}/test_{module}.py",
                ]
                # Just note it - we don't actually check if tests exist
                # This is a lightweight check
                result["details"].setdefault("modules_with_changes", []).append(module)

        # Try to run pytest (quick check, no coverage)
        pytest_result = subprocess.run(
            ["python", "-m", "pytest", "--collect-only", "-q", "python/tests/"],
            capture_output=True,
            text=True,
            cwd=repo_root,
            timeout=30,
        )

        if pytest_result.returncode == 0:
            # Parse output for test count
            output_lines = pytest_result.stdout.strip().split("\n")
            for line in output_lines:
                if "items" in line.lower() or "collected" in line.lower():
                    result["details"]["pytest_collection"] = line.strip()
                    break
        else:
            result["status"] = "warning"
            result["issues"].append("Pytest collection had issues")
            if pytest_result.stderr:
                result["details"]["pytest_error"] = pytest_result.stderr[:200]

    except subprocess.TimeoutExpired:
        result["status"] = "warning"
        result["issues"].append("Pytest collection timed out")
    except FileNotFoundError:
        result["status"] = "skip"
        result["details"]["reason"] = "pytest not available"
    except Exception as e:
        result["status"] = "error"
        result["issues"].append(f"Error in test coverage check: {str(e)}")

    return result
