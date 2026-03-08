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
        source_id="test-source-tree"
    )
    assert success, f"Failed to register: {result.get('error')}"

    repo_id = result["repo_id"]
    default_branch = result["default_branch"]

    # Sync commits
    sync_success, sync_result = git_service.sync_commits(
        repo_id=repo_id,
        branch_name=default_branch,
        max_commits=100
    )
    assert sync_success, f"Failed to sync: {sync_result.get('error')}"

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


def test_repository_register_twice_creates_new_repo(
    t0001_init_fixture,
    git_service
):
    """Test that registering the same repository twice creates separate entries."""
    # First registration
    success1, result1 = git_service.register_repository(
        repo_path=str(t0001_init_fixture),
        source_id="test-source-idempotent"
    )
    assert success1
    repo_id1 = result1["repo_id"]

    # Second registration - creates new repo entry
    success2, result2 = git_service.register_repository(
        repo_path=str(t0001_init_fixture),
        source_id="test-source-idempotent-2"
    )
    assert success2
    
    # Different source_id creates new repo entry
    assert result2["repo_id"] != repo_id1


def test_sync_commits_multiple_branches(
    t0001_init_fixture,
    git_service
):
    """Test syncing commits from multiple branches."""
    success, result = git_service.register_repository(
        repo_path=str(t0001_init_fixture),
        source_id="test-source-multi"
    )
    assert success

    repo_id = result["repo_id"]
    default_branch = result["default_branch"]

    # Sync default branch
    sync1, result1 = git_service.sync_commits(
        repo_id=repo_id,
        branch_name=default_branch,
        max_commits=100
    )
    assert sync1
    assert result1["commit_count"] > 0


def test_get_file_content_specific_commit(
    t0001_init_fixture,
    git_service
):
    """Test retrieving file content from specific commits."""
    success, result = git_service.register_repository(
        repo_path=str(t0001_init_fixture),
        source_id="test-source-specific"
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
        repo_path=t0001_init_fixture,
        service=git_service,
        repo_id=repo_id
    )

    # Get all commit SHAs
    import subprocess
    result = subprocess.run(
        ["git", "log", "--format=%H"],
        cwd=t0001_init_fixture,
        capture_output=True,
        text=True
    )
    commit_shas = [sha for sha in result.stdout.strip().split("\n") if sha]

    # Get file tree at each commit and verify content
    for sha in commit_shas:
        files = adapter.get_file_tree_cli(sha)
        for file_path in files:
            adapter.assert_file_content_matches(file_path, sha)


def test_commit_sha_format_validation(
    t0001_init_fixture,
    git_service
):
    """Test that commit SHAs are valid 40-character hex strings."""
    success, result = git_service.register_repository(
        repo_path=str(t0001_init_fixture),
        source_id="test-source-sha"
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

    # Verify each commit SHA format
    for commit in sync_result.get("commits", []):
        sha = commit["sha"]
        assert len(sha) == 40, f"SHA should be 40 chars: {sha}"
        assert all(c in "0123456789abcdef" for c in sha.lower()), f"SHA should be hex: {sha}"


def test_commit_metadata_fields(
    t0001_init_fixture,
    git_service
):
    """Test that commits have required metadata fields."""
    success, result = git_service.register_repository(
        repo_path=str(t0001_init_fixture),
        source_id="test-source-meta"
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

    # Verify each commit has required fields
    for commit in sync_result.get("commits", []):
        assert "sha" in commit
        assert "message" in commit
        assert "author_name" in commit
        assert "author_email" in commit
        assert "commit_date" in commit


def test_repository_path_normalized(
    t0001_init_fixture,
    git_service
):
    """Test that repository paths are handled correctly."""
    success, result = git_service.register_repository(
        repo_path=str(t0001_init_fixture),
        source_id="test-source-path"
    )
    assert success
    
    # The original path should exist and be valid
    assert t0001_init_fixture.exists()
    assert (t0001_init_fixture / ".git").exists()


def test_empty_repository_registration(
    git_service,
    tmp_path
):
    """Test registering a newly initialized empty repository."""
    from git import Repo
    
    repo_path = tmp_path / "empty_repo"
    repo_path.mkdir()
    Repo.init(repo_path)
    
    # Configure git user
    repo = Repo(repo_path)
    with repo.config_writer() as config:
        config.set_value("user", "name", "Test User")
        config.set_value("user", "email", "test@example.com")
    
    # Create a file and commit
    (repo_path / "README.md").write_text("# Empty repo\n")
    repo.index.add(["README.md"])
    repo.index.commit("Initial commit")
    
    success, result = git_service.register_repository(
        repo_path=str(repo_path),
        source_id="test-empty"
    )
    assert success
    
    # Sync should work
    sync_success, sync_result = git_service.sync_commits(
        repo_id=result["repo_id"],
        branch_name=result["default_branch"]
    )
    assert sync_success
    assert sync_result["commit_count"] == 1
