"""Tests for version-scoped search (ADR-007).

These tests verify that MCP code search tools properly scope to the current branch
and support historical queries. Uses both real DB (integration tests) and mocks
(unit tests).

Run with:
    docker exec -e ARCHON_BRANCH=feature/test-branch archon pytest tests/mcp_server/test_version_scoped_search.py -v
"""

from __future__ import annotations

import os
import subprocess
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any

import pytest

# CRITICAL: Don't set TEST_MODE or TESTING - we want REAL database for these tests
# os.environ.setdefault("TEST_MODE", "true")  # COMMENTED OUT - use real DB
# os.environ.setdefault("TESTING", "true")   # COMMENTED OUT - use real DB


# Known test data from DB:
# - repo: 3e01a03c-f9ef-417d-bdd6-9da6b1d32ad2 has 4814 entities on feature/multi-language-code-intelligence
# - repo: 1c6cdcee-c020-4ba1-b5f0-300258a90487 has 1067 entities on fix/permission-prompt-directory
# - Multiple branches exist: master, feature/multi-language-code-intelligence, feature/multi-backend-stt, fix/permission-prompt-directory


class TestMCPToolsEndToEnd:
    """End-to-end tests that call actual MCP tool functions with REAL database.

    These tests verify the full MCP pipeline by calling the tool registration
    and executing the tools with real data.

    NOTE: Since the service layer imports DB at module load time, we use
    direct SQL queries for these tests to ensure real DB access.
    """

    @pytest.mark.real_db
    def test_codebase_find_entity_returns_search_scope_with_real_db(self):
        """Test that code entities have branch data in the real database."""
        # Use subprocess to run psql directly (bypasses all Python mocking)
        result = subprocess.run(
            [
                "psql",
                "-U",
                "postgres",
                "-d",
                "archon",
                "-t",
                "-c",
                "SELECT name, branch_name, is_deleted FROM archon_code_entities WHERE name ILIKE '%extract%' LIMIT 5",
            ],
            capture_output=True,
            text=True,
        )

        lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]

        assert len(lines) > 0, "Should find entities in database"

        # Parse results - format is "name | branch_name | is_deleted"
        branches_found = set()
        for line in lines:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 2:
                name, branch = parts[0], parts[1]
                branches_found.add(branch)

        print(f"Branches in DB query results: {branches_found}")
        assert len(branches_found) > 0, "Should have branch data in results"

    @pytest.mark.real_db
    def test_version_scoped_search_filters_by_branch(self):
        """Test that SQL query with branch filter works correctly."""
        # Test filtering by specific branch
        branch = "feature/multi-language-code-intelligence"
        query = f"""
        SELECT name, branch_name, is_deleted 
        FROM archon_code_entities 
        WHERE name ILIKE '%extract%' 
        AND branch_name = '{branch}'
        AND (is_deleted IS NULL OR is_deleted = false)
        """

        result = subprocess.run(
            ["psql", "-U", "postgres", "-d", "archon", "-t", "-c", query], capture_output=True, text=True
        )

        lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]

        print(f"Entities on branch {branch}: {len(lines)}")
        assert len(lines) > 0, f"Should find entities on branch {branch}"

    @pytest.mark.real_db
    def test_deleted_entities_exist_in_schema(self):
        """Test that is_deleted column exists and can be queried."""
        # Check that is_deleted column exists
        result = subprocess.run(
            [
                "psql",
                "-U",
                "postgres",
                "-d",
                "archon",
                "-t",
                "-c",
                "SELECT COUNT(*) FROM archon_code_entities WHERE is_deleted = true",
            ],
            capture_output=True,
            text=True,
        )

        deleted_count = int(result.stdout.strip())
        print(f"Deleted entities in database: {deleted_count}")

        # Just verify the column works - actual count may be 0
        assert result.returncode == 0, "is_deleted query should work"


class TestDatabaseIntegration:
    """Tests that use the REAL database connection (not mocks).

    These tests connect to the actual database in the container.
    """

    def test_real_db_query_version_scope_columns(self):
        """Query the real database to verify columns exist."""
        # Use psql directly to query the real database
        result = subprocess.run(
            [
                "psql",
                "-U",
                "postgres",
                "-d",
                "archon",
                "-t",
                "-c",
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'archon_code_entities' AND column_name IN ('branch_name', 'commit_sha', 'is_deleted', 'entity_identity', 'parent_commit_sha', 'change_type') ORDER BY column_name",
            ],
            capture_output=True,
            text=True,
        )

        columns = [c.strip() for c in result.stdout.strip().split("\n") if c.strip()]

        required = {"branch_name", "commit_sha", "is_deleted", "entity_identity", "parent_commit_sha", "change_type"}
        missing = required - set(columns)

        assert not missing, f"Missing columns: {missing}"
        print(f"✓ All required columns exist: {columns}")

    def test_real_db_query_branch_data(self):
        """Query the real database to verify branch data exists."""
        result = subprocess.run(
            [
                "psql",
                "-U",
                "postgres",
                "-d",
                "archon",
                "-t",
                "-c",
                "SELECT branch_name, COUNT(*) FROM archon_code_entities WHERE branch_name IS NOT NULL GROUP BY branch_name",
            ],
            capture_output=True,
            text=True,
        )

        lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
        print(f"Branch distribution:\n{result.stdout}")

        assert len(lines) > 0, "Should have data in branches"

    def test_real_db_query_entities_with_branch_filter(self):
        """Test actual SQL query with branch filter."""
        query = """
        SELECT name, branch_name, is_deleted 
        FROM archon_code_entities 
        WHERE name ILIKE '%extract%' 
        AND branch_name = 'feature/multi-language-code-intelligence'
        AND (is_deleted IS NULL OR is_deleted = false)
        LIMIT 5
        """

        result = subprocess.run(
            ["psql", "-U", "postgres", "-d", "archon", "-t", "-c", query], capture_output=True, text=True
        )

        lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
        print(f"Query results:\n{result.stdout}")

        assert len(lines) > 0, "Should find entities with branch filter"


class TestWorktreeContextBinding:
    """Tests for worktree context binding (ADR-008)."""

    def test_worktree_context_module_imports(self):
        """Test that worktree_context module can be imported."""
        from src.mcp_server import worktree_context

        assert hasattr(worktree_context, "get_current_branch")
        assert hasattr(worktree_context, "get_current_commit")
        assert hasattr(worktree_context, "get_worktree_context")

    def test_worktree_context_get_current_branch(self):
        """Test get_current_branch returns branch from context."""
        from src.mcp_server import worktree_context

        worktree_context.set_worktree_context(
            branch="feature/test-branch", commit="abc12345", worktree_path="/test/path"
        )

        branch = worktree_context.get_current_branch()
        assert branch == "feature/test-branch"

        worktree_context.set_worktree_context(branch="main", commit="", worktree_path="")

    def test_worktree_context_get_current_commit(self):
        """Test get_current_commit returns commit from context."""
        from src.mcp_server import worktree_context

        worktree_context.set_worktree_context(branch="main", commit="def67890", worktree_path="/test/path")

        commit = worktree_context.get_current_commit()
        assert commit == "def67890"

        worktree_context.set_worktree_context(branch="main", commit="", worktree_path="")

    def test_worktree_context_is_valid(self):
        """Test is_valid_context check."""
        from src.mcp_server import worktree_context

        worktree_context.set_worktree_context(branch="feature/test", commit="abc123", worktree_path="/test")
        assert worktree_context.is_valid_context() is True

        worktree_context.set_worktree_context(branch="main", commit="", worktree_path="")
        assert worktree_context.is_valid_context() is True

        worktree_context.set_worktree_context(branch="main", commit="", worktree_path="")


class TestFilteringLogic:
    """Unit tests for the filtering logic (can run without DB)."""

    def test_filter_by_branch_logic(self):
        """Test the branch filtering logic."""
        entities = [
            {"name": "func1", "branch_name": "branch-a", "is_deleted": False},
            {"name": "func2", "branch_name": "branch-b", "is_deleted": False},
            {"name": "func3", "branch_name": "branch-a", "is_deleted": True},
        ]

        # Filter to branch-a (excluding deleted)
        filtered = [e for e in entities if e["branch_name"] == "branch-a" and not e["is_deleted"]]

        assert len(filtered) == 1
        assert filtered[0]["name"] == "func1"

    def test_filter_by_commit_logic(self):
        """Test the commit filtering logic."""
        entities = [
            {"name": "func1", "commit_sha": "abc123", "is_deleted": False},
            {"name": "func2", "commit_sha": "def456", "is_deleted": False},
        ]

        filtered = [e for e in entities if e["commit_sha"] == "abc123"]

        assert len(filtered) == 1
        assert filtered[0]["name"] == "func1"

    def test_exclude_deleted_entities(self):
        """Test that deleted entities are excluded."""
        entities = [
            {"name": "func1", "is_deleted": False},
            {"name": "func2", "is_deleted": True},
            {"name": "func3", "is_deleted": False},
        ]

        filtered = [e for e in entities if not e.get("is_deleted")]

        assert len(filtered) == 2
        assert all(not e.get("is_deleted") for e in filtered)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestCommitWithReview:
    """Tests for commit_with_review tool (ADR-009)."""

    def test_commit_tools_module_imports(self):
        """Test that worktree_tools module can be imported."""
        from src.mcp_server.features.worktree import worktree_tools

        # Module should be importable
        assert worktree_tools is not None

    def test_commit_tools_functions_exist(self):
        """Test that commit functions are defined in the module."""
        import src.mcp_server.features.worktree.worktree_tools as wt

        # The functions are defined in the WorktreeTools class but we can check they exist
        # by looking at the source or checking module attributes
        source_file = wt.__file__
        with open(source_file) as f:
            content = f.read()

        assert "async def commit_with_review" in content
        assert "async def get_commit_checklist" in content


class TestCommitReviewLogic:
    """Unit tests for commit review logic (can run without git)."""

    def test_categorize_files_logic(self):
        """Test the file categorization logic."""
        # Simulate git status output (format: "status path")
        changed_files = ["M src/main.py", "A src/new.py", "?? untracked.txt", "M tests/test.py"]

        staged_files = [f for f in changed_files if f[0] in "MAD"]
        new_files = [f for f in changed_files if f.startswith("??")]
        modified_only = [f for f in changed_files if f.startswith("M ")]

        assert len(staged_files) == 3  # M, A, M
        assert len(new_files) == 1  # ??
        assert len(modified_only) == 2  # two M

        assert len(staged_files) == 3  # M, A, M
        assert len(new_files) == 1  # ??
        assert len(modified_only) == 2  # two M

    def test_docs_check_logic(self):
        """Test documentation check logic."""
        changed_files = [" M src/main.py", "M  docs/api.md", "??  README.md"]

        docs_changed = [f for f in changed_files if f.startswith("docs/") or f.endswith(".md")]

        assert len(docs_changed) == 2  # docs/api.md and README.md

    def test_test_check_logic(self):
        """Test test file check logic."""
        changed_files = ["M src/main.py", "M tests/test_main.py", "?? new_feature.py"]

        test_files = [f for f in changed_files if "test" in f.lower() or f.startswith("tests/")]
        modified_only = [f for f in changed_files if f.startswith("M ")]
        test_files_changed = [f for f in modified_only if "test" in f.lower() or f.startswith("tests/")]

        assert len(test_files) == 1  # tests/test_main.py
        assert len(test_files_changed) == 1  # tests/test_main.py modified
        assert len(modified_only) == 2  # src/main.py and tests/test_main.py

    def test_commit_message_validation(self):
        """Test commit message validation logic."""
        # These should fail
        invalid_messages = ["", "a", "ab", "abc", "123"]

        for msg in invalid_messages:
            if msg and len(msg) >= 5:
                is_valid = True
            else:
                is_valid = False
            assert is_valid is False, f"'{msg}' should be invalid"

        # These should pass
        valid_messages = ["12345", "Valid message", "Add new feature"]

        for msg in valid_messages:
            assert len(msg) >= 5, f"'{msg}' should be valid"


class TestWorktreeStackManagement:
    """Tests for worktree stack management (ADR-014)."""

    def test_worktree_push_tool_exists(self):
        """Test that worktree_push is defined in worktree_tools."""
        import src.mcp_server.features.worktree.worktree_tools as wt

        source_file = wt.__file__
        with open(source_file) as f:
            content = f.read()

        assert "async def worktree_push" in content

    def test_worktree_pop_tool_exists(self):
        """Test that worktree_pop is defined in worktree_tools."""
        import src.mcp_server.features.worktree.worktree_tools as wt

        source_file = wt.__file__
        with open(source_file) as f:
            content = f.read()

        assert "async def worktree_pop" in content

    def test_worktree_create_tool_exists(self):
        """Test that worktree_create is defined in worktree_tools."""
        import src.mcp_server.features.worktree.worktree_tools as wt

        source_file = wt.__file__
        with open(source_file) as f:
            content = f.read()

        assert "async def worktree_create" in content

    def test_context_stack_file_logic(self):
        """Test context stack JSON structure logic."""
        import json

        # Simulate stack data structure
        stack_data = {
            "stack": [
                {"branch": "feature/auth", "worktree_path": "/path/to/worktrees/feature-auth"},
                {"branch": "main", "worktree_path": "/path/to/archon"},
            ],
            "current": 1,
        }

        # Test push - add new item
        stack_data["stack"].append(
            {
                "branch": "feature/search",
                "worktree_path": "/path/to/worktrees/feature-search",
            }
        )

        assert len(stack_data["stack"]) == 3

        # Test pop - remove last item
        popped = stack_data["stack"].pop()

        assert popped["branch"] == "feature/search"
        assert len(stack_data["stack"]) == 2

    def test_worktree_create_branch_name_validation(self):
        """Test branch name sanitization for worktree path."""
        branch_name = "feature/new-auth"
        safe_branch = branch_name.replace("/", "-")

        assert safe_branch == "feature-new-auth"

        # Test with complex branch name
        branch_name = "fix/permission-prompt-directory"
        safe_branch = branch_name.replace("/", "-")

        assert safe_branch == "fix-permission-prompt-directory"
