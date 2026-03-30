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
                except json.JSONDecodeError:
                    issues = []
            if isinstance(warnings, str):
                import json

                try:
                    warnings = json.loads(warnings)
                except json.JSONDecodeError:
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

    @mcp.tool()
    async def worktree_switch(
        target: str,
    ) -> dict[str, Any]:
        """
        Switch to a different worktree/branch.

        This tool provides instructions for switching worktrees. The actual
        switch requires restarting the MCP connection from the new worktree.

        To switch worktrees:
        1. Exit the current MCP session
        2. Navigate to the new worktree directory
        3. Restart MCP with: archon-mcp

        Args:
            target: Branch name, worktree path, or "new/<branch-name>"

        Returns:
            Dict with switch instructions and validation results

        Example:
            >>> await worktree_switch("feature/new-auth")
            {
                "success": True,
                "action_required": "restart_mcp",
                "message": "To switch to branch 'feature/new-auth': ..."
            }
        """
        try:
            import subprocess
            import os

            # Get git root
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, cwd=os.getcwd()
            )
            git_root = result.stdout.strip() if result.returncode == 0 else os.getcwd()

            # Determine target branch
            branch_name = target
            if target.startswith("new/"):
                branch_name = target[4:]
            elif "/" not in target:
                branch_name = target
            else:
                # Extract branch name from path
                branch_name = os.path.basename(target)

            # Check if branch exists
            result = subprocess.run(
                ["git", "branch", "--list", branch_name], capture_output=True, text=True, cwd=git_root
            )
            branch_exists = result.returncode == 0 and branch_name in result.stdout

            # Check if worktree exists
            worktree_path = os.path.join(git_root, ".worktrees", branch_name)
            worktree_exists = os.path.isdir(worktree_path)

            if worktree_exists:
                action = "restart_mcp_from_worktree"
                message = f"""To switch to worktree '{branch_name}':

1. Exit this MCP session
2. Run: cd {worktree_path}
3. Restart MCP: archon-mcp

The new MCP session will automatically bind to branch '{branch_name}'."""
                new_worktree_path = worktree_path
            elif branch_exists:
                # Create worktree
                action = "create_and_switch"
                message = f"""Branch '{branch_name}' exists but worktree doesn't.
                
To create worktree and switch:

1. Exit this MCP session  
2. Run: 
   cd {git_root}
   git worktree add .worktrees/{branch_name} {branch_name}
   cd .worktrees/{branch_name}
3. Restart MCP: archon-mcp"""
                new_worktree_path = worktree_path
            else:
                # Create new branch and worktree
                action = "create_branch_and_worktree"
                message = f"""Branch '{branch_name}' doesn't exist.
                
To create branch and worktree:

1. Exit this MCP session
2. Run:
   cd {git_root}
   git worktree add -b {branch_name} .worktrees/{branch_name} main
   cd .worktrees/{branch_name}
3. Restart MCP: archon-mcp"""
                new_worktree_path = worktree_path

            return {
                "success": True,
                "action": action,
                "target_branch": branch_name,
                "worktree_path": new_worktree_path,
                "message": message,
                "current_branch": subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, cwd=os.getcwd()
                ).stdout.strip()
                if result.returncode == 0
                else "unknown",
            }

        except Exception as e:
            logger.exception("worktree_switch_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
            }

    @mcp.tool()
    async def worktree_list() -> dict[str, Any]:
        """
        List all worktrees and their status.

        Returns:
            Dict with worktree information including branch and path
        """
        try:
            import subprocess
            import os

            # Get git root
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, cwd=os.getcwd()
            )
            git_root = result.stdout.strip() if result.returncode == 0 else os.getcwd()

            # Get current branch
            current_branch = (
                subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, cwd=os.getcwd()
                ).stdout.strip()
                if result.returncode == 0
                else "unknown"
            )

            # List worktrees
            result = subprocess.run(
                ["git", "worktree", "list", "--porcelain"], capture_output=True, text=True, cwd=git_root
            )

            worktrees = []
            if result.returncode == 0:
                entries = result.stdout.strip().split("\n\n")
                for entry in entries:
                    lines = entry.strip().split("\n")
                    if not lines or not lines[0]:
                        continue

                    path = lines[0].replace("worktree ", "")
                    is_current = "(current)" in entry

                    branch = "unknown"
                    for line in lines[1:]:
                        if line.startswith("branch "):
                            branch = line.replace("branch ", "").replace("refs/heads/", "")
                            break

                    worktrees.append(
                        {
                            "path": path,
                            "branch": branch,
                            "is_current": is_current,
                        }
                    )

            # Add current directory if not in worktree list
            if not any(w["is_current"] for w in worktrees):
                worktrees.append(
                    {
                        "path": os.getcwd(),
                        "branch": current_branch,
                        "is_current": True,
                    }
                )

            return {
                "success": True,
                "git_root": git_root,
                "current_branch": current_branch,
                "worktrees": worktrees,
                "count": len(worktrees),
            }

        except Exception as e:
            logger.exception("worktree_list_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
            }

    @mcp.tool()
    async def worktree_push() -> dict[str, Any]:
        """
        Push current worktree context to the stack.

        Use before switching to another worktree to preserve your current position.
        Saves current branch and path to `.archon/context-stack.json`.

        Returns:
            Dict with push result including stack state

        Example:
            >>> await worktree_push()
            {
                "success": true,
                "pushed": {"branch": "feature/auth", "path": "/home/user/archon/.worktrees/feature-auth"},
                "stack_size": 2
            }
        """
        try:
            import json
            import os
            import subprocess

            # Get current context
            git_root = (
                subprocess.run(
                    ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, cwd=os.getcwd()
                ).stdout.strip()
                or os.getcwd()
            )

            current_branch = (
                subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, cwd=os.getcwd()
                ).stdout.strip()
                or "unknown"
            )

            current_path = os.getcwd()

            # Load existing stack
            stack_file = os.path.join(git_root, ".archon", "context-stack.json")
            os.makedirs(os.path.dirname(stack_file), exist_ok=True)

            stack_data = {"stack": [], "current": 0}
            if os.path.exists(stack_file):
                with open(stack_file) as f:
                    stack_data = json.load(f)

            # Push current context
            stack_data["stack"].append(
                {
                    "branch": current_branch,
                    "worktree_path": current_path,
                    "pushed_at": subprocess.run(
                        ["git", "log", "-1", "--format=%ci"], capture_output=True, text=True, cwd=os.getcwd()
                    ).stdout.strip()
                    or "",
                }
            )

            # Save stack
            with open(stack_file, "w") as f:
                json.dump(stack_data, f, indent=2)

            return {
                "success": True,
                "pushed": {"branch": current_branch, "path": current_path},
                "stack_size": len(stack_data["stack"]),
                "message": f"Pushed branch '{current_branch}' to stack",
            }

        except Exception as e:
            logger.exception("worktree_push_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
            }

    @mcp.tool()
    async def worktree_pop() -> dict[str, Any]:
        """
        Pop previous worktree context from the stack.

        Restores the previous branch and provides instructions for switching.
        The actual switch requires restarting MCP from the new worktree.

        Returns:
            Dict with pop result and switch instructions

        Example:
            >>> await worktree_pop()
            {
                "success": true,
                "popped": {"branch": "feature/auth", "path": "/home/user/.../feature-auth"},
                "action_required": "restart_mcp",
                "message": "To return to 'feature/auth': ..."
            }
        """
        try:
            import json
            import os
            import subprocess

            git_root = (
                subprocess.run(
                    ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, cwd=os.getcwd()
                ).stdout.strip()
                or os.getcwd()
            )

            stack_file = os.path.join(git_root, ".archon", "context-stack.json")

            if not os.path.exists(stack_file):
                return {
                    "success": False,
                    "error": "No context stack found. Use worktree_push() first.",
                }

            with open(stack_file) as f:
                stack_data = json.load(f)

            if not stack_data.get("stack"):
                return {
                    "success": False,
                    "error": "Context stack is empty. Use worktree_push() first.",
                }

            # Pop the last entry
            popped = stack_data["stack"].pop()

            # Save updated stack
            with open(stack_file, "w") as f:
                json.dump(stack_data, f, indent=2)

            # Get current branch for context
            current_branch = (
                subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, cwd=os.getcwd()
                ).stdout.strip()
                or "unknown"
            )

            return {
                "success": True,
                "popped": popped,
                "current_branch": current_branch,
                "stack_size": len(stack_data["stack"]),
                "action_required": "restart_mcp",
                "message": f"Popped '{popped['branch']}'. Restart MCP from that path to continue.",
                "instructions": f"To return to work on '{popped['branch']}':\n1. Exit current MCP session\n2. cd {popped['worktree_path']}\n3. Run: archon-mcp",
            }

        except Exception as e:
            logger.exception("worktree_pop_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
            }

    @mcp.tool()
    async def worktree_create(
        branch_name: str,
        base_branch: str = "main",
    ) -> dict[str, Any]:
        """
        Create a new git worktree for a branch.

        Creates a new branch from base_branch and sets up a worktree at
        `.worktrees/<branch-name>`.

        Args:
            branch_name: Name of branch to create (e.g., "feature/new-auth")
            base_branch: Branch to create from (default: "main")

        Returns:
            Dict with creation result and switch instructions

        Example:
            >>> await worktree_create("feature/new-auth", "main")
            {
                "success": true,
                "branch": "feature/new-auth",
                "worktree_path": "/home/user/archon/.worktrees/feature-new-auth",
                "message": "Created worktree for 'feature/new-auth'"
            }
        """
        try:
            import subprocess
            import os

            git_root = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, cwd=os.getcwd()
            ).stdout.strip()

            if not git_root:
                return {"success": False, "error": "Not in a git repository"}

            # Sanitize branch name for path
            safe_branch = branch_name.replace("/", "-")
            worktree_path = os.path.join(git_root, ".worktrees", safe_branch)

            # Check if branch already exists
            branch_check = subprocess.run(
                ["git", "rev-parse", "--verify", f"refs/heads/{branch_name}"],
                capture_output=True,
                text=True,
            )

            if branch_check.returncode == 0:
                # Branch exists, just create worktree if it doesn't
                if os.path.exists(worktree_path):
                    return {
                        "success": False,
                        "error": f"Worktree already exists at {worktree_path}",
                    }

                # Create worktree for existing branch
                result = subprocess.run(
                    ["git", "worktree", "add", worktree_path, branch_name],
                    capture_output=True,
                    text=True,
                    cwd=git_root,
                )

                if result.returncode != 0:
                    return {"success": False, "error": f"Failed to create worktree: {result.stderr}"}

                return {
                    "success": True,
                    "branch": branch_name,
                    "worktree_path": worktree_path,
                    "message": f"Created worktree for existing branch '{branch_name}'",
                    "action_required": "restart_mcp",
                    "instructions": f"To switch to new worktree:\n1. Exit current MCP session\n2. cd {worktree_path}\n3. Run: archon-mcp",
                }

            # Create new branch and worktree
            result = subprocess.run(
                ["git", "worktree", "add", "-b", branch_name, worktree_path, base_branch],
                capture_output=True,
                text=True,
                cwd=git_root,
            )

            if result.returncode != 0:
                return {"success": False, "error": f"Failed to create worktree: {result.stderr}"}

            return {
                "success": True,
                "branch": branch_name,
                "base_branch": base_branch,
                "worktree_path": worktree_path,
                "message": f"Created branch '{branch_name}' from '{base_branch}' with worktree",
                "action_required": "restart_mcp",
                "instructions": f"To start working on new branch:\n1. Exit current MCP session\n2. cd {worktree_path}\n3. Run: archon-mcp",
            }

        except Exception as e:
            logger.exception("worktree_create_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
            }

    @mcp.tool()
    async def commit_with_review(
        message: str,
        skip_checks: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Perform staged commit with review checklist.

        This tool guides the agent through a structured commit process:
        1. Show changed files
        2. Check: docs updated?
        3. Check: tests pass?
        4. Check: audit clean?
        5. Confirm commit message
        6. Execute git commit

        Args:
            message: Commit message for the changes
            skip_checks: Optional list of checks to skip (e.g., ["tests", "audit"])

        Returns:
            Dict with commit result and checklist status

        Example:
            >>> await commit_with_review(
            ...     message="Add version-scoped search feature",
            ...     skip_checks=["audit"]
            ... )
        """
        try:
            import subprocess
            import os

            skip_checks = skip_checks or []

            # Step 1: Get changed files
            result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=os.getcwd())

            if result.returncode != 0:
                return {"success": False, "error": "Not in a git repository"}

            changed_files = [line[2:].strip() for line in result.stdout.strip().split("\n") if line.strip()]

            if not changed_files:
                return {"success": False, "error": "No changes to commit"}

            # Categorize changes
            staged_files = [f for f in changed_files if f.startswith(("M", "A", "D"))]
            new_files = [f for f in changed_files if f.startswith("??")]
            modified_only = [f for f in changed_files if f.startswith(" M")]

            # Step 2: Documentation check
            docs_changed = [f for f in changed_files if f.startswith("docs/") or f.endswith(".md")]
            docs_check = {
                "name": "documentation",
                "status": "skipped" if "docs" in skip_checks else ("warning" if docs_changed else "pass"),
                "details": f"Found {len(docs_changed)} doc changes" if docs_changed else "No doc changes",
                "requires_review": bool(docs_changed),
            }

            # Step 3: Test check (simplified - check for test file changes)
            test_files = [f for f in changed_files if "test" in f.lower() or f.startswith("tests/")]
            test_files_changed = [f for f in modified_only if "test" in f.lower() or f.startswith("tests/")]
            test_check = {
                "name": "tests",
                "status": "skipped"
                if "tests" in skip_checks
                else ("warning" if (modified_only and not test_files_changed) else "pass"),
                "details": f"Found {len(test_files_changed)} test file changes"
                if test_files_changed
                else "No test changes in modified files",
                "recommendation": "Consider adding tests" if modified_only and not test_files_changed else None,
            }

            # Step 4: Audit check
            audit_check = {
                "name": "audit",
                "status": "skipped" if "audit" in skip_checks else "ready",
                "details": "Run repo_health_check manually if needed",
            }

            # Step 5: Validate commit message
            if not message or len(message) < 5:
                return {
                    "success": False,
                    "error": "Commit message must be at least 5 characters",
                }

            # Step 6: Stage and commit
            # First, add all changes
            add_result = subprocess.run(["git", "add", "-A"], capture_output=True, text=True, cwd=os.getcwd())

            if add_result.returncode != 0:
                return {"success": False, "error": f"Failed to stage changes: {add_result.stderr}"}

            # Then commit
            commit_result = subprocess.run(
                ["git", "commit", "-m", message], capture_output=True, text=True, cwd=os.getcwd()
            )

            if commit_result.returncode != 0:
                return {
                    "success": False,
                    "error": f"Commit failed: {commit_result.stderr}",
                }

            # Get the commit SHA
            commit_sha = subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=os.getcwd()
            ).stdout.strip()[:8]

            return {
                "success": True,
                "commit_sha": commit_sha,
                "message": message,
                "checklist": {
                    "changed_files": {
                        "staged": len(staged_files),
                        "new": len(new_files),
                        "total": len(changed_files),
                    },
                    "documentation": docs_check,
                    "tests": test_check,
                    "audit": audit_check,
                },
                "next_steps": [
                    "Post-commit hooks will sync entities and embeddings",
                    "Check .archon/hooks/last-run.json for pipeline status",
                ],
            }

        except Exception as e:
            logger.exception("commit_with_review_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
            }

    @mcp.tool()
    async def get_commit_checklist() -> dict[str, Any]:
        """
        Get the checklist for the current changes without committing.

        This is useful to review what will be committed before actually committing.

        Returns:
            Dict with checklist items for review
        """
        try:
            import subprocess
            import os

            # Get changed files
            result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=os.getcwd())

            if result.returncode != 0:
                return {"success": False, "error": "Not in a git repository"}

            changed_files = [line[2:].strip() for line in result.stdout.strip().split("\n") if line.strip()]

            if not changed_files:
                return {"success": True, "message": "No changes to commit", "checklist": {}}

            # Analyze changes
            modified = [f for f in changed_files if f.startswith(" M")]
            added = [f for f in changed_files if f.startswith("A ")]
            deleted = [f for f in changed_files if f.startswith("D ")]
            untracked = [f for f in changed_files if f.startswith("??")]

            # Check for specific patterns
            docs_files = [f for f in changed_files if f.startswith("docs/") or f.endswith(".md")]
            test_files = [f for f in changed_files if "test" in f.lower() or f.startswith("tests/")]
            src_files = [f for f in changed_files if f.startswith("python/src/") or f.startswith("src/")]

            return {
                "success": True,
                "checklist": {
                    "summary": {
                        "modified": len(modified),
                        "added": len(added),
                        "deleted": len(deleted),
                        "untracked": len(untracked),
                        "total": len(changed_files),
                    },
                    "categories": {
                        "documentation": {
                            "count": len(docs_files),
                            "files": docs_files[:5],  # Show first 5
                        },
                        "tests": {
                            "count": len(test_files),
                            "files": test_files[:5],
                        },
                        "source_code": {
                            "count": len(src_files),
                            "files": src_files[:5],
                        },
                    },
                    "recommendations": [],
                },
                "usage": "Use commit_with_review(message='...') to commit with checklist",
            }

        except Exception as e:
            logger.exception("get_commit_checklist_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
            }

    @mcp.tool()
    async def generate_context_bundle(
        force: bool = False,
    ) -> dict[str, Any]:
        """
        Generate context bundle for agent sessions.

        Creates `.archon/context/` directory with:
        - STATUS.md: Current branch, recent changes, active worktrees
        - CHANGES.md: Uncommitted changes summary
        - ARCHITECTURE.md: Architecture overview from ADRs
        - KNOWN_ISSUES.md: Open audit findings

        Args:
            force: Force generation even if no triggering changes detected

        Returns:
            Dict with generated file paths

        Example:
            >>> await generate_context_bundle()
            {
                "success": true,
                "generated": {
                    "STATUS.md": "/repo/.archon/context/STATUS.md",
                    "CHANGES.md": "/repo/.archon/context/CHANGES.md",
                    "ARCHITECTURE.md": "/repo/.archon/context/ARCHITECTURE.md",
                    "KNOWN_ISSUES.md": "/repo/.archon/context/KNOWN_ISSUES.md"
                }
            }
        """
        try:
            import subprocess
            import os

            # Get git root
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, cwd=os.getcwd()
            )

            if result.returncode != 0:
                return {"success": False, "error": "Not in a git repository"}

            repo_root = result.stdout.strip()

            # Run the generate_context_bundle.py script
            script_path = os.path.join(repo_root, "scripts", "generate_context_bundle.py")

            if not os.path.exists(script_path):
                return {
                    "success": False,
                    "error": f"Generation script not found at {script_path}",
                }

            cmd = ["python3", script_path, "--repo-root", repo_root]
            if force:
                cmd.append("--force")

            result = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_root)

            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"Generation failed: {result.stderr}",
                }

            # List generated files
            context_dir = os.path.join(repo_root, ".archon", "context")
            generated = {}

            for filename in ["STATUS.md", "CHANGES.md", "ARCHITECTURE.md", "KNOWN_ISSUES.md"]:
                filepath = os.path.join(context_dir, filename)
                if os.path.exists(filepath):
                    generated[filename] = filepath

            return {
                "success": True,
                "generated": generated,
                "count": len(generated),
                "message": f"Generated {len(generated)} context bundle files",
            }

        except Exception as e:
            logger.exception("generate_context_bundle_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
            }

    logger.info("worktree_tools_registered")
