"""MCP Tools for Code Repository Management

Provides MCP tools for:
- Creating and indexing code repositories
- Checking repository status
- Listing registered repositories
"""

import asyncio
import json
import logging
from typing import Any

import httpx
from mcp.server.fastmcp import Context, FastMCP

from src.mcp_server.utils.error_handling import MCPErrorFormatter
from src.mcp_server.utils.timeout_config import get_default_timeout
from src.server.config.service_discovery import get_api_url

logger = logging.getLogger(__name__)


def register_code_repos_tools(mcp: FastMCP):
    """Register code repository management tools with the MCP server."""

    @mcp.tool()
    async def code_repos_create_and_index(
        ctx: Context,
        name: str,
        local_path: str,
        github_url: str | None = None,
        wait_for_ready: bool = False,
        timeout_seconds: int = 300,
        poll_interval: int = 5,
    ) -> str:
        """
        Create a code repository entry and trigger indexing.
        
        This is the single sanctioned path for adding new repositories to Archon.
        It creates the repo row and triggers indexing in one operation.
        
        Idempotent: If repo already exists by local_path, returns existing info.
        
        Args:
            name: Repository display name (e.g., "Omnibus")
            local_path: Absolute path to local git repository
            github_url: Optional GitHub URL for the repository
            wait_for_ready: If True, block until indexing completes (or timeout)
            timeout_seconds: Maximum seconds to wait if wait_for_ready=True
            poll_interval: Seconds between status checks when waiting
        
        Returns:
            JSON with repo_id, status, entities_count, and any error_message
        
        Example:
            >>> await code_repos_create_and_index(
            ...     name="Omnibus",
            ...     local_path="/home/zebastjan/dev/Omnibus",
            ...     github_url="https://github.com/zebastjan/Omnibus"
            ... )
            {
                "success": True,
                "repo_id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Omnibus",
                "status": "queued",
                "entities_count": 0,
                "existing": False,
                "error_message": None
            }
        
        Status values:
            - "queued": Indexing job submitted, not yet started
            - "indexing": Ingestion in progress
            - "ready": Fully indexed and available
            - "error": Indexing failed (see error_message)
        
        Error handling:
            - Path doesn't exist → status="error", error_message="Path not found: ..."
            - Path not a git repo → status="error", error_message="Not a git repository"
            - If MCP call fails → STOP and report (no shell fallback per archon-system-prompt.md)
        """
        try:
            api_url = get_api_url()
            timeout = get_default_timeout()
            
            # Call the HTTP API to create and index
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{api_url}/api/code_repos/create-and-index",
                    json={
                        "name": name,
                        "local_path": local_path,
                        "github_url": github_url,
                    }
                )
                
                if response.status_code != 200:
                    return MCPErrorFormatter.from_http_error(response, "create and index repo")
                
                result = response.json()
                repo_id = result.get("repo_id")
                status = result.get("status")
                
                # If requested, wait until ready
                if wait_for_ready and status in ["queued", "indexing"] and repo_id:
                    start_time = asyncio.get_event_loop().time()
                    
                    while True:
                        # Check if we've exceeded timeout
                        elapsed = asyncio.get_event_loop().time() - start_time
                        if elapsed > timeout_seconds:
                            result["status"] = "indexing"  # Still in progress
                            result["message"] = f"Timeout after {timeout_seconds}s. Indexing continues in background."
                            break
                        
                        # Poll status
                        await asyncio.sleep(poll_interval)
                        
                        status_response = await client.get(
                            f"{api_url}/api/code_repos/{repo_id}/status",
                            timeout=timeout
                        )
                        
                        if status_response.status_code == 200:
                            status_data = status_response.json()
                            current_status = status_data.get("status")
                            
                            if current_status == "ready":
                                # Update result with final status
                                result["status"] = "ready"
                                result["entities_count"] = status_data.get("entities_count", 0)
                                result["last_synced"] = status_data.get("last_synced")
                                break
                            elif current_status == "error":
                                result["status"] = "error"
                                result["error_message"] = status_data.get("error_message", "Unknown error")
                                break
                            # Otherwise continue polling (still queued/indexing)
                
                return json.dumps(result)
                
        except httpx.RequestError as e:
            return MCPErrorFormatter.from_exception(e, "create and index repo")
        except Exception as e:
            logger.exception(f"Error in code_repos_create_and_index: {e}")
            return MCPErrorFormatter.from_exception(e, "create and index repo")

    @mcp.tool()
    async def code_repos_get_status(
        ctx: Context,
        repo_id: str,
    ) -> str:
        """
        Get the current status of a repository.
        
        Args:
            repo_id: Repository UUID
        
        Returns:
            JSON with status, entities_count, last_synced, etc.
        
        Example:
            >>> await code_repos_get_status(repo_id="550e8400-e29b-41d4-a716-446655440000")
            {
                "repo_id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Omnibus",
                "status": "ready",
                "entities_count": 1234,
                "last_synced": "2025-01-15T10:30:00Z",
                "last_commit": "abc123..."
            }
        """
        try:
            api_url = get_api_url()
            timeout = get_default_timeout()
            
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    f"{api_url}/api/code_repos/{repo_id}/status",
                )
                
                if response.status_code == 404:
                    return MCPErrorFormatter.format_error(
                        error_type="not_found",
                        message=f"Repository {repo_id} not found",
                        suggestion="Verify the repo_id or create the repository first",
                    )
                elif response.status_code != 200:
                    return MCPErrorFormatter.from_http_error(response, "get repo status")
                
                return json.dumps({
                    "success": True,
                    **response.json()
                })
                
        except httpx.RequestError as e:
            return MCPErrorFormatter.from_exception(e, "get repo status")
        except Exception as e:
            logger.exception(f"Error in code_repos_get_status: {e}")
            return MCPErrorFormatter.from_exception(e, "get repo status")

    @mcp.tool()
    async def code_repos_list(
        ctx: Context,
    ) -> str:
        """
        List all registered code repositories.
        
        Returns:
            JSON array of repos with their current status
        
        Example:
            >>> await code_repos_list()
            {
                "success": True,
                "repos": [
                    {
                        "repo_id": "...",
                        "name": "Omnibus",
                        "local_path": "/home/zebastjan/dev/Omnibus",
                        "status": "ready",
                        "entities_count": 1234
                    }
                ]
            }
        """
        try:
            api_url = get_api_url()
            timeout = get_default_timeout()
            
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    f"{api_url}/api/code_repos",
                )
                
                if response.status_code != 200:
                    return MCPErrorFormatter.from_http_error(response, "list repos")
                
                repos = response.json()
                
                return json.dumps({
                    "success": True,
                    "repos": repos,
                    "count": len(repos),
                })
                
        except httpx.RequestError as e:
            return MCPErrorFormatter.from_exception(e, "list repos")
        except Exception as e:
            logger.exception(f"Error in code_repos_list: {e}")
            return MCPErrorFormatter.from_exception(e, "list repos")

    logger.info("code_repos_tools_registered")
