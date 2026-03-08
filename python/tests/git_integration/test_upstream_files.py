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


@pytest.fixture
def t1100_commit_tree_fixture(upstream_fixture_path):
    """Return path to t1100-commit-tree test fixture."""
    fixture_path = upstream_fixture_path / "t1100-commit-tree"
    if not fixture_path.exists():
        pytest.skip(f"Fixture not found: {fixture_path}. Run create_fixtures.py first.")
    return fixture_path


def test_t1100_commit_tree_structure(
    t1100_commit_tree_fixture,
    git_service
):
    """Test complex directory structure in commit tree."""
    success, result = git_service.register_repository(
        repo_path=str(t1100_commit_tree_fixture),
        source_id="test-source-t1100"
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
    assert sync_result["commit_count"] == 3  # Initial + add + modify

    adapter = GitTestAdapter(
        repo_path=t1100_commit_tree_fixture,
        service=git_service,
        repo_id=repo_id
    )

    head_sha = adapter.get_commit_sha("HEAD")
    files = adapter.get_file_tree_cli(head_sha)

    # Should have 7 files (5 initial + 2 added)
    assert len(files) == 7, f"Expected 7 files, got {len(files)}"
    
    # Verify specific files exist
    assert "root.txt" in files
    assert "dir1/file1.txt" in files
    assert "dir1/subdir/file2.txt" in files
    assert "dir1/file4.txt" in files  # Added in second commit
    assert "dir3/new.txt" in files  # Added in second commit


def test_t1100_file_tree_at_each_commit(
    t1100_commit_tree_fixture,
    git_service
):
    """Test file tree changes across multiple commits."""
    success, result = git_service.register_repository(
        repo_path=str(t1100_commit_tree_fixture),
        source_id="test-source-t1100-commits"
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
        repo_path=t1100_commit_tree_fixture,
        service=git_service,
        repo_id=repo_id
    )

    # Get all commit SHAs
    import subprocess
    result = subprocess.run(
        ["git", "log", "--format=%H"],
        cwd=t1100_commit_tree_fixture,
        capture_output=True,
        text=True
    )
    commit_shas = result.stdout.strip().split("\n")
    
    # Verify file tree at each commit
    for sha in commit_shas:
        if sha:
            adapter.assert_file_tree_matches(sha)


def test_t1100_modified_file_content(
    t1100_commit_tree_fixture,
    git_service
):
    """Test that modified file content is correctly retrieved."""
    success, result = git_service.register_repository(
        repo_path=str(t1100_commit_tree_fixture),
        source_id="test-source-t1100-modified"
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
        repo_path=t1100_commit_tree_fixture,
        service=git_service,
        repo_id=repo_id
    )

    # Get commits
    import subprocess
    result = subprocess.run(
        ["git", "log", "--format=%H"],
        cwd=t1100_commit_tree_fixture,
        capture_output=True,
        text=True
    )
    commit_shas = result.stdout.strip().split("\n")
    
    # First commit should have original root.txt content
    first_commit = commit_shas[-1]  # Oldest
    adapter.assert_file_content_matches("root.txt", first_commit)
    
    # Last commit should have modified content
    last_commit = commit_shas[0]  # Newest
    adapter.assert_file_content_matches("root.txt", last_commit)


@pytest.fixture
def t1200_checkout_fixture(upstream_fixture_path):
    """Return path to t1200-checkout test fixture."""
    fixture_path = upstream_fixture_path / "t1200-checkout"
    if not fixture_path.exists():
        pytest.skip(f"Fixture not found: {fixture_path}. Run create_fixtures.py first.")
    return fixture_path


def test_t1200_checkout_branch_file_trees(
    t1200_checkout_fixture,
    git_service
):
    """Test file trees differ between branches after checkout."""
    success, result = git_service.register_repository(
        repo_path=str(t1200_checkout_fixture),
        source_id="test-source-t1200"
    )
    assert success

    repo_id = result["repo_id"]

    adapter = GitTestAdapter(
        repo_path=t1200_checkout_fixture,
        service=git_service,
        repo_id=repo_id
    )

    # Sync commits from all branches
    for branch in ["main", "master", "branch-a", "branch-b"]:
        try:
            git_service.sync_commits(repo_id=repo_id, branch_name=branch, max_commits=100)
        except:
            pass

    # Get SHAs for each branch
    main_sha = adapter.get_commit_sha("main") if "main" in ["main", "master"] else adapter.get_commit_sha("master")
    branch_a_sha = adapter.get_commit_sha("branch-a")
    branch_b_sha = adapter.get_commit_sha("branch-b")

    # Get file trees
    main_files = set(adapter.get_file_tree_cli(main_sha))
    branch_a_files = set(adapter.get_file_tree_cli(branch_a_sha))
    branch_b_files = set(adapter.get_file_tree_cli(branch_b_sha))

    # Branch-specific files
    assert "branch-a-only.txt" in branch_a_files
    assert "branch-b-only.txt" in branch_b_files
    assert "branch-a-only.txt" not in main_files
    assert "branch-b-only.txt" not in main_files


def test_t1200_checkout_content_differences(
    t1200_checkout_fixture,
    git_service
):
    """Test file content differs between branches."""
    success, result = git_service.register_repository(
        repo_path=str(t1200_checkout_fixture),
        source_id="test-source-t1200-content"
    )
    assert success

    repo_id = result["repo_id"]

    adapter = GitTestAdapter(
        repo_path=t1200_checkout_fixture,
        service=git_service,
        repo_id=repo_id
    )

    # Get branch-a SHA and verify content
    branch_a_sha = adapter.get_commit_sha("branch-a")
    adapter.assert_file_content_matches("shared.txt", branch_a_sha)
    adapter.assert_file_content_matches("branch-a-only.txt", branch_a_sha)


@pytest.fixture
def t2000_checkout_fixture(upstream_fixture_path):
    """Return path to t2000-checkout test fixture."""
    fixture_path = upstream_fixture_path / "t2000-checkout"
    if not fixture_path.exists():
        pytest.skip(f"Fixture not found: {fixture_path}. Run create_fixtures.py first.")
    return fixture_path


def test_t2000_checkout_develop_branch_changes(
    t2000_checkout_fixture,
    git_service
):
    """Test file operations (add, delete, modify) in develop branch."""
    success, result = git_service.register_repository(
        repo_path=str(t2000_checkout_fixture),
        source_id="test-source-t2000"
    )
    assert success

    repo_id = result["repo_id"]

    adapter = GitTestAdapter(
        repo_path=t2000_checkout_fixture,
        service=git_service,
        repo_id=repo_id
    )

    # Sync develop branch
    git_service.sync_commits(repo_id=repo_id, branch_name="develop", max_commits=100)

    main_sha = adapter.get_commit_sha("main") if "main" in ["main", "master"] else adapter.get_commit_sha("master")
    develop_sha = adapter.get_commit_sha("develop")

    # Main should have config.yaml
    main_files = adapter.get_file_tree_cli(main_sha)
    assert "config.yaml" in main_files

    # Develop should NOT have config.yaml (deleted)
    develop_files = adapter.get_file_tree_cli(develop_sha)
    assert "config.yaml" not in develop_files
    assert "src/new_feature.py" in develop_files  # Added
    assert "src/app.py" in develop_files  # Modified


def test_t2000_modified_file_retrieval(
    t2000_checkout_fixture,
    git_service
):
    """Test that modified file content is correctly retrieved."""
    success, result = git_service.register_repository(
        repo_path=str(t2000_checkout_fixture),
        source_id="test-source-t2000-modified"
    )
    assert success

    repo_id = result["repo_id"]

    adapter = GitTestAdapter(
        repo_path=t2000_checkout_fixture,
        service=git_service,
        repo_id=repo_id
    )

    # Sync develop branch
    git_service.sync_commits(repo_id=repo_id, branch_name="develop", max_commits=100)

    # Get both SHAs and verify modified file
    main_sha = adapter.get_commit_sha("main") if "main" in ["main", "master"] else adapter.get_commit_sha("master")
    develop_sha = adapter.get_commit_sha("develop")

    adapter.assert_file_content_matches("src/app.py", main_sha)
    adapter.assert_file_content_matches("src/app.py", develop_sha)
