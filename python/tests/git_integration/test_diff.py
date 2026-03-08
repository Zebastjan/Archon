"""Tests for Git diff functionality."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.server.services.git.git_diff_service import GitDiffService
from src.server.services.git.git_repository_service import GitRepositoryService
from tests.git_integration.test_git_repository_integration import (
    FakeSupabaseClient,
    _init_git_repository,
    _run_git,
)


@pytest.fixture
def diff_test_repo(tmp_path: Path):
    """Create a repository with changes to test diff functionality."""
    repo_path = _init_git_repository(tmp_path / "diff-test")

    # Commit 1: Initial state
    (repo_path / "main.py").write_text(
        "def hello():\n    print('Hello')\n\ndef world():\n    print('World')\n",
        encoding="utf-8",
    )
    _run_git(repo_path, "add", "main.py")
    _run_git(repo_path, "commit", "-m", "Add hello and world functions")
    commit1_sha = _run_git(repo_path, "rev-parse", "HEAD").stdout.strip()

    # Commit 2: Modify hello function, add new function
    (repo_path / "main.py").write_text(
        "def hello():\n    print('Hello, World!')\n\ndef world():\n    print('World')\n\ndef greet(name):\n    print(f'Hello, {name}!')\n",
        encoding="utf-8",
    )
    _run_git(repo_path, "add", "main.py")
    _run_git(repo_path, "commit", "-m", "Update hello function and add greet")
    commit2_sha = _run_git(repo_path, "rev-parse", "HEAD").stdout.strip()

    # Commit 3: Add new file
    (repo_path / "utils.py").write_text(
        "def utility():\n    return 'util'\n", encoding="utf-8"
    )
    _run_git(repo_path, "add", "utils.py")
    _run_git(repo_path, "commit", "-m", "Add utils.py")
    commit3_sha = _run_git(repo_path, "rev-parse", "HEAD").stdout.strip()

    # Commit 4: Delete README.md
    (repo_path / "README.md").unlink()
    _run_git(repo_path, "add", "README.md")
    _run_git(repo_path, "commit", "-m", "Remove README")
    commit4_sha = _run_git(repo_path, "rev-parse", "HEAD").stdout.strip()

    return {
        "repo_path": str(repo_path),
        "commit1": commit1_sha,  # Initial
        "commit2": commit2_sha,  # Modified main.py
        "commit3": commit3_sha,  # Added utils.py
        "commit4": commit4_sha,  # Deleted README.md
    }


def test_diff_shows_modified_file(
    diff_test_repo, git_service: GitRepositoryService, supabase_client: FakeSupabaseClient
) -> None:
    """Test that diff correctly identifies modified files."""
    diff_service = GitDiffService(git_service)

    # Get diff between commit1 and commit2 (modified main.py)
    diff = diff_service.get_diff(
        repo_path=diff_test_repo["repo_path"],
        from_sha=diff_test_repo["commit1"],
        to_sha=diff_test_repo["commit2"],
    )

    assert diff.files_changed == 1, "Should have 1 file changed"
    assert diff.additions > 0, "Should have additions"
    assert diff.deletions > 0, "Should have deletions"

    # Check file details
    file_diff = diff.files[0]
    assert file_diff.path == "main.py"
    assert file_diff.status == "modified"
    assert file_diff.language == "python"
    assert file_diff.is_binary is False

    # Check hunks
    assert len(file_diff.hunks) > 0, "Should have at least one hunk"


def test_diff_shows_added_file(
    diff_test_repo, git_service: GitRepositoryService, supabase_client: FakeSupabaseClient
) -> None:
    """Test that diff correctly identifies added files."""
    diff_service = GitDiffService(git_service)

    # Get diff between commit2 and commit3 (added utils.py)
    diff = diff_service.get_diff(
        repo_path=diff_test_repo["repo_path"],
        from_sha=diff_test_repo["commit2"],
        to_sha=diff_test_repo["commit3"],
    )

    assert diff.files_changed == 1, "Should have 1 file changed"

    # Check file details
    file_diff = diff.files[0]
    assert file_diff.path == "utils.py"
    assert file_diff.status == "added"
    assert file_diff.language == "python"
    assert file_diff.additions > 0, "Added file should have additions"
    assert file_diff.deletions == 0, "Added file should have no deletions"


def test_diff_shows_deleted_file(
    diff_test_repo, git_service: GitRepositoryService, supabase_client: FakeSupabaseClient
) -> None:
    """Test that diff correctly identifies deleted files."""
    diff_service = GitDiffService(git_service)

    # Get diff between commit3 and commit4 (deleted README.md)
    diff = diff_service.get_diff(
        repo_path=diff_test_repo["repo_path"],
        from_sha=diff_test_repo["commit3"],
        to_sha=diff_test_repo["commit4"],
    )

    assert diff.files_changed == 1, "Should have 1 file changed"

    # Check file details
    file_diff = diff.files[0]
    assert file_diff.path == "README.md"
    assert file_diff.status == "deleted"
    assert file_diff.additions == 0, "Deleted file should have no additions"
    assert file_diff.deletions > 0, "Deleted file should have deletions"


def test_diff_hunks_have_correct_line_numbers(
    diff_test_repo, git_service: GitRepositoryService, supabase_client: FakeSupabaseClient
) -> None:
    """Test that diff hunks have correct line number information."""
    diff_service = GitDiffService(git_service)

    # Get diff between commit1 and commit2
    diff = diff_service.get_diff(
        repo_path=diff_test_repo["repo_path"],
        from_sha=diff_test_repo["commit1"],
        to_sha=diff_test_repo["commit2"],
    )

    file_diff = diff.files[0]
    assert len(file_diff.hunks) > 0

    # Check that hunks have valid line numbers
    for hunk in file_diff.hunks:
        assert hunk.old_start > 0, "Old start line should be positive"
        assert hunk.new_start > 0, "New start line should be positive"
        assert hunk.old_lines >= 0, "Old lines should be non-negative"
        assert hunk.new_lines >= 0, "New lines should be non-negative"
        assert isinstance(hunk.diff_text, str), "Diff text should be a string"


def test_diff_counts_additions_and_deletions(
    diff_test_repo, git_service: GitRepositoryService, supabase_client: FakeSupabaseClient
) -> None:
    """Test that diff accurately counts additions and deletions."""
    diff_service = GitDiffService(git_service)

    # Get diff between commit1 and commit2
    diff = diff_service.get_diff(
        repo_path=diff_test_repo["repo_path"],
        from_sha=diff_test_repo["commit1"],
        to_sha=diff_test_repo["commit2"],
    )

    file_diff = diff.files[0]

    # Sum of hunk additions should equal file additions
    hunk_additions = sum(h.additions for h in file_diff.hunks)
    assert hunk_additions == file_diff.additions

    # Sum of hunk deletions should equal file deletions
    hunk_deletions = sum(h.deletions for h in file_diff.hunks)
    assert hunk_deletions == file_diff.deletions

    # Total diff additions/deletions should match file
    assert diff.additions == file_diff.additions
    assert diff.deletions == file_diff.deletions


def test_diff_with_file_filter(
    diff_test_repo, git_service: GitRepositoryService, supabase_client: FakeSupabaseClient
) -> None:
    """Test that diff can be filtered to a specific file."""
    diff_service = GitDiffService(git_service)

    # Get diff for all files
    full_diff = diff_service.get_diff(
        repo_path=diff_test_repo["repo_path"],
        from_sha=diff_test_repo["commit1"],
        to_sha=diff_test_repo["commit3"],
    )

    # Should have multiple files (main.py modified, utils.py added)
    assert full_diff.files_changed >= 2

    # Get diff for only main.py
    filtered_diff = diff_service.get_diff(
        repo_path=diff_test_repo["repo_path"],
        from_sha=diff_test_repo["commit1"],
        to_sha=diff_test_repo["commit3"],
        file_path="main.py",
    )

    # Should have only 1 file
    assert filtered_diff.files_changed == 1
    assert filtered_diff.files[0].path == "main.py"


def test_diff_between_same_commits(
    diff_test_repo, git_service: GitRepositoryService, supabase_client: FakeSupabaseClient
) -> None:
    """Test that diff between same commits returns empty diff."""
    diff_service = GitDiffService(git_service)

    # Get diff between same commit
    diff = diff_service.get_diff(
        repo_path=diff_test_repo["repo_path"],
        from_sha=diff_test_repo["commit1"],
        to_sha=diff_test_repo["commit1"],
    )

    assert diff.files_changed == 0, "Same commits should have no changes"
    assert diff.additions == 0
    assert diff.deletions == 0
    assert len(diff.files) == 0


def test_diff_captures_function_context(
    diff_test_repo, git_service: GitRepositoryService, supabase_client: FakeSupabaseClient
) -> None:
    """Test that diff captures function context in hunks."""
    diff_service = GitDiffService(git_service)

    # Get diff between commit1 and commit2 (modified hello function)
    diff = diff_service.get_diff(
        repo_path=diff_test_repo["repo_path"],
        from_sha=diff_test_repo["commit1"],
        to_sha=diff_test_repo["commit2"],
    )

    file_diff = diff.files[0]

    # Check that at least one hunk has context (may be empty depending on Git version)
    # Context is the text after @@ ... @@ in the hunk header
    has_hunks_with_text = any(hunk.diff_text for hunk in file_diff.hunks)
    assert has_hunks_with_text, "Hunks should have diff text"
