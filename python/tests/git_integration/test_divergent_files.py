"""Tests for divergent file content across branches."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.server.services.git.git_repository_service import GitRepositoryService
from tests.git_integration.fixtures.generators import create_divergent_files_fixture
from tests.git_integration.test_git_repository_integration import FakeSupabaseClient


@pytest.fixture
def divergent_fixture(tmp_path: Path):
    """Create divergent-files test fixture."""
    return create_divergent_files_fixture(tmp_path)


def test_same_file_different_content_across_branches(
    divergent_fixture, git_service: GitRepositoryService, supabase_client: FakeSupabaseClient
) -> None:
    """Test that the same file path can have different content on different branches."""
    # Register repository
    success, result = git_service.register_repository(
        str(divergent_fixture.repo_path), source_id="source-divergent"
    )
    assert success is True
    repo_id = result["repo_id"]

    # Sync main branch
    sync_success, _ = git_service.sync_commits(repo_id, "main", max_commits=10)
    assert sync_success is True

    # Sync feature branch
    sync_success, _ = git_service.sync_commits(repo_id, "feature/config-changes", max_commits=10)
    assert sync_success is True

    # Get file tree for main branch at HEAD
    tree_success, main_tree = git_service.get_file_tree(
        repo_id, divergent_fixture.main_commit_sha
    )
    assert tree_success is True

    # Get file tree for feature branch at HEAD
    tree_success, feature_tree = git_service.get_file_tree(
        repo_id, divergent_fixture.feature_commit_sha
    )
    assert tree_success is True

    # Find config.json in both trees
    main_config = next(
        (f for f in main_tree["files"] if f["file_path"] == "config.json"), None
    )
    feature_config = next(
        (f for f in feature_tree["files"] if f["file_path"] == "config.json"), None
    )

    assert main_config is not None, "config.json should exist on main branch"
    assert feature_config is not None, "config.json should exist on feature branch"

    # Blob SHAs should be different (different content)
    assert main_config["blob_sha"] != feature_config["blob_sha"], (
        "config.json should have different blob SHAs on different branches"
    )

    # Both should be detected as JSON files (lowercase)
    assert main_config["language"] == "json"
    assert feature_config["language"] == "json"


def test_file_content_retrieval_differs_by_branch(
    divergent_fixture, git_service: GitRepositoryService, supabase_client: FakeSupabaseClient
) -> None:
    """Test that reading file content returns different content per branch."""
    # Register and sync
    success, result = git_service.register_repository(
        str(divergent_fixture.repo_path), source_id="source-content-test"
    )
    assert success is True
    repo_id = result["repo_id"]

    # Get file content from main branch
    content_success, main_content = git_service.get_file_content(
        repo_id, divergent_fixture.main_commit_sha, "config.json"
    )
    assert content_success is True
    assert '"debug": false' in main_content["content"]
    assert '"verbose"' not in main_content["content"]

    # Get file content from feature branch
    content_success, feature_content = git_service.get_file_content(
        repo_id, divergent_fixture.feature_commit_sha, "config.json"
    )
    assert content_success is True
    assert '"debug": true' in feature_content["content"]
    assert '"verbose": true' in feature_content["content"]


def test_shared_file_has_same_content(
    divergent_fixture, git_service: GitRepositoryService, supabase_client: FakeSupabaseClient
) -> None:
    """Test that shared files (README.md) have identical content and blob SHA."""
    # Register repository
    success, result = git_service.register_repository(
        str(divergent_fixture.repo_path), source_id="source-shared"
    )
    assert success is True
    repo_id = result["repo_id"]

    # Get file tree for both branches
    tree_success, main_tree = git_service.get_file_tree(
        repo_id, divergent_fixture.main_commit_sha
    )
    assert tree_success is True

    tree_success, feature_tree = git_service.get_file_tree(
        repo_id, divergent_fixture.feature_commit_sha
    )
    assert tree_success is True

    # Find README.md in both trees
    main_readme = next((f for f in main_tree["files"] if f["file_path"] == "README.md"), None)
    feature_readme = next(
        (f for f in feature_tree["files"] if f["file_path"] == "README.md"), None
    )

    assert main_readme is not None
    assert feature_readme is not None

    # Blob SHAs should be identical (same content)
    assert main_readme["blob_sha"] == feature_readme["blob_sha"], (
        "README.md should have same blob SHA on both branches"
    )


def test_branch_specific_files_not_in_other_branch(
    divergent_fixture, git_service: GitRepositoryService, supabase_client: FakeSupabaseClient
) -> None:
    """Test that branch-specific files don't appear in other branch's tree."""
    # Register repository
    success, result = git_service.register_repository(
        str(divergent_fixture.repo_path), source_id="source-specific"
    )
    assert success is True
    repo_id = result["repo_id"]

    # Get file tree for main branch
    tree_success, main_tree = git_service.get_file_tree(
        repo_id, divergent_fixture.main_commit_sha
    )
    assert tree_success is True
    main_files = {f["file_path"] for f in main_tree["files"]}

    # Get file tree for feature branch
    tree_success, feature_tree = git_service.get_file_tree(
        repo_id, divergent_fixture.feature_commit_sha
    )
    assert tree_success is True
    feature_files = {f["file_path"] for f in feature_tree["files"]}

    # Verify main-only file
    assert "settings.yaml" in main_files, "settings.yaml should exist on main"
    assert "settings.yaml" not in feature_files, "settings.yaml should NOT exist on feature branch"

    # Verify feature-only file
    assert "experiment.py" in feature_files, "experiment.py should exist on feature branch"
    assert "experiment.py" not in main_files, "experiment.py should NOT exist on main"


def test_file_count_differs_by_branch(
    divergent_fixture, git_service: GitRepositoryService, supabase_client: FakeSupabaseClient
) -> None:
    """Test that file counts differ between branches."""
    # Register repository
    success, result = git_service.register_repository(
        str(divergent_fixture.repo_path), source_id="source-count"
    )
    assert success is True
    repo_id = result["repo_id"]

    # Get file counts for both branches
    tree_success, main_tree = git_service.get_file_tree(
        repo_id, divergent_fixture.main_commit_sha
    )
    assert tree_success is True

    tree_success, feature_tree = git_service.get_file_tree(
        repo_id, divergent_fixture.feature_commit_sha
    )
    assert tree_success is True

    # File counts should differ
    main_count = len(main_tree["files"])
    feature_count = len(feature_tree["files"])

    # Main has: README.md, config.json, settings.yaml = 3
    # Feature has: README.md, config.json, experiment.py = 3
    assert main_count == 3, f"Expected 3 files on main, got {main_count}"
    assert feature_count == 3, f"Expected 3 files on feature, got {feature_count}"

    # But the actual files are different
    main_files = {f["file_path"] for f in main_tree["files"]}
    feature_files = {f["file_path"] for f in feature_tree["files"]}
    assert main_files != feature_files, "File sets should differ between branches"
