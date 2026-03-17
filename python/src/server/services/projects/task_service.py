"""
Task Service Module for Archon

This module provides core business logic for task operations that can be
shared between MCP tools and FastAPI endpoints.
Includes automatic worktree safety validation.
"""

# Removed direct logging import - using unified config
from datetime import datetime
from typing import Any

from ...config.logfire_config import get_logger
from ..database import get_database_connector
from ..worktree_service import get_worktree_service

logger = get_logger(__name__)

# Task updates are handled via polling - no broadcasting needed


class TaskService:
    """Service class for task operations"""

    VALID_STATUSES = ["todo", "doing", "review", "done"]

    def __init__(self):
        """Initialize task service"""
        pass

    def validate_status(self, status: str) -> tuple[bool, str]:
        """Validate task status"""
        if status not in self.VALID_STATUSES:
            return (
                False,
                f"Invalid status '{status}'. Must be one of: {', '.join(self.VALID_STATUSES)}",
            )
        return True, ""

    def validate_assignee(self, assignee: str) -> tuple[bool, str]:
        """Validate task assignee"""
        if not assignee or not isinstance(assignee, str) or len(assignee.strip()) == 0:
            return False, "Assignee must be a non-empty string"
        return True, ""

    def validate_priority(self, priority: str) -> tuple[bool, str]:
        """Validate task priority against allowed enum values"""
        VALID_PRIORITIES = ["low", "medium", "high", "critical"]
        if priority not in VALID_PRIORITIES:
            return (
                False,
                f"Invalid priority '{priority}'. Must be one of: {', '.join(VALID_PRIORITIES)}",
            )
        return True, ""

    async def create_task(
        self,
        project_id: str,
        title: str,
        description: str = "",
        assignee: str = "User",
        task_order: int = 0,
        priority: str = "medium",
        feature: str | None = None,
        sources: list[dict[str, Any]] = None,
        code_examples: list[dict[str, Any]] = None,
        file_paths: list[str] = None,
        entity_ids: list[str] = None,
        skip_worktree_validation: bool = False,
    ) -> tuple[bool, dict[str, Any]]:
        """
        Create a new task under a project with automatic reordering and worktree safety.

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            # Automatic worktree safety validation
            if not skip_worktree_validation:
                worktree_service = get_worktree_service()
                validation = await worktree_service.validate_safe_to_work(
                    file_paths=file_paths,
                    entity_ids=entity_ids,
                )

                if not validation.is_safe:
                    logger.warning(f"Worktree validation failed for task creation: {validation.issues}")
                    return False, {
                        "error": "Worktree safety validation failed",
                        "error_type": "worktree_conflict",
                        "issues": validation.issues,
                        "warnings": validation.warnings,
                        "context": validation.context.to_dict() if validation.context else None,
                    }
                
                # Log warnings
                if validation.warnings:
                    logger.info(f"Worktree validation warnings: {validation.warnings}")
            
            # Validate inputs
            if not title or not isinstance(title, str) or len(title.strip()) == 0:
                return False, {"error": "Task title is required and must be a non-empty string"}

            if not project_id or not isinstance(project_id, str):
                return False, {"error": "Project ID is required and must be a string"}

            # Validate assignee
            is_valid, error_msg = self.validate_assignee(assignee)
            if not is_valid:
                return False, {"error": error_msg}

            # Validate priority
            is_valid, error_msg = self.validate_priority(priority)
            if not is_valid:
                return False, {"error": error_msg}

            task_status = "todo"

            # REORDERING LOGIC: If inserting at a specific position, increment existing tasks
            if task_order > 0:
                # Get all tasks in the same project and status with task_order >= new task's order
                db = get_database_connector()
                existing_tasks_response = await db.fetch(
                    """
                    SELECT id, task_order FROM archon_tasks
                    WHERE project_id = $1 AND status = $2 AND task_order >= $3
                    """,
                    project_id,
                    task_status,
                    task_order
                )

                if existing_tasks_response:
                    logger.info(f"Reordering {len(existing_tasks_response)} existing tasks")

                    # Increment task_order for all affected tasks
                    for existing_task in existing_tasks_response:
                        new_order = existing_task["task_order"] + 1
                        await db.execute(
                            """
                            UPDATE archon_tasks
                            SET task_order = $1, updated_at = $2
                            WHERE id = $3
                            """,
                            new_order,
                            datetime.now().isoformat(),
                            existing_task["id"],
                        )

            task_data = {
                "project_id": project_id,
                "title": title,
                "description": description,
                "status": task_status,
                "assignee": assignee,
                "task_order": task_order,
                "priority": priority,
                "sources": sources or [],
                "code_examples": code_examples or [],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }

            if feature:
                task_data["feature"] = feature

            # Add worktree context
            import json
            if not skip_worktree_validation:
                worktree_service = get_worktree_service()
                context = await worktree_service.get_current_context()
                if context and context.worktree_id:
                    task_data.update({
                        "worktree_id": context.worktree_id,
                        "branch_name": context.branch_name,
                        "repo_path": context.repo_path,
                        "base_branch": context.base_branch,
                        "is_isolated": True,
                        "worktree_status": "active" if context.is_clean else "conflict",
                        "merge_conflicts_expected": json.dumps(file_paths or []),
                        "entities_affected": json.dumps(entity_ids or []),
                    })

            db = get_database_connector()
            response = await db.fetch(
                """
                INSERT INTO archon_tasks
                (project_id, title, description, status, assignee, task_order, priority, sources, code_examples,
                 feature, worktree_id, branch_name, repo_path, base_branch, is_isolated, worktree_status,
                 merge_conflicts_expected, entities_affected, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20)
                RETURNING *
                """,
                task_data["project_id"],
                task_data["title"],
                task_data["description"],
                task_data["status"],
                task_data["assignee"],
                task_data["task_order"],
                task_data["priority"],
                json.dumps(task_data.get("sources", [])),
                json.dumps(task_data.get("code_examples", [])),
                task_data.get("feature"),
                task_data.get("worktree_id"),
                task_data.get("branch_name"),
                task_data.get("repo_path"),
                task_data.get("base_branch"),
                task_data.get("is_isolated"),
                task_data.get("worktree_status"),
                task_data.get("merge_conflicts_expected"),
                task_data.get("entities_affected"),
                task_data["created_at"],
                task_data["updated_at"],
            )

            if response:
                task = response[0]


                return True, {
                    "task": {
                        "id": str(task["id"]),
                        "project_id": str(task["project_id"]),
                        "title": task["title"],
                        "description": task["description"],
                        "status": task["status"],
                        "assignee": task["assignee"],
                        "task_order": task["task_order"],
                        "priority": task["priority"],
                        "created_at": task["created_at"],
                    }
                }
            else:
                return False, {"error": "Failed to create task"}

        except Exception as e:
            logger.error(f"Error creating task: {e}")
            return False, {"error": f"Error creating task: {str(e)}"}

    async def list_tasks(
        self,
        project_id: str = None,
        status: str = None,
        include_closed: bool = False,
        exclude_large_fields: bool = False,
        include_archived: bool = False,
        search_query: str = None
    ) -> tuple[bool, dict[str, Any]]:
        """
        List tasks with various filters.

        Args:
            project_id: Filter by project
            status: Filter by status
            include_closed: Include done tasks
            exclude_large_fields: If True, excludes sources and code_examples fields
            include_archived: If True, includes archived tasks
            search_query: Keyword search in title, description, and feature fields

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            db = get_database_connector()

            # Build WHERE clause dynamically
            where_clauses = []
            params = []
            param_count = 1
            filters_applied = []

            # Apply filters
            if project_id:
                where_clauses.append(f"project_id = ${param_count}")
                params.append(project_id)
                param_count += 1
                filters_applied.append(f"project_id={project_id}")

            if status:
                # Validate status
                is_valid, error_msg = self.validate_status(status)
                if not is_valid:
                    return False, {"error": error_msg}
                where_clauses.append(f"status = ${param_count}")
                params.append(status)
                param_count += 1
                filters_applied.append(f"status={status}")
            elif not include_closed:
                # Only exclude done tasks if no specific status filter is applied
                where_clauses.append("status != 'done'")
                filters_applied.append("exclude done tasks")

            # Apply keyword search if provided
            if search_query:
                search_term = f"%{search_query.lower()}%"
                where_clauses.append(
                    f"(LOWER(title) LIKE ${param_count} OR LOWER(description) LIKE ${param_count} OR LOWER(feature) LIKE ${param_count})"
                )
                params.append(search_term)
                param_count += 1
                filters_applied.append(f"search={search_query}")

            # Filter out archived tasks only if not including them
            if not include_archived:
                where_clauses.append("(archived IS NULL OR archived = false)")
                filters_applied.append("exclude archived tasks (null or false)")
            else:
                filters_applied.append("include all tasks (including archived)")

            logger.debug(f"Listing tasks with filters: {', '.join(filters_applied)}")

            # Build complete query
            where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
            query = f"SELECT * FROM archon_tasks {where_sql} ORDER BY task_order ASC, created_at ASC"

            # Execute query
            response = await db.fetch(query, *params)

            # Debug: Log task status distribution and filter effectiveness
            if response:
                status_counts = {}
                archived_counts = {"null": 0, "true": 0, "false": 0}

                for task in response:
                    task_status = task.get("status", "unknown")
                    status_counts[task_status] = status_counts.get(task_status, 0) + 1

                    # Check archived field
                    archived_value = task.get("archived")
                    if archived_value is None:
                        archived_counts["null"] += 1
                    elif archived_value is True:
                        archived_counts["true"] += 1
                    else:
                        archived_counts["false"] += 1

                logger.debug(
                    f"Retrieved {len(response)} tasks. Status distribution: {status_counts}"
                )
                logger.debug(f"Archived field distribution: {archived_counts}")

                # If we're filtering by status and getting wrong results, log sample
                if status and len(response) > 0:
                    first_task = response[0]
                    logger.warning(
                        f"Status filter: {status}, First task status: {first_task.get('status')}, archived: {first_task.get('archived')}"
                    )
            else:
                logger.debug("No tasks found with current filters")

            tasks = []
            for task in response:
                task_data = {
                    "id": str(task["id"]),
                    "project_id": str(task["project_id"]),
                    "title": task["title"],
                    "description": task["description"],
                    "status": task["status"],
                    "assignee": task.get("assignee", "User"),
                    "task_order": task.get("task_order", 0),
                    "priority": task.get("priority", "medium"),
                    "feature": task.get("feature"),
                    "created_at": task["created_at"],
                    "updated_at": task["updated_at"],
                    "archived": task.get("archived", False),
                }

                if not exclude_large_fields:
                    # Include full JSONB fields
                    task_data["sources"] = task.get("sources", [])
                    task_data["code_examples"] = task.get("code_examples", [])
                else:
                    # Add counts instead of full content
                    task_data["stats"] = {
                        "sources_count": len(task.get("sources", [])),
                        "code_examples_count": len(task.get("code_examples", []))
                    }

                tasks.append(task_data)

            filter_info = []
            if project_id:
                filter_info.append(f"project_id={project_id}")
            if status:
                filter_info.append(f"status={status}")
            if not include_closed:
                filter_info.append("excluding closed tasks")

            return True, {
                "tasks": tasks,
                "total_count": len(tasks),
                "filters_applied": ", ".join(filter_info) if filter_info else "none",
                "include_closed": include_closed,
            }

        except Exception as e:
            logger.error(f"Error listing tasks: {e}")
            return False, {"error": f"Error listing tasks: {str(e)}"}

    async def get_task(self, task_id: str) -> tuple[bool, dict[str, Any]]:
        """
        Get a specific task by ID.

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            db = get_database_connector()
            response = await db.fetch(
                "SELECT * FROM archon_tasks WHERE id = $1",
                task_id
            )

            if response:
                task = dict(response[0])
                task["id"] = str(task["id"])
                task["project_id"] = str(task["project_id"])
                return True, {"task": task}
            else:
                return False, {"error": f"Task with ID {task_id} not found"}

        except Exception as e:
            logger.error(f"Error getting task: {e}")
            return False, {"error": f"Error getting task: {str(e)}"}

    async def update_task(
        self, task_id: str, update_fields: dict[str, Any], skip_worktree_validation: bool = False
    ) -> tuple[bool, dict[str, Any]]:
        """
        Update task with specified fields and worktree safety validation.

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            # Validate worktree safety when status changes to "doing" (active work)
            if not skip_worktree_validation and update_fields.get("status") == "doing":
                worktree_service = get_worktree_service()
                validation = await worktree_service.validate_safe_to_work(
                    task_id=task_id,
                )

                if not validation.is_safe:
                    logger.warning(f"Worktree validation failed for task update: {validation.issues}")
                    return False, {
                        "error": "Worktree safety validation failed",
                        "error_type": "worktree_conflict",
                        "issues": validation.issues,
                        "warnings": validation.warnings,
                    }
            
            # Build update data
            update_data = {"updated_at": datetime.now().isoformat()}

            # Validate and add fields
            if "title" in update_fields:
                update_data["title"] = update_fields["title"]

            if "description" in update_fields:
                update_data["description"] = update_fields["description"]

            if "status" in update_fields:
                is_valid, error_msg = self.validate_status(update_fields["status"])
                if not is_valid:
                    return False, {"error": error_msg}
                update_data["status"] = update_fields["status"]

            if "assignee" in update_fields:
                is_valid, error_msg = self.validate_assignee(update_fields["assignee"])
                if not is_valid:
                    return False, {"error": error_msg}
                update_data["assignee"] = update_fields["assignee"]

            if "priority" in update_fields:
                is_valid, error_msg = self.validate_priority(update_fields["priority"])
                if not is_valid:
                    return False, {"error": error_msg}
                update_data["priority"] = update_fields["priority"]

            if "task_order" in update_fields:
                update_data["task_order"] = update_fields["task_order"]

            if "feature" in update_fields:
                update_data["feature"] = update_fields["feature"]

            # Update task
            db = get_database_connector()

            # Build SET clause dynamically
            set_clauses = []
            params = []
            param_count = 1

            for key, value in update_data.items():
                set_clauses.append(f"{key} = ${param_count}")
                params.append(value)
                param_count += 1

            # Add task_id as last parameter
            params.append(task_id)

            response = await db.fetch(
                f"UPDATE archon_tasks SET {', '.join(set_clauses)} WHERE id = ${param_count} RETURNING *",
                *params
            )

            if response:
                task = dict(response[0])
                task["id"] = str(task["id"])
                task["project_id"] = str(task["project_id"])
                return True, {"task": task, "message": "Task updated successfully"}
            else:
                return False, {"error": f"Task with ID {task_id} not found"}

        except Exception as e:
            logger.error(f"Error updating task: {e}")
            return False, {"error": f"Error updating task: {str(e)}"}

    async def archive_task(
        self, task_id: str, archived_by: str = "mcp"
    ) -> tuple[bool, dict[str, Any]]:
        """
        Archive a task and all its subtasks (soft delete).

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            db = get_database_connector()

            # First, check if task exists and is not already archived
            task_response = await db.fetch(
                "SELECT * FROM archon_tasks WHERE id = $1",
                task_id
            )

            if not task_response:
                return False, {"error": f"Task with ID {task_id} not found"}

            task = dict(task_response[0])
            if task.get("archived") is True:
                return False, {"error": f"Task with ID {task_id} is already archived"}

            # Archive the main task
            response = await db.fetch(
                """
                UPDATE archon_tasks
                SET archived = $1, archived_at = $2, archived_by = $3, updated_at = $4
                WHERE id = $5
                RETURNING *
                """,
                True,
                datetime.now().isoformat(),
                archived_by,
                datetime.now().isoformat(),
                task_id
            )

            if response:
                return True, {"task_id": task_id, "message": "Task archived successfully"}
            else:
                return False, {"error": f"Failed to archive task {task_id}"}

        except Exception as e:
            logger.error(f"Error archiving task: {e}")
            return False, {"error": f"Error archiving task: {str(e)}"}

    async def get_all_project_task_counts(self) -> tuple[bool, dict[str, dict[str, int]]]:
        """
        Get task counts for all projects in a single optimized query.

        Returns task counts grouped by project_id and status.

        Returns:
            Tuple of (success, counts_dict) where counts_dict is:
            {"project-id": {"todo": 5, "doing": 2, "review": 3, "done": 10}}
        """
        try:
            logger.debug("Fetching task counts for all projects in batch")

            db = get_database_connector()

            # Query all non-archived tasks grouped by project_id and status
            response = await db.fetch(
                """
                SELECT project_id, status
                FROM archon_tasks
                WHERE archived IS NULL OR archived = false
                """
            )

            if not response:
                logger.debug("No tasks found")
                return True, {}

            # Process results into counts by project and status
            counts_by_project = {}

            for task in response:
                project_id = str(task.get("project_id")) if task.get("project_id") else None
                status = task.get("status")

                if not project_id or not status:
                    continue

                # Initialize project counts if not exists
                if project_id not in counts_by_project:
                    counts_by_project[project_id] = {
                        "todo": 0,
                        "doing": 0,
                        "review": 0,
                        "done": 0
                    }

                # Count all statuses separately
                if status in ["todo", "doing", "review", "done"]:
                    counts_by_project[project_id][status] += 1

            logger.debug(f"Task counts fetched for {len(counts_by_project)} projects")

            return True, counts_by_project

        except Exception as e:
            logger.error(f"Error fetching task counts: {e}")
            return False, {"error": f"Error fetching task counts: {str(e)}"}
