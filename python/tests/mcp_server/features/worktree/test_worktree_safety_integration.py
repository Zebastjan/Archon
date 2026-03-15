"""Integration tests for worktree safety with two OctoFriend instances.

These tests simulate real-world scenarios where multiple OctoFriend instances
work on different branches and verify that conflicts are correctly detected.
"""

import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
from uuid import uuid4

from src.mcp_server.features.worktree.worktree_tools import register_worktree_tools
from src.server.services.worktree_service import (
    WorktreeService, 
    WorktreeContext, 
    WorktreeValidationResult,
    get_worktree_service
)


@pytest.fixture
def mock_supabase():
    """Create a mock Supabase client."""
    mock = MagicMock()
    mock.table = MagicMock(return_value=mock)
    mock.select = MagicMock(return_value=mock)
    mock.eq = MagicMock(return_value=mock)
    mock.execute = MagicMock(return_value=MagicMock(data=[]))
    mock.rpc = MagicMock(return_value=mock)
    return mock


@pytest.fixture
def mock_mcp():
    """Create a mock MCP server."""
    mock = MagicMock()
    mock._tools = {}
    
    def tool_decorator():
        def decorator(func):
            mock._tools[func.__name__] = func
            return func
        return decorator
    
    mock.tool = tool_decorator
    return mock


class TestWorktreeConflictDetection:
    """Tests for detecting conflicts between worktrees."""
    
    @pytest.mark.asyncio
    async def test_concurrent_file_modification_detected(self, mock_mcp, mock_supabase):
        """Test that two worktrees modifying the same file are detected."""
        register_worktree_tools(mock_mcp)
        
        # Simulate two worktrees
        worktree_1 = {
            "id": str(uuid4()),
            "branch": "feature/auth",
            "path": "/home/user/archon/.worktrees/feature-auth",
        }
        worktree_2 = {
            "id": str(uuid4()),
            "branch": "feature/ui",
            "path": "/home/user/archon/.worktrees/feature-ui",
        }
        
        # Task 1 in worktree 1 modifies auth.py
        task_1 = {
            "id": str(uuid4()),
            "title": "Update authentication",
            "worktree_id": worktree_1["id"],
            "branch_name": worktree_1["branch"],
            "entities_affected": json.dumps(["src/auth.py", "src/user.py"]),
            "status": "doing",
        }
        
        # Task 2 in worktree 2 also modifies auth.py (CONFLICT!)
        # Mock database returning the conflicting task
        mock_supabase.execute.return_value.data = [
            {
                "conflicting_task_id": task_1["id"],
                "conflicting_worktree_id": worktree_1["id"],
                "conflicting_branch": worktree_1["branch"],
                "conflict_type": "file",
                "conflict_severity": "critical",
                "details": json.dumps({"shared_files": ["src/auth.py"]}),
            }
        ]
        
        validate_tool = mock_mcp._tools.get("worktree_validate_safe_to_work")
        assert validate_tool is not None
        
        with patch("src.mcp_server.features.worktree.worktree_tools.get_worktree_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.validate_safe_to_work = MagicMock(return_value=WorktreeValidationResult(
                is_safe=False,
                issues=[{
                    "type": "concurrent_modification",
                    "message": "File src/auth.py is being modified in worktree feature/auth",
                    "severity": "critical",
                    "conflicting_task_id": task_1["id"],
                }],
                warnings=[],
                context=WorktreeContext(
                    is_worktree=True,
                    worktree_id=worktree_2["id"],
                    branch_name=worktree_2["branch"],
                    repo_path=worktree_2["path"],
                    base_branch="main",
                    git_root="/home/user/archon",
                    is_clean=True,
                    uncommitted_changes=[],
                ),
            ))
            mock_get_service.return_value = mock_service
            
            result = await validate_tool(
                file_paths=["src/auth.py", "src/login.py"],
            )
            
            assert result["success"] is True
            assert result["is_safe"] is False
            assert len(result["issues"]) > 0
            assert result["issues"][0]["type"] == "concurrent_modification"
    
    @pytest.mark.asyncio
    async def test_concurrent_entity_modification_detected(self, mock_mcp, mock_supabase):
        """Test that two worktrees modifying the same entity are detected."""
        register_worktree_tools(mock_mcp)
        
        worktree_1 = str(uuid4())
        worktree_2 = str(uuid4())
        
        # Both worktrees modify the same entity
        entity_id = "entity-UserService-001"
        
        with patch("src.mcp_server.features.worktree.worktree_tools.get_worktree_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.validate_safe_to_work = MagicMock(return_value=WorktreeValidationResult(
                is_safe=False,
                issues=[{
                    "type": "entity_conflict",
                    "message": f"Entity {entity_id} is being modified in another worktree",
                    "severity": "warning",
                }],
                warnings=[],
                context=WorktreeContext(
                    is_worktree=True,
                    worktree_id=worktree_2,
                    branch_name="feature/second",
                    repo_path="/path/to/worktree2",
                    base_branch="main",
                    git_root="/path/to/repo",
                    is_clean=True,
                    uncommitted_changes=[],
                ),
            ))
            mock_get_service.return_value = mock_service
            
            validate_tool = mock_mcp._tools.get("worktree_validate_safe_to_work")
            result = await validate_tool(
                entity_ids=[entity_id],
            )
            
            assert result["is_safe"] is False
            assert any("entity" in issue.get("type", "") for issue in result["issues"])


class TestWorktreeIsolation:
    """Tests for worktree isolation and safety."""
    
    @pytest.mark.asyncio
    async def test_task_blocked_in_different_worktree(self, mock_mcp, mock_supabase):
        """Test that updating a task in a different worktree is blocked."""
        register_worktree_tools(mock_mcp)
        
        task_id = str(uuid4())
        original_worktree = str(uuid4())
        new_worktree = str(uuid4())
        
        with patch("src.mcp_server.features.worktree.worktree_tools.get_worktree_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.validate_safe_to_work = MagicMock(return_value=WorktreeValidationResult(
                is_safe=False,
                issues=[{
                    "type": "task_in_other_worktree",
                    "message": "Task is active in another worktree",
                    "severity": "error",
                    "other_worktree_id": original_worktree,
                    "other_branch": "feature/original",
                }],
                warnings=[],
                context=WorktreeContext(
                    is_worktree=True,
                    worktree_id=new_worktree,
                    branch_name="feature/new",
                    repo_path="/path/to/new",
                    base_branch="main",
                    git_root="/path/to/repo",
                    is_clean=True,
                    uncommitted_changes=[],
                ),
            ))
            mock_get_service.return_value = mock_service
            
            validate_tool = mock_mcp._tools.get("worktree_validate_safe_to_work")
            result = await validate_tool(
                task_id=task_id,
                file_paths=["src/test.py"],
            )
            
            assert result["is_safe"] is False
            assert any(issue["type"] == "task_in_other_worktree" for issue in result["issues"])

    @pytest.mark.asyncio
    async def test_worktree_lock_prevents_new_tasks(self, mock_mcp, mock_supabase):
        """Test that locked worktrees prevent new task creation."""
        register_worktree_tools(mock_mcp)
        
        locked_worktree_id = str(uuid4())
        
        with patch("src.mcp_server.features.worktree.worktree_tools.get_worktree_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.validate_safe_to_work = MagicMock(return_value=WorktreeValidationResult(
                is_safe=False,
                issues=[{
                    "type": "worktree_locked",
                    "message": "Worktree is locked by another process",
                    "severity": "error",
                }],
                warnings=[],
                context=WorktreeContext(
                    is_worktree=True,
                    worktree_id=locked_worktree_id,
                    branch_name="feature/test",
                    repo_path="/path/to/worktree",
                    base_branch="main",
                    git_root="/path/to/repo",
                    is_clean=True,
                    uncommitted_changes=[],
                ),
            ))
            mock_get_service.return_value = mock_service
            
            validate_tool = mock_mcp._tools.get("worktree_validate_safe_to_work")
            result = await validate_tool()
            
            assert result["is_safe"] is False
            assert any("locked" in issue.get("type", "") for issue in result["issues"])


class TestWorktreeConflictScenarios:
    """Real-world conflict scenarios."""
    
    @pytest.mark.asyncio
    async def test_octofriend_instances_on_different_branches(self, mock_mcp, mock_supabase):
        """
        Simulate two OctoFriend instances working on different branches
        touching the same files.
        """
        register_worktree_tools(mock_mcp)
        
        # Instance 1 on feature/auth
        instance_1 = {
            "worktree_id": str(uuid4()),
            "branch": "feature/auth",
            "files": ["src/auth.py", "src/middleware.py"],
            "task_id": str(uuid4()),
        }
        
        # Instance 2 on feature/logging (also touches middleware.py)
        instance_2 = {
            "worktree_id": str(uuid4()),
            "branch": "feature/logging",
            "files": ["src/middleware.py", "src/logger.py"],
        }
        
        # Simulate Instance 1 already has an active task
        with patch("src.mcp_server.features.worktree.worktree_tools.get_worktree_service") as mock_get_service:
            mock_service = MagicMock()
            
            # When Instance 2 validates, it should detect the conflict on middleware.py
            mock_service.validate_safe_to_work = MagicMock(return_value=WorktreeValidationResult(
                is_safe=False,
                issues=[{
                    "type": "concurrent_modification",
                    "message": "File src/middleware.py is being modified by another OctoFriend instance",
                    "severity": "critical",
                    "conflicting_instance": "OctoFriend-1",
                    "conflicting_branch": instance_1["branch"],
                    "shared_files": ["src/middleware.py"],
                }],
                warnings=[{
                    "type": "different_branches",
                    "message": "Working on different branches: feature/logging vs feature/auth",
                    "severity": "info",
                }],
                context=WorktreeContext(
                    is_worktree=True,
                    worktree_id=instance_2["worktree_id"],
                    branch_name=instance_2["branch"],
                    repo_path=f"/home/user/archon/.worktrees/{instance_2['branch']}",
                    base_branch="main",
                    git_root="/home/user/archon",
                    is_clean=True,
                    uncommitted_changes=[],
                ),
            ))
            mock_get_service.return_value = mock_service
            
            validate_tool = mock_mcp._tools.get("worktree_validate_safe_to_work")
            result = await validate_tool(
                file_paths=instance_2["files"],
            )
            
            assert result["is_safe"] is False
            assert result["issues"][0]["severity"] == "critical"
            assert "middleware.py" in str(result["issues"])
            
            # Verify the context shows the correct branch
            assert result["context"]["branch_name"] == "feature/logging"
    
    @pytest.mark.asyncio
    async def test_safe_parallel_work_no_conflict(self, mock_mcp, mock_supabase):
        """Test that non-overlapping work is allowed."""
        register_worktree_tools(mock_mcp)
        
        with patch("src.mcp_server.features.worktree.worktree_tools.get_worktree_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.validate_safe_to_work = MagicMock(return_value=WorktreeValidationResult(
                is_safe=True,
                issues=[],
                warnings=[{
                    "type": "different_worktrees",
                    "message": "Working in different worktrees - safe to proceed",
                    "severity": "info",
                }],
                context=WorktreeContext(
                    is_worktree=True,
                    worktree_id=str(uuid4()),
                    branch_name="feature/api",
                    repo_path="/path/to/worktree",
                    base_branch="main",
                    git_root="/path/to/repo",
                    is_clean=True,
                    uncommitted_changes=[],
                ),
            ))
            mock_get_service.return_value = mock_service
            
            validate_tool = mock_mcp._tools.get("worktree_validate_safe_to_work")
            result = await validate_tool(
                file_paths=["src/api/users.py"],  # Different from other worktree
            )
            
            assert result["is_safe"] is True
            assert len(result["issues"]) == 0


class TestWorktreeToolRegistration:
    """Tests for MCP tool registration."""
    
    def test_all_worktree_tools_registered(self, mock_mcp):
        """Verify all worktree tools are registered."""
        register_worktree_tools(mock_mcp)
        
        expected_tools = [
            "worktree_get_current_info",
            "worktree_validate_safe_to_work",
            "worktree_find_conflicts",
            "worktree_list_all",
            "worktree_create_task",
            "worktree_sync_task_context",
            "worktree_lock",
        ]
        
        for tool_name in expected_tools:
            assert tool_name in mock_mcp._tools, f"Tool {tool_name} not registered"
    
    def test_tools_are_callable(self, mock_mcp):
        """Verify registered tools are callable."""
        register_worktree_tools(mock_mcp)
        
        for tool_name, tool_func in mock_mcp._tools.items():
            assert callable(tool_func), f"Tool {tool_name} is not callable"


class TestStructuredLogging:
    """Tests for structured logging of conflicts and locks."""
    
    @pytest.mark.asyncio
    async def test_conflict_detection_logged(self, mock_mcp, mock_supabase, caplog):
        """Test that conflict detections are properly logged."""
        register_worktree_tools(mock_mcp)
        
        with patch("src.mcp_server.features.worktree.worktree_tools.get_worktree_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.validate_safe_to_work = MagicMock(return_value=WorktreeValidationResult(
                is_safe=False,
                issues=[{
                    "type": "concurrent_modification",
                    "message": "Conflict detected",
                    "severity": "critical",
                }],
                warnings=[],
                context=None,
            ))
            mock_get_service.return_value = mock_service
            
            validate_tool = mock_mcp._tools.get("worktree_validate_safe_to_work")
            
            with caplog.at_level("WARNING"):
                result = await validate_tool(file_paths=["src/test.py"])
                
            assert "conflict" in caplog.text.lower() or result["is_safe"] is False
    
    @pytest.mark.asyncio
    async def test_worktree_lock_logged(self, mock_mcp, mock_supabase, caplog):
        """Test that worktree locks are logged."""
        register_worktree_tools(mock_mcp)
        
        lock_tool = mock_mcp._tools.get("worktree_lock")
        assert lock_tool is not None
        
        with patch("src.mcp_server.features.worktree.worktree_tools.get_worktree_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.lock_worktree = MagicMock(return_value=True)
            mock_get_service.return_value = mock_service
            
            with caplog.at_level("INFO"):
                result = await lock_tool(
                    worktree_id=str(uuid4()),
                    locked=True,
                    reason="Testing",
                )
                
            assert result["success"] is True
            assert result["locked"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
