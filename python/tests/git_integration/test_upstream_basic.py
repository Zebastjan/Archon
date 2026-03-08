"""
Test GitRepositoryService against Git's upstream test fixtures (Phase 1: Basic operations).
"""

import pytest
from pathlib import Path

from src.server.services.git.git_repository_service import GitRepositoryService
from tests.git_integration.upstream.git_test_adapter import GitTestAdapter


@pytest.fixture
def upstream_fixture_path():
    """Return path to upstream fixtures directory."""
    return Path(__file__).parent / "fixtures" / "upstream"


@pytest.fixture
def t0001_init_fixture(upstream_fixture_path):
    """Return path to t0001-init test fixture."""
    fixture_path = upstream_fixture_path / "t0001-init"
    if not fixture_path.exists():
        pytest.skip(f"Fixture not found: {fixture_path}. Run extract_fixtures.py first.")
    return fixture_path


def test_t0001_repository_initialization(
    t0001_init_fixture,
    git_service
):
    """
    Test that GitRepositoryService correctly handles initialized repositories.

    Validates against Git's t0001-init.sh test.
    """
    # Register repository
    success, result = git_service.register_repository(
        repo_path=str(t0001_init_fixture),
        source_id="test-source-t0001"
    )

    assert success, f"Failed to register repository: {result.get('error', 'Unknown error')}"

    repo_id = result["repo_id"]
    default_branch = result["default_branch"]

    # Create adapter
    adapter = GitTestAdapter(
        repo_path=t0001_init_fixture,
        service=git_service,
        repo_id=repo_id
    )

    # Test 1: Repository has .git directory
    assert (t0001_init_fixture / ".git").exists()

    # Test 2: Can get current branch
    branch = adapter.get_branch_name()
    assert branch in ["main", "master"]

    # Test 3: Repository metadata is correct
    assert result["repo_name"] == t0001_init_fixture.name


def test_t0001_commit_history(
    t0001_init_fixture,
    git_service
):
    """
    Test that GitRepositoryService correctly retrieves commit history.

    Validates against Git's t0001-init.sh test.
    """
    # Register repository
    success, result = git_service.register_repository(
        repo_path=str(t0001_init_fixture),
        source_id="test-source-t0001-commits"
    )

    assert success, f"Failed to register repository: {result.get('error', 'Unknown error')}"

    repo_id = result["repo_id"]
    default_branch = result["default_branch"]

    # Sync commits
    sync_success, sync_result = git_service.sync_commits(
        repo_id=repo_id,
        branch_name=default_branch,
        max_commits=100
    )

    assert sync_success, f"Failed to sync commits: {sync_result.get('error', 'Unknown error')}"
    assert sync_result["commit_count"] > 0, "Should have at least one commit"


def test_upstream_file_content_matches_cli(
    t0001_init_fixture,
    git_service
):
    """
    Test that file content retrieved via service matches git CLI output.
    """
    # Register repository
    success, result = git_service.register_repository(
        repo_path=str(t0001_init_fixture),
        source_id="test-source-t0001-content"
    )

    assert success, f"Failed to register repository: {result.get('error', 'Unknown error')}"

    repo_id = result["repo_id"]
    default_branch = result["default_branch"]

    # Sync commits
    sync_success, sync_result = git_service.sync_commits(
        repo_id=repo_id,
        branch_name=default_branch,
        max_commits=100
    )

    assert sync_success, f"Failed to sync commits: {sync_result.get('error', 'Unknown error')}"

    # Create adapter
    adapter = GitTestAdapter(
        repo_path=t0001_init_fixture,
        service=git_service,
        repo_id=repo_id
    )

    # Get HEAD commit
    head_sha = adapter.get_commit_sha("HEAD")

    # Get file tree
    files = adapter.get_file_tree_cli(head_sha)

    if not files:
        pytest.skip("No files in repository")

    # Test first file's content matches
    first_file = files[0]
    adapter.assert_file_content_matches(first_file, head_sha)


def test_upstream_file_tree_matches_cli(
    t0001_init_fixture,
    git_service
):
    """
    Test that file tree retrieved via service matches git CLI output.
    """
    # Register repository
    success, result = git_service.register_repository(
        repo_path=str(t0001_init_fixture),
        source_id="test-source-t0001-tree"
    )

    assert success, f"Failed to register repository: {result.get('error', 'Unknown error')}"

    repo_id = result["repo_id"]
    default_branch = result["default_branch"]

    # Sync commits
    sync_success, sync_result = git_service.sync_commits(
        repo_id=repo_id,
        branch_name=default_branch,
        max_commits=100
    )

    assert sync_success, f"Failed to sync commits: {sync_result.get('error', 'Unknown error')}"

    # Create adapter
    adapter = GitTestAdapter(
        repo_path=t0001_init_fixture,
        service=git_service,
        repo_id=repo_id
    )

    # Get HEAD commit
    head_sha = adapter.get_commit_sha("HEAD")

    # Assert file trees match
    adapter.assert_file_tree_matches(head_sha)
