"""Generator for edge-cases test fixture.

This fixture creates a repository with various edge cases:
- Unicode and special characters in filenames
- Very long file paths (255+ characters)
- Empty files (0 bytes)
- Deeply nested directories (10+ levels)
- Binary files (for access blocking tests)
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class EdgeCasesFixture:
    """Metadata about the generated edge-cases fixture."""

    repo_path: Path
    main_branch: str
    # Special character files
    unicode_file_path: str  # File with unicode characters
    special_chars_file_path: str  # File with special characters
    # Long path
    long_path_file: str  # Very long file path (255+ characters)
    # Empty file
    empty_file_path: str  # 0-byte file
    # Deeply nested
    deeply_nested_file: str  # File 10+ levels deep
    # Binary file
    binary_file_path: str  # PNG file for access blocking test
    # Commit info
    commit_sha: str


def _run_git(repo_path: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Execute a git command in the target repository."""
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo_path),
        check=False,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed: {result.stderr.strip() or result.stdout.strip()}"
        )
    return result


def create_edge_cases_fixture(base_path: Path) -> EdgeCasesFixture:
    """
    Create a test repository with various edge cases.

    Structure:
        - README.md (normal file)
        - files/unicode_文件名.txt (unicode characters)
        - files/special!@#$%.txt (special characters)
        - empty.txt (0 bytes)
        - assets/test.png (binary file)
        - very/long/path/.../file.txt (255+ character path)
        - deeply/nested/.../level10/file.txt (10 levels deep)

    This validates:
        - Unicode filename handling
        - Special character support
        - Empty file detection
        - Binary file access blocking
        - Long path support
        - Deep nesting support
    """
    repo_path = base_path / "edge-cases"
    repo_path.mkdir(parents=True, exist_ok=True)

    # Initialize repository
    init_result = _run_git(repo_path, "init", "-b", "main", check=False)
    if init_result.returncode != 0:
        _run_git(repo_path, "init")
        _run_git(repo_path, "checkout", "-b", "main")

    _run_git(repo_path, "config", "user.email", "archon-tests@example.com")
    _run_git(repo_path, "config", "user.name", "Archon Test")

    # Create normal README
    readme_content = "# Edge Cases Test\n\nTesting various edge cases for Git integration.\n"
    (repo_path / "README.md").write_text(readme_content, encoding="utf-8")

    # Create files directory
    files_dir = repo_path / "files"
    files_dir.mkdir(exist_ok=True)

    # 1. Unicode filename (Chinese, Japanese, Emoji)
    unicode_file = files_dir / "unicode_文件名_ファイル_📄.txt"
    unicode_content = "This file has unicode characters in its name: 文件名 ファイル 📄\n"
    unicode_file.write_text(unicode_content, encoding="utf-8")
    unicode_file_path = str(unicode_file.relative_to(repo_path))

    # 2. Special characters in filename (allowed by most filesystems)
    # Note: Avoid characters that are invalid on some systems (/, \, :, *, ?, ", <, >, |)
    special_file = files_dir / "special!@#$%^&()_+-=[]{}~`.txt"
    special_content = "This file has special characters in its name: !@#$%^&()_+-=[]{}\n"
    special_file.write_text(special_content, encoding="utf-8")
    special_chars_file_path = str(special_file.relative_to(repo_path))

    # 3. Empty file (0 bytes)
    empty_file = repo_path / "empty.txt"
    empty_file.write_text("", encoding="utf-8")
    empty_file_path = str(empty_file.relative_to(repo_path))

    # 4. Binary file (PNG)
    assets_dir = repo_path / "assets"
    assets_dir.mkdir(exist_ok=True)
    binary_file = assets_dir / "test.png"
    # Create a minimal valid PNG file (1x1 transparent pixel)
    png_data = (
        b"\x89PNG\r\n\x1a\n"  # PNG signature
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"  # IHDR chunk
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
        b"\r\n-\xb4"  # IDAT chunk
        b"\x00\x00\x00\x00IEND\xaeB`\x82"  # IEND chunk
    )
    binary_file.write_bytes(png_data)
    binary_file_path = str(binary_file.relative_to(repo_path))

    # 5. Very long path (close to 255 character limit)
    # Create a path with many nested directories to reach ~250 characters
    long_path_parts = ["very", "long", "path", "to", "test", "maximum"]
    # Add more parts to reach desired length
    current_length = len("/".join(long_path_parts)) + len("file.txt")
    while current_length < 240:  # Leave some room
        long_path_parts.append("another_directory_with_a_long_name")
        current_length = len("/".join(long_path_parts)) + len("/file.txt")

    long_path_dir = repo_path
    for part in long_path_parts:
        long_path_dir = long_path_dir / part
    long_path_dir.mkdir(parents=True, exist_ok=True)

    long_path_file = long_path_dir / "file.txt"
    long_path_content = f"This file has a path length of {len(str(long_path_file.relative_to(repo_path)))} characters\n"
    long_path_file.write_text(long_path_content, encoding="utf-8")
    long_path_file_path = str(long_path_file.relative_to(repo_path))

    # 6. Deeply nested directory (10+ levels)
    deeply_nested = repo_path / "deeply"
    for i in range(1, 11):  # Create 10 levels
        deeply_nested = deeply_nested / f"level{i}"
    deeply_nested.mkdir(parents=True, exist_ok=True)

    deeply_nested_file = deeply_nested / "file.txt"
    deeply_nested_content = "This file is nested 10 levels deep\n"
    deeply_nested_file.write_text(deeply_nested_content, encoding="utf-8")
    deeply_nested_file_path = str(deeply_nested_file.relative_to(repo_path))

    # Add all files and commit
    _run_git(repo_path, "add", ".")
    _run_git(repo_path, "commit", "-m", "Add edge case test files")
    commit_sha = _run_git(repo_path, "rev-parse", "HEAD").stdout.strip()

    return EdgeCasesFixture(
        repo_path=repo_path,
        main_branch="main",
        unicode_file_path=unicode_file_path,
        special_chars_file_path=special_chars_file_path,
        long_path_file=long_path_file_path,
        empty_file_path=empty_file_path,
        deeply_nested_file=deeply_nested_file_path,
        binary_file_path=binary_file_path,
        commit_sha=commit_sha,
    )
