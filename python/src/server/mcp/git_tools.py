"""
Git Tools for MCP (Model Context Protocol) Integration

Provides Git-aware tools for MCP agents to search commits, file history,
and repository context.
"""

from datetime import datetime
from typing import Any

from supabase import Client

from ..services.search.git_search_strategy import GitSearchStrategy
from ..config.logfire_config import get_logger

logger = get_logger(__name__)


class GitTools:
    """
    Git tools for MCP agent integration.

    Provides agents with the ability to:
    - Search commits semantically
    - Find file change history
    - Get commit context
    - Query by intent, risk, author, etc.
    """

    def __init__(self, supabase_client: Client):
        """
        Initialize Git tools with Supabase client.

        Args:
            supabase_client: Supabase client for database operations
        """
        self.git_strategy = GitSearchStrategy(supabase_client)

    async def search_commits(
        self,
        query: str,
        repo_id: str | None = None,
        branch: str | None = None,
        limit: int = 5,
        intent: list[str] | None = None,
        risk_level: list[str] | None = None,
        author: str | None = None,
        since: str | None = None,
        until: str | None = None,
        breaking_only: bool = False,
        security_only: bool = False,
    ) -> dict[str, Any]:
        """
        Search Git commits semantically.

        MCP tool for searching commits by natural language query.

        Args:
            query: Natural language query (e.g., "performance improvements")
            repo_id: Filter by repository ID
            branch: Filter by branch name
            limit: Number of results (default 5, max 20)
            intent: Filter by intent (feature, bugfix, refactor, etc.)
            risk_level: Filter by risk (low, medium, high)
            author: Filter by author name or email
            since: ISO date string for commits after this date
            until: ISO date string for commits before this date
            breaking_only: Only return breaking changes
            security_only: Only return security-related commits

        Returns:
            Dict with results array and metadata
        """
        try:
            # Parse date strings
            since_dt = datetime.fromisoformat(since) if since else None
            until_dt = datetime.fromisoformat(until) if until else None

            # Limit max results
            limit = min(limit, 20)

            # Search commits
            results = await self.git_strategy.search_commits(
                query=query,
                match_count=limit,
                repo_id=repo_id,
                branch=branch,
                intent_filter=intent,
                risk_filter=risk_level,
                author=author,
                since=since_dt,
                until=until_dt,
                breaking_only=breaking_only,
                security_only=security_only,
            )

            return {
                "success": True,
                "query": query,
                "count": len(results),
                "results": results,
            }

        except Exception as e:
            logger.error(f"MCP git search failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query,
                "count": 0,
                "results": [],
            }

    async def get_file_history(
        self,
        file_path: str,
        repo_id: str,
        branch: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """
        Get commit history for a specific file.

        MCP tool for finding all commits that modified a file.

        Args:
            file_path: Path to file (e.g., "src/server/main.py")
            repo_id: Repository ID
            branch: Optional branch filter
            limit: Number of commits (default 10, max 50)

        Returns:
            Dict with commits that modified the file
        """
        try:
            limit = min(limit, 50)

            results = await self.git_strategy.search_commits_for_file(
                file_path=file_path,
                repo_id=repo_id,
                branch=branch,
                match_count=limit,
            )

            return {
                "success": True,
                "file_path": file_path,
                "count": len(results),
                "commits": results,
            }

        except Exception as e:
            logger.error(f"MCP file history failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "file_path": file_path,
                "count": 0,
                "commits": [],
            }

    async def get_commit_context(
        self,
        commit_sha: str,
        repo_id: str,
    ) -> dict[str, Any]:
        """
        Get detailed context for a specific commit.

        MCP tool for retrieving full commit information.

        Args:
            commit_sha: Commit SHA to look up
            repo_id: Repository ID

        Returns:
            Dict with commit details or error
        """
        try:
            context = await self.git_strategy.get_commit_context(
                commit_sha=commit_sha,
                repo_id=repo_id,
            )

            if context:
                return {
                    "success": True,
                    "commit": context,
                }
            else:
                return {
                    "success": False,
                    "error": f"Commit {commit_sha} not found",
                }

        except Exception as e:
            logger.error(f"MCP get commit context failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """
        Get MCP tool definitions for registration.

        Returns tool schemas that MCP servers can register.

        Returns:
            List of tool definition dicts
        """
        return [
            {
                "name": "git_search_commits",
                "description": "Search Git commits using natural language queries. Find commits by semantic meaning, intent, risk level, or author.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language search query (e.g., 'performance improvements', 'security fixes')",
                        },
                        "repo_id": {
                            "type": "string",
                            "description": "Repository ID to search (optional)",
                        },
                        "branch": {
                            "type": "string",
                            "description": "Branch name filter (optional)",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of results (default 5, max 20)",
                            "default": 5,
                        },
                        "intent": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Filter by intent: feature, bugfix, refactor, security_fix, performance, test, documentation",
                        },
                        "risk_level": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Filter by risk: low, medium, high",
                        },
                        "author": {
                            "type": "string",
                            "description": "Filter by author name or email",
                        },
                        "breaking_only": {
                            "type": "boolean",
                            "description": "Only return breaking changes",
                            "default": False,
                        },
                        "security_only": {
                            "type": "boolean",
                            "description": "Only return security-related commits",
                            "default": False,
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "git_file_history",
                "description": "Get commit history for a specific file. Shows all commits that modified the file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to the file (e.g., 'src/server/main.py')",
                        },
                        "repo_id": {
                            "type": "string",
                            "description": "Repository ID",
                        },
                        "branch": {
                            "type": "string",
                            "description": "Branch name filter (optional)",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of commits (default 10, max 50)",
                            "default": 10,
                        },
                    },
                    "required": ["file_path", "repo_id"],
                },
            },
            {
                "name": "git_commit_context",
                "description": "Get detailed context for a specific commit including metadata, files changed, and classification.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "commit_sha": {
                            "type": "string",
                            "description": "Commit SHA to look up",
                        },
                        "repo_id": {
                            "type": "string",
                            "description": "Repository ID",
                        },
                    },
                    "required": ["commit_sha", "repo_id"],
                },
            },
        ]
