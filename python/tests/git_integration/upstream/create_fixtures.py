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


def create_all_fixtures():
    """Create all test fixtures."""
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    
    fixtures = [
        ("t0001-init", create_t0001_init_fixture),
        ("t1000-read-tree", create_t1000_read_tree_fixture),
        ("t3200-branch", create_t3200_branch_fixture),
        ("t3400-rebase", create_t3400_rebase_fixture),
        ("t3600-rm", create_t3600_rm_fixture),
        ("t3900-unicode", create_t3900_unicode_fixture),
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
            "t3200-branch": create_t3200_branch_fixture,
            "t3400-rebase": create_t3400_rebase_fixture,
            "t3600-rm": create_t3600_rm_fixture,
            "t3900-unicode": create_t3900_unicode_fixture,
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
