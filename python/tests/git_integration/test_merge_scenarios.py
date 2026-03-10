"""Tests for complex merge scenarios with multiple parents."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.server.services.git.git_repository_service import GitRepositoryService
from tests.git_integration.fixtures.generators import create_merge_scenarios_fixture
from tests.git_integration.test_git_repository_integration import FakeSupabaseClient


@pytest.fixture
def merge_fixture(tmp_path: Path):
    """Create merge-scenarios test fixture."""
    return create_merge_scenarios_fixture(tmp_path)


def test_merge_commit_has_multiple_parents(
    merge_fixture, git_service: GitRepositoryService, supabase_client: FakeSupabaseClient
) -> None:
    """Test that merge commits have multiple parents in parent_shas array."""
    # Register repository
    success, result = git_service.register_repository(str(merge_fixture.repo_path), source_id="source-merge")
    assert success is True
    repo_id = result["repo_id"]

    # Sync main branch (includes merge commit)
    sync_success, _ = git_service.sync_commits(repo_id, "main", max_commits=10)
    assert sync_success is True

    # Get merge commit from database
    commits_table = supabase_client.table("archon_git_commits")
    merge_commit = next(
        (c for c in commits_table.rows if c["commit_sha"] == merge_fixture.merge_commit_sha),
        None,
    )

    assert merge_commit is not None, "Merge commit should be stored in database"
    assert "parent_shas" in merge_commit, "Merge commit should have parent_shas field"

    # Verify parent_shas are properly populated
    parent_shas = merge_commit["parent_shas"]
    assert isinstance(parent_shas, list), "parent_shas should be a list"
    assert len(parent_shas) == 2, f"Merge commit should have 2 parents, got {len(parent_shas)}"

    # Both parent commits should be in the database
    for parent_sha in parent_shas:
        parent_commit = next((c for c in commits_table.rows if c["commit_sha"] == parent_sha), None)
        assert parent_commit is not None, f"Parent commit {parent_sha} should be in database"


def test_merge_commit_file_tree_includes_both_features(
    merge_fixture, git_service: GitRepositoryService, supabase_client: FakeSupabaseClient
) -> None:
    """Test that file tree at merge commit includes files from both branches."""
    # Register repository
    success, result = git_service.register_repository(str(merge_fixture.repo_path), source_id="source-tree")
    assert success is True
    repo_id = result["repo_id"]

    # Get file tree at merge commit
    tree_success, merge_tree = git_service.get_file_tree(repo_id, merge_fixture.merge_commit_sha)
    assert tree_success is True

    merge_files = {f["file_path"] for f in merge_tree["files"]}

    # Should include files from both feature branches
    assert "README.md" in merge_files, "README.md should exist (from initial commit)"
    assert "feature_a.py" in merge_files, "feature_a.py should exist (from feature-a)"
    assert "feature_b.py" in merge_files, "feature_b.py should exist (from feature-b)"

    assert len(merge_files) == 3, f"Expected 3 files at merge, got {len(merge_files)}"


def test_feature_branches_have_different_files(
    merge_fixture, git_service: GitRepositoryService, supabase_client: FakeSupabaseClient
) -> None:
    """Test that feature branches have their own specific files before merge."""
    # Register repository
    success, result = git_service.register_repository(str(merge_fixture.repo_path), source_id="source-features")
    assert success is True
    repo_id = result["repo_id"]

    # Get file tree for feature-a
    tree_success, feature_a_tree = git_service.get_file_tree(repo_id, merge_fixture.feature_a_commit_sha)
    assert tree_success is True
    feature_a_files = {f["file_path"] for f in feature_a_tree["files"]}

    # Get file tree for feature-b
    tree_success, feature_b_tree = git_service.get_file_tree(repo_id, merge_fixture.feature_b_commit_sha)
    assert tree_success is True
    feature_b_files = {f["file_path"] for f in feature_b_tree["files"]}

    # Feature-a should have feature_a.py but not feature_b.py
    assert "feature_a.py" in feature_a_files
    assert "feature_b.py" not in feature_a_files

    # Feature-b should have feature_b.py but not feature_a.py
    assert "feature_b.py" in feature_b_files
    assert "feature_a.py" not in feature_b_files

    # Both should have README.md
    assert "README.md" in feature_a_files
    assert "README.md" in feature_b_files


def test_all_commits_properly_tracked(
    merge_fixture, git_service: GitRepositoryService, supabase_client: FakeSupabaseClient
) -> None:
    """Test that all commits in merge scenario are properly tracked."""
    # Register repository
    success, result = git_service.register_repository(str(merge_fixture.repo_path), source_id="source-all-commits")
    assert success is True
    repo_id = result["repo_id"]

    # Sync all branches
    git_service.sync_commits(repo_id, "main", max_commits=20)
    git_service.sync_commits(repo_id, "feature-a", max_commits=20)
    git_service.sync_commits(repo_id, "feature-b", max_commits=20)

    # Get all commits
    commits_table = supabase_client.table("archon_git_commits")
    all_commits = [row for row in commits_table.rows if row.get("repo_id") == repo_id]

    # Should have at least 4 commits:
    # - Initial commit
    # - Feature-a commit
    # - Feature-b commit
    # - Merge commits (could be 2: merge feature-a, merge feature-b)
    assert len(all_commits) >= 4, f"Expected at least 4 commits, got {len(all_commits)}"

    # Verify specific commits exist
    commit_shas = {c["commit_sha"] for c in all_commits}
    assert merge_fixture.initial_commit_sha in commit_shas, "Initial commit should be tracked"
    assert merge_fixture.feature_a_commit_sha in commit_shas, "Feature-a commit should be tracked"
    assert merge_fixture.feature_b_commit_sha in commit_shas, "Feature-b commit should be tracked"
    assert merge_fixture.merge_commit_sha in commit_shas, "Merge commit should be tracked"


def test_branch_associations_after_merge(
    merge_fixture, git_service: GitRepositoryService, supabase_client: FakeSupabaseClient
) -> None:
    """Test that branch associations are correct after merge."""
    # Register repository
    success, result = git_service.register_repository(str(merge_fixture.repo_path), source_id="source-branches")
    assert success is True
    repo_id = result["repo_id"]

    # Sync all branches
    git_service.sync_commits(repo_id, "main", max_commits=20)
    git_service.sync_commits(repo_id, "feature-a", max_commits=20)
    git_service.sync_commits(repo_id, "feature-b", max_commits=20)

    # Get commits
    commits_table = supabase_client.table("archon_git_commits")

    # Initial commit should be on all branches
    initial_commit = next(
        (c for c in commits_table.rows if c["commit_sha"] == merge_fixture.initial_commit_sha),
        None,
    )
    assert initial_commit is not None
    assert set(initial_commit["branches"]) == {"main", "feature-a", "feature-b"}

    # Feature-a commit should be on main and feature-a
    feature_a_commit = next(
        (c for c in commits_table.rows if c["commit_sha"] == merge_fixture.feature_a_commit_sha),
        None,
    )
    assert feature_a_commit is not None
    assert "feature-a" in feature_a_commit["branches"]
    assert "main" in feature_a_commit["branches"]  # Merged into main

    # Feature-b commit should be on main and feature-b
    feature_b_commit = next(
        (c for c in commits_table.rows if c["commit_sha"] == merge_fixture.feature_b_commit_sha),
        None,
    )
    assert feature_b_commit is not None
    assert "feature-b" in feature_b_commit["branches"]
    assert "main" in feature_b_commit["branches"]  # Merged into main

    # Merge commit should be on main only
    merge_commit = next(
        (c for c in commits_table.rows if c["commit_sha"] == merge_fixture.merge_commit_sha),
        None,
    )
    assert merge_commit is not None
    assert "main" in merge_commit["branches"]
