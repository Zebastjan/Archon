"""Generator for merge-scenarios test fixture.

This fixture creates a repository with complex merge scenarios:
- Multiple parents (2+ parent commits)
- 3-way merges
- Merge commits with file changes from both branches
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class MergeScenariosFixture:
    """Metadata about the generated merge-scenarios fixture."""

    repo_path: Path
    main_branch: str
    feature_a_branch: str
    feature_b_branch: str
    initial_commit_sha: str
    feature_a_commit_sha: str
    feature_b_commit_sha: str
    merge_commit_sha: str
    feature_a_file_path: str
    feature_b_file_path: str
    shared_file_path: str


def _run_git(repo_path: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Execute a git command in the target repository."""
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo_path),
        check=False,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed: {result.stderr.strip() or result.stdout.strip()}"
        )
    return result


def create_merge_scenarios_fixture(base_path: Path) -> MergeScenariosFixture:
    """
    Create a test repository with complex merge scenarios.

    Structure:
        * M3 (main) - Merge feature-a and feature-b
        |\\
        | * F2 (feature-b) - Add feature B
        * | F1 (feature-a) - Add feature A
        |/
        * C0 - Initial commit

    This validates:
        - Merge commit has 2 parent SHAs in parent_shas[] array
        - All parent commits properly tracked
        - File tree at merge commit includes files from both branches
        - Multi-parent commit ancestry
    """
    repo_path = base_path / "merge-scenarios"
    repo_path.mkdir(parents=True, exist_ok=True)

    # Initialize repository
    init_result = _run_git(repo_path, "init", "-b", "main", check=False)
    if init_result.returncode != 0:
        _run_git(repo_path, "init")
        _run_git(repo_path, "checkout", "-b", "main")

    _run_git(repo_path, "config", "user.email", "archon-tests@example.com")
    _run_git(repo_path, "config", "user.name", "Archon Test")

    # C0: Initial commit
    readme_content = "# Merge Scenarios Test\n\nInitial project setup.\n"
    (repo_path / "README.md").write_text(readme_content, encoding="utf-8")

    _run_git(repo_path, "add", "README.md")
    _run_git(repo_path, "commit", "-m", "Initial commit")
    initial_commit_sha = _run_git(repo_path, "rev-parse", "HEAD").stdout.strip()

    # Create feature-a branch and add feature A
    _run_git(repo_path, "checkout", "-b", "feature-a")
    feature_a_content = '"""Feature A implementation."""\n\ndef feature_a():\n    return "Feature A active"\n'
    (repo_path / "feature_a.py").write_text(feature_a_content, encoding="utf-8")

    _run_git(repo_path, "add", "feature_a.py")
    _run_git(repo_path, "commit", "-m", "Add feature A")
    feature_a_commit_sha = _run_git(repo_path, "rev-parse", "HEAD").stdout.strip()

    # Go back to initial commit and create feature-b branch
    _run_git(repo_path, "checkout", initial_commit_sha)
    _run_git(repo_path, "checkout", "-b", "feature-b")

    feature_b_content = '"""Feature B implementation."""\n\ndef feature_b():\n    return "Feature B active"\n'
    (repo_path / "feature_b.py").write_text(feature_b_content, encoding="utf-8")

    _run_git(repo_path, "add", "feature_b.py")
    _run_git(repo_path, "commit", "-m", "Add feature B")
    feature_b_commit_sha = _run_git(repo_path, "rev-parse", "HEAD").stdout.strip()

    # Merge both features into main
    _run_git(repo_path, "checkout", "main")

    # Merge feature-a (fast-forward not possible since we'll merge feature-b too)
    _run_git(repo_path, "merge", "--no-ff", "feature-a", "-m", "Merge feature-a")

    # Merge feature-b (creates the multi-parent merge)
    _run_git(repo_path, "merge", "--no-ff", "feature-b", "-m", "Merge feature-b")

    merge_commit_sha = _run_git(repo_path, "rev-parse", "HEAD").stdout.strip()

    # Verify merge commit has 2 parents
    parents_output = _run_git(repo_path, "rev-list", "--parents", "-n", "1", "HEAD").stdout.strip()
    parent_count = len(parents_output.split()) - 1  # First is the commit itself
    if parent_count != 2:
        raise RuntimeError(
            f"Expected merge commit to have 2 parents, got {parent_count}. "
            f"Git output: {parents_output}"
        )

    return MergeScenariosFixture(
        repo_path=repo_path,
        main_branch="main",
        feature_a_branch="feature-a",
        feature_b_branch="feature-b",
        initial_commit_sha=initial_commit_sha,
        feature_a_commit_sha=feature_a_commit_sha,
        feature_b_commit_sha=feature_b_commit_sha,
        merge_commit_sha=merge_commit_sha,
        feature_a_file_path="feature_a.py",
        feature_b_file_path="feature_b.py",
        shared_file_path="README.md",
    )
