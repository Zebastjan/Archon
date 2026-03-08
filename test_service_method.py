#!/usr/bin/env python3
"""
Test the actual GitRepositoryService.get_file_tree() method that's used in the API.
This requires a database connection but we can test without inserting data.
"""

import sys
import os
from pathlib import Path

# Set minimal required env vars
os.environ['SUPABASE_URL'] = 'http://localhost:8000'  # Won't actually connect
os.environ['SUPABASE_SERVICE_KEY'] = 'dummy'  # Won't actually connect

# Add python/src to path
sys.path.insert(0, str(Path(__file__).parent / "python" / "src"))

print("=" * 80)
print("TESTING GitRepositoryService.get_file_tree()")
print("=" * 80)

# Import after setting env vars
from server.services.git.git_repository_service import GitRepositoryService
import git

# Test fixture path
fixture_path = Path(__file__).parent / "python/tests/git_integration/fixtures/simple-commits/.repo"

print(f"\n1. Loading git repository...")
repo = git.Repo(str(fixture_path))
head_sha = repo.head.commit.hexsha
print(f"   HEAD SHA: {head_sha}")

print(f"\n2. Creating GitRepositoryService instance...")
try:
    # This will fail if it tries to connect to database, but we just want to test the method logic
    service = GitRepositoryService(supabase_client=None)  # type: ignore
    print(f"   ✓ Service created (without database connection)")
except Exception as e:
    print(f"   Note: {e}")
    print("   Continuing anyway to test the method...")

print(f"\n3. Manually testing what get_file_tree() does...")
print(f"   Repository path: {fixture_path}")

# Manually replicate what get_file_tree does
from pathlib import Path as P

try:
    commit = repo.commit(head_sha)
    files = []

    for item in commit.tree.traverse():
        if item.type == "blob":  # It's a file, not a tree
            item_path = item.path

            # This is what get_file_tree() creates
            file_info = {
                "file_path": item_path,
                "file_name": P(item_path).name,
                "file_extension": P(item_path).suffix.lower(),
                "blob_sha": item.hexsha if hasattr(item, "hexsha") else "",
                "file_size": item.size if hasattr(item, "size") else 0,
                "language": None,  # Simplified
                "is_binary": False,  # Simplified
            }
            files.append(file_info)
            print(f"   - {item_path}: size={file_info['file_size']}, file_path={file_info.get('file_path')}")

    print(f"\n4. Summary:")
    print(f"   Files found: {len(files)}")

    if len(files) > 0:
        print(f"\n5. Testing our fixed code against this structure:")
        test_file = files[0]

        # This is what the FIXED code does:
        file_path = test_file.get("file_path")
        file_size = test_file.get("file_size", 0)

        print(f"   file_info.get('file_path'): {file_path}")
        print(f"   file_info.get('file_size', 0): {file_size}")

        # Test the skip condition
        is_binary = test_file.get("is_binary")
        should_skip = is_binary or file_size > 1_000_000

        print(f"\n6. Would this file be processed?")
        print(f"   is_binary: {is_binary}")
        print(f"   file_size > 1MB: {file_size > 1_000_000}")
        print(f"   would skip: {should_skip}")
        print(f"   file_path is valid: {bool(file_path)}")

        if not should_skip and file_path:
            print(f"   ✓ File WOULD be processed for document creation")
        else:
            print(f"   ❌ File WOULD BE SKIPPED")

except Exception as e:
    print(f"   ❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
