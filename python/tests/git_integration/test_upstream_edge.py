"""
Test GitRepositoryService against upstream test fixtures (Phase 4: Edge cases).
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
def t3900_unicode_fixture(upstream_fixture_path):
    """Return path to t3900-unicode test fixture."""
    fixture_path = upstream_fixture_path / "t3900-unicode"
    if not fixture_path.exists():
        pytest.skip(f"Fixture not found: {fixture_path}. Run create_fixtures.py first.")
    return fixture_path


def test_t3900_unicode_file_content(
    t3900_unicode_fixture,
    git_service
):
    """Test handling of unicode content in files."""
    success, result = git_service.register_repository(
        repo_path=str(t3900_unicode_fixture),
        source_id="test-source-t3900"
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
        repo_path=t3900_unicode_fixture,
        service=git_service,
        repo_id=repo_id
    )

    head_sha = adapter.get_commit_sha("HEAD")

    # Verify unicode file content
    adapter.assert_file_content_matches("unicode.txt", head_sha)


def test_t3900_unicode_commit_message(
    t3900_unicode_fixture,
    git_service
):
    """Test that unicode commit messages are handled."""
    success, result = git_service.register_repository(
        repo_path=str(t3900_unicode_fixture),
        source_id="test-source-t3900-message"
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
    assert sync_result["commit_count"] > 0


def test_t3900_unicode_file_tree(
    t3900_unicode_fixture,
    git_service
):
    """Test file tree with unicode filenames."""
    success, result = git_service.register_repository(
        repo_path=str(t3900_unicode_fixture),
        source_id="test-source-t3900-tree"
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
        repo_path=t3900_unicode_fixture,
        service=git_service,
        repo_id=repo_id
    )

    head_sha = adapter.get_commit_sha("HEAD")
    
    # Verify file tree matches (unicode filename if filesystem supports it)
    try:
        adapter.assert_file_tree_matches(head_sha)
    except (UnicodeEncodeError, OSError):
        pytest.skip("Filesystem does not support unicode filenames")
