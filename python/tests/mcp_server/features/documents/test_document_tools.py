"""Unit tests for document management tools.

These tests mock the DocumentService directly since the tools now use
direct service imports instead of HTTP calls.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.server.fastmcp import Context


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


@pytest.mark.asyncio
async def test_create_document_success(mock_mcp, mock_context):
    """Test successful document creation."""
    from src.mcp_server.features.documents.document_tools import register_document_tools

    mock_doc = {
        "id": "doc-123",
        "title": "Test Document",
        "document_type": "spec",
        "status": "draft",
    }

    with patch("src.mcp_server.features.documents.document_tools.DocumentService") as MockService:
        mock_service = MagicMock()
        mock_service.add_document = AsyncMock(return_value=(True, {"document": mock_doc}))
        MockService.return_value = mock_service

        register_document_tools(mock_mcp)
        manage_document = mock_mcp._tools.get("manage_document")
        assert manage_document is not None

        result = await manage_document(
            mock_context,
            action="create",
            project_id="project-123",
            title="Test Document",
            document_type="spec",
            content={"test": "content"},
        )

        result_data = json.loads(result)
        assert result_data["success"] is True
        assert result_data["document_id"] == "doc-123"
        assert "Document created successfully" in result_data["message"]


@pytest.mark.asyncio
async def test_find_documents_success(mock_mcp, mock_context):
    """Test successful document listing."""
    from src.mcp_server.features.documents.document_tools import register_document_tools

    mock_docs = [
        {"id": "doc-1", "title": "Doc 1", "document_type": "spec"},
        {"id": "doc-2", "title": "Doc 2", "document_type": "design"},
    ]

    with patch("src.mcp_server.features.documents.document_tools.DocumentService") as MockService:
        mock_service = MagicMock()
        mock_service.list_documents = AsyncMock(return_value=(True, {"documents": mock_docs, "total_count": 2}))
        MockService.return_value = mock_service

        register_document_tools(mock_mcp)
        find_documents = mock_mcp._tools.get("find_documents")
        assert find_documents is not None

        result = await find_documents(mock_context, project_id="project-123")

        result_data = json.loads(result)
        assert result_data["success"] is True
        assert len(result_data["documents"]) == 2
        assert result_data["total"] == 2


@pytest.mark.asyncio
async def test_update_document_partial_update(mock_mcp, mock_context):
    """Test partial document update."""
    from src.mcp_server.features.documents.document_tools import register_document_tools

    mock_doc = {
        "id": "doc-123",
        "title": "Updated Title",
        "document_type": "spec",
    }

    with patch("src.mcp_server.features.documents.document_tools.DocumentService") as MockService:
        mock_service = MagicMock()
        mock_service.update_document = AsyncMock(return_value=(True, {"document": mock_doc}))
        MockService.return_value = mock_service

        register_document_tools(mock_mcp)
        manage_document = mock_mcp._tools.get("manage_document")

        result = await manage_document(
            mock_context, action="update", project_id="project-123", document_id="doc-123", title="Updated Title"
        )

        result_data = json.loads(result)
        assert result_data["success"] is True
        assert "Document updated successfully" in result_data["message"]


@pytest.mark.asyncio
async def test_delete_document_not_found(mock_mcp, mock_context):
    """Test deleting a non-existent document."""
    from src.mcp_server.features.documents.document_tools import register_document_tools

    with patch("src.mcp_server.features.documents.document_tools.DocumentService") as MockService:
        mock_service = MagicMock()
        mock_service.delete_document = AsyncMock(return_value=(False, {"error": "Document not found in project"}))
        MockService.return_value = mock_service

        register_document_tools(mock_mcp)
        manage_document = mock_mcp._tools.get("manage_document")

        result = await manage_document(
            mock_context, action="delete", project_id="project-123", document_id="non-existent"
        )

        result_data = json.loads(result)
        assert result_data["success"] is False
        assert "error" in result_data
        assert isinstance(result_data["error"], dict)


@pytest.mark.asyncio
async def test_get_document_by_id(mock_mcp, mock_context):
    """Test getting a specific document."""
    from src.mcp_server.features.documents.document_tools import register_document_tools

    mock_doc = {
        "id": "doc-123",
        "title": "Test Document",
        "document_type": "spec",
        "content": {"section": "content"},
    }

    with patch("src.mcp_server.features.documents.document_tools.DocumentService") as MockService:
        mock_service = MagicMock()
        mock_service.get_document = AsyncMock(return_value=(True, {"document": mock_doc}))
        MockService.return_value = mock_service

        register_document_tools(mock_mcp)
        find_documents = mock_mcp._tools.get("find_documents")

        result = await find_documents(mock_context, project_id="project-123", document_id="doc-123")

        result_data = json.loads(result)
        assert result_data["success"] is True
        assert result_data["document"]["id"] == "doc-123"


@pytest.mark.asyncio
async def test_document_type_filter(mock_mcp, mock_context):
    """Test filtering documents by type."""
    from src.mcp_server.features.documents.document_tools import register_document_tools

    mock_docs = [
        {"id": "doc-1", "title": "API Spec", "document_type": "spec"},
    ]

    with patch("src.mcp_server.features.documents.document_tools.DocumentService") as MockService:
        mock_service = MagicMock()
        mock_service.list_documents = AsyncMock(return_value=(True, {"documents": mock_docs, "total_count": 1}))
        MockService.return_value = mock_service

        register_document_tools(mock_mcp)
        find_documents = mock_mcp._tools.get("find_documents")

        result = await find_documents(mock_context, project_id="project-123", document_type="spec")

        result_data = json.loads(result)
        assert result_data["success"] is True
        assert result_data["documents"][0]["document_type"] == "spec"


@pytest.mark.asyncio
async def test_document_search_query(mock_mcp, mock_context):
    """Test searching documents with query."""
    from src.mcp_server.features.documents.document_tools import register_document_tools

    mock_docs = [
        {"id": "doc-1", "title": "Authentication Spec", "document_type": "spec"},
    ]

    with patch("src.mcp_server.features.documents.document_tools.DocumentService") as MockService:
        mock_service = MagicMock()
        mock_service.list_documents = AsyncMock(return_value=(True, {"documents": mock_docs, "total_count": 1}))
        MockService.return_value = mock_service

        register_document_tools(mock_mcp)
        find_documents = mock_mcp._tools.get("find_documents")

        result = await find_documents(mock_context, project_id="project-123", query="auth")

        result_data = json.loads(result)
        assert result_data["success"] is True
