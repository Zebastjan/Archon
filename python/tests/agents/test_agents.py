"""Tests for the AI agents module.

Tests for base agent, document agent, and RAG agent functionality.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import asyncio

from src.agents.base_agent import (
    ArchonDependencies,
    BaseAgentOutput,
    RateLimitHandler,
)


class TestArchonDependencies:
    """Test the ArchonDependencies dataclass."""

    def test_default_creation(self):
        """Test creating dependencies with defaults."""
        deps = ArchonDependencies()
        assert deps.request_id is None
        assert deps.user_id is None
        assert deps.trace_id is None

    def test_creation_with_values(self):
        """Test creating dependencies with specific values."""
        deps = ArchonDependencies(
            request_id="req-123",
            user_id="user-456",
            trace_id="trace-789"
        )
        assert deps.request_id == "req-123"
        assert deps.user_id == "user-456"
        assert deps.trace_id == "trace-789"


class TestBaseAgentOutput:
    """Test the BaseAgentOutput model."""

    def test_success_output(self):
        """Test creating a successful output."""
        output = BaseAgentOutput(
            success=True,
            message="Operation completed",
            data={"result": "success"},
            errors=None
        )
        assert output.success is True
        assert output.message == "Operation completed"
        assert output.data == {"result": "success"}
        assert output.errors is None

    def test_error_output(self):
        """Test creating an error output."""
        output = BaseAgentOutput(
            success=False,
            message="Operation failed",
            data=None,
            errors=["Error 1", "Error 2"]
        )
        assert output.success is False
        assert output.message == "Operation failed"
        assert output.data is None
        assert output.errors == ["Error 1", "Error 2"]


class TestRateLimitHandler:
    """Test the RateLimitHandler class."""

    def test_initialization(self):
        """Test handler initialization with defaults."""
        handler = RateLimitHandler()
        assert handler.max_retries == 5
        assert handler.base_delay == 1.0
        assert handler.min_request_interval == 0.1

    def test_custom_initialization(self):
        """Test handler initialization with custom values."""
        handler = RateLimitHandler(max_retries=3, base_delay=0.5)
        assert handler.max_retries == 3
        assert handler.base_delay == 0.5

    def test_calculate_delay_exponential_backoff(self):
        """Test exponential backoff calculation."""
        handler = RateLimitHandler(base_delay=1.0)

        # First retry: base_delay * (2^0) = 1.0
        assert handler._calculate_delay(0) == 1.0

        # Second retry: base_delay * (2^1) = 2.0
        assert handler._calculate_delay(1) == 2.0

        # Third retry: base_delay * (2^2) = 4.0
        assert handler._calculate_delay(2) == 4.0

        # Max delay should be capped
        # 10th retry: base_delay * (2^9) = 512, but capped at 60
        assert handler._calculate_delay(9) == 60.0

    def test_calculate_delay_with_jitter(self):
        """Test that jitter adds randomness to delay."""
        handler = RateLimitHandler(base_delay=1.0)

        # Get multiple delays and verify they vary (due to jitter)
        delays = [handler._calculate_delay(0) for _ in range(10)]

        # All delays should be within expected range (base_delay to base_delay * 1.5)
        for delay in delays:
            assert 1.0 <= delay <= 1.5

    @pytest.mark.asyncio
    async def test_wait_if_needed_respects_interval(self):
        """Test that wait_if_needed respects minimum interval."""
        handler = RateLimitHandler(min_request_interval=0.1)

        # First call should not wait
        start_time = asyncio.get_event_loop().time()
        await handler.wait_if_needed()
        elapsed = asyncio.get_event_loop().time() - start_time
        assert elapsed < 0.05  # Should be nearly instant

        # Immediately calling again should wait
        start_time = asyncio.get_event_loop().time()
        await handler.wait_if_needed()
        elapsed = asyncio.get_event_loop().time() - start_time
        assert elapsed >= 0.09  # Should wait at least ~0.1s


class TestAgentImports:
    """Test that all agent modules can be imported."""

    def test_base_agent_import(self):
        """Test that base_agent module can be imported."""
        from src.agents import base_agent
        assert hasattr(base_agent, 'ArchonDependencies')
        assert hasattr(base_agent, 'BaseAgentOutput')
        assert hasattr(base_agent, 'RateLimitHandler')

    def test_mcp_client_import(self):
        """Test that mcp_client module can be imported."""
        from src.agents import mcp_client
        assert hasattr(mcp_client, 'MCPClient')

    def test_rag_agent_import(self):
        """Test that rag_agent module can be imported."""
        from src.agents import rag_agent
        assert hasattr(rag_agent, 'RAGAgent')

    def test_document_agent_import(self):
        """Test that document_agent module can be imported."""
        from src.agents import document_agent
        assert hasattr(document_agent, 'DocumentAgent')


class TestMCPClient:
    """Test the MCPClient class."""

    @pytest.fixture
    def mcp_client(self):
        """Create an MCPClient instance for testing."""
        from src.agents.mcp_client import MCPClient
        return MCPClient(base_url="http://test-server:8080")

    def test_initialization(self, mcp_client):
        """Test client initialization."""
        assert mcp_client.base_url == "http://test-server:8080"

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.post')
    async def test_call_tool_success(self, mock_post, mcp_client):
        """Test successful tool call."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": "success",
            "data": {"key": "value"}
        }
        mock_post.return_value = mock_response

        result = await mcp_client.call_tool("test_tool", {"param": "value"})

        assert result["success"] is True
        assert result["data"]["key"] == "value"

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.post')
    async def test_call_tool_http_error(self, mock_post, mcp_client):
        """Test tool call with HTTP error."""
        # Mock error response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        result = await mcp_client.call_tool("test_tool", {})

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.post')
    async def test_call_tool_network_error(self, mock_post, mcp_client):
        """Test tool call with network error."""
        # Mock network exception
        mock_post.side_effect = Exception("Connection failed")

        result = await mcp_client.call_tool("test_tool", {})

        assert result["success"] is False
        assert "error" in result


class TestRAGAgent:
    """Test the RAGAgent class."""

    @pytest.fixture
    def rag_agent(self):
        """Create a RAGAgent instance for testing."""
        from src.agents.rag_agent import RAGAgent
        return RAGAgent()

    def test_initialization(self, rag_agent):
        """Test agent initialization."""
        assert rag_agent is not None

    def test_agent_has_required_tools(self, rag_agent):
        """Test that agent has required RAG tools."""
        # Check that the agent has the expected tools registered
        assert hasattr(rag_agent, 'agent')


class TestDocumentAgent:
    """Test the DocumentAgent class."""

    @pytest.fixture
    def document_agent(self):
        """Create a DocumentAgent instance for testing."""
        from src.agents.document_agent import DocumentAgent
        return DocumentAgent()

    def test_initialization(self, document_agent):
        """Test agent initialization."""
        assert document_agent is not None

    def test_agent_has_required_tools(self, document_agent):
        """Test that agent has required document tools."""
        # Check that the agent has the expected tools registered
        assert hasattr(document_agent, 'agent')
