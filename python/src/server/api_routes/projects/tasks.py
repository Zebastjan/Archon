"""
Task Management API Routes

Handles task CRUD operations:
- List, create, update, delete tasks
- MCP task status updates
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi import status as http_status
from email.utils import format_datetime

from ...config.logfire_config import get_logger, logfire
from ...services.projects import TaskService
from ...utils.etag_utils import check_etag, generate_etag
from ...utils.service_result_handler import handle_service_result
from .models import CreateTaskRequest, UpdateTaskRequest

logger = get_logger(__name__)
router = APIRouter()


@router.get("/projects/{project_id}/tasks")
async def list_project_tasks(
    project_id: str,
    request: Request,
    response: Response,
    include_archived: bool = False,
    exclude_large_fields: bool = False,
) -> list[dict[str, Any]]:
    """List all tasks for a specific project with ETag support for efficient polling."""
    try:
        # Get If-None-Match header for ETag comparison
        if_none_match = request.headers.get("If-None-Match")

        logfire.debug(
            f"Listing project tasks | project_id={project_id} | include_archived={include_archived} | "
            f"exclude_large_fields={exclude_large_fields} | etag={if_none_match}"
        )

        # Use TaskService to list tasks
        task_service = TaskService()
        success, result = await task_service.list_tasks(
            project_id=project_id,
            include_closed=True,  # Get all tasks, including done
            exclude_large_fields=exclude_large_fields,
            include_archived=include_archived,
        )

        if not success:
            raise HTTPException(status_code=500, detail=result)

        tasks = result.get("tasks", [])

        # Generate ETag from task data
        etag_tasks: list[dict[str, object]] = []
        last_modified_dt: datetime | None = None

        for task in tasks:
            raw_updated = task.get("updated_at")
            parsed_updated: datetime | None = None
            if isinstance(raw_updated, datetime):
                parsed_updated = raw_updated
            elif isinstance(raw_updated, str):
                try:
                    parsed_updated = datetime.fromisoformat(raw_updated.replace("Z", "+00:00"))
                except ValueError:
                    parsed_updated = None

            if parsed_updated is not None:
                parsed_updated = parsed_updated.astimezone(UTC)
                if last_modified_dt is None or parsed_updated > last_modified_dt:
                    last_modified_dt = parsed_updated

            etag_tasks.append(
                {
                    "id": task.get("id") or "",
                    "title": task.get("title") or "",
                    "status": task.get("status") or "",
                    "task_order": task.get("task_order") or 0,
                    "assignee": task.get("assignee") or "",
                    "priority": task.get("priority") or "",
                    "feature": task.get("feature") or "",
                    "description": task.get("description") or "",
                    "updated_at": (
                        parsed_updated.isoformat()
                        if parsed_updated is not None
                        else (str(raw_updated) if raw_updated else "")
                    ),
                }
            )

        etag_data = {"tasks": etag_tasks, "project_id": project_id, "count": len(tasks)}
        current_etag = generate_etag(etag_data)

        # Check if client's ETag matches (304 Not Modified)
        if check_etag(if_none_match, current_etag):
            response.status_code = 304
            response.headers["ETag"] = current_etag
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
            response.headers["Last-Modified"] = format_datetime(last_modified_dt or datetime.now(UTC))
            logfire.debug(f"Tasks unchanged, returning 304 | project_id={project_id} | etag={current_etag}")
            return None

        # Set ETag headers for successful response
        response.headers["ETag"] = current_etag
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
        response.headers["Last-Modified"] = format_datetime(last_modified_dt or datetime.now(UTC))

        logfire.debug(
            f"Project tasks retrieved | project_id={project_id} | task_count={len(tasks)} | etag={current_etag}"
        )

        return tasks

    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Failed to list project tasks | project_id={project_id}", exc_info=True)
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.post("/tasks")
async def create_task(request: CreateTaskRequest) -> dict[str, Any]:
    """Create a new task with automatic reordering."""
    try:
        # Use TaskService to create the task
        task_service = TaskService()
        success, result = await task_service.create_task(
            project_id=request.project_id,
            title=request.title,
            description=request.description or "",
            assignee=request.assignee or "User",
            task_order=request.task_order or 0,
            priority=request.priority or "medium",
            feature=request.feature,
        )

        if not success:
            raise HTTPException(status_code=400, detail=result)

        created_task = result["task"]

        logfire.info(f"Task created successfully | task_id={created_task['id']} | project_id={request.project_id}")

        return {"message": "Task created successfully", "task": created_task}

    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Failed to create task | error={str(e)} | project_id={request.project_id}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.get("/tasks")
async def list_tasks(
    status: str | None = None,
    project_id: str | None = None,
    include_closed: bool = True,
    page: int = 1,
    per_page: int = 10,
    exclude_large_fields: bool = False,
    q: str | None = None,
) -> dict[str, Any]:
    """List tasks with optional filters including status, project, and keyword search."""
    try:
        logfire.info(
            f"Listing tasks | status={status} | project_id={project_id} | include_closed={include_closed} | "
            f"page={page} | per_page={per_page} | q={q}"
        )

        # Use TaskService to list tasks
        task_service = TaskService()
        success, result = await task_service.list_tasks(
            project_id=project_id,
            status=status,
            include_closed=include_closed,
            exclude_large_fields=exclude_large_fields,
            search_query=q,
        )

        if not success:
            raise HTTPException(status_code=500, detail=result)

        tasks = result.get("tasks", [])

        # Apply pagination
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_tasks = tasks[start_idx:end_idx]

        response = {
            "tasks": paginated_tasks,
            "pagination": {
                "total": len(tasks),
                "page": page,
                "per_page": per_page,
                "pages": (len(tasks) + per_page - 1) // per_page,
            },
        }

        logfire.info(f"Tasks listed successfully | count={len(paginated_tasks)}")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Failed to list tasks | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.get("/tasks/{task_id}")
async def get_task(task_id: str) -> dict[str, Any]:
    """Get a specific task by ID."""
    try:
        # Use TaskService to get the task
        task_service = TaskService()
        success, result = await task_service.get_task(task_id)

        result = handle_service_result(success, result, resource_type="task", resource_id=task_id)

        task = result["task"]

        logfire.info(f"Task retrieved successfully | task_id={task_id} | project_id={task.get('project_id')}")

        return task

    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Failed to get task | error={str(e)} | task_id={task_id}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.put("/tasks/{task_id}")
async def update_task(task_id: str, request: UpdateTaskRequest) -> dict[str, Any]:
    """Update a task."""
    try:
        # Build update fields dictionary
        update_fields = {}
        if request.title is not None:
            update_fields["title"] = request.title
        if request.description is not None:
            update_fields["description"] = request.description
        if request.status is not None:
            update_fields["status"] = request.status
        if request.assignee is not None:
            update_fields["assignee"] = request.assignee
        if request.task_order is not None:
            update_fields["task_order"] = request.task_order
        if request.priority is not None:
            update_fields["priority"] = request.priority
        if request.feature is not None:
            update_fields["feature"] = request.feature

        # Use TaskService to update the task
        task_service = TaskService()
        success, result = await task_service.update_task(task_id, update_fields)

        result = handle_service_result(success, result, resource_type="task", resource_id=task_id)

        updated_task = result["task"]

        logfire.info(
            f"Task updated successfully | task_id={task_id} | project_id={updated_task.get('project_id')} | "
            f"updated_fields={list(update_fields.keys())}"
        )

        return {"message": "Task updated successfully", "task": updated_task}

    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Failed to update task | error={str(e)} | task_id={task_id}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str) -> dict[str, Any]:
    """Archive a task (soft delete)."""
    try:
        # Use TaskService to archive the task
        task_service = TaskService()
        success, result = await task_service.archive_task(task_id, archived_by="api")

        result = handle_service_result(success, result, resource_type="task", resource_id=task_id)

        logfire.info(f"Task archived successfully | task_id={task_id}")

        return {"message": result.get("message", "Task archived successfully")}

    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Failed to archive task | error={str(e)} | task_id={task_id}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.put("/mcp/tasks/{task_id}/status")
async def mcp_update_task_status(task_id: str, status: str) -> dict[str, Any]:
    """Update task status via MCP tools."""
    try:
        logfire.info(f"MCP task status update | task_id={task_id} | status={status}")

        # Use TaskService to update the task
        task_service = TaskService()
        success, result = await task_service.update_task(task_id=task_id, update_fields={"status": status})

        result = handle_service_result(success, result, resource_type="task", resource_id=task_id)

        updated_task = result["task"]
        project_id = updated_task["project_id"]

        logfire.info(f"Task status updated | task_id={task_id} | project_id={project_id} | status={status}")

        return {"message": "Task status updated successfully", "task": updated_task}

    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Failed to update task status | error={str(e)} | task_id={task_id}")
        raise HTTPException(status_code=500, detail=str(e))
