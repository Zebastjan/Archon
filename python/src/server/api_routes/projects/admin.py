"""
Projects Admin API Routes

Administrative endpoints for project management:
- Health checks
- Task counts
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response

from ...config.logfire_config import get_logger, logfire
from ...services.projects import ProjectService, TaskService
from ...utils import get_supabase_client

logger = get_logger(__name__)
router = APIRouter()


@router.get("/projects/health")
async def projects_health() -> dict[str, Any]:
    """Health check for projects API and database schema validation."""
    try:
        logfire.info("Projects health check requested")
        supabase_client = get_supabase_client()

        # Check if projects table exists by testing ProjectService
        try:
            project_service = ProjectService(supabase_client)
            # Try to list projects with limit 1 to test table access
            success, _ = await project_service.list_projects()
            projects_table_exists = success
            if success:
                logfire.info("Projects table detected successfully")
            else:
                logfire.warning("Projects table access failed")
        except Exception as e:
            projects_table_exists = False
            logfire.warning(f"Projects table not found | error={str(e)}")

        # Check if tasks table exists by testing TaskService
        try:
            task_service = TaskService(supabase_client)
            # Try to list tasks with limit 1 to test table access
            success, _ = await task_service.list_tasks(include_closed=True)
            tasks_table_exists = success
            if success:
                logfire.info("Tasks table detected successfully")
            else:
                logfire.warning("Tasks table access failed")
        except Exception as e:
            tasks_table_exists = False
            logfire.warning(f"Tasks table not found | error={str(e)}")

        schema_valid = projects_table_exists and tasks_table_exists

        result = {
            "status": "healthy" if schema_valid else "schema_missing",
            "service": "projects",
            "schema": {
                "projects_table": projects_table_exists,
                "tasks_table": tasks_table_exists,
                "valid": schema_valid,
            },
        }

        logfire.info(f"Projects health check completed | status={result['status']} | schema_valid={schema_valid}")

        return result

    except Exception as e:
        logfire.error(f"Projects health check failed | error={str(e)}")
        return {
            "status": "error",
            "service": "projects",
            "error": str(e),
            "schema": {"projects_table": False, "tasks_table": False, "valid": False},
        }


@router.get("/projects/task-counts")
async def get_all_task_counts(
    request: Request,
    response: Response,
    if_none_match: str | None = None,
) -> dict[str, Any]:
    """
    Get task counts across all projects with ETag support.

    Returns counts per status and per project for dashboard display.
    """
    try:
        from email.utils import format_datetime
        from datetime import datetime, UTC

        logfire.debug("Fetching task counts for all projects")

        supabase_client = get_supabase_client()

        # Get all tasks
        task_service = TaskService(supabase_client)
        success, result = await task_service.list_tasks(include_closed=True)

        if not success:
            logfire.error(f"Failed to fetch tasks | error={result}")
            raise HTTPException(status_code=500, detail=result)

        tasks = result.get("tasks", [])

        # Calculate counts by status
        status_counts = {
            "todo": 0,
            "doing": 0,
            "review": 0,
            "done": 0,
            "total": len(tasks),
        }

        for task in tasks:
            status = task.get("status", "todo")
            if status in status_counts:
                status_counts[status] += 1

        # Calculate counts by project
        project_counts = {}
        for task in tasks:
            project_id = task.get("project_id")
            if project_id:
                if project_id not in project_counts:
                    project_counts[project_id] = {
                        "total": 0,
                        "todo": 0,
                        "doing": 0,
                        "review": 0,
                        "done": 0,
                    }
                project_counts[project_id]["total"] += 1
                status = task.get("status", "todo")
                if status in project_counts[project_id]:
                    project_counts[project_id][status] += 1

        # Generate ETag
        from ...utils.etag_utils import generate_etag, check_etag

        etag_data = {
            "status_counts": status_counts,
            "project_count": len(project_counts),
            "total_tasks": len(tasks),
        }
        current_etag = generate_etag(etag_data)

        # Check if client's ETag matches
        if check_etag(if_none_match, current_etag):
            response.status_code = 304
            response.headers["ETag"] = current_etag
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
            logfire.debug("Task counts unchanged, returning 304")
            return None

        response.headers["ETag"] = current_etag
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
        response.headers["Last-Modified"] = format_datetime(datetime.now(UTC))

        logfire.debug(
            f"Task counts retrieved | total={len(tasks)} | projects={len(project_counts)} | "
            f"todo={status_counts['todo']} | doing={status_counts['doing']}"
        )

        return {
            "status_counts": status_counts,
            "project_counts": project_counts,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Failed to get task counts | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})
