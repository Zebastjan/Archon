"""Generator for file-deletions test fixture.

This fixture creates a repository with file deletion scenarios:
- Files exist on one branch but deleted on another
- Validates proper file tree filtering
- Tests 404 handling for deleted files
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FileDeletionsFixture:
    """Metadata about the generated file-deletions fixture."""

    repo_path: Path
    main_branch: str
    cleanup_branch: str
    # Files that exist on both branches
    shared_file_path: str
    # Deleted on main, exists on cleanup branch
    legacy_file_path: str
    # Deleted on cleanup branch, exists on main
    old_util_file_path: str
    initial_commit_sha: str
    main_deletion_commit_sha: str
    cleanup_deletion_commit_sha: str


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


def create_file_deletions_fixture(base_path: Path) -> FileDeletionsFixture:
    """
    Create a test repository with file deletion scenarios.

    Structure:
        Initial state (both branches):
            - app.py (survives on both)
            - legacy.py (deleted on main, kept on feature/cleanup)
            - old_util.py (kept on main, deleted on feature/cleanup)

        main branch after deletion:
            - app.py ✓
            - old_util.py ✓
            [legacy.py deleted]

        feature/cleanup branch after deletion:
            - app.py ✓
            - legacy.py ✓
            [old_util.py deleted]

    This validates:
        - File tree shows different files per branch
        - Deleted files don't appear in tree
        - Reading deleted file returns 404
        - File counts differ per branch
    """
    repo_path = base_path / "file-deletions"
    repo_path.mkdir(parents=True, exist_ok=True)

    # Initialize repository
    init_result = _run_git(repo_path, "init", "-b", "main", check=False)
    if init_result.returncode != 0:
        _run_git(repo_path, "init")
        _run_git(repo_path, "checkout", "-b", "main")

    _run_git(repo_path, "config", "user.email", "archon-tests@example.com")
    _run_git(repo_path, "config", "user.name", "Archon Test")

    # Initial commit with all files
    app_content = '"""Main application entry point."""\n\ndef main():\n    print("App running")\n\nif __name__ == "__main__":\n    main()\n'
    legacy_content = '"""Legacy code to be removed."""\n\ndef old_function():\n    # This function is deprecated\n    pass\n'
    old_util_content = '"""Old utility functions."""\n\ndef helper():\n    return "legacy helper"\n'

    (repo_path / "app.py").write_text(app_content, encoding="utf-8")
    (repo_path / "legacy.py").write_text(legacy_content, encoding="utf-8")
    (repo_path / "old_util.py").write_text(old_util_content, encoding="utf-8")

    _run_git(repo_path, "add", ".")
    _run_git(repo_path, "commit", "-m", "Initial commit with all files")
    initial_commit_sha = _run_git(repo_path, "rev-parse", "HEAD").stdout.strip()

    # Create cleanup branch before making changes
    _run_git(repo_path, "checkout", "-b", "feature/cleanup")

    # On cleanup branch: delete old_util.py
    (repo_path / "old_util.py").unlink()
    _run_git(repo_path, "add", "old_util.py")
    _run_git(repo_path, "commit", "-m", "Remove old utility functions")
    cleanup_deletion_commit_sha = _run_git(repo_path, "rev-parse", "HEAD").stdout.strip()

    # Switch back to main and delete different file
    _run_git(repo_path, "checkout", "main")

    # On main branch: delete legacy.py
    (repo_path / "legacy.py").unlink()
    _run_git(repo_path, "add", "legacy.py")
    _run_git(repo_path, "commit", "-m", "Remove legacy code")
    main_deletion_commit_sha = _run_git(repo_path, "rev-parse", "HEAD").stdout.strip()

    return FileDeletionsFixture(
        repo_path=repo_path,
        main_branch="main",
        cleanup_branch="feature/cleanup",
        shared_file_path="app.py",
        legacy_file_path="legacy.py",
        old_util_file_path="old_util.py",
        initial_commit_sha=initial_commit_sha,
        main_deletion_commit_sha=main_deletion_commit_sha,
        cleanup_deletion_commit_sha=cleanup_deletion_commit_sha,
    )
