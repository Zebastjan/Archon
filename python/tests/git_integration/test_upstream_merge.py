"""
Test GitRepositoryService against upstream test fixtures (Phase 3: Merge scenarios).
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
def t3400_rebase_fixture(upstream_fixture_path):
    """Return path to t3400-rebase test fixture."""
    fixture_path = upstream_fixture_path / "t3400-rebase"
    if not fixture_path.exists():
        pytest.skip(f"Fixture not found: {fixture_path}. Run create_fixtures.py first.")
    return fixture_path


@pytest.fixture
def t3600_rm_fixture(upstream_fixture_path):
    """Return path to t3600-rm test fixture."""
    fixture_path = upstream_fixture_path / "t3600-rm"
    if not fixture_path.exists():
        pytest.skip(f"Fixture not found: {fixture_path}. Run create_fixtures.py first.")
    return fixture_path


def test_t3400_divergent_branches_file_trees(
    t3400_rebase_fixture,
    git_service
):
    """Test file trees differ between divergent branches."""
    success, result = git_service.register_repository(
        repo_path=str(t3400_rebase_fixture),
        source_id="test-source-t3400"
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

    sync_success2, sync_result2 = git_service.sync_commits(
        repo_id=repo_id,
        branch_name="branch-a",
        max_commits=100
    )
    assert sync_success2

    sync_success3, sync_result3 = git_service.sync_commits(
        repo_id=repo_id,
        branch_name="branch-b",
        max_commits=100
    )
    assert sync_success3

    adapter = GitTestAdapter(
        repo_path=t3400_rebase_fixture,
        service=git_service,
        repo_id=repo_id
    )

    # Get commit SHAs for each branch
    main_sha = adapter.get_commit_sha(default_branch)
    branch_a_sha = adapter.get_commit_sha("branch-a")
    branch_b_sha = adapter.get_commit_sha("branch-b")

    # Get file trees
    main_files = set(adapter.get_file_tree_cli(main_sha))
    branch_a_files = set(adapter.get_file_tree_cli(branch_a_sha))
    branch_b_files = set(adapter.get_file_tree_cli(branch_b_sha))

    # Each branch should have different files
    assert "file-a.txt" in branch_a_files, "branch-a should have file-a.txt"
    assert "file-b.txt" in branch_b_files, "branch-b should have file-b.txt"
    assert "file-a.txt" not in main_files, "main should not have file-a.txt"
    assert "file-b.txt" not in main_files, "main should not have file-b.txt"


def test_t3400_branch_specific_file_content(
    t3400_rebase_fixture,
    git_service
):
    """Test that file content is branch-specific."""
    success, result = git_service.register_repository(
        repo_path=str(t3400_rebase_fixture),
        source_id="test-source-t3400-content"
    )
    assert success

    repo_id = result["repo_id"]

    adapter = GitTestAdapter(
        repo_path=t3400_rebase_fixture,
        service=git_service,
        repo_id=repo_id
    )

    branch_a_sha = adapter.get_commit_sha("branch-a")
    
    # Verify file content on branch-a
    adapter.assert_file_content_matches("file-a.txt", branch_a_sha)


def test_t3600_file_deletion_not_in_tree(
    t3600_rm_fixture,
    git_service
):
    """Test that deleted files are not in current tree but exist in history."""
    success, result = git_service.register_repository(
        repo_path=str(t3600_rm_fixture),
        source_id="test-source-t3600"
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
        repo_path=t3600_rm_fixture,
        service=git_service,
        repo_id=repo_id
    )

    head_sha = adapter.get_commit_sha("HEAD")
    files = adapter.get_file_tree_cli(head_sha)

    # remove.txt should not be in current tree
    assert "remove.txt" not in files, "remove.txt should be deleted from HEAD"
    assert "keep.txt" in files, "keep.txt should still exist"
    assert "also-keep.txt" in files, "also-keep.txt should still exist"


def test_t3600_file_count_after_deletion(
    t3600_rm_fixture,
    git_service
):
    """Test correct file count after file deletion."""
    success, result = git_service.register_repository(
        repo_path=str(t3600_rm_fixture),
        source_id="test-source-t3600-count"
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
        repo_path=t3600_rm_fixture,
        service=git_service,
        repo_id=repo_id
    )

    head_sha = adapter.get_commit_sha("HEAD")
    files = adapter.get_file_tree_cli(head_sha)

    # Should have 2 files after removing one of the initial 3
    assert len(files) == 2, f"Expected 2 files after deletion, got {len(files)}: {files}"


@pytest.fixture
def t3000_ls_files_fixture(upstream_fixture_path):
    """Return path to t3000-ls-files test fixture."""
    fixture_path = upstream_fixture_path / "t3000-ls-files"
    if not fixture_path.exists():
        pytest.skip(f"Fixture not found: {fixture_path}. Run create_fixtures.py first.")
    return fixture_path


def test_t3000_tracked_files_in_tree(
    t3000_ls_files_fixture,
    git_service
):
    """Test tracked files appear in file tree."""
    success, result = git_service.register_repository(
        repo_path=str(t3000_ls_files_fixture),
        source_id="test-source-t3000"
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
        repo_path=t3000_ls_files_fixture,
        service=git_service,
        repo_id=repo_id
    )

    head_sha = adapter.get_commit_sha("HEAD")
    files = adapter.get_file_tree_cli(head_sha)

    # Tracked files should be in tree
    assert "tracked.txt" in files
    assert "src/tracked.py" in files
    assert "docs/readme.md" in files


def test_t3000_untracked_files_not_in_tree(
    t3000_ls_files_fixture,
    git_service
):
    """Test untracked files don't appear in file tree at commit."""
    success, result = git_service.register_repository(
        repo_path=str(t3000_ls_files_fixture),
        source_id="test-source-t3000-untracked"
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
        repo_path=t3000_ls_files_fixture,
        service=git_service,
        repo_id=repo_id
    )

    head_sha = adapter.get_commit_sha("HEAD")
    files = adapter.get_file_tree_cli(head_sha)

    # Untracked files should NOT be in commit tree
    assert "untracked.txt" not in files
    assert "temp/cache.tmp" not in files
    assert "build/output.js" not in files


def test_t3000_ignored_files_not_in_tree(
    t3000_ls_files_fixture,
    git_service
):
    """Test gitignored files don't appear in file tree."""
    success, result = git_service.register_repository(
        repo_path=str(t3000_ls_files_fixture),
        source_id="test-source-t3000-ignored"
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
        repo_path=t3000_ls_files_fixture,
        service=git_service,
        repo_id=repo_id
    )

    head_sha = adapter.get_commit_sha("HEAD")
    files = adapter.get_file_tree_cli(head_sha)

    # Ignored files should NOT be in commit tree
    assert "debug.log" not in files
    assert "secret/password.txt" not in files


@pytest.fixture
def t4000_diff_fixture(upstream_fixture_path):
    """Return path to t4000-diff test fixture."""
    fixture_path = upstream_fixture_path / "t4000-diff"
    if not fixture_path.exists():
        pytest.skip(f"Fixture not found: {fixture_path}. Run create_fixtures.py first.")
    return fixture_path


def test_t4000_file_tree_at_multiple_commits(
    t4000_diff_fixture,
    git_service
):
    """Test file tree changes across multiple commits."""
    success, result = git_service.register_repository(
        repo_path=str(t4000_diff_fixture),
        source_id="test-source-t4000"
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
    assert sync_result["commit_count"] == 3  # Three commits

    adapter = GitTestAdapter(
        repo_path=t4000_diff_fixture,
        service=git_service,
        repo_id=repo_id
    )

    # Get commits in order (newest to oldest)
    import subprocess
    result = subprocess.run(
        ["git", "log", "--format=%H"],
        cwd=t4000_diff_fixture,
        capture_output=True,
        text=True
    )
    commit_shas = [sha for sha in result.stdout.strip().split("\n") if sha]

    # First commit: 3 files
    first_commit = commit_shas[-1]
    first_files = adapter.get_file_tree_cli(first_commit)
    assert len(first_files) == 3
    assert "file1.txt" in first_files
    assert "file2.txt" in first_files
    assert "file3.txt" in first_files

    # Second commit: file2 deleted, file4 added, file1 modified
    second_commit = commit_shas[1]
    second_files = adapter.get_file_tree_cli(second_commit)
    assert len(second_files) == 3
    assert "file1.txt" in second_files
    assert "file2.txt" not in second_files  # Deleted
    assert "file3.txt" in second_files
    assert "file4.txt" in second_files  # Added

    # Third commit: file1 and file3 modified
    third_commit = commit_shas[0]
    third_files = adapter.get_file_tree_cli(third_commit)
    assert len(third_files) == 3


def test_t4000_modified_content_across_commits(
    t4000_diff_fixture,
    git_service
):
    """Test modified file content is correctly stored per commit."""
    success, result = git_service.register_repository(
        repo_path=str(t4000_diff_fixture),
        source_id="test-source-t4000-content"
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
        repo_path=t4000_diff_fixture,
        service=git_service,
        repo_id=repo_id
    )

    # Get commits
    import subprocess
    result = subprocess.run(
        ["git", "log", "--format=%H"],
        cwd=t4000_diff_fixture,
        capture_output=True,
        text=True
    )
    commit_shas = [sha for sha in result.stdout.strip().split("\n") if sha]

    # Verify file1.txt content at each commit
    for sha in commit_shas:
        adapter.assert_file_content_matches("file1.txt", sha)

    # Verify file3.txt content at commits where it exists
    adapter.assert_file_content_matches("file3.txt", commit_shas[0])  # Third commit
    adapter.assert_file_content_matches("file3.txt", commit_shas[1])  # Second commit
    adapter.assert_file_content_matches("file3.txt", commit_shas[2])  # First commit
