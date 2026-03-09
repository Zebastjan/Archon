"""
Embedded Test Repository Generator

Creates a test repository with pre-embedded commits and classifications
for testing RAG integration with real data.
"""

import subprocess
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any


class EmbeddedRepoGenerator:
    """Generate test repository with embedded commits and classifications."""

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.repo_path.mkdir(parents=True, exist_ok=True)

    def _run_git(self, *args: str) -> str:
        """Run git command in repository."""
        result = subprocess.run(
            ["git", *args],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    def _create_file(self, path: str, content: str) -> None:
        """Create a file with given content."""
        file_path = self.repo_path / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)

    def _commit(self, message: str, author: str = "Test User <test@example.com>") -> str:
        """Create a commit and return its SHA."""
        self._run_git("add", ".")
        self._run_git(
            "-c", f"user.name=Test User",
            "-c", f"user.email={author}",
            "commit", "-m", message,
        )
        return self._run_git("rev-parse", "HEAD")

    def generate(self) -> dict[str, Any]:
        """Generate the embedded test repository."""
        # Initialize git repo with main branch
        self._run_git("init", "-b", "main")
        self._run_git("config", "user.name", "Test User")
        self._run_git("config", "user.email", "test@example.com")

        commits = []

        # Commit 1: Initial setup (feature)
        self._create_file("README.md", "# Test Project\n\nA test repository for RAG integration testing.")
        self._create_file("src/app.py", "def main():\n    print('Hello World')\n")
        sha1 = self._commit("Initial commit: Add project structure and README")
        commits.append({
            "sha": sha1,
            "message": "Initial commit: Add project structure and README",
            "intent": "feature",
            "risk_level": "low",
            "security_relevant": False,
            "breaking_change": False,
            "description": "Initial project setup with basic structure",
        })

        # Commit 2: Feature addition
        self._create_file("src/auth.py", """
def authenticate(username, password):
    # Simple authentication
    if username and password:
        return True
    return False
""")
        sha2 = self._commit("Add basic authentication module")
        commits.append({
            "sha": sha2,
            "message": "Add basic authentication module",
            "intent": "feature",
            "risk_level": "medium",
            "security_relevant": True,
            "breaking_change": False,
            "description": "Implements basic user authentication",
        })

        # Commit 3: Bug fix
        self._create_file("src/auth.py", """
def authenticate(username, password):
    # Fixed: Check for None values
    if username is not None and password is not None:
        if len(username) > 0 and len(password) > 0:
            return True
    return False
""")
        sha3 = self._commit("Fix authentication null pointer issue")
        commits.append({
            "sha": sha3,
            "message": "Fix authentication null pointer issue",
            "intent": "bugfix",
            "risk_level": "medium",
            "security_relevant": True,
            "breaking_change": False,
            "description": "Fixes potential crash when null values passed to auth",
        })

        # Commit 4: Security fix
        self._create_file("src/auth.py", """
import hashlib

def authenticate(username, password):
    # Security fix: Hash passwords
    if username is not None and password is not None:
        if len(username) > 0 and len(password) > 0:
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            # Check against stored hash (stub)
            return True
    return False
""")
        sha4 = self._commit("Security: Hash passwords before storage")
        commits.append({
            "sha": sha4,
            "message": "Security: Hash passwords before storage",
            "intent": "security_fix",
            "risk_level": "high",
            "security_relevant": True,
            "breaking_change": False,
            "description": "Critical security fix to prevent plaintext password storage",
        })

        # Commit 5: Breaking API change
        self._create_file("src/auth.py", """
import hashlib

class AuthService:
    def authenticate(self, username: str, password: str) -> dict:
        # Breaking change: New class-based API returns dict instead of bool
        if username and password:
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            return {"authenticated": True, "username": username}
        return {"authenticated": False, "error": "Invalid credentials"}
""")
        sha5 = self._commit("Refactor authentication to class-based API")
        commits.append({
            "sha": sha5,
            "message": "Refactor authentication to class-based API",
            "intent": "refactor",
            "risk_level": "high",
            "security_relevant": False,
            "breaking_change": True,
            "description": "Major refactoring that changes authentication API",
        })

        # Commit 6: Performance optimization
        self._create_file("src/cache.py", """
from functools import lru_cache

@lru_cache(maxsize=128)
def get_user(user_id: int):
    # Cache user lookups for performance
    return {"id": user_id, "name": f"User {user_id}"}
""")
        sha6 = self._commit("Optimize user lookups with LRU cache")
        commits.append({
            "sha": sha6,
            "message": "Optimize user lookups with LRU cache",
            "intent": "performance",
            "risk_level": "low",
            "security_relevant": False,
            "breaking_change": False,
            "description": "Adds caching to improve performance of user lookups",
        })

        # Commit 7: Documentation
        self._create_file("docs/API.md", """
# API Documentation

## Authentication

Use `AuthService` class for authentication:

```python
from src.auth import AuthService

auth = AuthService()
result = auth.authenticate("user", "pass")
if result["authenticated"]:
    print(f"Welcome {result['username']}")
```
""")
        sha7 = self._commit("Add API documentation for authentication")
        commits.append({
            "sha": sha7,
            "message": "Add API documentation for authentication",
            "intent": "documentation",
            "risk_level": "low",
            "security_relevant": False,
            "breaking_change": False,
            "description": "Documents the new authentication API",
        })

        # Commit 8: Test addition
        self._create_file("tests/test_auth.py", """
import pytest
from src.auth import AuthService

def test_authenticate_success():
    auth = AuthService()
    result = auth.authenticate("testuser", "password123")
    assert result["authenticated"] is True
    assert result["username"] == "testuser"

def test_authenticate_failure():
    auth = AuthService()
    result = auth.authenticate("", "")
    assert result["authenticated"] is False
""")
        sha8 = self._commit("Add comprehensive authentication tests")
        commits.append({
            "sha": sha8,
            "message": "Add comprehensive authentication tests",
            "intent": "test",
            "risk_level": "low",
            "security_relevant": False,
            "breaking_change": False,
            "description": "Adds unit tests for authentication module",
        })

        # Create feature branch
        self._run_git("checkout", "-b", "feature/api-v2")

        # Commit 9: Feature branch work
        self._create_file("src/api_v2.py", """
class ApiV2:
    def get_users(self, limit=10):
        return [{"id": i, "name": f"User {i}"} for i in range(limit)]
""")
        sha9 = self._commit("Add API v2 endpoints")
        commits.append({
            "sha": sha9,
            "message": "Add API v2 endpoints",
            "intent": "feature",
            "risk_level": "medium",
            "security_relevant": False,
            "breaking_change": False,
            "description": "Implements new API v2 with improved endpoints",
        })

        # Switch back to main
        self._run_git("checkout", "main")

        # Commit 10: Merge conflict setup
        self._create_file("src/config.py", """
CONFIG = {
    "debug": False,
    "log_level": "INFO"
}
""")
        sha10 = self._commit("Add configuration module")
        commits.append({
            "sha": sha10,
            "message": "Add configuration module",
            "intent": "feature",
            "risk_level": "low",
            "security_relevant": False,
            "breaking_change": False,
            "description": "Adds application configuration support",
        })

        return {
            "repo_path": str(self.repo_path),
            "commits": commits,
            "branches": ["main", "feature/api-v2"],
            "total_commits": len(commits),
        }


def generate_embedded_fixture() -> dict[str, Any]:
    """Generate embedded test repository fixture."""
    fixtures_dir = Path(__file__).parent.parent
    repo_path = fixtures_dir / "embedded-test-repo"

    # Clean up if exists
    if repo_path.exists():
        import shutil
        shutil.rmtree(repo_path)

    generator = EmbeddedRepoGenerator(repo_path)
    return generator.generate()


if __name__ == "__main__":
    import json
    result = generate_embedded_fixture()
    print(json.dumps(result, indent=2))
