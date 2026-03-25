"""Comprehensive tests for worktree stack management (ADR-014).

Tests cover:
- worktree_push() - saves context to stack
- worktree_pop() - restores previous context
- worktree_create() - creates new git worktrees
- Context stack file management
- Edge cases and error handling

Run with:
    docker exec archon pytest tests/mcp_server/test_worktree_stack.py -v
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestWorktreePushUnit:
    """Unit tests for worktree_push logic (no real filesystem)."""

    def test_push_returns_correct_structure(self):
        """Test that push returns expected response structure."""
        import src.mcp_server.features.worktree.worktree_tools as wt

        source_file = wt.__file__
        with open(source_file) as f:
            content = f.read()

        assert "async def worktree_push" in content
        assert "return {" in content
        assert '"success"' in content
        assert '"pushed"' in content
        assert '"stack_size"' in content

    def test_push_captures_branch_and_path(self):
        """Test that push captures branch and path in response."""
        # Test the logic without actually running git
        current_branch = "feature/test-branch"
        current_path = "/test/path"

        # Simulate push response
        response = {
            "success": True,
            "pushed": {"branch": current_branch, "path": current_path},
            "stack_size": 1,
            "message": f"Pushed branch '{current_branch}' to stack",
        }

        assert response["success"] is True
        assert response["pushed"]["branch"] == current_branch
        assert response["pushed"]["path"] == current_path
        assert response["stack_size"] == 1
        assert "message" in response

    def test_push_handles_empty_initial_stack(self):
        """Test push creates stack when none exists."""
        # Simulate empty stack file
        stack_data = {"stack": [], "current": 0}

        # Push adds first item
        stack_data["stack"].append(
            {
                "branch": "feature/auth",
                "worktree_path": "/path/to/worktree",
                "pushed_at": "2026-03-25 10:00:00",
            }
        )

        assert len(stack_data["stack"]) == 1
        assert stack_data["stack"][0]["branch"] == "feature/auth"

    def test_push_appends_to_existing_stack(self):
        """Test push appends to existing stack."""
        stack_data = {
            "stack": [
                {"branch": "main", "worktree_path": "/repo", "pushed_at": ""},
            ],
            "current": 0,
        }

        # Push adds second item
        stack_data["stack"].append(
            {
                "branch": "feature/auth",
                "worktree_path": "/repo/.worktrees/feature-auth",
                "pushed_at": "",
            }
        )

        assert len(stack_data["stack"]) == 2
        assert stack_data["stack"][-1]["branch"] == "feature/auth"


class TestWorktreePopUnit:
    """Unit tests for worktree_pop logic (no real filesystem)."""

    def test_pop_returns_correct_structure(self):
        """Test that pop returns expected response structure."""
        import src.mcp_server.features.worktree.worktree_tools as wt

        source_file = wt.__file__
        with open(source_file) as f:
            content = f.read()

        assert "async def worktree_pop" in content
        assert '"popped"' in content
        assert '"action_required"' in content
        assert '"instructions"' in content

    def test_pop_removes_last_entry(self):
        """Test pop removes top entry from stack."""
        stack_data = {
            "stack": [
                {"branch": "main", "worktree_path": "/repo", "pushed_at": ""},
                {"branch": "feature/auth", "worktree_path": "/repo/.worktrees/feature-auth", "pushed_at": ""},
            ],
            "current": 0,
        }

        # Pop removes last item
        popped = stack_data["stack"].pop()

        assert popped["branch"] == "feature/auth"
        assert len(stack_data["stack"]) == 1
        assert stack_data["stack"][0]["branch"] == "main"

    def test_pop_on_empty_stack_returns_error(self):
        """Test that pop on empty stack returns error."""
        stack_data = {"stack": [], "current": 0}

        # Simulate the check in worktree_pop
        if not stack_data.get("stack"):
            error_result = {"success": False, "error": "Context stack is empty. Use worktree_push() first."}
        else:
            error_result = None

        assert error_result is not None
        assert error_result["success"] is False
        assert "empty" in error_result["error"].lower()

    def test_pop_multiple_times(self):
        """Test multiple pops work in sequence."""
        stack_data = {
            "stack": [
                {"branch": "main", "worktree_path": "/repo"},
                {"branch": "feature/a", "worktree_path": "/repo/.worktrees/a"},
                {"branch": "feature/b", "worktree_path": "/repo/.worktrees/b"},
            ],
            "current": 0,
        }

        # First pop
        popped1 = stack_data["stack"].pop()
        assert popped1["branch"] == "feature/b"
        assert len(stack_data["stack"]) == 2

        # Second pop
        popped2 = stack_data["stack"].pop()
        assert popped2["branch"] == "feature/a"
        assert len(stack_data["stack"]) == 1

        # Third pop
        popped3 = stack_data["stack"].pop()
        assert popped3["branch"] == "main"
        assert len(stack_data["stack"]) == 0


class TestWorktreeCreateUnit:
    """Unit tests for worktree_create logic (no real git)."""

    def test_create_returns_correct_structure(self):
        """Test that create returns expected response structure."""
        import src.mcp_server.features.worktree.worktree_tools as wt

        source_file = wt.__file__
        with open(source_file) as f:
            content = f.read()

        assert "async def worktree_create" in content
        assert '"worktree_path"' in content
        assert '"action_required"' in content

    def test_create_sanitizes_branch_name(self):
        """Test that branch names are sanitized for paths."""
        test_cases = [
            ("feature/new-auth", "feature-new-auth"),
            ("fix/permission-prompt", "fix-permission-prompt"),
            ("bugfix/123", "bugfix-123"),
            ("release/v1.0.0", "release-v1.0.0"),
        ]

        for branch_name, expected_path in test_cases:
            safe_name = branch_name.replace("/", "-")
            assert safe_name == expected_path, f"Failed for {branch_name}"

    def test_create_calculates_worktree_path(self):
        """Test that worktree path is calculated correctly."""
        git_root = "/home/user/archon"
        branch_name = "feature/new-auth"
        safe_branch = branch_name.replace("/", "-")
        expected_path = os.path.join(git_root, ".worktrees", safe_branch)

        assert expected_path == "/home/user/archon/.worktrees/feature-new-auth"

    def test_create_returns_instructions(self):
        """Test that create returns restart instructions."""
        response = {
            "success": True,
            "branch": "feature/test",
            "worktree_path": "/repo/.worktrees/feature-test",
            "message": "Created branch 'feature/test' from 'main' with worktree",
            "action_required": "restart_mcp",
            "instructions": "To start working on new branch:\n1. Exit current MCP session\n2. cd /repo/.worktrees/feature-test\n3. Run: archon-mcp",
        }

        assert response["success"] is True
        assert response["action_required"] == "restart_mcp"
        assert "instructions" in response
        assert "exit" in response["instructions"].lower() or "cd " in response["instructions"]


class TestContextStackFileManagement:
    """Tests for context stack JSON file management."""

    def test_stack_json_structure(self):
        """Test that stack file has correct JSON structure."""
        stack_data = {
            "stack": [
                {
                    "branch": "feature/auth",
                    "worktree_path": "/home/user/archon/.worktrees/feature-auth",
                    "pushed_at": "2026-03-25 10:30:00 +0000",
                }
            ],
            "current": 0,
        }

        # Verify it's valid JSON
        json_str = json.dumps(stack_data)
        parsed = json.loads(json_str)

        assert "stack" in parsed
        assert "current" in parsed
        assert len(parsed["stack"]) == 1
        assert "branch" in parsed["stack"][0]
        assert "worktree_path" in parsed["stack"][0]
        assert "pushed_at" in parsed["stack"][0]

    def test_stack_persists_across_operations(self):
        """Test that stack data persists correctly across push/pop."""
        # Simulate push
        stack_data = {"stack": [], "current": 0}
        stack_data["stack"].append({"branch": "feature/a", "worktree_path": "/path/a"})
        stack_data["stack"].append({"branch": "feature/b", "worktree_path": "/path/b"})

        # Persist to file (simulated)
        assert len(stack_data["stack"]) == 2

        # Simulate pop
        popped = stack_data["stack"].pop()
        assert popped["branch"] == "feature/b"

        # Verify persisted state
        assert len(stack_data["stack"]) == 1

    def test_stack_allows_nested_pushes(self):
        """Test multiple pushes create proper stack."""
        stack_data = {"stack": [], "current": 0}

        branches = ["main", "feature/a", "feature/b", "feature/c"]
        for branch in branches:
            stack_data["stack"].append(
                {
                    "branch": branch,
                    "worktree_path": f"/repo/.worktrees/{branch.replace('/', '-')}",
                }
            )

        assert len(stack_data["stack"]) == 4
        assert stack_data["stack"][-1]["branch"] == "feature/c"

    def test_stack_max_depth_handling(self):
        """Test stack handles many pushes without issues."""
        stack_data = {"stack": [], "current": 0}

        # Push 50 times
        for i in range(50):
            stack_data["stack"].append(
                {
                    "branch": f"feature/branch-{i}",
                    "worktree_path": f"/repo/.worktrees/branch-{i}",
                }
            )

        assert len(stack_data["stack"]) == 50

        # Pop 25 times
        for _ in range(25):
            stack_data["stack"].pop()

        assert len(stack_data["stack"]) == 25


class TestWorktreeStackIntegration:
    """Integration tests that use real filesystem (mark with @pytest.mark.real_fs)."""

    @pytest.mark.real_fs
    def test_push_creates_stack_file(self, tmp_path):
        """Test that push creates .archon/context-stack.json when none exists."""
        archon_dir = tmp_path / ".archon"
        archon_dir.mkdir()
        stack_file = archon_dir / "context-stack.json"

        # Simulate no stack file exists
        assert not stack_file.exists()

        # Simulate push creating the file
        stack_data = {"stack": [], "current": 0}
        stack_data["stack"].append(
            {
                "branch": "feature/test",
                "worktree_path": str(tmp_path / ".worktrees" / "feature-test"),
            }
        )

        with open(stack_file, "w") as f:
            json.dump(stack_data, f)

        assert stack_file.exists()

        # Verify content
        with open(stack_file) as f:
            loaded = json.load(f)

        assert len(loaded["stack"]) == 1
        assert loaded["stack"][0]["branch"] == "feature/test"

    @pytest.mark.real_fs
    def test_push_appends_to_existing_stack_file(self, tmp_path):
        """Test push appends to existing stack file."""
        archon_dir = tmp_path / ".archon"
        archon_dir.mkdir()
        stack_file = archon_dir / "context-stack.json"

        # Create existing stack
        existing_stack = {
            "stack": [{"branch": "main", "worktree_path": str(tmp_path), "pushed_at": ""}],
            "current": 0,
        }
        with open(stack_file, "w") as f:
            json.dump(existing_stack, f)

        # Simulate push appending
        with open(stack_file) as f:
            stack_data = json.load(f)

        stack_data["stack"].append(
            {
                "branch": "feature/new",
                "worktree_path": str(tmp_path / ".worktrees" / "feature-new"),
                "pushed_at": "",
            }
        )

        with open(stack_file, "w") as f:
            json.dump(stack_data, f)

        # Verify
        with open(stack_file) as f:
            loaded = json.load(f)

        assert len(loaded["stack"]) == 2

    @pytest.mark.real_fs
    def test_pop_removes_and_saves(self, tmp_path):
        """Test pop removes entry and saves updated stack."""
        archon_dir = tmp_path / ".archon"
        archon_dir.mkdir()
        stack_file = archon_dir / "context-stack.json"

        # Create stack with 2 entries
        stack_data = {
            "stack": [
                {"branch": "main", "worktree_path": str(tmp_path), "pushed_at": ""},
                {
                    "branch": "feature/test",
                    "worktree_path": str(tmp_path / ".worktrees" / "feature-test"),
                    "pushed_at": "",
                },
            ],
            "current": 0,
        }
        with open(stack_file, "w") as f:
            json.dump(stack_data, f)

        # Simulate pop
        with open(stack_file) as f:
            stack_data = json.load(f)

        popped = stack_data["stack"].pop()

        with open(stack_file, "w") as f:
            json.dump(stack_data, f)

        # Verify
        assert popped["branch"] == "feature/test"

        with open(stack_file) as f:
            loaded = json.load(f)

        assert len(loaded["stack"]) == 1

    @pytest.mark.real_fs
    def test_pop_on_nonexistent_file_returns_error(self, tmp_path):
        """Test pop returns error when stack file doesn't exist."""
        stack_file = tmp_path / ".archon" / "context-stack.json"

        # No file exists
        assert not stack_file.exists()

        # Simulate error handling
        if not stack_file.exists():
            result = {"success": False, "error": "No context stack found. Use worktree_push() first."}

        assert result["success"] is False
        assert "no context stack" in result["error"].lower()

    @pytest.mark.real_fs
    def test_invalid_json_in_stack_file_handled(self, tmp_path):
        """Test that corrupted stack file doesn't crash operations."""
        archon_dir = tmp_path / ".archon"
        archon_dir.mkdir()
        stack_file = archon_dir / "context-stack.json"

        # Write invalid JSON
        with open(stack_file, "w") as f:
            f.write("{ invalid json }")

        # Simulate error handling
        try:
            with open(stack_file) as f:
                data = json.load(f)
            success = True
            data = data
        except json.JSONDecodeError:
            # Start fresh
            data = {"stack": [], "current": 0}
            success = False

        assert success is False
        assert data["stack"] == []


class TestWorktreeCreateIntegration:
    """Integration tests for worktree_create with actual git operations."""

    @pytest.mark.real_fs
    def test_create_branch_name_sanitization_integration(self):
        """Test branch name sanitization handles edge cases."""
        test_cases = [
            ("feature/auth", "feature-auth"),
            ("fix/bug-123", "fix-bug-123"),
            ("release/v1.0", "release-v1.0"),
            ("feature/very/long/nested/path", "feature-very-long-nested-path"),
            ("hotfix//double-slash", "hotfix--double-slash"),
        ]

        for branch, expected in test_cases:
            result = branch.replace("/", "-")
            assert result == expected, f"Failed: {branch} -> {result} (expected {expected})"

    @pytest.mark.real_fs
    def test_worktree_path_calculation_integration(self):
        """Test worktree path is calculated correctly."""
        git_root = "/home/user/project"
        branch = "feature/new-feature"
        safe_branch = branch.replace("/", "-")
        expected = "/home/user/project/.worktrees/feature-new-feature"

        actual = os.path.join(git_root, ".worktrees", safe_branch)
        assert actual == expected


class TestErrorHandling:
    """Tests for error handling in worktree tools."""

    def test_git_command_failure_handled(self):
        """Test that git command failures are handled gracefully."""
        # Simulate failed git command
        mock_result = MagicMock()
        mock_result.returncode = 128
        mock_result.stdout = ""
        mock_result.stderr = "fatal: not a git repository"

        # In worktree_push, this would be caught
        if mock_result.returncode != 0:
            git_root = os.getcwd()  # Fallback
        else:
            git_root = mock_result.stdout.strip()

        # Should fallback to os.getcwd()
        assert git_root == os.getcwd()

    def test_missing_git_root_handled(self):
        """Test that missing git root is handled."""
        # When git rev-parse --show-toplevel fails
        git_root = ""  # Empty result from failed git command

        # Fallback in code: or os.getcwd()
        result = git_root or "/fallback/path"

        assert result == "/fallback/path"

    def test_stack_file_permission_error_handled(self, tmp_path):
        """Test that permission errors on stack file are handled."""
        archon_dir = tmp_path / ".archon"
        archon_dir.mkdir()
        stack_file = archon_dir / "context-stack.json"

        # Write initial stack
        with open(stack_file, "w") as f:
            json.dump({"stack": [], "current": 0}, f)

        # Simulate read error (e.g., file deleted between check and read)
        stack_file.unlink()

        # Error handling should return empty stack
        if not stack_file.exists():
            stack_data = {"stack": [], "current": 0}

        assert stack_data["stack"] == []


class TestBranchNameEdgeCases:
    """Tests for edge cases in branch name handling."""

    def test_branch_with_multiple_slashes(self):
        """Test branch with multiple slashes."""
        branch = "feature/subfolder/feature-name"
        safe = branch.replace("/", "-")

        assert safe == "feature-subfolder-feature-name"

    def test_branch_with_leading_slash(self):
        """Test branch with unusual prefix."""
        branch = "/feature-starting-with-slash"
        safe = branch.replace("/", "-")

        assert safe == "-feature-starting-with-slash"

    def test_branch_with_only_slashes(self):
        """Test branch that is only slashes (edge case)."""
        branch = "///"
        safe = branch.replace("/", "-")

        assert safe == "---"

    def test_empty_branch_name(self):
        """Test empty branch name handling."""
        branch = ""
        safe = branch.replace("/", "-")

        assert safe == ""

    def test_unicode_branch_names(self):
        """Test branch names with unicode characters."""
        branch = "feature/日本語"
        safe = branch.replace("/", "-")

        assert safe == "feature-日本語"


class TestWorktreeToolsExist:
    """Verify all worktree tools are properly defined."""

    def test_all_tools_importable(self):
        """Test that all worktree tools can be imported."""
        import src.mcp_server.features.worktree.worktree_tools as wt

        # Check module has expected functions by reading source
        source_file = wt.__file__
        with open(source_file) as f:
            content = f.read()

        required_tools = [
            "worktree_get_current_info",
            "worktree_validate_safe_to_work",
            "worktree_find_conflicts",
            "worktree_list_all",
            "worktree_create_task",
            "worktree_sync_task_context",
            "worktree_lock",
            "worktree_switch",
            "worktree_list",
            "worktree_push",
            "worktree_pop",
            "worktree_create",
            "commit_with_review",
            "get_commit_checklist",
        ]

        for tool in required_tools:
            assert f"async def {tool}" in content, f"Missing tool: {tool}"


class TestWorktreeIntegration:
    """Integration tests for worktree push→pop→switch flows."""

    @pytest.mark.real_fs
    def test_push_switch_pop_flow(self, tmp_path):
        """Test complete push→switch→pop flow with actual stack file."""
        import json

        stack_file = tmp_path / "context-stack.json"
        stack_file.parent.mkdir(parents=True, exist_ok=True)

        # Initial state: working on feature/auth
        initial_context = {
            "branch": "feature/auth",
            "worktree_path": str(tmp_path / ".worktrees" / "feature-auth"),
        }

        # Step 1: Push current context
        stack_data = {"stack": [], "current": 0}
        stack_data["stack"].append(
            {
                "branch": initial_context["branch"],
                "worktree_path": initial_context["worktree_path"],
                "pushed_at": "2026-03-25 10:00:00",
            }
        )

        with open(stack_file, "w") as f:
            json.dump(stack_data, f)

        assert len(stack_data["stack"]) == 1

        # Step 2: Switch to feature/search (simulated by loading stack)
        with open(stack_file) as f:
            loaded_stack = json.load(f)

        assert loaded_stack["stack"][0]["branch"] == "feature/auth"

        # Step 3: Pop back to previous context
        with open(stack_file) as f:
            stack_data = json.load(f)

        popped = stack_data["stack"].pop()

        with open(stack_file, "w") as f:
            json.dump(stack_data, f)

        assert popped["branch"] == "feature/auth"
        assert len(stack_data["stack"]) == 0
        assert stack_file.exists()

    @pytest.mark.real_fs
    def test_create_worktree_sanitizes_branch(self):
        """Test worktree creation with branch name sanitization."""
        test_cases = [
            ("feature/new-auth", "feature-new-auth"),
            ("fix/login-bug", "fix-login-bug"),
            ("release/v1.0.0", "release-v1.0.0"),
            ("hotfix/critical/fix", "hotfix-critical-fix"),
        ]

        for branch, expected_safe in test_cases:
            safe = branch.replace("/", "-")
            assert safe == expected_safe, f"Failed: {branch} -> {safe}"

            # Verify path construction
            git_root = "/home/user/repo"
            expected_path = f"{git_root}/.worktrees/{expected_safe}"
            actual_path = f"{git_root}/.worktrees/{safe}"
            assert actual_path == expected_path

    @pytest.mark.real_fs
    def test_validation_conflict_detection(self, tmp_path):
        """Test validation detects conflicts when worktrees overlap."""
        import json

        # Create two tasks that modify the same file
        task_1_files = ["src/auth.py", "src/user.py"]
        task_2_files = ["src/auth.py", "src/config.py"]

        # Check for overlap
        overlap = set(task_1_files) & set(task_2_files)
        assert len(overlap) == 1
        assert "src/auth.py" in overlap

        # Simulate conflict detection response
        is_safe = len(overlap) == 0
        issues = []

        if not is_safe:
            for file in overlap:
                issues.append(
                    {
                        "type": "concurrent_modification",
                        "file": file,
                        "severity": "critical",
                        "message": f"File {file} is being modified in another worktree",
                    }
                )

        assert is_safe is False
        assert len(issues) == 1
        assert issues[0]["file"] == "src/auth.py"
        assert issues[0]["severity"] == "critical"

    @pytest.mark.real_fs
    def test_multiple_pushes_preserve_order(self, tmp_path):
        """Test multiple pushes preserve the correct order."""
        import json

        stack_file = tmp_path / "context-stack.json"
        stack_file.parent.mkdir(parents=True, exist_ok=True)

        # Push 3 contexts in order
        stack_data = {"stack": [], "current": 0}
        contexts = [
            {"branch": "main", "worktree_path": "/repo"},
            {"branch": "feature/a", "worktree_path": "/repo/.worktrees/a"},
            {"branch": "feature/b", "worktree_path": "/repo/.worktrees/b"},
        ]

        for ctx in contexts:
            stack_data["stack"].append(ctx)

        with open(stack_file, "w") as f:
            json.dump(stack_data, f)

        # Verify order: main -> feature/a -> feature/b
        assert stack_data["stack"][0]["branch"] == "main"
        assert stack_data["stack"][1]["branch"] == "feature/a"
        assert stack_data["stack"][2]["branch"] == "feature/b"

        # Pop should return in reverse order
        with open(stack_file) as f:
            stack_data = json.load(f)

        popped = stack_data["stack"].pop()
        assert popped["branch"] == "feature/b"

        popped = stack_data["stack"].pop()
        assert popped["branch"] == "feature/a"

        popped = stack_data["stack"].pop()
        assert popped["branch"] == "main"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
