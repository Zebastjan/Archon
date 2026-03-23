"""Unit tests for project management tools.

These tests mock the ProjectService directly since the tools now use
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
    # Store registered tools
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


@pytest.mark.asyncio
async def test_create_project_success(mock_mcp, mock_context):
    """Test successful project creation."""
    from src.mcp_server.features.projects.project_tools import register_project_tools

    mock_project = {
        "id": "project-123",
        "title": "Test Project",
        "github_repo": "https://github.com/test/repo",
        "created_at": "2024-01-01T00:00:00",
    }

    # Patch ProjectService before registering tools
    with patch("src.mcp_server.features.projects.project_tools.ProjectService") as MockService:
        mock_service = MagicMock()
        mock_service.create_project = AsyncMock(return_value=(True, {"project": mock_project}))
        MockService.return_value = mock_service

        register_project_tools(mock_mcp)
        manage_project = mock_mcp._tools.get("manage_project")
        assert manage_project is not None, "manage_project tool not registered"

        result = await manage_project(
            mock_context,
            action="create",
            title="Test Project",
            description="A test project",
            github_repo="https://github.com/test/repo",
        )

        result_data = json.loads(result)
        assert result_data["success"] is True
        assert result_data["project"]["id"] == "project-123"
        assert result_data["project_id"] == "project-123"
        assert "Project created successfully" in result_data["message"]


@pytest.mark.asyncio
async def test_create_project_validation_error(mock_mcp, mock_context):
    """Test project creation with missing title."""
    from src.mcp_server.features.projects.project_tools import register_project_tools

    register_project_tools(mock_mcp)
    manage_project = mock_mcp._tools.get("manage_project")

    # Test without title - should fail validation
    result = await manage_project(
        mock_context,
        action="create",
        title="",
        description="A test project",
    )

    result_data = json.loads(result)
    assert result_data["success"] is False
    assert "title required" in result_data["error"]["message"].lower()


@pytest.mark.asyncio
async def test_find_projects_success(mock_mcp, mock_context):
    """Test listing projects."""
    from src.mcp_server.features.projects.project_tools import register_project_tools

    mock_projects = [
        {"id": "proj-1", "title": "Project 1", "created_at": "2024-01-01"},
        {"id": "proj-2", "title": "Project 2", "created_at": "2024-01-02"},
    ]

    with patch("src.mcp_server.features.projects.project_tools.ProjectService") as MockService:
        mock_service = MagicMock()
        mock_service.list_projects = AsyncMock(return_value=(True, {"projects": mock_projects, "total_count": 2}))
        MockService.return_value = mock_service

        register_project_tools(mock_mcp)
        find_projects = mock_mcp._tools.get("find_projects")
        assert find_projects is not None, "find_projects tool not registered"

        result = await find_projects(mock_context)

        result_data = json.loads(result)
        assert result_data["success"] is True
        assert len(result_data["projects"]) == 2
        assert result_data["total"] == 2


@pytest.mark.asyncio
async def test_get_project_by_id_success(mock_mcp, mock_context):
    """Test getting a specific project by ID."""
    from src.mcp_server.features.projects.project_tools import register_project_tools

    mock_project = {
        "id": "proj-123",
        "title": "Test Project",
        "description": "Test description",
        "features": [],
        "created_at": "2024-01-01",
    }

    with patch("src.mcp_server.features.projects.project_tools.ProjectService") as MockService:
        mock_service = MagicMock()
        mock_service.get_project = AsyncMock(return_value=(True, {"project": mock_project}))
        MockService.return_value = mock_service

        register_project_tools(mock_mcp)
        find_projects = mock_mcp._tools.get("find_projects")

        result = await find_projects(mock_context, project_id="proj-123")

        result_data = json.loads(result)
        assert result_data["success"] is True
        assert result_data["project"]["id"] == "proj-123"


@pytest.mark.asyncio
async def test_get_project_not_found(mock_mcp, mock_context):
    """Test getting a non-existent project."""
    from src.mcp_server.features.projects.project_tools import register_project_tools

    with patch("src.mcp_server.features.projects.project_tools.ProjectService") as MockService:
        mock_service = MagicMock()
        mock_service.get_project = AsyncMock(return_value=(False, {"error": "Project not found"}))
        MockService.return_value = mock_service

        register_project_tools(mock_mcp)
        find_projects = mock_mcp._tools.get("find_projects")

        result = await find_projects(mock_context, project_id="non-existent")

        result_data = json.loads(result)
        assert result_data["success"] is False
        assert "error" in result_data
        assert isinstance(result_data["error"], dict)
        assert result_data["error"]["type"] == "not_found"


@pytest.mark.asyncio
async def test_update_project_success(mock_mcp, mock_context):
    """Test updating a project."""
    from src.mcp_server.features.projects.project_tools import register_project_tools

    mock_project = {
        "id": "proj-123",
        "title": "Updated Title",
        "description": "Updated description",
    }

    with patch("src.mcp_server.features.projects.project_tools.ProjectService") as MockService:
        mock_service = MagicMock()
        mock_service.update_project = AsyncMock(return_value=(True, {"project": mock_project}))
        MockService.return_value = mock_service

        register_project_tools(mock_mcp)
        manage_project = mock_mcp._tools.get("manage_project")

        result = await manage_project(
            mock_context,
            action="update",
            project_id="proj-123",
            title="Updated Title",
            description="Updated description",
        )

        result_data = json.loads(result)
        assert result_data["success"] is True
        assert "Project updated successfully" in result_data["message"]


@pytest.mark.asyncio
async def test_delete_project_success(mock_mcp, mock_context):
    """Test deleting a project."""
    from src.mcp_server.features.projects.project_tools import register_project_tools

    with patch("src.mcp_server.features.projects.project_tools.ProjectService") as MockService:
        mock_service = MagicMock()
        mock_service.delete_project = AsyncMock(return_value=(True, {"message": "Project deleted"}))
        MockService.return_value = mock_service

        register_project_tools(mock_mcp)
        manage_project = mock_mcp._tools.get("manage_project")

        result = await manage_project(
            mock_context,
            action="delete",
            project_id="proj-123",
        )

        result_data = json.loads(result)
        assert result_data["success"] is True
        assert "deleted" in result_data["message"].lower()


@pytest.mark.asyncio
async def test_project_search_filter(mock_mcp, mock_context):
    """Test searching projects with query filter."""
    from src.mcp_server.features.projects.project_tools import register_project_tools

    mock_projects = [
        {"id": "proj-1", "title": "Auth Project", "description": "Authentication"},
    ]

    with patch("src.mcp_server.features.projects.project_tools.ProjectService") as MockService:
        mock_service = MagicMock()
        mock_service.list_projects = AsyncMock(return_value=(True, {"projects": mock_projects, "total_count": 1}))
        MockService.return_value = mock_service

        register_project_tools(mock_mcp)
        find_projects = mock_mcp._tools.get("find_projects")

        result = await find_projects(mock_context, query="auth")

        result_data = json.loads(result)
        assert result_data["success"] is True
        assert result_data["query"] == "auth"


@pytest.mark.asyncio
async def test_invalid_action(mock_mcp, mock_context):
    """Test manage_project with invalid action."""
    from src.mcp_server.features.projects.project_tools import register_project_tools

    register_project_tools(mock_mcp)
    manage_project = mock_mcp._tools.get("manage_project")

    result = await manage_project(
        mock_context,
        action="invalid_action",
        project_id="proj-123",
    )

    result_data = json.loads(result)
    assert result_data["success"] is False
    assert result_data["error"]["type"] == "invalid_action"
