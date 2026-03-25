"""Orchestrator: Runs all commit pipeline stages.

Executes stages 1-3 in sequence and writes results to
.archon/hooks/last-run.json

Usage:
    python -m scripts.commit_pipeline.orchestrator --repo-root /path/to/repo
    OR
    cd /path/to/repo && python scripts/commit_pipeline/orchestrator.py
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.commit_pipeline.stage_1_doc_maintenance import run_stage_1_doc_maintenance
from scripts.commit_pipeline.stage_2_test_coverage import run_stage_2_test_coverage
from scripts.commit_pipeline.stage_3_code_audit import run_stage_3_code_audit


def get_current_branch(repo_root: Path) -> str:
    """Get current git branch name."""
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def get_commit_info(repo_root: Path) -> dict[str, str]:
    """Get information about the latest commit."""
    result = subprocess.run(
        ["git", "log", "-1", "--format=%H|%h|%s|%ci"],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )

    if result.returncode != 0:
        return {"sha": "unknown", "short_sha": "unknown", "message": "", "date": ""}

    parts = result.stdout.strip().split("|", 3)
    if len(parts) == 4:
        return {
            "sha": parts[0],
            "short_sha": parts[1],
            "message": parts[2],
            "date": parts[3],
        }
    return {"sha": "unknown", "short_sha": "unknown", "message": "", "date": ""}


def run_pipeline(
    repo_root: Path | None = None, commit_sha: str | None = None
) -> dict[str, Any]:
    """Run the complete commit pipeline.

    Args:
        repo_root: Root directory of git repository
        commit_sha: Optional specific commit to analyze (default: HEAD)

    Returns:
        Dict with pipeline results
    """
    if repo_root is None:
        # Try to get repo root from git
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
        )
        repo_root = (
            Path(result.stdout.strip()) if result.returncode == 0 else Path.cwd()
        )

    branch = get_current_branch(repo_root)
    commit_info = get_commit_info(repo_root)

    pipeline_result = {
        "version": "1.0",
        "commit": commit_info["sha"],
        "short_commit": commit_info["short_sha"],
        "branch": branch,
        "commit_message": commit_info["message"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stages": {},
    }

    # Run Stage 1: Documentation Maintenance
    print("[Pipeline] Running Stage 1: Doc Maintenance...")
    try:
        stage_1_result = run_stage_1_doc_maintenance(repo_root)
        pipeline_result["stages"]["doc_maintenance"] = stage_1_result
        print(f"  Status: {stage_1_result['status']}")
    except Exception as e:
        pipeline_result["stages"]["doc_maintenance"] = {
            "status": "error",
            "error": str(e),
        }
        print(f"  Error: {e}")

    # Run Stage 2: Test Coverage
    print("[Pipeline] Running Stage 2: Test Coverage...")
    try:
        stage_2_result = run_stage_2_test_coverage(repo_root)
        pipeline_result["stages"]["test_coverage"] = stage_2_result
        print(f"  Status: {stage_2_result['status']}")
    except Exception as e:
        pipeline_result["stages"]["test_coverage"] = {
            "status": "error",
            "error": str(e),
        }
        print(f"  Error: {e}")

    # Run Stage 3: Code Audit
    print("[Pipeline] Running Stage 3: Code Audit...")
    try:
        stage_3_result = run_stage_3_code_audit(repo_root)
        pipeline_result["stages"]["code_audit"] = stage_3_result
        print(f"  Status: {stage_3_result['status']}")
    except Exception as e:
        pipeline_result["stages"]["code_audit"] = {
            "status": "error",
            "error": str(e),
        }
        print(f"  Error: {e}")

    # Write results to .archon/hooks/last-run.json
    hooks_dir = repo_root / ".archon" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    output_file = hooks_dir / "last-run.json"

    with open(output_file, "w") as f:
        json.dump(pipeline_result, f, indent=2)

    print(f"[Pipeline] Results written to {output_file}")

    return pipeline_result


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Run commit pipeline stages")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Git repository root (default: auto-detect)",
    )
    parser.add_argument(
        "--commit",
        type=str,
        default=None,
        help="Commit SHA to analyze (default: HEAD)",
    )
    args = parser.parse_args()

    result = run_pipeline(args.repo_root, args.commit)

    # Print summary
    print("\n=== Pipeline Summary ===")
    for stage_name, stage_result in result["stages"].items():
        status = stage_result.get("status", "unknown")
        print(f"  {stage_name}: {status}")

    sys.exit(0)


if __name__ == "__main__":
    main()
