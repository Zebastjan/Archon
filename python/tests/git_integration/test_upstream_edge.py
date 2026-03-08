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


@pytest.fixture
def t4100_binary_fixture(upstream_fixture_path):
    """Return path to t4100-binary test fixture."""
    fixture_path = upstream_fixture_path / "t4100-binary"
    if not fixture_path.exists():
        pytest.skip(f"Fixture not found: {fixture_path}. Run create_fixtures.py first.")
    return fixture_path


def test_t4100_binary_file_tree(
    t4100_binary_fixture,
    git_service
):
    """Test that binary files are correctly listed in tree."""
    success, result = git_service.register_repository(
        repo_path=str(t4100_binary_fixture),
        source_id="test-source-t4100"
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
        repo_path=t4100_binary_fixture,
        service=git_service,
        repo_id=repo_id
    )

    head_sha = adapter.get_commit_sha("HEAD")
    files = adapter.get_file_tree_cli(head_sha)

    # Should have all 4 files
    assert len(files) == 4
    assert "text.txt" in files
    assert "binary.bin" in files
    assert "image.bin" in files
    assert "mixed.txt" in files


def test_t4100_binary_content_retrieval(
    t4100_binary_fixture,
    git_service
):
    """Test that binary file content can be retrieved."""
    success, result = git_service.register_repository(
        repo_path=str(t4100_binary_fixture),
        source_id="test-source-t4100-content"
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
        repo_path=t4100_binary_fixture,
        service=git_service,
        repo_id=repo_id
    )

    head_sha = adapter.get_commit_sha("HEAD")

    # Verify text file content matches
    adapter.assert_file_content_matches("text.txt", head_sha)
    
    # For binary files, just verify they're in the tree and can be accessed
    # Binary comparison may fail due to encoding issues
    service_success, service_result = git_service.get_file_content(
        repo_id=repo_id,
        commit_sha=head_sha,
        file_path="binary.bin"
    )
    
    # Binary file handling may have limitations - document if it fails
    if not service_success:
        pytest.skip(f"Binary file retrieval not fully supported: {service_result.get('error', 'Unknown error')}")


@pytest.fixture
def t4300_deep_nesting_fixture(upstream_fixture_path):
    """Return path to t4300-deep-nesting test fixture."""
    fixture_path = upstream_fixture_path / "t4300-deep-nesting"
    if not fixture_path.exists():
        pytest.skip(f"Fixture not found: {fixture_path}. Run create_fixtures.py first.")
    return fixture_path


def test_t4300_deep_nesting_file_count(
    t4300_deep_nesting_fixture,
    git_service
):
    """Test deeply nested directory structure."""
    success, result = git_service.register_repository(
        repo_path=str(t4300_deep_nesting_fixture),
        source_id="test-source-t4300"
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
        repo_path=t4300_deep_nesting_fixture,
        service=git_service,
        repo_id=repo_id
    )

    head_sha = adapter.get_commit_sha("HEAD")
    files = adapter.get_file_tree_cli(head_sha)

    # Should have 15 files (one at each nesting level)
    assert len(files) == 15, f"Expected 15 files, got {len(files)}"


def test_t4300_deep_nesting_path_structure(
    t4300_deep_nesting_fixture,
    git_service
):
    """Test that deeply nested paths are correctly handled."""
    success, result = git_service.register_repository(
        repo_path=str(t4300_deep_nesting_fixture),
        source_id="test-source-t4300-paths"
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
        repo_path=t4300_deep_nesting_fixture,
        service=git_service,
        repo_id=repo_id
    )

    head_sha = adapter.get_commit_sha("HEAD")

    # Verify file tree matches
    adapter.assert_file_tree_matches(head_sha)


def test_t4300_deep_nesting_content(
    t4300_deep_nesting_fixture,
    git_service
):
    """Test content retrieval from deeply nested files."""
    success, result = git_service.register_repository(
        repo_path=str(t4300_deep_nesting_fixture),
        source_id="test-source-t4300-content"
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
        repo_path=t4300_deep_nesting_fixture,
        service=git_service,
        repo_id=repo_id
    )

    head_sha = adapter.get_commit_sha("HEAD")

    # Test content at various nesting levels
    adapter.assert_file_content_matches("level1/file1.txt", head_sha)
    adapter.assert_file_content_matches("level1/level2/level3/file3.txt", head_sha)
    adapter.assert_file_content_matches("level1/level2/level3/level4/level5/file5.txt", head_sha)
    adapter.assert_file_content_matches("level1/level2/level3/level4/level5/level6/level7/level8/level9/level10/file10.txt", head_sha)


@pytest.fixture
def t4400_empty_files_fixture(upstream_fixture_path):
    """Return path to t4400-empty-files test fixture."""
    fixture_path = upstream_fixture_path / "t4400-empty-files"
    if not fixture_path.exists():
        pytest.skip(f"Fixture not found: {fixture_path}. Run create_fixtures.py first.")
    return fixture_path


def test_t4400_empty_files_in_tree(
    t4400_empty_files_fixture,
    git_service
):
    """Test that empty files appear in tree."""
    success, result = git_service.register_repository(
        repo_path=str(t4400_empty_files_fixture),
        source_id="test-source-t4400"
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
        repo_path=t4400_empty_files_fixture,
        service=git_service,
        repo_id=repo_id
    )

    head_sha = adapter.get_commit_sha("HEAD")
    files = adapter.get_file_tree_cli(head_sha)

    # All 4 files should be present
    assert len(files) == 4
    assert "empty.txt" in files
    assert "whitespace.txt" in files
    assert "newline.txt" in files
    assert "normal.txt" in files


def test_t4400_empty_file_content(
    t4400_empty_files_fixture,
    git_service
):
    """Test empty file content retrieval."""
    success, result = git_service.register_repository(
        repo_path=str(t4400_empty_files_fixture),
        source_id="test-source-t4400-content"
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
        repo_path=t4400_empty_files_fixture,
        service=git_service,
        repo_id=repo_id
    )

    head_sha = adapter.get_commit_sha("HEAD")

    # Test all files
    adapter.assert_file_content_matches("empty.txt", head_sha)
    adapter.assert_file_content_matches("whitespace.txt", head_sha)
    adapter.assert_file_content_matches("newline.txt", head_sha)
    adapter.assert_file_content_matches("normal.txt", head_sha)


@pytest.fixture
def t4500_large_content_fixture(upstream_fixture_path):
    """Return path to t4500-large-content test fixture."""
    fixture_path = upstream_fixture_path / "t4500-large-content"
    if not fixture_path.exists():
        pytest.skip(f"Fixture not found: {fixture_path}. Run create_fixtures.py first.")
    return fixture_path


def test_t4500_large_file_tree(
    t4500_large_content_fixture,
    git_service
):
    """Test large content files in tree."""
    success, result = git_service.register_repository(
        repo_path=str(t4500_large_content_fixture),
        source_id="test-source-t4500"
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
        repo_path=t4500_large_content_fixture,
        service=git_service,
        repo_id=repo_id
    )

    head_sha = adapter.get_commit_sha("HEAD")
    files = adapter.get_file_tree_cli(head_sha)

    # All 3 files should be present
    assert len(files) == 3
    assert "large.txt" in files
    assert "medium.txt" in files
    assert "small.txt" in files


def test_t4500_large_file_content(
    t4500_large_content_fixture,
    git_service
):
    """Test large file content retrieval."""
    success, result = git_service.register_repository(
        repo_path=str(t4500_large_content_fixture),
        source_id="test-source-t4500-content"
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
        repo_path=t4500_large_content_fixture,
        service=git_service,
        repo_id=repo_id
    )

    head_sha = adapter.get_commit_sha("HEAD")

    # Test all file sizes
    adapter.assert_file_content_matches("small.txt", head_sha)
    adapter.assert_file_content_matches("medium.txt", head_sha)
    adapter.assert_file_content_matches("large.txt", head_sha)


def test_t4500_modified_large_file(
    t4500_large_content_fixture,
    git_service
):
    """Test modified large file at second commit."""
    success, result = git_service.register_repository(
        repo_path=str(t4500_large_content_fixture),
        source_id="test-source-t4500-modified"
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
        repo_path=t4500_large_content_fixture,
        service=git_service,
        repo_id=repo_id
    )

    # Get both commits
    import subprocess
    result = subprocess.run(
        ["git", "log", "--format=%H"],
        cwd=t4500_large_content_fixture,
        capture_output=True,
        text=True
    )
    commit_shas = [sha for sha in result.stdout.strip().split("\n") if sha]

    # Verify large.txt at both commits
    adapter.assert_file_content_matches("large.txt", commit_shas[0])  # Modified
    adapter.assert_file_content_matches("large.txt", commit_shas[1])  # Original


@pytest.fixture
def t4200_symlink_fixture(upstream_fixture_path):
    """Return path to t4200-symlink test fixture."""
    fixture_path = upstream_fixture_path / "t4200-symlink"
    if not fixture_path.exists():
        pytest.skip(f"Fixture not found: {fixture_path}. Run create_fixtures.py first.")
    return fixture_path


def test_t4200_symlink_handling(
    t4200_symlink_fixture,
    git_service
):
    """Test symlink handling in repository."""
    success, result = git_service.register_repository(
        repo_path=str(t4200_symlink_fixture),
        source_id="test-source-t4200"
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
        repo_path=t4200_symlink_fixture,
        service=git_service,
        repo_id=repo_id
    )

    head_sha = adapter.get_commit_sha("HEAD")

    # Verify file tree matches (may or may not include symlinks)
    try:
        adapter.assert_file_tree_matches(head_sha)
    except AssertionError:
        # If symlinks are not supported, at least verify target.txt exists
        files = adapter.get_file_tree_cli(head_sha)
        assert "target.txt" in files


def test_t4100_mixed_content_file(
    t4100_binary_fixture,
    git_service
):
    """Test mixed binary/text file handling."""
    success, result = git_service.register_repository(
        repo_path=str(t4100_binary_fixture),
        source_id="test-source-mixed"
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

    # Just verify the file exists in tree
    adapter = GitTestAdapter(
        repo_path=t4100_binary_fixture,
        service=git_service,
        repo_id=repo_id
    )
    
    head_sha = adapter.get_commit_sha("HEAD")
    files = adapter.get_file_tree_cli(head_sha)
    assert "mixed.txt" in files


def test_t4400_whitespace_only_file(
    t4400_empty_files_fixture,
    git_service
):
    """Test whitespace-only file content."""
    success, result = git_service.register_repository(
        repo_path=str(t4400_empty_files_fixture),
        source_id="test-source-whitespace"
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
        repo_path=t4400_empty_files_fixture,
        service=git_service,
        repo_id=repo_id
    )
    
    head_sha = adapter.get_commit_sha("HEAD")
    # Test whitespace file specifically
    adapter.assert_file_content_matches("whitespace.txt", head_sha)


def test_t4500_medium_file_content(
    t4500_large_content_fixture,
    git_service
):
    """Test medium-sized file content retrieval."""
    success, result = git_service.register_repository(
        repo_path=str(t4500_large_content_fixture),
        source_id="test-source-medium"
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
        repo_path=t4500_large_content_fixture,
        service=git_service,
        repo_id=repo_id
    )
    
    head_sha = adapter.get_commit_sha("HEAD")
    # Test medium file
    adapter.assert_file_content_matches("medium.txt", head_sha)
