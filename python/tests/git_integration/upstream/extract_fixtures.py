#!/usr/bin/env python3
"""
Extract test fixtures from Git's test suite.

Usage:
    python extract_fixtures.py t0001-init t1000-read-tree
"""

import subprocess
import shutil
import sys
from pathlib import Path

GIT_TEST_DIR = Path(__file__).parent / "git" / "t"
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "upstream"


def extract_fixture(test_name: str) -> bool:
    """
    Run a Git test script and extract the resulting repository.

    Args:
        test_name: Test name without .sh extension (e.g., "t0001-init")

    Returns:
        True if extraction succeeded, False otherwise
    """
    test_script = GIT_TEST_DIR / f"{test_name}.sh"

    if not test_script.exists():
        print(f"❌ Test script not found: {test_script}")
        return False

    print(f"🏃 Running test: {test_name}")

    # Run test script
    result = subprocess.run(
        ["bash", str(test_script)],
        cwd=GIT_TEST_DIR,
        capture_output=True,
        text=True
    )

    # Find trash directory
    trash_dir = GIT_TEST_DIR / f"trash directory.{test_name}"

    if not trash_dir.exists():
        print(f"⚠️  No trash directory found for {test_name}")
        print(f"Test output:\n{result.stdout}\n{result.stderr}")
        return False

    # Copy to fixtures
    output_dir = FIXTURES_DIR / test_name
    if output_dir.exists():
        print(f"🗑️  Removing existing fixture: {output_dir}")
        shutil.rmtree(output_dir)

    shutil.copytree(trash_dir, output_dir)

    # Clean up trash directory
    shutil.rmtree(trash_dir)

    print(f"✅ Extracted fixture: {test_name} → {output_dir}")
    return True


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_fixtures.py TEST_NAME [TEST_NAME ...]")
        print("Example: python extract_fixtures.py t0001-init t1000-read-tree")
        sys.exit(1)

    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    successes = 0
    failures = 0

    for test_name in sys.argv[1:]:
        # Remove .sh extension if provided
        test_name = test_name.replace(".sh", "")

        if extract_fixture(test_name):
            successes += 1
        else:
            failures += 1

    print(f"\n📊 Results: {successes} succeeded, {failures} failed")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
