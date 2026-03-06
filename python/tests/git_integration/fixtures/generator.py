"""
Git Test Fixture Generator

Generates git repositories from YAML spec files and creates EXPECTED.json manifests
for verifying integration test results.

Inspired by repo-smith (https://github.com/git-mastery/repo-smith) but implemented
as a lightweight solution since repo-smith requires Python 3.13+.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Step:
    name: str | None = None
    description: str | None = None
    type: str = ""
    filename: str | None = None
    contents: str | None = None
    files: list[str] | None = None
    message: str | None = None
    branch_name: str | None = None
    new_name: str | None = None
    start_point: str | None = None
    commit_hash: str | None = None
    empty: bool = False
    no_ff: bool = False
    runs: str | None = None
    tag_name: str | None = None
    id: str | None = None


@dataclass
class Initialization:
    clone_from: str | None = None
    steps: list[Step] = field(default_factory=list)


@dataclass
class FixtureSpec:
    name: str = ""
    description: str = ""
    initialization: Initialization = field(default_factory=Initialization)


def run_git(repo_path: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Execute a git command in the target repository."""
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo_path),
        check=False,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip() or result.stdout.strip()}")
    return result


def parse_spec(spec_path: Path) -> FixtureSpec:
    """Parse a YAML spec file into a FixtureSpec."""
    with open(spec_path) as f:
        data = yaml.safe_load(f)

    spec = FixtureSpec(
        name=data.get("name", ""),
        description=data.get("description", ""),
    )

    init_data = data.get("initialization", {})
    spec.initialization.clone_from = init_data.get("clone-from")

    for step_data in init_data.get("steps", []):
        step = Step(
            name=step_data.get("name"),
            description=step_data.get("description"),
            type=step_data.get("type", ""),
            filename=step_data.get("filename"),
            contents=step_data.get("contents"),
            files=step_data.get("files"),
            message=step_data.get("message"),
            branch_name=step_data.get("branch-name"),
            new_name=step_data.get("new-name"),
            start_point=step_data.get("start-point"),
            commit_hash=step_data.get("commit-hash"),
            empty=step_data.get("empty", False),
            no_ff=step_data.get("no-ff", False),
            runs=step_data.get("runs"),
            tag_name=step_data.get("tag-name"),
            id=step_data.get("id"),
        )
        spec.initialization.steps.append(step)

    return spec


def initialize_repository(repo_path: Path, spec: FixtureSpec) -> None:
    """Initialize a git repository from a spec."""
    repo_path.mkdir(parents=True, exist_ok=True)

    # Initialize git repo
    run_git(repo_path, "init", "-b", "main", check=False)
    if (repo_path / ".git").exists():
        pass
    else:
        run_git(repo_path, "init")
        run_git(repo_path, "checkout", "-b", "main")

    # Configure git user
    run_git(repo_path, "config", "user.email", "archon-tests@example.com")
    run_git(repo_path, "config", "user.name", "Archon Test")

    # Process steps
    for step in spec.initialization.steps:
        _process_step(repo_path, step)


def _process_step(repo_path: Path, step: Step) -> None:
    """Process a single step from the spec."""
    if step.type == "new-file":
        _handle_new_file(repo_path, step)
    elif step.type == "edit-file":
        _handle_edit_file(repo_path, step)
    elif step.type == "add":
        _handle_add(repo_path, step)
    elif step.type == "commit":
        _handle_commit(repo_path, step)
    elif step.type == "branch":
        _handle_branch(repo_path, step)
    elif step.type == "checkout":
        _handle_checkout(repo_path, step)
    elif step.type == "merge":
        _handle_merge(repo_path, step)
    elif step.type == "tag":
        _handle_tag(repo_path, step)
    elif step.type == "bash":
        _handle_bash(repo_path, step)
    else:
        raise ValueError(f"Unknown step type: {step.type}")


def _handle_new_file(repo_path: Path, step: Step) -> None:
    """Handle new-file step."""
    if not step.filename or step.contents is None:
        raise ValueError("new-file requires filename and contents")

    file_path = repo_path / step.filename
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(step.contents, encoding="utf-8")


def _handle_edit_file(repo_path: Path, step: Step) -> None:
    """Handle edit-file step (overwrite)."""
    if not step.filename or step.contents is None:
        raise ValueError("edit-file requires filename and contents")

    file_path = repo_path / step.filename
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(step.contents, encoding="utf-8")


def _handle_add(repo_path: Path, step: Step) -> None:
    """Handle add step."""
    if not step.files:
        raise ValueError("add requires files")

    for f in step.files:
        run_git(repo_path, "add", f)


def _handle_commit(repo_path: Path, step: Step) -> None:
    """Handle commit step."""
    if not step.message:
        raise ValueError("commit requires message")

    if step.empty:
        run_git(repo_path, "commit", "--allow-empty", "-m", step.message)
    else:
        run_git(repo_path, "commit", "-m", step.message)


def _handle_branch(repo_path: Path, step: Step) -> None:
    """Handle branch creation step."""
    if not step.branch_name:
        raise ValueError("branch requires branch-name")

    run_git(repo_path, "branch", step.branch_name)


def _handle_checkout(repo_path: Path, step: Step) -> None:
    """Handle checkout step."""
    if not step.branch_name:
        raise ValueError("checkout requires branch-name")

    if step.start_point:
        run_git(repo_path, "checkout", "-b", step.branch_name, step.start_point)
    else:
        run_git(repo_path, "checkout", step.branch_name)


def _handle_merge(repo_path: Path, step: Step) -> None:
    """Handle merge step."""
    if not step.branch_name:
        raise ValueError("merge requires branch-name")

    if step.no_ff:
        run_git(repo_path, "merge", "--no-ff", step.branch_name)
    else:
        run_git(repo_path, "merge", step.branch_name)


def _handle_tag(repo_path: Path, step: Step) -> None:
    """Handle tag step."""
    if not step.tag_name:
        raise ValueError("tag requires tag-name")

    run_git(repo_path, "tag", step.tag_name)


def _handle_bash(repo_path: Path, step: Step) -> None:
    """Handle bash step."""
    if not step.runs:
        raise ValueError("bash requires runs")

    result = subprocess.run(
        step.runs,
        cwd=str(repo_path),
        shell=True,
        check=True,
        capture_output=True,
        text=True,
    )


def generate_expected(repo_path: Path) -> dict[str, Any]:
    """Generate EXPECTED.json from an initialized repository."""
    # Get branches
    branches_result = run_git(repo_path, "branch", "--format=%(refname:short)")
    branches = [b.strip() for b in branches_result.stdout.strip().split("\n") if b.strip()]

    # Get commits
    commits_result = run_git(
        repo_path,
        "log",
        "--format=%H|%an|%ae|%ad|%s",
        "--date=iso",
    )
    commits = []
    for line in commits_result.stdout.strip().split("\n"):
        if line.strip():
            parts = line.split("|")
            if len(parts) >= 5:
                commits.append(
                    {
                        "sha": parts[0],
                        "author_name": parts[1],
                        "author_email": parts[2],
                        "date": parts[3],
                        "message": "|".join(parts[4:]),
                    }
                )

    # Get tags
    tags_result = run_git(repo_path, "tag", "--format=%(refname:short)|%(objectname:short)")
    tags = []
    for line in tags_result.stdout.strip().split("\n"):
        if line.strip():
            parts = line.split("|")
            if len(parts) >= 2:
                tags.append(
                    {
                        "name": parts[0],
                        "sha": parts[1],
                    }
                )

    # Get files at HEAD
    files_result = run_git(
        repo_path,
        "ls-tree",
        "-r",
        "--full-tree",
        "--format=%(objecttype)|%(path)|%(objectname)",
        "HEAD",
    )
    files = []
    for line in files_result.stdout.strip().split("\n"):
        if line.strip():
            parts = line.split("|")
            if len(parts) >= 3:
                obj_type = parts[0]
                file_path = parts[1]
                blob_sha = parts[2]

                # Only process blob (file) entries, not trees or submodules
                if obj_type == "blob":
                    # Get raw content to check for binary (without text mode conversion)
                    content_result = subprocess.run(
                        ["git", "cat-file", "-p", blob_sha],
                        cwd=str(repo_path),
                        check=False,
                        capture_output=True,
                    )
                    if content_result.returncode == 0:
                        # Check for null bytes in raw output
                        is_binary = b"\x00" in content_result.stdout
                    else:
                        is_binary = False

                    # Get size
                    size_result = run_git(repo_path, "cat-file", "-s", blob_sha, check=False)
                    size = (
                        int(size_result.stdout.strip())
                        if size_result.returncode == 0 and size_result.stdout.strip().isdigit()
                        else 0
                    )

                    files.append(
                        {
                            "path": file_path,
                            "sha": blob_sha,
                            "size": size,
                            "type": obj_type,
                            "is_binary": is_binary,
                        }
                    )

    return {
        "name": repo_path.name,
        "branches": branches,
        "commits": commits,
        "tags": tags,
        "files": files,
        "default_branch": "main",
    }


def generate_fixture(fixture_dir: Path, output_dir: Path | None = None) -> Path:
    """
    Generate a fixture repository and return the path.

    Args:
        fixture_dir: Directory containing spec.yaml
        output_dir: Optional output directory (defaults to same as fixture_dir)

    Returns:
        Path to the generated repository
    """
    if output_dir is None:
        output_dir = fixture_dir

    spec_path = fixture_dir / "spec.yaml"
    if not spec_path.exists():
        raise FileNotFoundError(f"Spec file not found: {spec_path}")

    spec = parse_spec(spec_path)
    repo_path = output_dir / ".repo"

    # Clean up existing repo
    if repo_path.exists():
        import shutil

        shutil.rmtree(repo_path)

    initialize_repository(repo_path, spec)

    # Generate EXPECTED.json
    expected = generate_expected(repo_path)
    expected_path = fixture_dir / "EXPECTED.json"
    with open(expected_path, "w") as f:
        json.dump(expected, f, indent=2)

    return repo_path


def get_fixture_path(fixture_name: str) -> Path:
    """Get the path to a fixture directory."""
    fixtures_dir = Path(__file__).parent / fixture_name
    if not fixtures_dir.exists():
        raise FileNotFoundError(f"Fixture not found: {fixture_name}")
    return fixtures_dir


def generate_all_fixtures() -> dict[str, Path]:
    """Generate all fixtures and return a mapping of name to path."""
    fixtures_base = Path(__file__).parent
    results = {}

    for fixture_dir in fixtures_base.iterdir():
        if fixture_dir.is_dir() and (fixture_dir / "spec.yaml").exists():
            print(f"Generating fixture: {fixture_dir.name}")
            repo_path = generate_fixture(fixture_dir)
            results[fixture_dir.name] = repo_path

    return results


if __name__ == "__main__":
    generate_all_fixtures()
