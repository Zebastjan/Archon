"""
Create test fixtures programmatically to match Git's test scenarios.

This approach creates repositories that mirror Git's upstream test scenarios
without requiring a full Git build environment.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

from git import Repo

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "upstream"


def create_t0001_init_fixture():
    """Create fixture matching Git's t0001-init.sh basic repository test."""
    fixture_path = FIXTURES_DIR / "t0001-init"
    
    # Clean up existing fixture
    if fixture_path.exists():
        shutil.rmtree(fixture_path)
    
    fixture_path.mkdir(parents=True)
    
    # Initialize repository
    repo = Repo.init(fixture_path)
    
    # Configure git user
    with repo.config_writer() as config:
        config.set_value("user", "name", "Test User")
        config.set_value("user", "email", "test@example.com")
    
    # Create initial file
    readme = fixture_path / "README.md"
    readme.write_text("# Test Repository\n\nThis is a test repository.\n")
    
    # Add and commit
    repo.index.add(["README.md"])
    repo.index.commit("Initial commit")
    
    # Create a second file
    src_dir = fixture_path / "src"
    src_dir.mkdir()
    main_file = src_dir / "main.py"
    main_file.write_text("print('Hello, World!')\n")
    
    # Add and commit
    repo.index.add(["src/main.py"])
    repo.index.commit("Add main.py")
    
    print(f"✅ Created fixture: {fixture_path}")
    return fixture_path


def create_t1000_read_tree_fixture():
    """Create fixture with multiple files for tree reading tests."""
    fixture_path = FIXTURES_DIR / "t1000-read-tree"
    
    if fixture_path.exists():
        shutil.rmtree(fixture_path)
    
    fixture_path.mkdir(parents=True)
    
    repo = Repo.init(fixture_path)
    
    with repo.config_writer() as config:
        config.set_value("user", "name", "Test User")
        config.set_value("user", "email", "test@example.com")
    
    # Create multiple files in nested directories
    files = [
        "README.md",
        "src/main.py",
        "src/utils.py",
        "tests/test_main.py",
        "docs/guide.md",
        "config.json",
    ]
    
    for file_path in files:
        full_path = fixture_path / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(f"# Content for {file_path}\n")
    
    # Add all and commit
    repo.index.add(files)
    repo.index.commit("Initial commit with multiple files")
    
    # Create a feature branch with additional files
    feature_branch = repo.create_head("feature-branch")
    feature_branch.checkout()
    
    feature_file = fixture_path / "src/feature.py"
    feature_file.write_text("# New feature code\n")
    repo.index.add(["src/feature.py"])
    repo.index.commit("Add feature")
    
    # Switch back to main/master
    default_branch = "main" if "main" in [h.name for h in repo.heads] else "master"
    repo.heads[default_branch].checkout()
    
    print(f"✅ Created fixture: {fixture_path}")
    return fixture_path


def create_t3200_branch_fixture():
    """Create fixture with multiple branches for branch tests."""
    fixture_path = FIXTURES_DIR / "t3200-branch"
    
    if fixture_path.exists():
        shutil.rmtree(fixture_path)
    
    fixture_path.mkdir(parents=True)
    
    repo = Repo.init(fixture_path)
    
    with repo.config_writer() as config:
        config.set_value("user", "name", "Test User")
        config.set_value("user", "email", "test@example.com")
    
    # Create base file
    readme = fixture_path / "README.md"
    readme.write_text("# Base\n")
    repo.index.add(["README.md"])
    base_commit = repo.index.commit("Base commit")
    
    # Create develop branch
    develop = repo.create_head("develop")
    develop.checkout()
    dev_file = fixture_path / "dev.txt"
    dev_file.write_text("Development work\n")
    repo.index.add(["dev.txt"])
    repo.index.commit("Development commit")
    
    # Create feature branch from main/master
    default_branch = "main" if "main" in [h.name for h in repo.heads] else "master"
    repo.heads[default_branch].checkout()
    feature = repo.create_head("feature/new-thing")
    feature.checkout()
    feature_file = fixture_path / "feature.txt"
    feature_file.write_text("New feature\n")
    repo.index.add(["feature.txt"])
    repo.index.commit("Feature commit")
    
    # Create hotfix branch
    repo.heads[default_branch].checkout()
    hotfix = repo.create_head("hotfix/urgent")
    hotfix.checkout()
    fix_file = fixture_path / "fix.txt"
    fix_file.write_text("Urgent fix\n")
    repo.index.add(["fix.txt"])
    repo.index.commit("Hotfix commit")
    
    # Back to main/master
    repo.heads[default_branch].checkout()
    
    print(f"✅ Created fixture: {fixture_path}")
    return fixture_path


def create_t3400_rebase_fixture():
    """Create fixture with divergent branches for merge/rebase tests."""
    fixture_path = FIXTURES_DIR / "t3400-rebase"
    
    if fixture_path.exists():
        shutil.rmtree(fixture_path)
    
    fixture_path.mkdir(parents=True)
    
    repo = Repo.init(fixture_path)
    
    with repo.config_writer() as config:
        config.set_value("user", "name", "Test User")
        config.set_value("user", "email", "test@example.com")
    
    # Base file
    base = fixture_path / "base.txt"
    base.write_text("Base content\n")
    repo.index.add(["base.txt"])
    repo.index.commit("Base")
    
    # Create branch A with changes
    branch_a = repo.create_head("branch-a")
    branch_a.checkout()
    file_a = fixture_path / "file-a.txt"
    file_a.write_text("Branch A content\n")
    repo.index.add(["file-a.txt"])
    repo.index.commit("Branch A commit")
    
    # Back to main/master, create branch B
    default_branch = "main" if "main" in [h.name for h in repo.heads] else "master"
    repo.heads[default_branch].checkout()
    branch_b = repo.create_head("branch-b")
    branch_b.checkout()
    file_b = fixture_path / "file-b.txt"
    file_b.write_text("Branch B content\n")
    repo.index.add(["file-b.txt"])
    repo.index.commit("Branch B commit")
    
    # Back to main/master
    repo.heads[default_branch].checkout()
    
    print(f"✅ Created fixture: {fixture_path}")
    return fixture_path


def create_t3600_rm_fixture():
    """Create fixture with file deletions for rm tests."""
    fixture_path = FIXTURES_DIR / "t3600-rm"
    
    if fixture_path.exists():
        shutil.rmtree(fixture_path)
    
    fixture_path.mkdir(parents=True)
    
    repo = Repo.init(fixture_path)
    
    with repo.config_writer() as config:
        config.set_value("user", "name", "Test User")
        config.set_value("user", "email", "test@example.com")
    
    # Create initial files
    files = ["keep.txt", "remove.txt", "also-keep.txt"]
    for f in files:
        (fixture_path / f).write_text(f"Content of {f}\n")
    
    repo.index.add(files)
    repo.index.commit("Initial commit with all files")
    
    # Remove one file in a new commit
    (fixture_path / "remove.txt").unlink()
    repo.index.remove(["remove.txt"])
    repo.index.commit("Remove file")
    
    print(f"✅ Created fixture: {fixture_path}")
    return fixture_path


def create_t3900_unicode_fixture():
    """Create fixture with unicode filenames and content."""
    fixture_path = FIXTURES_DIR / "t3900-unicode"
    
    if fixture_path.exists():
        shutil.rmtree(fixture_path)
    
    fixture_path.mkdir(parents=True)
    
    repo = Repo.init(fixture_path)
    
    with repo.config_writer() as config:
        config.set_value("user", "name", "Ünicödé Üser")
        config.set_value("user", "email", "unicode@example.com")
    
    # Create file with unicode content
    unicode_file = fixture_path / "unicode.txt"
    unicode_file.write_text("Hello 世界 🌍 ñáéíóú\n", encoding="utf-8")
    
    # Create file with unicode name
    try:
        unicode_name = fixture_path / "文件.txt"
        unicode_name.write_text("Content", encoding="utf-8")
        files = ["unicode.txt", "文件.txt"]
    except (OSError, UnicodeEncodeError):
        # Fallback if filesystem doesn't support unicode names
        files = ["unicode.txt"]
    
    repo.index.add(files)
    repo.index.commit("Ünicödé commit message: 世界 🌍")
    
    print(f"✅ Created fixture: {fixture_path}")
    return fixture_path


def create_t1100_commit_tree_fixture():
    """Create fixture with complex commit tree structure."""
    fixture_path = FIXTURES_DIR / "t1100-commit-tree"
    
    if fixture_path.exists():
        shutil.rmtree(fixture_path)
    
    fixture_path.mkdir(parents=True)
    
    repo = Repo.init(fixture_path)
    
    with repo.config_writer() as config:
        config.set_value("user", "name", "Test User")
        config.set_value("user", "email", "test@example.com")
    
    # Create multiple files in various directories
    files_content = {
        "root.txt": "Root level file\n",
        "dir1/file1.txt": "File in dir1\n",
        "dir1/subdir/file2.txt": "File in subdir\n",
        "dir2/file3.txt": "File in dir2\n",
        "dir2/another.txt": "Another file\n",
    }
    
    for path, content in files_content.items():
        full_path = fixture_path / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
    
    repo.index.add(list(files_content.keys()))
    initial_commit = repo.index.commit("Initial commit with directory structure")
    
    # Add more files in a second commit
    more_files = {
        "dir1/file4.txt": "Fourth file\n",
        "dir3/new.txt": "New directory file\n",
    }
    
    for path, content in more_files.items():
        full_path = fixture_path / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
    
    repo.index.add(list(more_files.keys()))
    second_commit = repo.index.commit("Add more files")
    
    # Modify existing file in third commit
    (fixture_path / "root.txt").write_text("Modified root content\n")
    repo.index.add(["root.txt"])
    third_commit = repo.index.commit("Modify root.txt")
    
    print(f"✅ Created fixture: {fixture_path}")
    return fixture_path


def create_t1200_checkout_fixture():
    """Create fixture for checkout tests with branch switching."""
    fixture_path = FIXTURES_DIR / "t1200-checkout"
    
    if fixture_path.exists():
        shutil.rmtree(fixture_path)
    
    fixture_path.mkdir(parents=True)
    
    repo = Repo.init(fixture_path)
    
    with repo.config_writer() as config:
        config.set_value("user", "name", "Test User")
        config.set_value("user", "email", "test@example.com")
    
    # Create initial file
    (fixture_path / "shared.txt").write_text("Shared content v1\n")
    repo.index.add(["shared.txt"])
    repo.index.commit("Initial commit")
    
    # Create branch A with different content
    branch_a = repo.create_head("branch-a")
    branch_a.checkout()
    (fixture_path / "shared.txt").write_text("Shared content v2 - branch A\n")
    (fixture_path / "branch-a-only.txt").write_text("Only in branch A\n")
    repo.index.add(["shared.txt", "branch-a-only.txt"])
    repo.index.commit("Branch A changes")
    
    # Back to main and create branch B
    default_branch = "main" if "main" in [h.name for h in repo.heads] else "master"
    repo.heads[default_branch].checkout()
    branch_b = repo.create_head("branch-b")
    branch_b.checkout()
    (fixture_path / "shared.txt").write_text("Shared content v2 - branch B\n")
    (fixture_path / "branch-b-only.txt").write_text("Only in branch B\n")
    repo.index.add(["shared.txt", "branch-b-only.txt"])
    repo.index.commit("Branch B changes")
    
    # Back to main
    repo.heads[default_branch].checkout()
    
    print(f"✅ Created fixture: {fixture_path}")
    return fixture_path


def create_t2000_checkout_fixture():
    """Create fixture for complex checkout scenarios."""
    fixture_path = FIXTURES_DIR / "t2000-checkout"
    
    if fixture_path.exists():
        shutil.rmtree(fixture_path)
    
    fixture_path.mkdir(parents=True)
    
    repo = Repo.init(fixture_path)
    
    with repo.config_writer() as config:
        config.set_value("user", "name", "Test User")
        config.set_value("user", "email", "test@example.com")
    
    # Initial files
    files = ["main.txt", "config.yaml", "src/app.py"]
    for f in files:
        full_path = fixture_path / f
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(f"Initial {f}\n")
    
    repo.index.add(files)
    repo.index.commit("Initial commit")
    
    # Create develop branch with file deletions and additions
    develop = repo.create_head("develop")
    develop.checkout()
    
    # Add new file
    (fixture_path / "src/new_feature.py").write_text("New feature code\n")
    repo.index.add(["src/new_feature.py"])
    
    # Delete a file
    (fixture_path / "config.yaml").unlink()
    repo.index.remove(["config.yaml"])
    
    # Modify existing file
    (fixture_path / "src/app.py").write_text("Modified app.py in develop\n")
    repo.index.add(["src/app.py"])
    
    repo.index.commit("Develop: add feature, delete config, modify app")
    
    # Back to main
    default_branch = "main" if "main" in [h.name for h in repo.heads] else "master"
    repo.heads[default_branch].checkout()
    
    print(f"✅ Created fixture: {fixture_path}")
    return fixture_path


def create_t3000_ls_files_fixture():
    """Create fixture with untracked files for ls-files tests."""
    fixture_path = FIXTURES_DIR / "t3000-ls-files"
    
    if fixture_path.exists():
        shutil.rmtree(fixture_path)
    
    fixture_path.mkdir(parents=True)
    
    repo = Repo.init(fixture_path)
    
    with repo.config_writer() as config:
        config.set_value("user", "name", "Test User")
        config.set_value("user", "email", "test@example.com")
    
    # Tracked files
    tracked_files = ["tracked.txt", "src/tracked.py", "docs/readme.md"]
    for f in tracked_files:
        full_path = fixture_path / f
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(f"Tracked: {f}\n")
    
    repo.index.add(tracked_files)
    repo.index.commit("Initial commit with tracked files")
    
    # Untracked files (not in index)
    untracked_files = ["untracked.txt", "temp/cache.tmp", "build/output.js"]
    for f in untracked_files:
        full_path = fixture_path / f
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(f"Untracked: {f}\n")
    
    # Ignored file
    (fixture_path / ".gitignore").write_text("*.log\nsecret/\n")
    repo.index.add([".gitignore"])
    
    # Create ignored file
    (fixture_path / "debug.log").write_text("Log content\n")
    (fixture_path / "secret").mkdir(parents=True, exist_ok=True)
    (fixture_path / "secret/password.txt").write_text("password123\n")
    
    repo.index.commit("Add gitignore")
    
    print(f"✅ Created fixture: {fixture_path}")
    return fixture_path


def create_t4000_diff_fixture():
    """Create fixture with clear diffs between commits."""
    fixture_path = FIXTURES_DIR / "t4000-diff"
    
    if fixture_path.exists():
        shutil.rmtree(fixture_path)
    
    fixture_path.mkdir(parents=True)
    
    repo = Repo.init(fixture_path)
    
    with repo.config_writer() as config:
        config.set_value("user", "name", "Test User")
        config.set_value("user", "email", "test@example.com")
    
    # Initial files
    initial_content = {
        "file1.txt": "Line 1\nLine 2\nLine 3\n",
        "file2.txt": "Content A\nContent B\n",
        "file3.txt": "Original\n",
    }
    
    for path, content in initial_content.items():
        full_path = fixture_path / path
        full_path.write_text(content)
    
    repo.index.add(list(initial_content.keys()))
    first_commit = repo.index.commit("Initial commit")
    
    # Second commit - modify, add, delete
    (fixture_path / "file1.txt").write_text("Line 1\nModified Line 2\nLine 3\nAdded line\n")
    (fixture_path / "file2.txt").unlink()  # Delete
    (fixture_path / "file4.txt").write_text("New file content\n")  # Add
    
    repo.index.add(["file1.txt", "file4.txt"])
    repo.index.remove(["file2.txt"])
    second_commit = repo.index.commit("Second commit: modify, delete, add")
    
    # Third commit - more modifications
    (fixture_path / "file3.txt").write_text("Modified original\nNew line\n")
    (fixture_path / "file1.txt").write_text("Line 1\nModified Line 2\nLine 3\nAdded line\nAnother addition\n")
    
    repo.index.add(["file1.txt", "file3.txt"])
    third_commit = repo.index.commit("Third commit")
    
    print(f"✅ Created fixture: {fixture_path}")
    return fixture_path


def create_t4100_binary_fixture():
    """Create fixture with binary files."""
    fixture_path = FIXTURES_DIR / "t4100-binary"
    
    if fixture_path.exists():
        shutil.rmtree(fixture_path)
    
    fixture_path.mkdir(parents=True)
    
    repo = Repo.init(fixture_path)
    
    with repo.config_writer() as config:
        config.set_value("user", "name", "Test User")
        config.set_value("user", "email", "test@example.com")
    
    # Text file
    (fixture_path / "text.txt").write_text("Text content\n")
    
    # Binary file (null bytes)
    (fixture_path / "binary.bin").write_bytes(b"Binary\x00data\xff\xfe")
    
    # Image-like binary
    (fixture_path / "image.bin").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)
    
    # Mixed content file
    (fixture_path / "mixed.txt").write_bytes(b"Text\n\x00Binary\n")
    
    repo.index.add(["text.txt", "binary.bin", "image.bin", "mixed.txt"])
    repo.index.commit("Initial commit with binary files")
    
    print(f"✅ Created fixture: {fixture_path}")
    return fixture_path


def create_t4200_symlink_fixture():
    """Create fixture with symlinks."""
    fixture_path = FIXTURES_DIR / "t4200-symlink"
    
    if fixture_path.exists():
        shutil.rmtree(fixture_path)
    
    fixture_path.mkdir(parents=True)
    
    repo = Repo.init(fixture_path)
    
    with repo.config_writer() as config:
        config.set_value("user", "name", "Test User")
        config.set_value("user", "email", "test@example.com")
    
    # Regular file
    (fixture_path / "target.txt").write_text("Target content\n")
    
    # Try to create symlinks (may fail on Windows without permissions)
    try:
        (fixture_path / "link.txt").symlink_to("target.txt")
        (fixture_path / "dir_link").symlink_to(".")
        files = ["target.txt", "link.txt", "dir_link"]
    except (OSError, NotImplementedError):
        # Fallback: just use regular files
        files = ["target.txt"]
    
    repo.index.add(files)
    repo.index.commit("Initial commit")
    
    print(f"✅ Created fixture: {fixture_path}")
    return fixture_path


def create_t4300_deep_nesting_fixture():
    """Create fixture with deeply nested directories."""
    fixture_path = FIXTURES_DIR / "t4300-deep-nesting"
    
    if fixture_path.exists():
        shutil.rmtree(fixture_path)
    
    fixture_path.mkdir(parents=True)
    
    repo = Repo.init(fixture_path)
    
    with repo.config_writer() as config:
        config.set_value("user", "name", "Test User")
        config.set_value("user", "email", "test@example.com")
    
    # Create deeply nested structure (15 levels)
    files = []
    for depth in range(1, 16):
        path_parts = [f"level{i}" for i in range(1, depth + 1)]
        path_parts.append(f"file{depth}.txt")
        path = "/".join(path_parts)
        
        full_path = fixture_path / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(f"Content at level {depth}\n")
        files.append(path)
    
    repo.index.add(files)
    repo.index.commit("Initial commit with deep nesting")
    
    print(f"✅ Created fixture: {fixture_path}")
    return fixture_path


def create_t4400_empty_files_fixture():
    """Create fixture with empty files."""
    fixture_path = FIXTURES_DIR / "t4400-empty-files"
    
    if fixture_path.exists():
        shutil.rmtree(fixture_path)
    
    fixture_path.mkdir(parents=True)
    
    repo = Repo.init(fixture_path)
    
    with repo.config_writer() as config:
        config.set_value("user", "name", "Test User")
        config.set_value("user", "email", "test@example.com")
    
    # Empty file
    (fixture_path / "empty.txt").write_text("")
    
    # File with only whitespace
    (fixture_path / "whitespace.txt").write_text("   \n\t\n")
    
    # File with single newline
    (fixture_path / "newline.txt").write_text("\n")
    
    # Normal file for comparison
    (fixture_path / "normal.txt").write_text("Normal content\n")
    
    repo.index.add(["empty.txt", "whitespace.txt", "newline.txt", "normal.txt"])
    repo.index.commit("Initial commit with empty/special files")
    
    print(f"✅ Created fixture: {fixture_path}")
    return fixture_path


def create_t4500_large_content_fixture():
    """Create fixture with files containing many lines."""
    fixture_path = FIXTURES_DIR / "t4500-large-content"
    
    if fixture_path.exists():
        shutil.rmtree(fixture_path)
    
    fixture_path.mkdir(parents=True)
    
    repo = Repo.init(fixture_path)
    
    with repo.config_writer() as config:
        config.set_value("user", "name", "Test User")
        config.set_value("user", "email", "test@example.com")
    
    # Large file with many lines
    lines = [f"Line {i}: This is content for line number {i}\n" for i in range(1, 101)]
    (fixture_path / "large.txt").write_text("".join(lines))
    
    # Medium file
    medium_lines = [f"Entry {i}\n" for i in range(1, 21)]
    (fixture_path / "medium.txt").write_text("".join(medium_lines))
    
    # Small file
    (fixture_path / "small.txt").write_text("Small\n")
    
    repo.index.add(["large.txt", "medium.txt", "small.txt"])
    repo.index.commit("Initial commit with various file sizes")
    
    # Modify large file
    lines[50] = "Line 51: MODIFIED LINE\n"
    (fixture_path / "large.txt").write_text("".join(lines))
    repo.index.add(["large.txt"])
    repo.index.commit("Modify line 51 in large file")
    
    print(f"✅ Created fixture: {fixture_path}")
    return fixture_path


def create_all_fixtures():
    """Create all test fixtures."""
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    
    fixtures = [
        ("t0001-init", create_t0001_init_fixture),
        ("t1000-read-tree", create_t1000_read_tree_fixture),
        ("t1100-commit-tree", create_t1100_commit_tree_fixture),
        ("t1200-checkout", create_t1200_checkout_fixture),
        ("t2000-checkout", create_t2000_checkout_fixture),
        ("t3000-ls-files", create_t3000_ls_files_fixture),
        ("t3200-branch", create_t3200_branch_fixture),
        ("t3400-rebase", create_t3400_rebase_fixture),
        ("t3600-rm", create_t3600_rm_fixture),
        ("t3900-unicode", create_t3900_unicode_fixture),
        ("t4000-diff", create_t4000_diff_fixture),
        ("t4100-binary", create_t4100_binary_fixture),
        ("t4200-symlink", create_t4200_symlink_fixture),
        ("t4300-deep-nesting", create_t4300_deep_nesting_fixture),
        ("t4400-empty-files", create_t4400_empty_files_fixture),
        ("t4500-large-content", create_t4500_large_content_fixture),
    ]
    
    successes = 0
    failures = 0
    
    for name, creator in fixtures:
        try:
            creator()
            successes += 1
        except Exception as e:
            print(f"❌ Failed to create {name}: {e}")
            failures += 1
    
    print(f"\n📊 Results: {successes} succeeded, {failures} failed")
    return failures == 0


def main():
    if len(sys.argv) > 1:
        # Create specific fixture
        fixture_name = sys.argv[1].replace(".sh", "")
        creators = {
            "t0001-init": create_t0001_init_fixture,
            "t1000-read-tree": create_t1000_read_tree_fixture,
            "t1100-commit-tree": create_t1100_commit_tree_fixture,
            "t1200-checkout": create_t1200_checkout_fixture,
            "t2000-checkout": create_t2000_checkout_fixture,
            "t3000-ls-files": create_t3000_ls_files_fixture,
            "t3200-branch": create_t3200_branch_fixture,
            "t3400-rebase": create_t3400_rebase_fixture,
            "t3600-rm": create_t3600_rm_fixture,
            "t3900-unicode": create_t3900_unicode_fixture,
            "t4000-diff": create_t4000_diff_fixture,
            "t4100-binary": create_t4100_binary_fixture,
            "t4200-symlink": create_t4200_symlink_fixture,
            "t4300-deep-nesting": create_t4300_deep_nesting_fixture,
            "t4400-empty-files": create_t4400_empty_files_fixture,
            "t4500-large-content": create_t4500_large_content_fixture,
        }
        
        if fixture_name in creators:
            FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
            creators[fixture_name]()
            return 0
        else:
            print(f"Unknown fixture: {fixture_name}")
            print(f"Available: {', '.join(creators.keys())}")
            return 1
    else:
        # Create all fixtures
        success = create_all_fixtures()
        return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
