"""Generator for divergent-files test fixture.

This fixture creates a repository with file content divergence across branches:
- Same file path exists on multiple branches with different content
- Different blob SHAs for the same file path
- Tests file tree filtering and content retrieval by branch
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DivergentFilesFixture:
    """Metadata about the generated divergent-files fixture."""

    repo_path: Path
    main_branch: str
    feature_branch: str
    shared_file_path: str  # Same path, same content on both branches
    divergent_file_path: str  # Same path, different content
    main_only_file_path: str  # Exists only on main
    feature_only_file_path: str  # Exists only on feature branch
    main_config_content: str
    feature_config_content: str
    initial_commit_sha: str
    main_commit_sha: str
    feature_commit_sha: str


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


def create_divergent_files_fixture(base_path: Path) -> DivergentFilesFixture:
    """
    Create a test repository with divergent file content across branches.

    Structure:
        main branch:
            - README.md (shared, same content)
            - config.json (divergent content: {"debug": false})
            - settings.yaml (main only)

        feature/config-changes branch:
            - README.md (shared, same content)
            - config.json (divergent content: {"debug": true, "verbose": true})
            - experiment.py (feature only)

    This validates:
        - Same file path with different content (different blob SHA)
        - File existence divergence
        - Proper content retrieval per branch
        - File tree filtering by branch
    """
    repo_path = base_path / "divergent-files"
    repo_path.mkdir(parents=True, exist_ok=True)

    # Initialize repository
    init_result = _run_git(repo_path, "init", "-b", "main", check=False)
    if init_result.returncode != 0:
        _run_git(repo_path, "init")
        _run_git(repo_path, "checkout", "-b", "main")

    _run_git(repo_path, "config", "user.email", "archon-tests@example.com")
    _run_git(repo_path, "config", "user.name", "Archon Test")

    # Initial commit with shared file and divergent file (base version)
    readme_content = "# Divergent Files Test\n\nThis file is identical on all branches.\n"
    config_main_content = '{\n  "debug": false,\n  "log_level": "info"\n}\n'

    (repo_path / "README.md").write_text(readme_content, encoding="utf-8")
    (repo_path / "config.json").write_text(config_main_content, encoding="utf-8")

    _run_git(repo_path, "add", ".")
    _run_git(repo_path, "commit", "-m", "Initial commit with base config")
    initial_commit_sha = _run_git(repo_path, "rev-parse", "HEAD").stdout.strip()

    # Add main-only file
    settings_content = "production:\n  enabled: true\n  timeout: 30\n"
    (repo_path / "settings.yaml").write_text(settings_content, encoding="utf-8")

    _run_git(repo_path, "add", "settings.yaml")
    _run_git(repo_path, "commit", "-m", "Add production settings")
    main_commit_sha = _run_git(repo_path, "rev-parse", "HEAD").stdout.strip()

    # Create feature branch from initial commit (before settings.yaml was added)
    _run_git(repo_path, "checkout", "-b", "feature/config-changes", initial_commit_sha)

    # Modify config.json with different content
    config_feature_content = '{\n  "debug": true,\n  "verbose": true,\n  "log_level": "debug"\n}\n'
    (repo_path / "config.json").write_text(config_feature_content, encoding="utf-8")

    # Add feature-only file
    experiment_content = '"""Experimental feature implementation."""\n\ndef experiment():\n    print("Testing new approach")\n'
    (repo_path / "experiment.py").write_text(experiment_content, encoding="utf-8")

    _run_git(repo_path, "add", ".")
    _run_git(repo_path, "commit", "-m", "Enable debug mode and add experiment")
    feature_commit_sha = _run_git(repo_path, "rev-parse", "HEAD").stdout.strip()

    # Return to main branch
    _run_git(repo_path, "checkout", "main")

    return DivergentFilesFixture(
        repo_path=repo_path,
        main_branch="main",
        feature_branch="feature/config-changes",
        shared_file_path="README.md",
        divergent_file_path="config.json",
        main_only_file_path="settings.yaml",
        feature_only_file_path="experiment.py",
        main_config_content=config_main_content,
        feature_config_content=config_feature_content,
        initial_commit_sha=initial_commit_sha,
        main_commit_sha=main_commit_sha,
        feature_commit_sha=feature_commit_sha,
    )
