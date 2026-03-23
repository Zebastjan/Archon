"""Unit tests for task management tools.

These tests mock the TaskService directly since the tools now use
direct service imports instead of HTTP calls.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.server.fastmcp import Context

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_mcp():
    """Create a mock MCP server for testing."""
    mock = MagicMock()
    mock._tools = {}

    def tool_decorator():
        def decorator(func):
            mock._tools[func.__name__] = func
            return func
        return decorator
    mock.tool = tool_decorator
    return mock


@pytest.fixture
def mock_context():
    """Create a mock context for testing."""
    return MagicMock(spec=Context)


def setup_task_service_mocks(mock_task_service, mock_worktree_service):
    """Helper to set up common service mocks."""
    # Mock worktree validation to pass by default
    mock_validation = MagicMock()
    mock_validation.is_safe = True
    mock_validation.issues = []
    mock_validation.warnings = []
    mock_worktree_service.return_value.validate_safe_to_work = AsyncMock(return_value=mock_validation)
    
    return mock_task_service, mock_worktree_service


@pytest.mark.asyncio
async def test_create_task_with_sources(mock_mcp, mock_context):
    """Test creating a task using manage_task."""
    from src.mcp_server.features.tasks.task_tools import register_task_tools

    mock_task = {
        "id": "task-123",
        "title": "Implement OAuth2",
        "description": "Add OAuth2 authentication",
        "assignee": "AI IDE Agent",
        "status": "todo",
    }

    with patch("src.mcp_server.features.tasks.task_tools.TaskService") as MockTaskService:
        with patch("src.mcp_server.features.tasks.task_tools.get_worktree_service") as MockWorktreeService:
            mock_service = MagicMock()
            mock_service.create_task = AsyncMock(return_value=(True, {"task": mock_task}))
            MockTaskService.return_value = mock_service
            
            # Setup worktree validation
            mock_worktree = MagicMock()
            mock_validation = MagicMock()
            mock_validation.is_safe = True
            mock_worktree.validate_safe_to_work = AsyncMock(return_value=mock_validation)
            MockWorktreeService.return_value = mock_worktree

            register_task_tools(mock_mcp)
            manage_task = mock_mcp._tools.get("manage_task")
            assert manage_task is not None

            result = await manage_task(
                mock_context,
                action="create",
                project_id="project-123",
                title="Implement OAuth2",
                description="Add OAuth2 authentication",
                assignee="AI IDE Agent",
            )

            result_data = json.loads(result)
            assert result_data["success"] is True
            assert result_data["task_id"] == "task-123"
            assert result_data["task"]["title"] == "Implement OAuth2"


@pytest.mark.asyncio
async def test_find_tasks_with_project_filter(mock_mcp, mock_context):
    """Test listing tasks with project filter."""
    from src.mcp_server.features.tasks.task_tools import register_task_tools

    mock_tasks = [
        {"id": "task-1", "title": "Task 1", "status": "todo"},
        {"id": "task-2", "title": "Task 2", "status": "doing"},
    ]

    with patch("src.mcp_server.features.tasks.task_tools.TaskService") as MockTaskService:
        mock_service = MagicMock()
        mock_service.list_tasks = AsyncMock(return_value=(True, {"tasks": mock_tasks, "total_count": 2}))
        MockTaskService.return_value = mock_service

        register_task_tools(mock_mcp)
        find_tasks = mock_mcp._tools.get("find_tasks")
        assert find_tasks is not None

        result = await find_tasks(mock_context, filter_by="project", filter_value="project-123")

        result_data = json.loads(result)
        assert result_data["success"] is True
        assert len(result_data["tasks"]) == 2
        assert result_data["total_count"] == 2


@pytest.mark.asyncio
async def test_find_tasks_with_status_filter(mock_mcp, mock_context):
    """Test listing tasks with status filter."""
    from src.mcp_server.features.tasks.task_tools import register_task_tools

    mock_tasks = [{"id": "task-1", "title": "Task 1", "status": "todo"}]

    with patch("src.mcp_server.features.tasks.task_tools.TaskService") as MockTaskService:
        mock_service = MagicMock()
        mock_service.list_tasks = AsyncMock(return_value=(True, {"tasks": mock_tasks, "total_count": 1}))
        MockTaskService.return_value = mock_service

        register_task_tools(mock_mcp)
        find_tasks = mock_mcp._tools.get("find_tasks")

        result = await find_tasks(
            mock_context, filter_by="status", filter_value="todo", project_id="project-123"
        )

        result_data = json.loads(result)
        assert result_data["success"] is True
        assert len(result_data["tasks"]) == 1


@pytest.mark.asyncio
async def test_update_task_status(mock_mcp, mock_context):
    """Test updating task status."""
    from src.mcp_server.features.tasks.task_tools import register_task_tools

    mock_task = {
        "id": "task-123",
        "title": "Test Task",
        "status": "doing",
        "assignee": "User",
    }

    with patch("src.mcp_server.features.tasks.task_tools.TaskService") as MockTaskService:
        with patch("src.mcp_server.features.tasks.task_tools.get_worktree_service") as MockWorktreeService:
            mock_service = MagicMock()
            mock_service.update_task = AsyncMock(return_value=(True, {"task": mock_task}))
            MockTaskService.return_value = mock_service
            
            mock_worktree = MagicMock()
            mock_validation = MagicMock()
            mock_validation.is_safe = True
            mock_worktree.validate_safe_to_work = AsyncMock(return_value=mock_validation)
            MockWorktreeService.return_value = mock_worktree

            register_task_tools(mock_mcp)
            manage_task = mock_mcp._tools.get("manage_task")

            result = await manage_task(
                mock_context, action="update", task_id="task-123", status="doing", assignee="User"
            )

            result_data = json.loads(result)
            assert result_data["success"] is True
            assert "Task updated successfully" in result_data["message"]


@pytest.mark.asyncio
async def test_update_task_no_fields(mock_mcp, mock_context):
    """Test updating task with no fields returns validation error."""
    from src.mcp_server.features.tasks.task_tools import register_task_tools

    register_task_tools(mock_mcp)
    manage_task = mock_mcp._tools.get("manage_task")

    result = await manage_task(mock_context, action="update", task_id="task-123")

    result_data = json.loads(result)
    assert result_data["success"] is False
    assert result_data["error"]["type"] == "validation_error"
    assert "No fields to update" in result_data["error"]["message"]


@pytest.mark.asyncio
async def test_delete_task_success(mock_mcp, mock_context):
    """Test deleting (archiving) a task."""
    from src.mcp_server.features.tasks.task_tools import register_task_tools

    with patch("src.mcp_server.features.tasks.task_tools.TaskService") as MockTaskService:
        mock_service = MagicMock()
        mock_service.archive_task = AsyncMock(return_value=(True, {"message": "Task archived successfully"}))
        MockTaskService.return_value = mock_service

        register_task_tools(mock_mcp)
        manage_task = mock_mcp._tools.get("manage_task")

        result = await manage_task(mock_context, action="delete", task_id="task-123")

        result_data = json.loads(result)
        assert result_data["success"] is True
        assert "deleted" in result_data["message"].lower() or "archived" in result_data["message"].lower()


@pytest.mark.asyncio
async def test_get_task_by_id(mock_mcp, mock_context):
    """Test getting a specific task by ID."""
    from src.mcp_server.features.tasks.task_tools import register_task_tools

    mock_task = {
        "id": "task-123",
        "title": "Test Task",
        "status": "doing",
        "description": "Task description",
        "assignee": "User",
    }

    with patch("src.mcp_server.features.tasks.task_tools.TaskService") as MockTaskService:
        mock_service = MagicMock()
        mock_service.get_task = AsyncMock(return_value=(True, {"task": mock_task}))
        MockTaskService.return_value = mock_service

        register_task_tools(mock_mcp)
        find_tasks = mock_mcp._tools.get("find_tasks")

        result = await find_tasks(mock_context, task_id="task-123")

        result_data = json.loads(result)
        assert result_data["success"] is True
        assert result_data["task"]["id"] == "task-123"


@pytest.mark.asyncio
async def test_task_search_query(mock_mcp, mock_context):
    """Test searching tasks with query."""
    from src.mcp_server.features.tasks.task_tools import register_task_tools

    mock_tasks = [
        {"id": "task-1", "title": "Auth task", "description": "Authentication"},
    ]

    with patch("src.mcp_server.features.tasks.task_tools.TaskService") as MockTaskService:
        mock_service = MagicMock()
        mock_service.list_tasks = AsyncMock(return_value=(True, {"tasks": mock_tasks, "total_count": 1}))
        MockTaskService.return_value = mock_service

        register_task_tools(mock_mcp)
        find_tasks = mock_mcp._tools.get("find_tasks")

        result = await find_tasks(mock_context, query="auth")

        result_data = json.loads(result)
        assert result_data["success"] is True
        assert result_data["query"] == "auth"


@pytest.mark.asyncio
async def test_worktree_validation_blocks_unsafe_task(mock_mcp, mock_context):
    """Test that worktree validation blocks unsafe task operations."""
    from src.mcp_server.features.tasks.task_tools import register_task_tools

    with patch("src.mcp_server.features.tasks.task_tools.TaskService"):
        with patch("src.mcp_server.features.tasks.task_tools.get_worktree_service") as MockWorktreeService:
            mock_worktree = MagicMock()
            mock_validation = MagicMock()
            mock_validation.is_safe = False
            mock_validation.issues = [{"message": "File is being modified in another worktree"}]
            mock_validation.warnings = []
            mock_worktree.validate_safe_to_work = AsyncMock(return_value=mock_validation)
            MockWorktreeService.return_value = mock_worktree

            register_task_tools(mock_mcp)
            manage_task = mock_mcp._tools.get("manage_task")

            result = await manage_task(
                mock_context,
                action="create",
                project_id="project-123",
                title="Test Task",
                file_paths=["src/main.py"],
            )

            result_data = json.loads(result)
            assert result_data["success"] is False
            assert result_data["error_type"] == "worktree_conflict"
            assert "Worktree safety validation failed" in result_data["error"]
