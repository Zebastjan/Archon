"""
Git MCP Server

MCP (Model Context Protocol) server for Git integration.
Provides Git search tools to MCP-compatible agents.
"""

from typing import Any

from supabase import Client

from .git_tools import GitTools
from ..config.logfire_config import get_logger

logger = get_logger(__name__)


class GitMCPServer:
    """
    MCP server for Git functionality.

    Registers and executes Git-related tools for MCP agents.
    """

    def __init__(self, supabase_client: Client):
        """
        Initialize Git MCP server.

        Args:
            supabase_client: Supabase client for database operations
        """
        self.git_tools = GitTools(supabase_client)
        self.tools = self._register_tools()

    def _register_tools(self) -> dict[str, Any]:
        """
        Register Git tools for MCP.

        Returns:
            Dict mapping tool names to tool functions
        """
        return {
            "git_search_commits": self.git_tools.search_commits,
            "git_file_history": self.git_tools.get_file_history,
            "git_commit_context": self.git_tools.get_commit_context,
        }

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """
        Get tool definitions for MCP protocol.

        Returns:
            List of tool definitions
        """
        return self.git_tools.get_tool_definitions()

    async def execute_tool(
        self,
        tool_name: str,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute a Git tool by name.

        Args:
            tool_name: Name of the tool to execute
            parameters: Tool parameters

        Returns:
            Tool execution result
        """
        if tool_name not in self.tools:
            return {
                "success": False,
                "error": f"Unknown tool: {tool_name}",
            }

        try:
            tool_func = self.tools[tool_name]
            result = await tool_func(**parameters)
            return result

        except Exception as e:
            logger.error(f"Tool execution failed: {tool_name}, error: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def list_tools(self) -> list[str]:
        """
        List available Git tools.

        Returns:
            List of tool names
        """
        return list(self.tools.keys())

    async def handle_git_query(
        self,
        query: str,
        repo_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        High-level handler for Git queries.

        Automatically routes to appropriate tool based on query.

        Args:
            query: Natural language query
            repo_id: Repository ID
            **kwargs: Additional parameters

        Returns:
            Query result
        """
        # For now, default to semantic search
        # Future: Could use LLM to route to appropriate tool
        return await self.git_tools.search_commits(
            query=query,
            repo_id=repo_id,
            **kwargs,
        )
