"""
Test GitRepositoryService against upstream test fixtures (Phase 2: File operations).
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
def t1000_read_tree_fixture(upstream_fixture_path):
    """Return path to t1000-read-tree test fixture."""
    fixture_path = upstream_fixture_path / "t1000-read-tree"
    if not fixture_path.exists():
        pytest.skip(f"Fixture not found: {fixture_path}. Run create_fixtures.py first.")
    return fixture_path


def test_t1000_read_tree_file_count(
    t1000_read_tree_fixture,
    git_service
):
    """Test that file tree returns correct number of files."""
    success, result = git_service.register_repository(
        repo_path=str(t1000_read_tree_fixture),
        source_id="test-source-t1000"
    )
    assert success, f"Failed to register repository: {result.get('error', 'Unknown error')}"

    repo_id = result["repo_id"]
    default_branch = result["default_branch"]

    sync_success, sync_result = git_service.sync_commits(
        repo_id=repo_id,
        branch_name=default_branch,
        max_commits=100
    )
    assert sync_success

    adapter = GitTestAdapter(
        repo_path=t1000_read_tree_fixture,
        service=git_service,
        repo_id=repo_id
    )

    head_sha = adapter.get_commit_sha("HEAD")
    cli_files = adapter.get_file_tree_cli(head_sha)
    
    # Should have 6 files as defined in fixture
    assert len(cli_files) == 6, f"Expected 6 files, got {len(cli_files)}"


def test_t1000_nested_directories(
    t1000_read_tree_fixture,
    git_service
):
    """Test that nested directory structures are handled correctly."""
    success, result = git_service.register_repository(
        repo_path=str(t1000_read_tree_fixture),
        source_id="test-source-t1000-nested"
    )
    assert success

    repo_id = result["repo_id"]
    default_branch = result["default_branch"]

    sync_success, sync_result = git_service.sync_commits(
        repo_id=repo_id,
        branch_name=default_branch,
        max_commits=100
    )
    assert sync_success

    adapter = GitTestAdapter(
        repo_path=t1000_read_tree_fixture,
        service=git_service,
        repo_id=repo_id
    )

    head_sha = adapter.get_commit_sha("HEAD")
    
    # Verify file tree matches
    adapter.assert_file_tree_matches(head_sha)


def test_t1000_all_file_content_matches(
    t1000_read_tree_fixture,
    git_service
):
    """Test that all files have matching content between CLI and service."""
    success, result = git_service.register_repository(
        repo_path=str(t1000_read_tree_fixture),
        source_id="test-source-t1000-content"
    )
    assert success

    repo_id = result["repo_id"]
    default_branch = result["default_branch"]

    sync_success, sync_result = git_service.sync_commits(
        repo_id=repo_id,
        branch_name=default_branch,
        max_commits=100
    )
    assert sync_success

    adapter = GitTestAdapter(
        repo_path=t1000_read_tree_fixture,
        service=git_service,
        repo_id=repo_id
    )

    head_sha = adapter.get_commit_sha("HEAD")
    files = adapter.get_file_tree_cli(head_sha)

    # Verify each file's content matches
    for file_path in files:
        adapter.assert_file_content_matches(file_path, head_sha)
