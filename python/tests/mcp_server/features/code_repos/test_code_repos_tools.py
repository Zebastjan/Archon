"""Unit tests for code repository management tools.

These tests mock the HTTP calls since code_repos tools use external API calls.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.server.fastmcp import Context

pytestmark = pytest.mark.unit

from src.mcp_server.features.code_repos.code_repos_tools import register_code_repos_tools


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


class TestCodeReposToolsRegistration:
    """Tests for code repos tool registration."""

    def test_all_code_repos_tools_registered(self, mock_mcp):
        """Verify all code repos tools are registered."""
        register_code_repos_tools(mock_mcp)

        expected_tools = [
            "code_repos_create_and_index",
            "code_repos_get_status",
            "code_repos_list",
        ]

        for tool_name in expected_tools:
            assert tool_name in mock_mcp._tools, f"Tool {tool_name} not registered"

    def test_tools_are_callable(self, mock_mcp):
        """Verify registered tools are callable."""
        register_code_repos_tools(mock_mcp)

        for tool_name, tool_func in mock_mcp._tools.items():
            assert callable(tool_func), f"Tool {tool_name} is not callable"


class TestCodeReposCreateAndIndex:
    """Tests for code_repos_create_and_index tool."""

    @pytest.mark.asyncio
    async def test_create_and_index_success(self, mock_mcp, mock_context):
        """Test successful repository creation and indexing."""
        register_code_repos_tools(mock_mcp)
        tool = mock_mcp._tools["code_repos_create_and_index"]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "repo_id": "550e8400-e29b-41d4-a716-446655440000",
            "name": "TestRepo",
            "status": "queued",
            "entities_count": 0,
            "existing": False,
            "error_message": None,
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await tool(
                ctx=mock_context,
                name="TestRepo",
                local_path="/home/user/test-repo",
            )

        result_data = json.loads(result)
        assert result_data["success"] is True
        assert result_data["repo_id"] == "550e8400-e29b-41d4-a716-446655440000"
        assert result_data["status"] == "queued"

    @pytest.mark.asyncio
    async def test_create_and_index_path_not_found(self, mock_mcp, mock_context):
        """Test repository creation with non-existent path."""
        register_code_repos_tools(mock_mcp)
        tool = mock_mcp._tools["code_repos_create_and_index"]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "repo_id": None,
            "status": "error",
            "error_message": "Path not found: /nonexistent/path",
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await tool(
                ctx=mock_context,
                name="TestRepo",
                local_path="/nonexistent/path",
            )

        result_data = json.loads(result)
        assert result_data["status"] == "error"
        assert "Path not found" in result_data["error_message"]

    @pytest.mark.asyncio
    async def test_create_and_index_not_git_repo(self, mock_mcp, mock_context):
        """Test repository creation with non-git directory."""
        register_code_repos_tools(mock_mcp)
        tool = mock_mcp._tools["code_repos_create_and_index"]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "repo_id": None,
            "status": "error",
            "error_message": "Not a git repository",
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await tool(
                ctx=mock_context,
                name="NotGit",
                local_path="/home/user/not-git",
            )

        result_data = json.loads(result)
        assert result_data["status"] == "error"
        assert "Not a git repository" in result_data["error_message"]

    @pytest.mark.asyncio
    async def test_create_and_index_with_github_url(self, mock_mcp, mock_context):
        """Test repository creation with GitHub URL."""
        register_code_repos_tools(mock_mcp)
        tool = mock_mcp._tools["code_repos_create_and_index"]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "repo_id": "550e8400-e29b-41d4-a716-446655440000",
            "name": "TestRepo",
            "status": "queued",
            "entities_count": 0,
            "existing": False,
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await tool(
                ctx=mock_context,
                name="TestRepo",
                local_path="/home/user/test-repo",
                github_url="https://github.com/user/test-repo",
            )

        result_data = json.loads(result)
        assert result_data["success"] is True

    @pytest.mark.asyncio
    async def test_create_and_index_http_error(self, mock_mcp, mock_context):
        """Test repository creation with HTTP error."""
        register_code_repos_tools(mock_mcp)
        tool = mock_mcp._tools["code_repos_create_and_index"]

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await tool(
                ctx=mock_context,
                name="TestRepo",
                local_path="/home/user/test-repo",
            )

        assert "error" in result.lower()


class TestCodeReposGetStatus:
    """Tests for code_repos_get_status tool."""

    @pytest.mark.asyncio
    async def test_get_status_success(self, mock_mcp, mock_context):
        """Test successful status retrieval."""
        register_code_repos_tools(mock_mcp)
        tool = mock_mcp._tools["code_repos_get_status"]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "repo_id": "550e8400-e29b-41d4-a716-446655440000",
            "name": "TestRepo",
            "status": "ready",
            "entities_count": 1234,
            "last_synced": "2025-01-15T10:30:00Z",
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await tool(
                ctx=mock_context,
                repo_id="550e8400-e29b-41d4-a716-446655440000",
            )

        result_data = json.loads(result)
        assert result_data["success"] is True
        assert result_data["status"] == "ready"
        assert result_data["entities_count"] == 1234

    @pytest.mark.asyncio
    async def test_get_status_not_found(self, mock_mcp, mock_context):
        """Test status retrieval for non-existent repo."""
        register_code_repos_tools(mock_mcp)
        tool = mock_mcp._tools["code_repos_get_status"]

        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await tool(
                ctx=mock_context,
                repo_id="00000000-0000-0000-0000-000000000000",
            )

        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_get_status_indexing(self, mock_mcp, mock_context):
        """Test status retrieval while indexing."""
        register_code_repos_tools(mock_mcp)
        tool = mock_mcp._tools["code_repos_get_status"]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "repo_id": "550e8400-e29b-41d4-a716-446655440000",
            "status": "indexing",
            "entities_count": 500,
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await tool(
                ctx=mock_context,
                repo_id="550e8400-e29b-41d4-a716-446655440000",
            )

        result_data = json.loads(result)
        assert result_data["status"] == "indexing"


class TestCodeReposList:
    """Tests for code_repos_list tool."""

    @pytest.mark.asyncio
    async def test_list_repos_success(self, mock_mcp, mock_context):
        """Test successful repository listing."""
        register_code_repos_tools(mock_mcp)
        tool = mock_mcp._tools["code_repos_list"]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "repo_id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Repo1",
                "status": "ready",
            },
            {
                "repo_id": "660e8400-e29b-41d4-a716-446655440001",
                "name": "Repo2",
                "status": "indexing",
            },
        ]

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await tool(ctx=mock_context)

        result_data = json.loads(result)
        assert result_data["success"] is True
        assert result_data["count"] == 2
        assert len(result_data["repos"]) == 2

    @pytest.mark.asyncio
    async def test_list_repos_empty(self, mock_mcp, mock_context):
        """Test listing with no repositories."""
        register_code_repos_tools(mock_mcp)
        tool = mock_mcp._tools["code_repos_list"]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await tool(ctx=mock_context)

        result_data = json.loads(result)
        assert result_data["success"] is True
        assert result_data["count"] == 0

    @pytest.mark.asyncio
    async def test_list_repos_error(self, mock_mcp, mock_context):
        """Test listing with HTTP error."""
        register_code_repos_tools(mock_mcp)
        tool = mock_mcp._tools["code_repos_list"]

        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.text = "Service Unavailable"

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await tool(ctx=mock_context)

        assert "error" in result.lower()
