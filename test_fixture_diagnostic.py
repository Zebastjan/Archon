#!/usr/bin/env python3
"""
Diagnostic script to test fixture file tree retrieval without needing database access.
This will help us understand why document creation is failing.
"""

import sys
from pathlib import Path

# Add python/src to path
sys.path.insert(0, str(Path(__file__).parent / "python" / "src"))

from server.services.git.git_repository_service import GitRepositoryService

# Test fixture path
fixture_path = Path(__file__).parent / "python/tests/git_integration/fixtures/simple-commits/.repo"

print("=" * 80)
print("GIT TEST FIXTURE DIAGNOSTIC")
print("=" * 80)

print(f"\n1. Checking fixture path: {fixture_path}")
print(f"   Exists: {fixture_path.exists()}")
print(f"   Is directory: {fixture_path.is_dir()}")
print(f"   Is git repo: {(fixture_path / '.git').exists()}")

if not fixture_path.exists():
    print("   ❌ FIXTURE PATH DOES NOT EXIST!")
    sys.exit(1)

print("\n2. Listing files in fixture:")
for file in fixture_path.rglob("*"):
    if file.is_file() and ".git" not in str(file):
        print(f"   - {file.relative_to(fixture_path)}")

print("\n3. Attempting to initialize GitRepositoryService...")
try:
    # Create a minimal service instance without database
    # This will test if we can read the git repo
    import git

    repo = git.Repo(str(fixture_path))
    print(f"   ✓ Git repo loaded successfully")
    print(f"   HEAD: {repo.head.commit.hexsha}")
    print(f"   Active branch: {repo.active_branch.name}")

    # Get file tree manually
    print("\n4. Getting file tree from HEAD commit...")
    head_commit = repo.head.commit
    print(f"   Commit SHA: {head_commit.hexsha}")

    files_found = []
    for item in head_commit.tree.traverse():
        if item.type == "blob":  # It's a file
            file_info = {
                "file_path": item.path,
                "file_size": item.size,
                "is_binary": False,  # Simplified for testing
            }
            files_found.append(file_info)
            print(f"   - {item.path} ({item.size} bytes)")

    print(f"\n5. Summary:")
    print(f"   Total files found: {len(files_found)}")

    if len(files_found) == 0:
        print("   ❌ NO FILES FOUND IN REPOSITORY!")
    else:
        print("   ✓ Files were found successfully")

        # Test field names
        print("\n6. Testing field name access (this is where the bug was):")
        test_file = files_found[0]
        print(f"   file_info.get('file_path'): {test_file.get('file_path')}")
        print(f"   file_info.get('path'): {test_file.get('path')} ← This was the bug (should be None)")
        print(f"   file_info.get('file_size'): {test_file.get('file_size')}")
        print(f"   file_info.get('size'): {test_file.get('size')} ← This was the bug (should be None)")

except Exception as e:
    print(f"   ❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 80)
print("DIAGNOSTIC COMPLETE")
print("=" * 80)
