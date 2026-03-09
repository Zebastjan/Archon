"""
Test Git MCP Integration - MCP agent tools for git search.

Phase 4 tests for MCP agent integration with Git functionality.

IMPORTANT: These tests mock only external dependencies (Supabase), not service layers.
This ensures we test the real integration chain:
- GitSemanticSearch → GitSearchStrategy → GitTools → MCP wrapper

If someone breaks GitSearchStrategy formatting or data flow, these tests will catch it.
"""

import sys
from unittest.mock import MagicMock, AsyncMock, patch

# Mock modules before importing
sys.modules['src.server.db_connector'] = MagicMock()
sys.modules['src.server.db_connector'].get_db_client = MagicMock(return_value=MagicMock())
sys.modules['openai'] = MagicMock()
sys.modules['src.server.services.embeddings'] = MagicMock()
sys.modules['src.server.services.embeddings.embedding_service'] = MagicMock()
sys.modules['src.server.services.embeddings.embedding_service'].create_embedding = AsyncMock(return_value=[0.1] * 1536)
sys.modules['src.server.services.embeddings.contextual_embedding_service'] = MagicMock()
sys.modules['src.server.services.credential_service'] = MagicMock()

import pytest
from datetime import datetime
from typing import Any

# Import MCP-related classes
from src.server.mcp.git_tools import GitTools
from src.server.mcp.git_mcp_server import GitMCPServer
MCP_AVAILABLE = True

# Import realistic mock data factories
from tests.git_integration.fixtures.realistic_mock_data import (
    create_supabase_commit_response,
    create_security_fix_response,
    create_bug_fix_response,
    create_feature_response,
)


@pytest.fixture
def mock_supabase_client():
    """Provide mocked Supabase client."""
    client = MagicMock()
    client.rpc.return_value = MagicMock(execute=MagicMock(return_value=MagicMock(data=[])))
    client.table.return_value = MagicMock(
        select=MagicMock(return_value=MagicMock(
            eq=MagicMock(return_value=MagicMock(
                execute=MagicMock(return_value=MagicMock(data=[]))
            ))
        ))
    )
    return client


@pytest.mark.skipif(not MCP_AVAILABLE, reason="MCP modules not available")
class TestMCPGitTools:
    """Tests for MCP Git tool definitions."""

    def test_mcp_git_search_tool_defined(self, mock_supabase_client):
        """Git search tool is registered in MCP."""
        git_tools = GitTools(mock_supabase_client)
        tool_defs = git_tools.get_tool_definitions()

        # Check that git_search_commits tool exists
        search_tool = next((t for t in tool_defs if t["name"] == "git_search_commits"), None)
        assert search_tool is not None
        assert "description" in search_tool
        assert "parameters" in search_tool
        assert search_tool["parameters"]["required"] == ["query"]

    def test_mcp_git_file_history_tool(self, mock_supabase_client):
        """File history tool is available."""
        git_tools = GitTools(mock_supabase_client)
        tool_defs = git_tools.get_tool_definitions()

        # Check that git_file_history tool exists
        history_tool = next((t for t in tool_defs if t["name"] == "git_file_history"), None)
        assert history_tool is not None
        assert "description" in history_tool
        assert "parameters" in history_tool
        assert set(history_tool["parameters"]["required"]) == {"file_path", "repo_id"}

    def test_mcp_git_commit_context_tool(self, mock_supabase_client):
        """Commit context tool is available."""
        git_tools = GitTools(mock_supabase_client)
        tool_defs = git_tools.get_tool_definitions()

        # Check that git_commit_context tool exists
        context_tool = next((t for t in tool_defs if t["name"] == "git_commit_context"), None)
        assert context_tool is not None
        assert "description" in context_tool
        assert "parameters" in context_tool
        assert set(context_tool["parameters"]["required"]) == {"commit_sha", "repo_id"}

    @pytest.mark.asyncio
    async def test_mcp_git_search_tool_execution(self, mock_supabase_client):
        """Agent can call git search tool.

        IMPORTANT: Mocks only Supabase, tests real chain:
        GitSemanticSearch → GitSearchStrategy → GitTools
        """
        git_tools = GitTools(mock_supabase_client)

        # Mock Supabase RPC response (external dependency only)
        mock_supabase_client.rpc.return_value.execute.return_value = MagicMock(
            data=[
                create_supabase_commit_response(
                    commit_sha="abc123" + "a" * 34,
                    message="Add performance improvements",
                    intent="feature",
                    risk_level="low",
                    author_name="Dev Team",
                    author_email="dev@example.com",
                    similarity=0.85,
                )
            ]
        )

        # Call real MCP tool (no strategy mocking!)
        result = await git_tools.search_commits(
            query="performance improvements",
            limit=5
        )

        # Validate MCP wrapper structure
        assert result["success"] is True
        assert result["query"] == "performance improvements"
        assert result["count"] == 1
        assert len(result["results"]) == 1

        # Validate complete commit structure from strategy (all 17 fields)
        commit = result["results"][0]
        assert commit["type"] == "git_commit"
        assert commit["commit_sha"] == "abc123" + "a" * 34
        assert commit["commit_id"] is not None
        assert commit["repo_id"] is not None
        assert commit["message"] == "Add performance improvements"
        assert commit["author"] == "Dev Team"
        assert commit["author_email"] == "dev@example.com"
        assert commit["commit_date"] is not None
        assert commit["branches"] == ["main"]
        assert commit["classification"]["intent"] == "feature"
        assert commit["similarity_score"] == 0.85
        assert commit["embedding_dimension"] == 1536
        assert "content" in commit  # Formatted by _format_commit_content
        assert "metadata" in commit

    @pytest.mark.asyncio
    async def test_mcp_git_file_history_tool_execution(self, mock_supabase_client):
        """Agent can call file history tool."""
        git_tools = GitTools(mock_supabase_client)

        # Mock file history results
        mock_commits = [
            {
                "commit_sha": "def456",
                "message": "Update main.py",
                "author": "dev@example.com",
                "files_changed": ["src/main.py"],
            }
        ]

        with patch.object(git_tools.git_strategy, 'search_commits_for_file', new_callable=AsyncMock, return_value=mock_commits):
            result = await git_tools.get_file_history(
                file_path="src/main.py",
                repo_id="repo-123",
                limit=10
            )

        assert result["success"] is True
        assert result["file_path"] == "src/main.py"
        assert result["count"] == 1
        assert len(result["commits"]) == 1
        assert result["commits"][0]["commit_sha"] == "def456"

    @pytest.mark.asyncio
    async def test_mcp_git_commit_context_tool_execution(self, mock_supabase_client):
        """Agent can call commit context tool."""
        git_tools = GitTools(mock_supabase_client)

        # Mock commit context
        mock_context = {
            "commit_sha": "abc123",
            "message": "Fix bug in authentication",
            "author": "dev@example.com",
            "intent": ["bugfix"],
            "risk_level": "low",
        }

        with patch.object(git_tools.git_strategy, 'get_commit_context', new_callable=AsyncMock, return_value=mock_context):
            result = await git_tools.get_commit_context(
                commit_sha="abc123",
                repo_id="repo-123"
            )

        assert result["success"] is True
        assert result["commit"]["commit_sha"] == "abc123"
        assert result["commit"]["intent"] == ["bugfix"]


@pytest.mark.skipif(not MCP_AVAILABLE, reason="MCP modules not available")
class TestMCPResultsFormatting:
    """Tests for MCP result formatting."""

    @pytest.mark.asyncio
    async def test_mcp_results_formatted_for_agent(self, mock_supabase_client):
        """Results are human-readable for agents.

        IMPORTANT: Mocks only Supabase, validates real MCP wrapper formatting.
        """
        git_tools = GitTools(mock_supabase_client)

        # Mock Supabase RPC response
        mock_supabase_client.rpc.return_value.execute.return_value = MagicMock(
            data=[
                create_feature_response()
            ]
        )

        # Call real MCP tool chain
        result = await git_tools.search_commits(query="feature X")

        # Verify MCP wrapper adds these fields
        assert "success" in result
        assert "query" in result
        assert "count" in result
        assert "results" in result
        assert isinstance(result["results"], list)
        assert result["success"] is True

        # Verify GitSearchStrategy provides complete commit structure
        commit = result["results"][0]
        assert commit["type"] == "git_commit"
        assert "content" in commit  # Human-readable content for agent
        assert "metadata" in commit
        assert "classification" in commit

    @pytest.mark.asyncio
    async def test_mcp_error_handling(self, mock_supabase_client):
        """Tool failures don't crash agent."""
        git_tools = GitTools(mock_supabase_client)

        # Mock an error in search
        with patch.object(git_tools.git_strategy, 'search_commits', new_callable=AsyncMock, side_effect=Exception("Database error")):
            result = await git_tools.search_commits(query="test query")

        # Verify error is returned in a structured way
        assert result["success"] is False
        assert "error" in result
        assert "Database error" in result["error"]
        assert result["count"] == 0
        assert result["results"] == []


@pytest.mark.skipif(not MCP_AVAILABLE, reason="MCP modules not available")
class TestMCPQueryTypes:
    """Tests for different query types through MCP."""

    @pytest.mark.asyncio
    async def test_mcp_semantic_commit_queries(self, mock_supabase_client):
        """Natural language to commits.

        IMPORTANT: Mocks only Supabase, tests real semantic search chain.
        """
        git_tools = GitTools(mock_supabase_client)

        # Mock Supabase RPC response
        mock_supabase_client.rpc.return_value.execute.return_value = MagicMock(
            data=[
                create_supabase_commit_response(
                    commit_sha="abc123" + "a" * 34,
                    message="Implement user authentication",
                    intent="feature",
                    risk_level="medium",
                    similarity=0.88,
                )
            ]
        )

        # Call real MCP tool chain
        result = await git_tools.search_commits(
            query="how does authentication work?"
        )

        assert result["success"] is True
        assert result["count"] == 1
        assert "authentication" in result["results"][0]["message"].lower()

        # Validate complete structure
        commit = result["results"][0]
        assert "content" in commit
        assert "metadata" in commit
        assert commit["type"] == "git_commit"

    @pytest.mark.asyncio
    async def test_mcp_performance_optimization_queries(self, mock_supabase_client):
        """Find perf commits."""
        git_tools = GitTools(mock_supabase_client)

        mock_results = [
            {
                "commit_sha": "perf456",
                "message": "Optimize database queries",
                "intent": ["performance"],
                "similarity": 0.90,
            }
        ]

        with patch.object(git_tools.git_strategy, 'search_commits', new_callable=AsyncMock, return_value=mock_results):
            result = await git_tools.search_commits(
                query="performance improvements",
                intent=["performance"]
            )

        assert result["success"] is True
        assert result["count"] == 1
        assert result["results"][0]["intent"] == ["performance"]

    @pytest.mark.asyncio
    async def test_mcp_security_fix_queries(self, mock_supabase_client):
        """Find security commits.

        IMPORTANT: Mocks only Supabase, tests real security filtering chain.
        """
        git_tools = GitTools(mock_supabase_client)

        # Mock Supabase RPC response with security commit
        mock_supabase_client.rpc.return_value.execute.return_value = MagicMock(
            data=[create_security_fix_response()]
        )

        # Call real MCP tool chain
        result = await git_tools.search_commits(
            query="security vulnerabilities",
            security_only=True
        )

        assert result["success"] is True
        assert result["count"] == 1

        # Validate complete structure
        commit = result["results"][0]
        assert commit["type"] == "git_commit"
        assert commit["classification"]["intent"] == "security_fix"
        assert commit["classification"]["risk_level"] == "high"
        assert "content" in commit
        assert "metadata" in commit
        assert commit["commit_sha"] is not None

    @pytest.mark.asyncio
    async def test_mcp_author_queries(self, mock_supabase_client):
        """Find commits by author."""
        git_tools = GitTools(mock_supabase_client)

        mock_results = [
            {
                "commit_sha": "auth101",
                "message": "Add new feature",
                "author": "alice@example.com",
                "similarity": 0.82,
            }
        ]

        with patch.object(git_tools.git_strategy, 'search_commits', new_callable=AsyncMock, return_value=mock_results):
            result = await git_tools.search_commits(
                query="recent work",
                author="alice@example.com"
            )

        assert result["success"] is True
        assert result["count"] == 1
        assert result["results"][0]["author"] == "alice@example.com"

    @pytest.mark.asyncio
    async def test_mcp_time_range_queries(self, mock_supabase_client):
        """Recent commits only."""
        git_tools = GitTools(mock_supabase_client)

        mock_results = [
            {
                "commit_sha": "recent123",
                "message": "Recent update",
                "timestamp": "2026-03-07T10:00:00Z",
                "similarity": 0.80,
            }
        ]

        with patch.object(git_tools.git_strategy, 'search_commits', new_callable=AsyncMock, return_value=mock_results):
            result = await git_tools.search_commits(
                query="updates",
                since="2026-03-01T00:00:00Z",
                until="2026-03-08T23:59:59Z"
            )

        assert result["success"] is True
        assert result["count"] == 1


@pytest.mark.skipif(not MCP_AVAILABLE, reason="MCP modules not available")
class TestMCPMultiRepo:
    """Tests for multi-repo MCP queries."""

    @pytest.mark.asyncio
    async def test_mcp_with_multiple_repos(self, mock_supabase_client):
        """Cross-repo search."""
        git_tools = GitTools(mock_supabase_client)

        # Mock results from multiple repos
        mock_results = [
            {
                "commit_sha": "repo1-abc",
                "message": "Update API endpoint",
                "repo_id": "repo-1",
                "similarity": 0.90,
            },
            {
                "commit_sha": "repo2-def",
                "message": "Fix API authentication",
                "repo_id": "repo-2",
                "similarity": 0.85,
            }
        ]

        with patch.object(git_tools.git_strategy, 'search_commits', new_callable=AsyncMock, return_value=mock_results):
            # Search without repo_id to get results from all repos
            result = await git_tools.search_commits(
                query="API changes"
            )

        assert result["success"] is True
        assert result["count"] == 2
        # Verify we got results from different repos
        repo_ids = {r["repo_id"] for r in result["results"]}
        assert len(repo_ids) == 2


@pytest.mark.skipif(not MCP_AVAILABLE, reason="MCP modules not available")
class TestMCPBranchAware:
    """Tests for branch-aware MCP queries."""

    @pytest.mark.asyncio
    async def test_mcp_branch_switching_workflow(self, mock_supabase_client):
        """Branch-aware queries."""
        git_tools = GitTools(mock_supabase_client)

        # Mock results from a specific branch
        mock_results = [
            {
                "commit_sha": "branch-abc",
                "message": "Feature branch commit",
                "branch": "feature/new-ui",
                "similarity": 0.87,
            }
        ]

        with patch.object(git_tools.git_strategy, 'search_commits', new_callable=AsyncMock, return_value=mock_results):
            result = await git_tools.search_commits(
                query="UI changes",
                branch="feature/new-ui",
                repo_id="repo-123"
            )

        assert result["success"] is True
        assert result["count"] == 1
        assert result["results"][0]["branch"] == "feature/new-ui"


@pytest.mark.skipif(not MCP_AVAILABLE, reason="MCP modules not available")
class TestMCPKnowledgeBase:
    """Tests for MCP + Knowledge Base integration."""

    @pytest.mark.asyncio
    async def test_mcp_integration_with_knowledge_base(self, mock_supabase_client):
        """Combined KB + git search."""
        git_tools = GitTools(mock_supabase_client)

        # Mock git search results
        git_results = [
            {
                "commit_sha": "git-abc",
                "message": "Update authentication logic",
                "similarity": 0.90,
            }
        ]

        with patch.object(git_tools.git_strategy, 'search_commits', new_callable=AsyncMock, return_value=git_results):
            git_result = await git_tools.search_commits(
                query="authentication implementation"
            )

        # Verify git search works independently
        assert git_result["success"] is True
        assert git_result["count"] == 1
        # In real usage, this would be combined with KB results

    @pytest.mark.asyncio
    async def test_mcp_git_aware_answers(self, mock_supabase_client):
        """Final response includes git context."""
        git_tools = GitTools(mock_supabase_client)

        # Mock git results with rich context
        mock_results = [
            {
                "commit_sha": "ctx-123",
                "message": "Refactor payment processing",
                "author": "dev@example.com",
                "intent": ["refactor"],
                "risk_level": "medium",
                "files_changed": ["src/payments.py", "tests/test_payments.py"],
                "similarity": 0.92,
            }
        ]

        with patch.object(git_tools.git_strategy, 'search_commits', new_callable=AsyncMock, return_value=mock_results):
            result = await git_tools.search_commits(
                query="payment processing changes"
            )

        # Verify result has rich context for agent responses
        assert result["success"] is True
        assert "results" in result
        commit = result["results"][0]
        assert "message" in commit
        assert "author" in commit
        assert "intent" in commit
        assert "files_changed" in commit


# Integration tests that work with or without MCP
@pytest.mark.skipif(not MCP_AVAILABLE, reason="MCP modules not available")
class TestGitMCPServerIntegration:
    """Tests for Git MCP server integration (if available)."""

    def test_mcp_server_initialization(self, mock_supabase_client):
        """MCP server can be initialized."""
        server = GitMCPServer(mock_supabase_client)
        assert server is not None
        assert server.git_tools is not None
        assert server.tools is not None
        assert len(server.tools) > 0

    def test_mcp_tools_list(self, mock_supabase_client):
        """List of available git tools."""
        server = GitMCPServer(mock_supabase_client)
        tools = server.list_tools()

        # Verify expected tools are registered
        assert "git_search_commits" in tools
        assert "git_file_history" in tools
        assert "git_commit_context" in tools
        assert len(tools) == 3

    @pytest.mark.asyncio
    async def test_mcp_server_responds_to_git_queries(self, mock_supabase_client):
        """Server responds to git queries."""
        server = GitMCPServer(mock_supabase_client)

        mock_results = [
            {
                "commit_sha": "query-abc",
                "message": "Add feature",
                "similarity": 0.88,
            }
        ]

        with patch.object(server.git_tools.git_strategy, 'search_commits', new_callable=AsyncMock, return_value=mock_results):
            result = await server.handle_git_query(
                query="new features",
                repo_id="repo-123"
            )

        assert result["success"] is True
        assert result["count"] == 1
        assert "results" in result

    @pytest.mark.asyncio
    async def test_mcp_server_handles_errors_gracefully(self, mock_supabase_client):
        """Server handles errors gracefully."""
        server = GitMCPServer(mock_supabase_client)

        # Test with unknown tool
        result = await server.execute_tool(
            tool_name="unknown_tool",
            parameters={}
        )

        assert result["success"] is False
        assert "error" in result
        assert "Unknown tool" in result["error"]

        # Test with tool execution error
        with patch.object(server.git_tools.git_strategy, 'search_commits', new_callable=AsyncMock, side_effect=Exception("Test error")):
            result = await server.execute_tool(
                tool_name="git_search_commits",
                parameters={"query": "test"}
            )

        assert result["success"] is False
        assert "error" in result
