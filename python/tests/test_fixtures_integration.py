#!/usr/bin/env python3
"""
Integration test for Git test fixtures API.

This script tests the actual fixture initialization endpoints
to ensure they work end-to-end with the database.

Usage:
    python tests/test_fixtures_integration.py

Requirements:
    - Supabase running in Docker
    - Backend server running on localhost:8000
"""

import requests
import sys
import time

BASE_URL = "http://localhost:8000"
PROJECT_ID = "git-integration-test-project"

FIXTURES = ["simple-commits", "multi-branch", "file-structure"]


def test_fixture_initialization(fixture_name: str) -> bool:
    """Test initializing a specific fixture.

    Args:
        fixture_name: Name of fixture to test

    Returns:
        True if successful, False otherwise
    """
    print(f"\n🧪 Testing fixture: {fixture_name}")

    # Initialize the fixture
    url = f"{BASE_URL}/api/projects/{PROJECT_ID}/test-fixtures/initialize"
    payload = {"fixture_name": fixture_name}

    try:
        response = requests.post(url, json=payload, timeout=30)

        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print(f"  ✅ {fixture_name}: Initialized successfully")
                print(f"     Repo ID: {data.get('repo_id')}")
                print(f"     Repo Name: {data.get('repo_name')}")
                return True
            else:
                print(f"  ❌ {fixture_name}: API returned success=false")
                print(f"     Message: {data.get('message')}")
                return False
        else:
            print(f"  ❌ {fixture_name}: HTTP {response.status_code}")
            print(f"     Error: {response.text[:200]}")
            return False

    except requests.exceptions.ConnectionError:
        print(f"  ❌ Cannot connect to backend at {BASE_URL}")
        print(f"     Is the server running? Start it with: cd python && uv run uvicorn src.server.main:app")
        return False
    except Exception as e:
        print(f"  ❌ {fixture_name}: Unexpected error - {e}")
        return False


def cleanup_fixtures() -> bool:
    """Cleanup all test fixtures."""
    print(f"\n🧹 Cleaning up test fixtures...")

    url = f"{BASE_URL}/api/projects/{PROJECT_ID}/test-fixtures"

    try:
        response = requests.delete(url, timeout=10)

        if response.status_code == 200:
            data = response.json()
            print(f"  ✅ Cleanup successful")
            print(f"     Deleted: {data.get('deleted_count', 0)} items")
            return True
        else:
            print(f"  ⚠️ Cleanup returned HTTP {response.status_code}")
            return False

    except Exception as e:
        print(f"  ⚠️ Cleanup error: {e}")
        return False


def main():
    """Run integration tests for all fixtures."""
    print("=" * 60)
    print("Git Test Fixtures - Integration Tests")
    print("=" * 60)

    # Test each fixture
    results = {}
    for fixture in FIXTURES:
        results[fixture] = test_fixture_initialization(fixture)
        time.sleep(1)  # Brief delay between tests

    # Cleanup
    cleanup_fixtures()

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for result in results.values() if result)
    total = len(results)

    for fixture, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {fixture}")

    print(f"\nResults: {passed}/{total} passed")

    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
