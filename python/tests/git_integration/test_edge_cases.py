"""Tests for edge cases in Git integration."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.server.services.git.git_repository_service import (
    GitFileNotFoundError,
    GitRepositoryService,
)
from tests.git_integration.fixtures.generators import create_edge_cases_fixture
from tests.git_integration.test_git_repository_integration import FakeSupabaseClient


@pytest.fixture
def edge_cases_fixture(tmp_path: Path):
    """Create edge-cases test fixture."""
    return create_edge_cases_fixture(tmp_path)


def test_unicode_filenames_supported(
    edge_cases_fixture, git_service: GitRepositoryService, supabase_client: FakeSupabaseClient
) -> None:
    """Test that files with unicode characters in names are properly handled."""
    # Register repository
    success, result = git_service.register_repository(
        str(edge_cases_fixture.repo_path), source_id="source-unicode"
    )
    assert success is True
    repo_id = result["repo_id"]

    # Get file tree
    tree_success, tree_result = git_service.get_file_tree(
        repo_id, edge_cases_fixture.commit_sha
    )
    assert tree_success is True
    file_paths = {f["file_path"] for f in tree_result["files"]}

    # Unicode filename should be in tree
    assert edge_cases_fixture.unicode_file_path in file_paths, (
        f"Unicode file '{edge_cases_fixture.unicode_file_path}' should be in tree"
    )

    # Should be able to read unicode filename content
    content_success, content_result = git_service.get_file_content(
        repo_id, edge_cases_fixture.commit_sha, edge_cases_fixture.unicode_file_path
    )
    assert content_success is True
    assert "unicode characters" in content_result["content"]
    assert "文件名" in content_result["content"]


def test_special_characters_in_filenames(
    edge_cases_fixture, git_service: GitRepositoryService, supabase_client: FakeSupabaseClient
) -> None:
    """Test that files with special characters in names are properly handled."""
    # Register repository
    success, result = git_service.register_repository(
        str(edge_cases_fixture.repo_path), source_id="source-special"
    )
    assert success is True
    repo_id = result["repo_id"]

    # Get file tree
    tree_success, tree_result = git_service.get_file_tree(
        repo_id, edge_cases_fixture.commit_sha
    )
    assert tree_success is True
    file_paths = {f["file_path"] for f in tree_result["files"]}

    # Special character filename should be in tree
    assert edge_cases_fixture.special_chars_file_path in file_paths, (
        f"Special chars file '{edge_cases_fixture.special_chars_file_path}' should be in tree"
    )

    # Should be able to read special character filename content
    content_success, content_result = git_service.get_file_content(
        repo_id, edge_cases_fixture.commit_sha, edge_cases_fixture.special_chars_file_path
    )
    assert content_success is True
    assert "special characters" in content_result["content"]


def test_empty_files_handled_correctly(
    edge_cases_fixture, git_service: GitRepositoryService, supabase_client: FakeSupabaseClient
) -> None:
    """Test that empty files (0 bytes) are properly handled."""
    # Register repository
    success, result = git_service.register_repository(
        str(edge_cases_fixture.repo_path), source_id="source-empty"
    )
    assert success is True
    repo_id = result["repo_id"]

    # Get file tree
    tree_success, tree_result = git_service.get_file_tree(
        repo_id, edge_cases_fixture.commit_sha
    )
    assert tree_success is True

    # Find empty file in tree
    empty_file = next(
        (f for f in tree_result["files"] if f["file_path"] == edge_cases_fixture.empty_file_path),
        None,
    )
    assert empty_file is not None, "Empty file should appear in file tree"
    assert empty_file["file_size"] == 0, "Empty file should have size 0"
    assert empty_file["is_binary"] is False, "Empty file should not be marked as binary"

    # Should be able to read empty file content
    content_success, content_result = git_service.get_file_content(
        repo_id, edge_cases_fixture.commit_sha, edge_cases_fixture.empty_file_path
    )
    assert content_success is True
    assert content_result["content"] == "", "Empty file should have empty content"
    assert content_result["file_size"] == 0, "Empty file should report size 0"


def test_binary_file_access_blocked(
    edge_cases_fixture, git_service: GitRepositoryService, supabase_client: FakeSupabaseClient
) -> None:
    """Test that attempting to read binary file content returns proper error."""
    # Register repository
    success, result = git_service.register_repository(
        str(edge_cases_fixture.repo_path), source_id="source-binary"
    )
    assert success is True
    repo_id = result["repo_id"]

    # Get file tree
    tree_success, tree_result = git_service.get_file_tree(
        repo_id, edge_cases_fixture.commit_sha
    )
    assert tree_success is True

    # Find binary file in tree
    binary_file = next(
        (f for f in tree_result["files"] if f["file_path"] == edge_cases_fixture.binary_file_path),
        None,
    )
    assert binary_file is not None, "Binary file should appear in file tree"
    assert binary_file["is_binary"] is True, "PNG should be marked as binary"

    # Attempting to read binary file should fail with clear error
    content_success, content_result = git_service.get_file_content(
        repo_id, edge_cases_fixture.commit_sha, edge_cases_fixture.binary_file_path
    )
    assert content_success is False, "Reading binary file should fail"
    assert "error" in content_result, "Should return error message"
    assert "is_binary" in content_result, "Should indicate file is binary"
    assert content_result["is_binary"] is True, "Should flag as binary"

    # Error message should be clear
    error_msg = content_result["error"].lower()
    assert "binary" in error_msg or "cannot read" in error_msg, (
        "Error message should mention binary or cannot read"
    )


def test_long_file_paths_supported(
    edge_cases_fixture, git_service: GitRepositoryService, supabase_client: FakeSupabaseClient
) -> None:
    """Test that very long file paths (close to 255 chars) are properly handled."""
    # Register repository
    success, result = git_service.register_repository(
        str(edge_cases_fixture.repo_path), source_id="source-longpath"
    )
    assert success is True
    repo_id = result["repo_id"]

    # Verify path is actually long
    path_length = len(edge_cases_fixture.long_path_file)
    assert path_length > 200, f"Test path should be >200 chars, got {path_length}"

    # Get file tree
    tree_success, tree_result = git_service.get_file_tree(
        repo_id, edge_cases_fixture.commit_sha
    )
    assert tree_success is True
    file_paths = {f["file_path"] for f in tree_result["files"]}

    # Long path should be in tree
    assert edge_cases_fixture.long_path_file in file_paths, (
        f"Long path file (length {path_length}) should be in tree"
    )

    # Should be able to read long path file content
    content_success, content_result = git_service.get_file_content(
        repo_id, edge_cases_fixture.commit_sha, edge_cases_fixture.long_path_file
    )
    assert content_success is True
    assert "path length" in content_result["content"]


def test_deeply_nested_directories_supported(
    edge_cases_fixture, git_service: GitRepositoryService, supabase_client: FakeSupabaseClient
) -> None:
    """Test that deeply nested directories (10+ levels) are properly handled."""
    # Register repository
    success, result = git_service.register_repository(
        str(edge_cases_fixture.repo_path), source_id="source-nested"
    )
    assert success is True
    repo_id = result["repo_id"]

    # Verify nesting is actually deep
    nesting_level = edge_cases_fixture.deeply_nested_file.count("/")
    assert nesting_level >= 10, f"Test file should be nested 10+ levels, got {nesting_level}"

    # Get file tree
    tree_success, tree_result = git_service.get_file_tree(
        repo_id, edge_cases_fixture.commit_sha
    )
    assert tree_success is True
    file_paths = {f["file_path"] for f in tree_result["files"]}

    # Deeply nested file should be in tree
    assert edge_cases_fixture.deeply_nested_file in file_paths, (
        f"Deeply nested file ({nesting_level} levels) should be in tree"
    )

    # Should be able to read deeply nested file content
    content_success, content_result = git_service.get_file_content(
        repo_id, edge_cases_fixture.commit_sha, edge_cases_fixture.deeply_nested_file
    )
    assert content_success is True
    assert "10 levels deep" in content_result["content"]


def test_all_edge_case_files_in_tree(
    edge_cases_fixture, git_service: GitRepositoryService, supabase_client: FakeSupabaseClient
) -> None:
    """Test that all edge case files are properly indexed in file tree."""
    # Register repository
    success, result = git_service.register_repository(
        str(edge_cases_fixture.repo_path), source_id="source-all"
    )
    assert success is True
    repo_id = result["repo_id"]

    # Get file tree
    tree_success, tree_result = git_service.get_file_tree(
        repo_id, edge_cases_fixture.commit_sha
    )
    assert tree_success is True
    file_paths = {f["file_path"] for f in tree_result["files"]}

    # All special files should be present
    expected_files = [
        "README.md",
        edge_cases_fixture.unicode_file_path,
        edge_cases_fixture.special_chars_file_path,
        edge_cases_fixture.empty_file_path,
        edge_cases_fixture.binary_file_path,
        edge_cases_fixture.long_path_file,
        edge_cases_fixture.deeply_nested_file,
    ]

    for expected_file in expected_files:
        assert expected_file in file_paths, f"Expected file '{expected_file}' should be in tree"

    # Should have at least 7 files (README + 6 edge cases)
    assert len(file_paths) >= 7, f"Expected at least 7 files, got {len(file_paths)}"


def test_file_metadata_accurate_for_edge_cases(
    edge_cases_fixture, git_service: GitRepositoryService, supabase_client: FakeSupabaseClient
) -> None:
    """Test that file metadata (size, binary flag, language) is accurate for edge cases."""
    # Register repository
    success, result = git_service.register_repository(
        str(edge_cases_fixture.repo_path), source_id="source-metadata"
    )
    assert success is True
    repo_id = result["repo_id"]

    # Get file tree
    tree_success, tree_result = git_service.get_file_tree(
        repo_id, edge_cases_fixture.commit_sha
    )
    assert tree_success is True
    files_by_path = {f["file_path"]: f for f in tree_result["files"]}

    # Empty file: size 0, not binary
    empty_file = files_by_path[edge_cases_fixture.empty_file_path]
    assert empty_file["file_size"] == 0
    assert empty_file["is_binary"] is False

    # Binary file: marked as binary
    binary_file = files_by_path[edge_cases_fixture.binary_file_path]
    assert binary_file["is_binary"] is True
    assert binary_file["file_size"] > 0

    # Unicode text file: not binary, has content
    unicode_file = files_by_path[edge_cases_fixture.unicode_file_path]
    assert unicode_file["is_binary"] is False
    assert unicode_file["file_size"] > 0
    # Should detect as text (language might be "text" or "txt")
    assert unicode_file["language"] in ["text", "txt", None]
