"""Worktree Safety Service

Manages worktree-aware operations to prevent conflicts when multiple
instances (OctoFriend, agents, etc.) work on different branches/worktrees.

This service provides:
- Worktree context detection
- Conflict prediction and detection  
- Safety validation before operations
- Worktree lifecycle management
"""

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4, UUID

from src.server.config.logfire_config import get_logger
from src.server.services.database import get_database_connector

logger = get_logger(__name__)


@dataclass
class WorktreeContext:
    """Represents the current worktree context."""
    is_worktree: bool
    worktree_id: str | None
    branch_name: str | None
    repo_path: str | None
    base_branch: str | None
    git_root: str | None
    is_clean: bool
    uncommitted_changes: list[str]
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "is_worktree": self.is_worktree,
            "worktree_id": self.worktree_id,
            "branch_name": self.branch_name,
            "repo_path": self.repo_path,
            "base_branch": self.base_branch,
            "git_root": self.git_root,
            "is_clean": self.is_clean,
            "uncommitted_changes": self.uncommitted_changes,
        }


@dataclass 
class WorktreeValidationResult:
    """Result of worktree safety validation."""
    is_safe: bool
    issues: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    context: WorktreeContext | None = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "is_safe": self.is_safe,
            "issues": self.issues,
            "warnings": self.warnings,
            "context": self.context.to_dict() if self.context else None,
        }


class WorktreeService:
    """Service for managing worktree safety and isolation."""

    def __init__(self):
        """Initialize worktree service."""
        self._current_context: WorktreeContext | None = None
    
    def detect_worktree_context(self, path: str | None = None) -> WorktreeContext:
        """
        Auto-detect current worktree context from git repository.
        
        Args:
            path: Optional path to detect from. Defaults to current directory.
            
        Returns:
            WorktreeContext with detected information
        """
        try:
            cwd = path or os.getcwd()
            
            # Find git root
            git_root = self._get_git_root(cwd)
            if not git_root:
                logger.debug(f"No git repository found at {cwd}")
                return WorktreeContext(
                    is_worktree=False,
                    worktree_id=None,
                    branch_name=None,
                    repo_path=None,
                    base_branch=None,
                    git_root=None,
                    is_clean=True,
                    uncommitted_changes=[],
                )
            
            branch_name = self._get_current_branch(git_root)
            is_worktree, worktree_path = self._is_worktree(git_root)
            worktree_id = self._get_worktree_id(worktree_path or git_root)
            base_branch = self._get_base_branch(git_root) if is_worktree else branch_name
            uncommitted = self._get_uncommitted_changes(git_root)
            
            context = WorktreeContext(
                is_worktree=is_worktree,
                worktree_id=worktree_id,
                branch_name=branch_name,
                repo_path=worktree_path or git_root,
                base_branch=base_branch,
                git_root=git_root,
                is_clean=len(uncommitted) == 0,
                uncommitted_changes=uncommitted,
            )
            
            self._current_context = context
            logger.info(f"Detected worktree context: {context.branch_name} at {context.repo_path}")
            return context
            
        except Exception as e:
            logger.error(f"Error detecting worktree context: {e}")
            return WorktreeContext(
                is_worktree=False,
                worktree_id=None,
                branch_name=None,
                repo_path=None,
                base_branch=None,
                git_root=None,
                is_clean=False,
                uncommitted_changes=[],
            )
    
    def _get_git_root(self, path: str) -> str | None:
        """Get the git repository root."""
        try:
            result = subprocess.run(
                ["git", "-C", path, "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None
    
    def _get_current_branch(self, git_root: str) -> str | None:
        """Get the current git branch name."""
        try:
            result = subprocess.run(
                ["git", "-C", git_root, "branch", "--show-current"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip() or None
        except subprocess.CalledProcessError:
            return None
    
    def _is_worktree(self, git_root: str) -> tuple[bool, str | None]:
        """Check if current directory is a worktree and return its path."""
        try:
            result = subprocess.run(
                ["git", "-C", git_root, "rev-parse", "--git-path", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            )
            gitdir = result.stdout.strip()
            
            main_git = Path(git_root) / ".git"
            is_worktree = not gitdir.startswith(str(main_git))
            
            if is_worktree:
                wt_result = subprocess.run(
                    ["git", "-C", git_root, "rev-parse", "--show-toplevel"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                return True, wt_result.stdout.strip()
            
            return False, None
            
        except subprocess.CalledProcessError:
            return False, None
    
    def _get_worktree_id(self, repo_path: str) -> str:
        """Generate a stable UUID for a worktree based on its path."""
        import uuid
        namespace = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')
        return str(uuid.uuid5(namespace, repo_path))
    
    def _get_base_branch(self, git_root: str) -> str | None:
        """Get the base branch this worktree was created from."""
        try:
            result = subprocess.run(
                ["git", "-C", git_root, "config", "--get", "worktree.basebranch"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            
            for branch in ["main", "master", "develop"]:
                result = subprocess.run(
                    ["git", "-C", git_root, "rev-parse", "--verify", branch],
                    capture_output=True,
                )
                if result.returncode == 0:
                    return branch
            
            return None
            
        except Exception:
            return None
    
    def _get_uncommitted_changes(self, git_root: str) -> list[str]:
        """Get list of files with uncommitted changes."""
        try:
            result = subprocess.run(
                ["git", "-C", git_root, "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=True,
            )
            changes = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split()
                    if len(parts) >= 2:
                        changes.append(parts[-1])
            return changes
            
        except subprocess.CalledProcessError:
            return []
    
    async def validate_safe_to_work(
        self,
        task_id: str | None = None,
        file_paths: list[str] = None,
        entity_ids: list[str] = None,
        worktree_id: str | None = None,
        branch_name: str | None = None,
    ) -> WorktreeValidationResult:
        """
        Validate if it's safe to start/modify work in current context.

        Args:
            task_id: Optional task ID to check
            file_paths: List of file paths that will be modified
            entity_ids: List of entity IDs that will be modified
            worktree_id: Optional override worktree ID
            branch_name: Optional override branch name

        Returns:
            WorktreeValidationResult with safety status
        """
        issues = []
        warnings = []

        context = self._current_context or self.detect_worktree_context()

        current_worktree = worktree_id or context.worktree_id
        current_branch = branch_name or context.branch_name

        # Build entities JSON for conflict detection
        entities = entity_ids or []
        if file_paths:
            entities.extend(file_paths)

        try:
            # Use database function for validation
            db = get_database_connector()
            result = await db.fetch(
                """
                SELECT * FROM validate_worktree_safe($1, $2, $3, $4, $5)
                """,
                current_worktree,
                current_branch,
                context.repo_path,
                task_id,
                json.dumps(entities) if entities else "[]",
            )

            if result:
                data = dict(result[0])
                is_safe = data.get("is_safe", False)
                db_issues = data.get("issues", [])
                db_warnings = data.get("warnings", [])

                issues.extend(db_issues)
                warnings.extend(db_warnings)
            else:
                is_safe = True

        except Exception as e:
            logger.error(f"Database validation error: {e}")
            warnings.append({
                "type": "validation_error",
                "message": f"Could not validate worktree safety: {e}",
                "severity": "warning",
            })
            is_safe = True

        if not context.is_clean and not task_id:
            warnings.append({
                "type": "uncommitted_changes",
                "message": f"You have {len(context.uncommitted_changes)} uncommitted changes",
                "severity": "warning",
                "files": context.uncommitted_changes[:10],
            })

        return WorktreeValidationResult(
            is_safe=is_safe and len(issues) == 0,
            issues=issues,
            warnings=warnings,
            context=context,
        )


    async def find_conflicts(
        self,
        worktree_id: str | None = None,
        file_paths: list[str] | None = None,
        entity_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Find conflicts with other worktrees."""
        try:
            db = get_database_connector()
            
            # Get current worktree if not provided
            context = self._current_context or self.detect_worktree_context()
            current_wt = worktree_id or context.worktree_id
            
            if not current_wt:
                return []
            
            # Query for tasks in other worktrees modifying same files/entities
            # This is a placeholder - implement actual conflict detection logic
            result = await db.fetch(
                """
                SELECT DISTINCT ON (t.id)
                    t.id as task_id,
                    t.title,
                    t.status,
                    t.worktree_id,
                    w.branch_name,
                    'file_conflict' as conflict_type,
                    'warning' as conflict_severity
                FROM archon_tasks t
                JOIN archon_worktrees w ON w.worktree_id = t.worktree_id
                WHERE t.worktree_id != $1
                AND t.status IN ('todo', 'doing', 'review')
                AND (
                    $2::text[] && t.file_paths
                    OR $3::text[] && t.entity_ids
                )
                LIMIT 50
                """,
                current_wt,
                file_paths or [],
                entity_ids or [],
            )
            
            return [dict(row) for row in result]
            
        except Exception as e:
            logger.error(f"Error finding conflicts: {e}")
            return []
    
    async def list_worktrees(self) -> list[dict[str, Any]]:
        """List all active worktrees with task counts."""
        try:
            db = get_database_connector()
            result = await db.fetch(
                """
                SELECT 
                    w.worktree_id,
                    w.branch_name,
                    w.repo_path,
                    COUNT(DISTINCT t.id) as active_task_count,
                    COUNT(DISTINCT CASE WHEN t.status = 'doing' THEN t.id END) as doing_count,
                    MAX(t.updated_at) as last_activity
                FROM archon_worktrees w
                LEFT JOIN archon_tasks t ON t.worktree_id = w.worktree_id 
                    AND t.status IN ('todo', 'doing', 'review')
                GROUP BY w.worktree_id, w.branch_name, w.repo_path
                ORDER BY last_activity DESC NULLS LAST
                LIMIT 100
                """
            )
            
            return [
                {
                    "worktree_id": row["worktree_id"],
                    "branch_name": row["branch_name"],
                    "repo_path": row["repo_path"],
                    "active_task_count": row["active_task_count"],
                    "doing_count": row["doing_count"],
                    "last_activity": row["last_activity"].isoformat() if row["last_activity"] else None,
                }
                for row in result
            ]
        except Exception as e:
            logger.error(f"Error listing worktrees: {e}")
            return []
    
    async def create_worktree_task(
        self,
        project_id: str,
        title: str,
        description: str,
        file_paths: list[str] | None,
        entity_ids: list[str] | None,
        assignee: str,
        priority: str,
        feature: str | None,
    ) -> tuple[bool, dict[str, Any]]:
        """Create a task with worktree context."""
        try:
            db = get_database_connector()
            context = self._current_context or self.detect_worktree_context()
            
            # Generate UUID for task
            task_id = str(uuid4())
            
            # Insert task with worktree context
            await db.execute(
                """
                INSERT INTO archon_tasks (
                    id, project_id, title, description, status,
                    assignee, priority, feature, worktree_id, branch_name,
                    file_paths, entity_ids, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW(), NOW())
                """,
                task_id,
                project_id,
                title,
                description,
                "todo",
                assignee,
                priority,
                feature,
                context.worktree_id,
                context.branch_name,
                file_paths or [],
                entity_ids or [],
            )
            
            # Ensure worktree exists in database
            await db.execute(
                """
                INSERT INTO archon_worktrees (worktree_id, branch_name, repo_path, created_at)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT (worktree_id) DO NOTHING
                """,
                context.worktree_id,
                context.branch_name,
                context.repo_path,
            )
            
            return True, {"task": {"id": task_id, "title": title}, "task_id": task_id}
            
        except Exception as e:
            logger.error(f"Error creating worktree task: {e}")
            return False, {"error": str(e)}
    
    async def sync_worktree_context(self, task_id: str) -> bool:
        """Sync worktree context for a task."""
        try:
            db = get_database_connector()
            context = self._current_context or self.detect_worktree_context()
            
            await db.execute(
                """
                UPDATE archon_tasks
                SET worktree_id = $1, branch_name = $2, updated_at = NOW()
                WHERE id = $3
                """,
                context.worktree_id,
                context.branch_name,
                task_id,
            )
            
            return True
        except Exception as e:
            logger.error(f"Error syncing worktree context: {e}")
            return False
    
    async def lock_worktree(self, worktree_id: str, locked: bool) -> bool:
        """Lock or unlock a worktree."""
        try:
            db = get_database_connector()
            
            await db.execute(
                """
                INSERT INTO archon_worktrees (worktree_id, locked, locked_at, updated_at)
                VALUES ($1, $2, CASE WHEN $2 THEN NOW() ELSE NULL END, NOW())
                ON CONFLICT (worktree_id) DO UPDATE
                SET locked = $2, locked_at = CASE WHEN $2 THEN NOW() ELSE NULL END, updated_at = NOW()
                """,
                worktree_id,
                locked,
            )
            
            return True
        except Exception as e:
            logger.error(f"Error locking worktree: {e}")
            return False


# Singleton instance
_worktree_service: WorktreeService | None = None


def get_worktree_service() -> WorktreeService:
    """Get or create singleton worktree service."""
    global _worktree_service
    if _worktree_service is None:
        _worktree_service = WorktreeService()
    return _worktree_service
