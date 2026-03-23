"""Tests for file deletion scenarios across branches."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

from src.server.services.git.git_repository_service import GitRepositoryService
from tests.git_integration.fixtures.generators import create_file_deletions_fixture
from tests.git_integration.test_git_repository_integration import FakeSupabaseClient


@pytest.fixture
def deletions_fixture(tmp_path: Path):
    """Create file-deletions test fixture."""
    return create_file_deletions_fixture(tmp_path)


def test_deleted_files_not_in_tree(
    deletions_fixture, git_service: GitRepositoryService, supabase_client: FakeSupabaseClient
) -> None:
    """Test that deleted files don't appear in file tree."""
    # Register repository
    success, result = git_service.register_repository(
        str(deletions_fixture.repo_path), source_id="source-deletions"
    )
    assert success is True
    repo_id = result["repo_id"]

    # Sync both branches
    git_service.sync_commits(repo_id, "main", max_commits=10)
    git_service.sync_commits(repo_id, "feature/cleanup", max_commits=10)

    # Get file tree for main branch (legacy.py deleted)
    tree_success, main_tree = git_service.get_file_tree(
        repo_id, deletions_fixture.main_deletion_commit_sha
    )
    assert tree_success is True
    main_files = {f["file_path"] for f in main_tree["files"]}

    assert "app.py" in main_files, "app.py should exist on main"
    assert "old_util.py" in main_files, "old_util.py should exist on main"
    assert "legacy.py" not in main_files, "legacy.py should be deleted on main"

    # Get file tree for cleanup branch (old_util.py deleted)
    tree_success, cleanup_tree = git_service.get_file_tree(
        repo_id, deletions_fixture.cleanup_deletion_commit_sha
    )
    assert tree_success is True
    cleanup_files = {f["file_path"] for f in cleanup_tree["files"]}

    assert "app.py" in cleanup_files, "app.py should exist on cleanup branch"
    assert "legacy.py" in cleanup_files, "legacy.py should exist on cleanup branch"
    assert "old_util.py" not in cleanup_files, "old_util.py should be deleted on cleanup branch"


def test_reading_deleted_file_fails(
    deletions_fixture, git_service: GitRepositoryService, supabase_client: FakeSupabaseClient
) -> None:
    """Test that reading a deleted file raises GitFileNotFoundError."""
    from src.server.services.git.git_repository_service import GitFileNotFoundError

    # Register repository
    success, result = git_service.register_repository(
        str(deletions_fixture.repo_path), source_id="source-read-deleted"
    )
    assert success is True
    repo_id = result["repo_id"]

    # Try to read legacy.py from main branch (where it's deleted)
    # Should raise GitFileNotFoundError
    with pytest.raises(GitFileNotFoundError) as exc_info:
        git_service.get_file_content(
            repo_id, deletions_fixture.main_deletion_commit_sha, "legacy.py"
        )

    assert "legacy.py" in str(exc_info.value).lower()

    # Same file should be readable from cleanup branch
    content_success, content_result = git_service.get_file_content(
        repo_id, deletions_fixture.cleanup_deletion_commit_sha, "legacy.py"
    )
    assert content_success is True
    assert "Legacy code" in content_result["content"]


def test_file_exists_in_initial_commit(
    deletions_fixture, git_service: GitRepositoryService, supabase_client: FakeSupabaseClient
) -> None:
    """Test that all files exist in the initial commit before deletions."""
    # Register repository
    success, result = git_service.register_repository(
        str(deletions_fixture.repo_path), source_id="source-initial"
    )
    assert success is True
    repo_id = result["repo_id"]

    # Get file tree at initial commit
    tree_success, initial_tree = git_service.get_file_tree(
        repo_id, deletions_fixture.initial_commit_sha
    )
    assert tree_success is True
    initial_files = {f["file_path"] for f in initial_tree["files"]}

    # All files should exist in initial state
    assert "app.py" in initial_files
    assert "legacy.py" in initial_files
    assert "old_util.py" in initial_files
    assert len(initial_files) == 3, f"Expected 3 files initially, got {len(initial_files)}"


def test_file_count_differs_after_deletion(
    deletions_fixture, git_service: GitRepositoryService, supabase_client: FakeSupabaseClient
) -> None:
    """Test that file counts differ between branches after deletions."""
    # Register repository
    success, result = git_service.register_repository(
        str(deletions_fixture.repo_path), source_id="source-count"
    )
    assert success is True
    repo_id = result["repo_id"]

    # Get file counts for all states
    tree_success, initial_tree = git_service.get_file_tree(
        repo_id, deletions_fixture.initial_commit_sha
    )
    assert tree_success is True

    tree_success, main_tree = git_service.get_file_tree(
        repo_id, deletions_fixture.main_deletion_commit_sha
    )
    assert tree_success is True

    tree_success, cleanup_tree = git_service.get_file_tree(
        repo_id, deletions_fixture.cleanup_deletion_commit_sha
    )
    assert tree_success is True

    # Verify counts
    assert len(initial_tree["files"]) == 3, "Initial should have 3 files"
    assert len(main_tree["files"]) == 2, "Main should have 2 files after deletion"
    assert len(cleanup_tree["files"]) == 2, "Cleanup should have 2 files after deletion"


def test_deletion_tracked_in_commits(
    deletions_fixture, git_service: GitRepositoryService, supabase_client: FakeSupabaseClient
) -> None:
    """Test that deletion commits are properly tracked."""
    # Register repository
    success, result = git_service.register_repository(
        str(deletions_fixture.repo_path), source_id="source-commit-tracking"
    )
    assert success is True
    repo_id = result["repo_id"]

    # Sync both branches
    git_service.sync_commits(repo_id, "main", max_commits=10)
    git_service.sync_commits(repo_id, "feature/cleanup", max_commits=10)

    # Get all commits
    commits_table = supabase_client.table("archon_git_commits")
    all_commits = [row for row in commits_table.rows if row.get("repo_id") == repo_id]

    # Find deletion commits by message
    main_deletion = next(
        (c for c in all_commits if "Remove legacy code" in c["message"]), None
    )
    cleanup_deletion = next(
        (c for c in all_commits if "Remove old utility" in c["message"]), None
    )

    assert main_deletion is not None, "Main deletion commit should be tracked"
    assert cleanup_deletion is not None, "Cleanup deletion commit should be tracked"

    # Verify branch associations
    assert "main" in main_deletion["branches"]
    assert "feature/cleanup" in cleanup_deletion["branches"]
