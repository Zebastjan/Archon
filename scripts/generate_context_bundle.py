#!/usr/bin/env python3
"""Generate context bundle for Archon agent sessions.

Creates .archon/context/ directory with:
- STATUS.md: Current branch, recent changes, active worktrees
- CHANGES.md: Uncommitted changes summary
- ARCHITECTURE.md: Architecture overview from ADRs
- KNOWN_ISSUES.md: Open audit findings and dismissed findings

Usage:
    python scripts/generate_context_bundle.py [--repo-root /path/to/repo] [--force]

This script can be called:
1. Manually from command line
2. By post-commit hook (on-change detection)
3. By MCP tool generate_context_bundle()
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def get_current_branch(repo_root: Path) -> str:
    """Get current git branch name."""
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def get_recent_commits(repo_root: Path, count: int = 5) -> list[dict[str, str]]:
    """Get recent commits with SHA and message."""
    result = subprocess.run(
        ["git", "log", f"-{count}", "--format=%h|%s"],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    commits = []
    if result.returncode == 0:
        for line in result.stdout.strip().split("\n"):
            if "|" in line:
                sha, message = line.split("|", 1)
                commits.append({"sha": sha.strip(), "message": message.strip()})
    return commits


def get_branch_purpose(branch: str) -> str:
    """Infer branch purpose from naming convention."""
    if branch == "main" or branch == "master":
        return "Main development branch"
    if branch.startswith("feature/"):
        return f"Feature development: {branch[8:]}"
    if branch.startswith("fix/") or branch.startswith("bugfix/"):
        return f"Bug fix: {branch.split('/', 1)[1]}"
    if branch.startswith("hotfix/"):
        return f"Hotfix: {branch[7:]}"
    if branch.startswith("release/"):
        return f"Release preparation: {branch[8:]}"
    return f"Development: {branch}"


def get_uncommitted_changes(repo_root: Path) -> dict[str, list[str]]:
    """Get uncommitted file changes categorized by status."""
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )

    changes = {"added": [], "modified": [], "deleted": [], "untracked": []}

    if result.returncode != 0:
        return changes

    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        status = line[:2].strip()
        file_path = line[3:].strip()

        if status == "M":
            changes["modified"].append(file_path)
        elif status == "A":
            changes["added"].append(file_path)
        elif status == "D":
            changes["deleted"].append(file_path)
        elif status == "??":
            changes["untracked"].append(file_path)

    return changes


def load_adrs(repo_root: Path) -> list[dict[str, str]]:
    """Load ADR metadata from docs/ADRs/."""
    adr_dir = repo_root / "docs" / "ADRs"
    adrs = []

    if not adr_dir.exists():
        return adrs

    for adr_file in adr_dir.glob("*.md"):
        content = adr_file.read_text()
        lines = content.split("\n")

        # Extract title from first line
        title = adr_file.stem
        if lines and lines[0].startswith("# "):
            title = lines[0][2:].strip()

        # Extract status
        status = "Unknown"
        for line in lines:
            if line.startswith("## Status:"):
                status = line.split(":", 1)[1].strip()
                break

        adrs.append(
            {
                "id": adr_file.stem,
                "title": title,
                "status": status,
            }
        )

    return sorted(adrs, key=lambda x: x["id"])


def render_template(
    template_name: str, context: dict[str, Any], output_path: Path, templates_dir: Path
) -> None:
    """Render Jinja2 template to output file."""
    try:
        from jinja2 import Environment, FileSystemLoader
    except ImportError:
        # Fallback: use simple string formatting
        _render_simple_template(template_name, context, output_path, templates_dir)
        return

    env = Environment(loader=FileSystemLoader(str(templates_dir)))
    template = env.get_template(template_name)
    content = template.render(**context)
    output_path.write_text(content)


def _render_simple_template(
    template_name: str, context: dict[str, Any], output_path: Path, templates_dir: Path
) -> None:
    """Simple template rendering without Jinja2 (fallback)."""
    template_path = templates_dir / template_name
    if not template_path.exists():
        output_path.write_text(f"# {template_name}\n\nTemplate not found.\n")
        return

    content = template_path.read_text()

    # Simple variable replacement
    for key, value in context.items():
        content = content.replace(f"{{{{ {key} }}}}", str(value))

    # Handle simple loops for lists
    for key, value in context.items():
        if isinstance(value, list) and value:
            # Find loop patterns
            start_pattern = f"{{% for item in {key} %}}"
            end_pattern = "{% endfor %}"
            if start_pattern in content and end_pattern in content:
                before, rest = content.split(start_pattern, 1)
                loop_content, after = rest.split(end_pattern, 1)
                items_text = ""
                for item in value:
                    items_text += loop_content.replace("{{ item }}", str(item))
                content = before + items_text + after

    output_path.write_text(content)


def should_generate(repo_root: Path) -> bool:
    """Check if context bundle should be regenerated based on changed files."""
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD~1..HEAD"],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )

    if result.returncode != 0:
        # No previous commit or other error - generate anyway
        return True

    changed_files = result.stdout.strip().split("\n")

    # Generate only if these paths changed
    trigger_paths = ["docs/ADRs/", "python/src/", "docs/"]
    skip_extensions = [".pyc", ".test.py"]

    for file in changed_files:
        if not file:
            continue

        # Skip test files and build artifacts
        if any(file.endswith(ext) for ext in skip_extensions):
            continue
        if "test" in file.lower():
            continue

        # Check if file matches trigger paths
        for trigger in trigger_paths:
            if file.startswith(trigger):
                return True

    return False


def generate_context_bundle(repo_root: Path, force: bool = False) -> dict[str, str]:
    """Generate all context bundle files.

    Args:
        repo_root: Root directory of git repository
        force: Force generation even if no changes detected

    Returns:
        Dict with generated file paths
    """
    # Ensure directories exist
    context_dir = repo_root / ".archon" / "context"
    context_dir.mkdir(parents=True, exist_ok=True)

    templates_dir = repo_root / "scripts" / "context_templates"

    # Check if should generate (unless forced)
    if not force and not should_generate(repo_root):
        return {"skipped": "No triggering changes detected"}

    # Collect data
    branch = get_current_branch(repo_root)
    recent_commits = get_recent_commits(repo_root)
    purpose = get_branch_purpose(branch)
    changes = get_uncommitted_changes(repo_root)
    adrs = load_adrs(repo_root)

    generated = {}

    # Generate STATUS.md
    status_context = {
        "branch": branch,
        "purpose": purpose,
        "recent_commits": recent_commits,
        "active_worktrees": [
            {"branch": branch, "path": str(repo_root), "is_current": True},
        ],
    }
    status_path = context_dir / "STATUS.md"
    render_template("STATUS.md.j2", status_context, status_path, templates_dir)
    generated["STATUS.md"] = str(status_path)

    # Generate CHANGES.md
    changes_context = {
        "added": changes.get("added", []),
        "modified": changes.get("modified", []),
        "deleted": changes.get("deleted", []),
        "ai_summary": "",  # Could be enhanced with LLM later
    }
    changes_path = context_dir / "CHANGES.md"
    render_template("CHANGES.md.j2", changes_context, changes_path, templates_dir)
    generated["CHANGES.md"] = str(changes_path)

    # Generate ARCHITECTURE.md
    arch_context = {
        "adrs": adrs,
    }
    arch_path = context_dir / "ARCHITECTURE.md"
    render_template("ARCHITECTURE.md.j2", arch_context, arch_path, templates_dir)
    generated["ARCHITECTURE.md"] = str(arch_path)

    # Generate KNOWN_ISSUES.md (simplified - no DB query)
    issues_context = {
        "audit_findings": [],
        "dismissed_findings": [],
        "tech_debt": [],
    }
    issues_path = context_dir / "KNOWN_ISSUES.md"
    render_template("KNOWN_ISSUES.md.j2", issues_context, issues_path, templates_dir)
    generated["KNOWN_ISSUES.md"] = str(issues_path)

    return generated


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Generate Archon context bundle")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Git repository root (default: current directory)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force generation even if no changes detected",
    )
    args = parser.parse_args()

    try:
        generated = generate_context_bundle(args.repo_root, force=args.force)

        if "skipped" in generated:
            print(f"Skipped: {generated['skipped']}")
            sys.exit(0)

        print("Generated context bundle:")
        for name, path in generated.items():
            print(f"  - {name}: {path}")

    except Exception as e:
        print(f"Error generating context bundle: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
