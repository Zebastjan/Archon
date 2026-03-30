"""
Consolidated task management tools for Archon MCP Server.

Uses direct service imports instead of HTTP calls.
Includes automatic worktree safety validation.
"""

import json
import logging
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from src.mcp_server.utils.error_handling import MCPErrorFormatter
from src.mcp_server.utils.tool_helpers import optimize_response, truncate_text
from src.server.services.projects.task_service import TaskService
from src.server.services.worktree_service import get_worktree_service

logger = logging.getLogger(__name__)

MAX_DESCRIPTION_LENGTH = 1000
DEFAULT_PAGE_SIZE = 10


def optimize_task_response(task: dict) -> dict:
    """Optimize task object for MCP response."""
    return optimize_response(task, description_field="description")

def register_task_tools(mcp: FastMCP):
    """Register consolidated task management tools with the MCP server."""
    
    service = TaskService()

    @mcp.tool()
    async def find_tasks(
        ctx: Context,
        query: str | None = None,
        task_id: str | None = None,
        filter_by: str | None = None,
        filter_value: str | None = None,
        project_id: str | None = None,
        include_closed: bool = True,
        page: int = 1,
        per_page: int = DEFAULT_PAGE_SIZE,
    ) -> str:
        """
        Find and search tasks (consolidated: list + search + get).
        
        Args:
            query: Keyword search in title, description, feature
            task_id: Get specific task by ID (returns full details)
            filter_by: "status" | "project" | "assignee"
            filter_value: Filter value
            project_id: Project UUID
            include_closed: Include done tasks
            page: Page number
            per_page: Items per page
        
        Returns:
            JSON array of tasks or single task
        """
        try:
            # Single task get mode
            if task_id:
                success, result = await service.get_task(task_id)
                if success:
                    return json.dumps({"success": True, "task": result["task"]})
                else:
                    return MCPErrorFormatter.format_error(
                        error_type="not_found",
                        message=result.get("error", f"Task {task_id} not found"),
                        http_status=404,
                    )

            # Determine filters
            search_project_id = project_id
            search_status = None
            
            if filter_by == "project" and filter_value:
                search_project_id = filter_value
            elif filter_by == "status" and filter_value:
                search_status = filter_value
            
            # Search with filters
            success, result = await service.list_tasks(
                project_id=search_project_id,
                status=search_status,
                include_closed=include_closed,
                exclude_large_fields=True,
                search_query=query
            )
            
            if success:
                tasks = result.get("tasks", [])
                
                # Apply pagination
                start_idx = (page - 1) * per_page
                end_idx = start_idx + per_page
                paginated = tasks[start_idx:end_idx]
                
                # Optimize responses
                optimized = [optimize_task_response(t) for t in paginated]
                
                return json.dumps({
                    "success": True,
                    "tasks": optimized,
                    "total_count": result.get("total_count", len(tasks)),
                    "count": len(optimized),
                    "query": query,
                })
            else:
                return MCPErrorFormatter.format_error(
                    "server_error",
                    result.get("error", "Failed to list tasks")
                )

        except Exception as e:
            logger.error(f"Error listing tasks: {e}", exc_info=True)
            return MCPErrorFormatter.from_exception(e, "list tasks")

    @mcp.tool()
    async def manage_task(
        ctx: Context,
        action: str,
        task_id: str | None = None,
        project_id: str | None = None,
        title: str | None = None,
        description: str | None = None,
        status: str | None = None,
        assignee: str | None = None,
        task_order: int | None = None,
        feature: str | None = None,
        file_paths: list[str] | None = None,
        entity_ids: list[str] | None = None,
        skip_worktree_validation: bool = False,
    ) -> str:
        """
        Manage tasks (consolidated: create/update/delete).

        Args:
            action: "create" | "update" | "delete"
            task_id: Task UUID for update/delete
            project_id: Project UUID for create
            title: Task title
            description: Task description
            status: "todo" | "doing" | "review" | "done"
            assignee: Assignee name
            task_order: Priority 0-100
            feature: Feature label
            file_paths: Files this task will modify
            entity_ids: Entities this task will modify
            skip_worktree_validation: Skip validation (use with caution)

        Returns: {success: bool, task?: object, message: string}
        """
        try:
            # Worktree validation for create/update
            if action in ("create", "update") and not skip_worktree_validation:
                worktree_service = get_worktree_service()
                validation = await worktree_service.validate_safe_to_work(
                    task_id=task_id,
                    file_paths=file_paths,
                    entity_ids=entity_ids,
                )
                
                if not validation.is_safe:
                    return json.dumps({
                        "success": False,
                        "error": "Worktree safety validation failed",
                        "error_type": "worktree_conflict",
                        "issues": validation.issues,
                        "warnings": validation.warnings,
                    })

            if action == "create":
                if not project_id or not title:
                    return MCPErrorFormatter.format_error(
                        "validation_error",
                        "project_id and title required for create"
                    )
                
                success, result = await service.create_task(
                    project_id=project_id,
                    title=title,
                    description=description or "",
                    assignee=assignee or "User",
                    task_order=task_order or 0,
                    feature=feature,
                    file_paths=file_paths,
                    entity_ids=entity_ids,
                    skip_worktree_validation=True,  # Already validated above
                )
                
                if success:
                    task = result.get("task", {})
                    return json.dumps({
                        "success": True,
                        "task": optimize_task_response(task),
                        "task_id": task.get("id"),
                        "message": "Task created successfully"
                    })
                else:
                    return MCPErrorFormatter.format_error(
                        "creation_failed",
                        result.get("error", "Failed to create task")
                    )

            elif action == "update":
                if not task_id:
                    return MCPErrorFormatter.format_error(
                        "validation_error",
                        "task_id required for update"
                    )
                
                update_fields = {}
                if title is not None:
                    update_fields["title"] = title
                if description is not None:
                    update_fields["description"] = description
                if status is not None:
                    update_fields["status"] = status
                if assignee is not None:
                    update_fields["assignee"] = assignee
                if task_order is not None:
                    update_fields["task_order"] = task_order
                if feature is not None:
                    update_fields["feature"] = feature
                
                if not update_fields:
                    return MCPErrorFormatter.format_error(
                        "validation_error",
                        "No fields to update"
                    )
                
                success, result = await service.update_task(
                    task_id=task_id,
                    update_fields=update_fields,
                    skip_worktree_validation=True,  # Already validated above
                )
                
                if success:
                    task = result.get("task")
                    if task:
                        task = optimize_task_response(task)
                    return json.dumps({
                        "success": True,
                        "task": task,
                        "message": result.get("message", "Task updated successfully")
                    })
                else:
                    return MCPErrorFormatter.format_error(
                        "update_failed",
                        result.get("error", "Failed to update task")
                    )

            elif action == "delete":
                if not task_id:
                    return MCPErrorFormatter.format_error(
                        "validation_error",
                        "task_id required for delete"
                    )
                
                # Archive instead of delete (soft delete)
                success, result = await service.archive_task(task_id)
                
                if success:
                    return json.dumps({
                        "success": True,
                        "message": result.get("message", "Task deleted successfully")
                    })
                else:
                    return MCPErrorFormatter.format_error(
                        "delete_failed",
                        result.get("error", "Failed to delete task")
                    )

            else:
                return MCPErrorFormatter.format_error(
                    "invalid_action",
                    f"Unknown action: {action}"
                )

        except Exception as e:
            logger.error(f"Error managing task ({action}): {e}", exc_info=True)
            return MCPErrorFormatter.from_exception(e, f"{action} task")
