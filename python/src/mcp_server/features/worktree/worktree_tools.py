"""MCP tools for worktree safety and branch isolation.

Prevents conflicts when multiple OctoFriend instances or agents
work on different branches/worktrees simultaneously.
"""

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from src.mcp_server.utils.error_handling import MCPErrorFormatter
from src.server.config.logfire_config import get_logger
from src.server.services.worktree_service import get_worktree_service, WorktreeContext

logger = get_logger(__name__)


def register_worktree_tools(mcp: FastMCP) -> None:
    """Register worktree safety MCP tools."""
    logger.info("registering_worktree_tools")

    @mcp.tool()
    async def worktree_get_current_info() -> dict[str, Any]:
        """
        Get current worktree context.
        
        Auto-detects git worktree, branch, and repository information.
        
        Returns:
            Dict with worktree context:
            - is_worktree: Whether current directory is a worktree
            - worktree_id: Stable UUID for this worktree
            - branch_name: Current git branch
            - repo_path: Absolute path to worktree
            - base_branch: Branch this worktree was created from
            - git_root: Root of git repository
            - is_clean: Whether working directory is clean
            - uncommitted_changes: List of modified files
        
        Example:
            >>> await worktree_get_current_info()
            {
                "success": True,
                "context": {
                    "is_worktree": True,
                    "worktree_id": "550e8400-e29b-41d4-a716-446655440000",
                    "branch_name": "feature/new-auth",
                    "repo_path": "/home/user/dev/archon/.worktrees/feature-new-auth",
                    "base_branch": "main",
                    "is_clean": False,
                    "uncommitted_changes": ["src/auth.py", "src/config.py"]
                }
            }
        """
        try:
            service = get_worktree_service()
            context = service.detect_worktree_context()
            
            return {
                "success": True,
                "context": context.to_dict(),
            }
            
        except Exception as e:
            logger.exception("worktree_get_current_info_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
            }

    @mcp.tool()
    async def worktree_validate_safe_to_work(
        task_id: str | None = None,
        file_paths: list[str] | None = None,
        entity_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Validate if it's safe to start/modify work in current context.
        
        Checks for:
        - Task active in another worktree
        - Concurrent modifications to same files/entities
        - Worktree locked by another process
        - Branch mismatches
        - Uncommitted changes
        
        Args:
            task_id: Optional task ID to check
            file_paths: Files that will be modified
            entity_ids: Entity IDs that will be modified
        
        Returns:
            Dict with validation result:
            - is_safe: True if safe to proceed
            - issues: List of blocking issues (error severity)
            - warnings: List of warnings (warning severity)
            - context: Current worktree context
        
        Example:
            >>> await worktree_validate_safe_to_work(
            ...     file_paths=["src/auth.py", "src/config.py"],
            ...     entity_ids=["entity-001", "entity-002"]
            ... )
        """
        try:
            service = get_worktree_service()
            
            result = await service.validate_safe_to_work(
                task_id=task_id,
                file_paths=file_paths,
                entity_ids=entity_ids,
            )
            
            # Parse JSON strings if needed
            issues = result.issues
            warnings = result.warnings
            
            # Handle case where database returns JSON as string
            if isinstance(issues, str):
                import json
                try:
                    issues = json.loads(issues)
                except:
                    issues = []
            if isinstance(warnings, str):
                import json
                try:
                    warnings = json.loads(warnings)
                except:
                    warnings = []
            
            return {
                "success": True,
                "is_safe": result.is_safe,
                "issues": issues,
                "warnings": warnings,
                "context": result.context.to_dict() if result.context else None,
            }
            
        except Exception as e:
            logger.exception("worktree_validate_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
                "is_safe": False,
            }

    @mcp.tool()
    async def worktree_find_conflicts(
        worktree_id: str | None = None,
        file_paths: list[str] | None = None,
        entity_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Find potential conflicts between this worktree and others.
        
        Identifies tasks in other worktrees that:
        - Modify the same files
        - Affect the same entities (functions, classes, etc.)
        - Are in active status (doing, review)
        
        Args:
            worktree_id: Optional worktree ID (defaults to current)
            file_paths: Files to check for conflicts
            entity_ids: Entities to check for conflicts
        
        Returns:
            Dict with conflicts found:
            - conflicts: List of conflicting tasks
            - by_severity: Count by severity level
        
        Example:
            >>> await worktree_find_conflicts(
            ...     file_paths=["src/auth.py"]
            ... )
        """
        try:
            service = get_worktree_service()
            
            conflicts = await service.find_conflicts(
                worktree_id=worktree_id,
                file_paths=file_paths,
                entity_ids=entity_ids,
            )
            
            by_severity = {"critical": 0, "warning": 0, "info": 0}
            for conflict in conflicts:
                sev = conflict.get("conflict_severity", "info")
                by_severity[sev] = by_severity.get(sev, 0) + 1
            
            return {
                "success": True,
                "conflict_count": len(conflicts),
                "by_severity": by_severity,
                "conflicts": conflicts[:20],  # Limit results
            }
            
        except Exception as e:
            logger.exception("worktree_find_conflicts_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
                "conflicts": [],
            }

    @mcp.tool()
    async def worktree_list_all() -> dict[str, Any]:
        """
        List all active worktrees and their task counts.
        
        Shows all worktrees that have active tasks, with:
        - Task counts by status
        - Branch names
        - Last activity
        
        Returns:
            Dict with worktree summaries
        
        Example:
            >>> await worktree_list_all()
            {
                "success": True,
                "worktrees": [
                    {
                        "worktree_id": "...",
                        "branch_name": "feature/new-auth",
                        "active_task_count": 5,
                        "doing_count": 2,
                        "last_activity": "2025-01-15T10:30:00Z"
                    }
                ]
            }
        """
        try:
            service = get_worktree_service()
            worktrees = await service.list_worktrees()
            
            return {
                "success": True,
                "count": len(worktrees),
                "worktrees": worktrees,
            }
            
        except Exception as e:
            logger.exception("worktree_list_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
                "worktrees": [],
            }

    @mcp.tool()
    async def worktree_create_task(
        project_id: str,
        title: str,
        description: str = "",
        file_paths: list[str] | None = None,
        entity_ids: list[str] | None = None,
        assignee: str = "User",
        priority: str = "medium",
        feature: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a task with automatic worktree context.
        
        Automatically detects worktree context and validates safety
        before creating the task.
        
        Args:
            project_id: Project ID
            title: Task title
            description: Task description
            file_paths: Files this task will modify
            entity_ids: Entities this task will modify
            assignee: Task assignee
            priority: Task priority (low/medium/high/critical)
            feature: Feature label
        
        Returns:
            Dict with created task or error
        
        Example:
            >>> await worktree_create_task(
            ...     project_id="proj-123",
            ...     title="Refactor authentication",
            ...     file_paths=["src/auth.py"],
            ...     entity_ids=["UserAuthenticator"]
            ... )
        """
        try:
            service = get_worktree_service()
            
            # Validate safety first
            validation = await service.validate_safe_to_work(
                file_paths=file_paths,
                entity_ids=entity_ids,
            )
            
            if not validation.is_safe:
                return {
                    "success": False,
                    "error": "Worktree safety validation failed",
                    "issues": validation.issues,
                    "warnings": validation.warnings,
                }
            
            # Create task with worktree context
            success, result = await service.create_worktree_task(
                project_id=project_id,
                title=title,
                description=description,
                file_paths=file_paths,
                entity_ids=entity_ids,
                assignee=assignee,
                priority=priority,
                feature=feature,
            )
            
            if success:
                return {
                    "success": True,
                    "task": result.get("task"),
                    "warnings": validation.warnings,
                    "message": "Task created with worktree context",
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Failed to create task"),
                }
                
        except Exception as e:
            logger.exception("worktree_create_task_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
            }

    @mcp.tool()
    async def worktree_sync_task_context(task_id: str) -> dict[str, Any]:
        """
        Sync worktree context for a task.
        
        Updates task with current git context (useful after branch switch).
        
        Args:
            task_id: Task ID to sync
        
        Returns:
            Dict with sync result
        """
        try:
            service = get_worktree_service()
            success = await service.sync_worktree_context(task_id)
            
            return {
                "success": success,
                "message": "Task context synced" if success else "Failed to sync context",
            }
            
        except Exception as e:
            logger.exception("worktree_sync_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
            }

    @mcp.tool()
    async def worktree_lock(
        worktree_id: str,
        locked: bool = True,
        reason: str = "",
    ) -> dict[str, Any]:
        """
        Lock or unlock a worktree.
        
        Locked worktrees prevent new tasks from being created,
        useful when:
        - Running automated operations
        - Performing maintenance
        - Resolving conflicts
        
        Args:
            worktree_id: Worktree to lock/unlock
            locked: True to lock, False to unlock
            reason: Reason for locking
        
        Returns:
            Dict with lock result
        """
        try:
            service = get_worktree_service()
            success = await service.lock_worktree(worktree_id, locked)
            
            return {
                "success": success,
                "worktree_id": worktree_id,
                "locked": locked,
                "reason": reason,
                "message": f"Worktree {'locked' if locked else 'unlocked'}",
            }
            
        except Exception as e:
            logger.exception("worktree_lock_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
            }

    logger.info("worktree_tools_registered")
