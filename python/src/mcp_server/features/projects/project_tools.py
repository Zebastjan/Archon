"""
Consolidated project management tools for Archon MCP Server.

Uses direct service imports instead of HTTP calls.
"""

import json
import logging
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from src.mcp_server.utils.error_handling import MCPErrorFormatter
from src.mcp_server.utils.tool_helpers import optimize_response, truncate_text
from src.server.services.projects.project_service import ProjectService

logger = logging.getLogger(__name__)

# Optimization constants
DEFAULT_PAGE_SIZE = 10


def optimize_project_response(project: dict) -> dict:
    """Optimize project object for MCP response."""
    return optimize_response(project, description_field="description")

def register_project_tools(mcp: FastMCP):
    """Register consolidated project management tools with the MCP server."""
    
    service = ProjectService()

    @mcp.tool()
    async def find_projects(
        ctx: Context,
        project_id: str | None = None,
        query: str | None = None,
        page: int = 1,
        per_page: int = DEFAULT_PAGE_SIZE,
    ) -> str:
        """
        List and search projects (consolidated: list + search + get).
        
        Args:
            project_id: Get specific project by ID (returns full details)
            query: Keyword search in title/description
            page: Page number for pagination  
            per_page: Items per page (default: 10)
        
        Returns:
            JSON array of projects or single project
        """
        try:
            # Single project get mode
            if project_id:
                success, result = await service.get_project(project_id)
                if success:
                    return json.dumps({"success": True, "project": result["project"]})
                else:
                    return MCPErrorFormatter.format_error(
                        error_type="not_found",
                        message=result.get("error", f"Project {project_id} not found"),
                        http_status=404,
                    )

            # List mode
            success, result = await service.list_projects(include_content=False)
            
            if success:
                projects = result.get("projects", [])
                
                # Apply search filter if provided
                if query:
                    query_lower = query.lower()
                    projects = [
                        p for p in projects
                        if query_lower in p.get("title", "").lower()
                        or query_lower in p.get("description", "").lower()
                    ]
                
                # Apply pagination
                start_idx = (page - 1) * per_page
                end_idx = start_idx + per_page
                paginated = projects[start_idx:end_idx]
                
                # Optimize project responses
                optimized = [optimize_project_response(p) for p in paginated]
                
                return json.dumps({
                    "success": True,
                    "projects": optimized,
                    "count": len(optimized),
                    "total": len(projects),
                    "page": page,
                    "per_page": per_page,
                    "query": query
                })
            else:
                return MCPErrorFormatter.format_error(
                    "server_error",
                    result.get("error", "Failed to list projects")
                )

        except Exception as e:
            logger.error(f"Error listing projects: {e}", exc_info=True)
            return MCPErrorFormatter.from_exception(e, "list projects")

    @mcp.tool()
    async def manage_project(
        ctx: Context,
        action: str,
        project_id: str | None = None,
        title: str | None = None,
        description: str | None = None,
        github_repo: str | None = None,
    ) -> str:
        """
        Manage projects (consolidated: create/update/delete).
        
        Args:
            action: "create" | "update" | "delete"
            project_id: Project UUID for update/delete
            title: Project title (required for create)
            description: Project goals and scope
            github_repo: GitHub URL
        
        Returns: {success: bool, project?: object, message: string}
        """
        try:
            if action == "create":
                if not title:
                    return MCPErrorFormatter.format_error(
                        "validation_error",
                        "title required for create"
                    )
                
                success, result = await service.create_project(
                    title=title,
                    github_repo=github_repo
                )
                
                if success:
                    project = result.get("project", {})
                    return json.dumps({
                        "success": True,
                        "project": optimize_project_response(project),
                        "project_id": project.get("id"),
                        "message": "Project created successfully"
                    })
                else:
                    return MCPErrorFormatter.format_error(
                        "creation_failed",
                        result.get("error", "Failed to create project")
                    )

            elif action == "update":
                if not project_id:
                    return MCPErrorFormatter.format_error(
                        "validation_error",
                        "project_id required for update"
                    )
                
                update_fields = {}
                if title is not None:
                    update_fields["title"] = title
                if description is not None:
                    update_fields["description"] = description
                if github_repo is not None:
                    update_fields["github_repo"] = github_repo
                
                if not update_fields:
                    return MCPErrorFormatter.format_error(
                        "validation_error",
                        "No fields to update"
                    )
                
                success, result = await service.update_project(project_id, update_fields)
                
                if success:
                    project = result.get("project")
                    if project:
                        project = optimize_project_response(project)
                    return json.dumps({
                        "success": True,
                        "project": project,
                        "message": "Project updated successfully"
                    })
                else:
                    return MCPErrorFormatter.format_error(
                        "update_failed",
                        result.get("error", "Failed to update project")
                    )

            elif action == "delete":
                if not project_id:
                    return MCPErrorFormatter.format_error(
                        "validation_error",
                        "project_id required for delete"
                    )
                
                success, result = await service.delete_project(project_id)
                
                if success:
                    return json.dumps({
                        "success": True,
                        "message": result.get("message", "Project deleted successfully")
                    })
                else:
                    return MCPErrorFormatter.format_error(
                        "delete_failed",
                        result.get("error", "Failed to delete project")
                    )

            else:
                return MCPErrorFormatter.format_error(
                    "invalid_action",
                    f"Unknown action: {action}"
                )

        except Exception as e:
            logger.error(f"Error managing project ({action}): {e}", exc_info=True)
            return MCPErrorFormatter.from_exception(e, f"{action} project")
