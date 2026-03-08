"""
Test GitRepositoryService against upstream test fixtures (Phase 2: Branch operations).
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
def t3200_branch_fixture(upstream_fixture_path):
    """Return path to t3200-branch test fixture."""
    fixture_path = upstream_fixture_path / "t3200-branch"
    if not fixture_path.exists():
        pytest.skip(f"Fixture not found: {fixture_path}. Run create_fixtures.py first.")
    return fixture_path


def test_t3200_list_branches(
    t3200_branch_fixture,
    git_service
):
    """Test listing all branches in repository."""
    success, result = git_service.register_repository(
        repo_path=str(t3200_branch_fixture),
        source_id="test-source-t3200"
    )
    assert success

    repo_id = result["repo_id"]
    
    # List branches via service
    branches = git_service.list_branches(str(t3200_branch_fixture))
    
    # Should have main/master, develop, feature/new-thing, hotfix/urgent
    assert len(branches) >= 4, f"Expected at least 4 branches, got {branches}"
    
    expected_branches = {"develop", "feature/new-thing", "hotfix/urgent"}
    found_branches = set(branches)
    
    # Check main or master exists
    assert "main" in found_branches or "master" in found_branches
    
    # Check other branches
    for expected in expected_branches:
        assert expected in found_branches, f"Missing expected branch: {expected}"


def test_t3200_get_current_branch(
    t3200_branch_fixture,
    git_service
):
    """Test getting current branch name."""
    success, result = git_service.register_repository(
        repo_path=str(t3200_branch_fixture),
        source_id="test-source-t3200-current"
    )
    assert success

    current_branch = git_service.get_current_branch(str(t3200_branch_fixture))
    
    # Should be main or master (the default after fixture creation)
    assert current_branch in ["main", "master"]


def test_t3200_branch_commit_shas_differ(
    t3200_branch_fixture,
    git_service
):
    """Test that different branches have different HEAD commits."""
    success, result = git_service.register_repository(
        repo_path=str(t3200_branch_fixture),
        source_id="test-source-t3200-shas"
    )
    assert success

    repo_id = result["repo_id"]
    default_branch = result["default_branch"]

    # Get commit SHAs for different branches
    main_sha = git_service.get_current_commit_sha(str(t3200_branch_fixture), default_branch)
    develop_sha = git_service.get_current_commit_sha(str(t3200_branch_fixture), "develop")
    feature_sha = git_service.get_current_commit_sha(str(t3200_branch_fixture), "feature/new-thing")
    
    # All SHAs should be different
    shas = [main_sha, develop_sha, feature_sha]
    assert len(set(shas)) == 3, f"Expected unique SHAs for each branch, got: {shas}"
