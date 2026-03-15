"""Git Repository Manager

Manages local repositories with optional GitHub linking.
Supports incremental updates via git hooks and file watching.
"""

import asyncio
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import logging

try:
    from server.services.code_entity_service import CodeEntityService
    from server.services.database.db_connector import get_database_connector, initialize_database
except ImportError:
    from src.server.services.code_entity_service import CodeEntityService
    from src.server.services.database.db_connector import get_database_connector, initialize_database

logger = logging.getLogger(__name__)


@dataclass
class RepositoryConfig:
    """Configuration for a managed repository."""
    
    repo_id: str
    local_path: Path
    github_url: str | None = None
    github_owner: str | None = None
    github_repo: str | None = None
    branch: str = "main"
    last_commit: str | None = None
    auto_sync: bool = True


class GitRepositoryManager:
    """Manages git repositories with code intelligence.
    
    Features:
    - Local repository tracking
    - Optional GitHub linking (for web UI, PRs, etc.)
    - Incremental updates on commits
    - Git hooks for automatic re-ingestion
    """
    
    def __init__(self):
        self._code_service = CodeEntityService()
        self._db = None
        self._repos: dict[str, RepositoryConfig] = {}
        self._config_file = Path.home() / ".config" / "archon" / "repositories.json"
        
    async def _ensure_db(self):
        """Initialize database connection."""
        if self._db is None:
            await initialize_database()
            self._db = get_database_connector()
            await self._db.initialize()
        return self._db
    
    async def register_local_repo(
        self,
        local_path: str | Path,
        name: str | None = None,
        github_url: str | None = None,
    ) -> RepositoryConfig:
        """Register a local repository for tracking.
        
        Args:
            local_path: Path to local git repository
            name: Optional display name
            github_url: Optional GitHub URL (e.g., https://github.com/zebastjan/archon)
            
        Returns:
            Repository configuration
        """
        local_path = Path(local_path).resolve()
        
        if not local_path.exists():
            raise ValueError(f"Path does not exist: {local_path}")
        
        if not (local_path / ".git").exists():
            raise ValueError(f"Not a git repository: {local_path}")
        
        # Parse GitHub URL if provided
        github_owner = None
        github_repo = None
        if github_url:
            # Parse https://github.com/owner/repo or git@github.com:owner/repo.git
            if "github.com" in github_url:
                parts = github_url.replace(".git", "").split("/")
                if len(parts) >= 2:
                    github_owner = parts[-2]
                    github_repo = parts[-1]
        
        # Get current commit
        try:
            result = subprocess.run(
                ["git", "-C", str(local_path), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True
            )
            last_commit = result.stdout.strip()
        except subprocess.CalledProcessError:
            last_commit = None
        
        # Get current branch
        try:
            result = subprocess.run(
                ["git", "-C", str(local_path), "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                check=True
            )
            branch = result.stdout.strip()
        except subprocess.CalledProcessError:
            branch = "main"
        
        repo_id = await self._create_repo_in_db(
            name=name or local_path.name,
            local_path=str(local_path),
            github_owner=github_owner,
            github_repo=github_repo,
            github_url=github_url,
            branch=branch,
            last_commit=last_commit,
        )
        
        config = RepositoryConfig(
            repo_id=repo_id,
            local_path=local_path,
            github_url=github_url,
            github_owner=github_owner,
            github_repo=github_repo,
            branch=branch,
            last_commit=last_commit,
        )
        
        self._repos[repo_id] = config
        self._save_config()
        
        # Install git hook for automatic updates
        await self._install_git_hook(repo_id, local_path)
        
        logger.info(f"Registered repository {repo_id}: {local_path}")
        return config
    
    async def _create_repo_in_db(
        self,
        name: str,
        local_path: str,
        github_owner: str | None,
        github_repo: str | None,
        github_url: str | None,
        branch: str,
        last_commit: str | None,
    ) -> str:
        """Create repository record in database."""
        db = await self._ensure_db()
        
        # Check if already exists
        existing = await db.fetch(
            "SELECT id FROM archon_code_repos WHERE local_path = $1",
            local_path
        )
        
        if existing:
            return str(existing[0]["id"])
        
        # Create new repo record
        # Note: This requires a new table - let's create it dynamically
        try:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS archon_code_repos (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name TEXT NOT NULL,
                    local_path TEXT UNIQUE NOT NULL,
                    github_owner TEXT,
                    github_repo TEXT,
                    github_url TEXT,
                    branch TEXT DEFAULT 'main',
                    last_commit_sha TEXT,
                    last_synced TIMESTAMPTZ,
                    auto_sync BOOLEAN DEFAULT true,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
        except Exception:
            pass  # Table might already exist
        
        result = await db.fetchrow("""
            INSERT INTO archon_code_repos 
            (name, local_path, github_owner, github_repo, github_url, branch, last_commit_sha)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (local_path) DO UPDATE SET
                name = EXCLUDED.name,
                github_owner = EXCLUDED.github_owner,
                github_repo = EXCLUDED.github_repo,
                github_url = EXCLUDED.github_url,
                updated_at = NOW()
            RETURNING id
        """, name, local_path, github_owner, github_repo, github_url, branch, last_commit)
        
        return str(result["id"])
    
    async def _install_git_hook(self, repo_id: str, repo_path: Path):
        """Install post-commit hook for automatic re-ingestion."""
        hooks_dir = repo_path / ".git" / "hooks"
        post_commit = hooks_dir / "post-commit"
        
        # Create archon hook script
        hook_script = f'''#!/bin/bash
# Archon auto-ingestion hook
REPO_ID="{repo_id}"
REPO_PATH="{repo_path}"

echo "[Archon] Detected commit, triggering incremental update..."

# Get changed files
CHANGED_FILES=$(git diff-tree --no-commit-id --name-only -r HEAD | grep -E "\\.(py|ts|tsx|js|jsx)$" || true)

if [ -n "$CHANGED_FILES" ]; then
    echo "[Archon] Changed files:"
    echo "$CHANGED_FILES"
    
    # Trigger archon update (in background)
    (
        cd /home/zebastjan/dev/archon/python
        echo "$CHANGED_FILES" | uv run python -c "
import asyncio
import sys
import os
os.environ['ARCHON_DATABASE_URL'] = 'postgresql://archon:archon_local_dev@localhost:5434/archon'

from src.server.services.git_repo_manager import GitRepositoryManager

async def update():
    manager = GitRepositoryManager()
    changed = sys.stdin.read().strip().split('\\n')
    if changed and changed[0]:
        await manager.incremental_update('{repo_id}', changed)

asyncio.run(update())
        " 2>&1 >> /tmp/archon-ingestion.log
    ) &
fi
'''
        
        if post_commit.exists():
            # Backup existing hook
            backup = hooks_dir / "post-commit.backup"
            post_commit.rename(backup)
            logger.info(f"Backed up existing post-commit hook to {backup}")
        
        post_commit.write_text(hook_script)
        post_commit.chmod(0o755)
        
        logger.info(f"Installed git hook at {post_commit}")
    
    async def incremental_update(self, repo_id: str, changed_files: list[str]):
        """Update only changed files (fast, for post-commit hook).
        
        Args:
            repo_id: Repository UUID
            changed_files: List of file paths relative to repo root
        """
        logger.info(f"Incremental update for {repo_id}: {len(changed_files)} files")
        
        if repo_id not in self._repos:
            await self._load_repos()
        
        if repo_id not in self._repos:
            raise ValueError(f"Repository {repo_id} not found")
        
        config = self._repos[repo_id]
        
        # Filter to supported extensions
        supported_files = [
            f for f in changed_files
            if f.endswith(('.py', '.ts', '.tsx', '.js', '.jsx'))
        ]
        
        if not supported_files:
            logger.info("No supported files changed")
            return
        
        # Get current commit
        try:
            result = subprocess.run(
                ["git", "-C", str(config.local_path), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True
            )
            commit_sha = result.stdout.strip()
        except subprocess.CalledProcessError:
            commit_sha = "unknown"
        
        # Remove old entities for changed files
        db = await self._ensure_db()
        for file_path in supported_files:
            await db.execute("""
                DELETE FROM archon_code_entities
                WHERE repo_id = $1 AND file_path = $2
            """, repo_id, file_path)
        
        # Re-extract changed files
        class FileProvider:
            def __init__(self, repo_path):
                self.repo_path = repo_path
            
            async def get_content(self, repo_id, commit_sha, file_path):
                full_path = self.repo_path / file_path
                try:
                    return full_path.read_text(encoding="utf-8", errors="ignore")
                except Exception as e:
                    logger.warning(f"Failed to read {file_path}: {e}")
                    return ""
        
        provider = FileProvider(config.local_path)
        
        results = await self._code_service.extract_and_store_entities(
            repo_id=repo_id,
            commit_sha=commit_sha,
            file_paths=supported_files,
            file_content_getter=provider.get_content,
        )
        
        # Update last commit
        await db.execute("""
            UPDATE archon_code_repos
            SET last_commit_sha = $1, last_synced = NOW()
            WHERE id = $2
        """, commit_sha, repo_id)
        
        config.last_commit = commit_sha
        self._repos[repo_id] = config
        
        logger.info(
            f"Incremental update complete: "
            f"{results['entities_created']} entities, "
            f"{results['relationships_created']} relationships"
        )
        
        return results
    
    async def full_reingest(self, repo_id: str):
        """Full re-ingestion (slower, use for initial import or major changes).
        
        Args:
            repo_id: Repository UUID
        """
        logger.info(f"Full re-ingestion for {repo_id}")
        
        if repo_id not in self._repos:
            await self._load_repos()
        
        if repo_id not in self._repos:
            raise ValueError(f"Repository {repo_id} not found")
        
        config = self._repos[repo_id]
        
        # Clear existing entities
        db = await self._ensure_db()
        await db.execute(
            "DELETE FROM archon_code_entities WHERE repo_id = $1",
            repo_id
        )
        
        # Run full ingestion via the quick_ingest script
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        
        from scripts.quick_ingest_repo import ingest_repository
        
        result = await ingest_repository(config.local_path, config.local_path.name)
        
        # Update repo ID mapping (new repo ID created)
        new_repo_id = result.get("repo_id")
        
        logger.info(f"Full re-ingestion complete. New repo ID: {new_repo_id}")
        
        return result
    
    async def get_github_info(self, repo_id: str) -> dict[str, Any] | None:
        """Get GitHub information for a repository.
        
        Returns:
            GitHub owner, repo, URL if linked
        """
        if repo_id not in self._repos:
            await self._load_repos()
        
        if repo_id not in self._repos:
            return None
        
        config = self._repos[repo_id]
        
        if not config.github_owner or not config.github_repo:
            return None
        
        return {
            "owner": config.github_owner,
            "repo": config.github_repo,
            "url": config.github_url,
            "branch": config.branch,
        }
    
    async def get_file_url(self, repo_id: str, file_path: str, line: int | None = None) -> str | None:
        """Generate GitHub URL for a file.
        
        Args:
            repo_id: Repository UUID
            file_path: Relative file path
            line: Optional line number
            
        Returns:
            GitHub URL or None if not linked
        """
        github_info = await self.get_github_info(repo_id)
        
        if not github_info:
            return None
        
        url = f"https://github.com/{github_info['owner']}/{github_info['repo']}/blob/{github_info['branch']}/{file_path}"
        
        if line:
            url += f"#L{line}"
        
        return url
    
    async def _load_repos(self):
        """Load repositories from config file."""
        if not self._config_file.exists():
            return
        
        try:
            data = json.loads(self._config_file.read_text())
            for repo_id, repo_data in data.items():
                self._repos[repo_id] = RepositoryConfig(
                    repo_id=repo_id,
                    local_path=Path(repo_data["local_path"]),
                    github_url=repo_data.get("github_url"),
                    github_owner=repo_data.get("github_owner"),
                    github_repo=repo_data.get("github_repo"),
                    branch=repo_data.get("branch", "main"),
                    last_commit=repo_data.get("last_commit"),
                    auto_sync=repo_data.get("auto_sync", True),
                )
        except Exception as e:
            logger.error(f"Failed to load repos config: {e}")
    
    def _save_config(self):
        """Save repository configurations."""
        self._config_file.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            repo_id: {
                "local_path": str(config.local_path),
                "github_url": config.github_url,
                "github_owner": config.github_owner,
                "github_repo": config.github_repo,
                "branch": config.branch,
                "last_commit": config.last_commit,
                "auto_sync": config.auto_sync,
            }
            for repo_id, config in self._repos.items()
        }
        
        self._config_file.write_text(json.dumps(data, indent=2))

    async def get_registered_repos(self) -> list[dict]:
        """Get all registered repositories from database."""
        db = await self._ensure_db()
        
        try:
            rows = await db.fetch("""
                SELECT id, name, local_path, github_owner, github_repo, github_url, 
                       branch, last_commit_sha, last_synced, created_at
                FROM archon_code_repos
                ORDER BY created_at DESC
            """)
            
            return [
                {
                    "repo_id": str(row["id"]),
                    "name": row["name"],
                    "local_path": row["local_path"],
                    "github_owner": row["github_owner"],
                    "github_repo": row["github_repo"],
                    "github_url": row["github_url"],
                    "branch": row["branch"],
                    "last_commit": row["last_commit_sha"],
                    "last_synced": row["last_synced"],
                    "created_at": row["created_at"],
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to get registered repos: {e}")
            return []


# Singleton
_repo_manager: GitRepositoryManager | None = None


def get_repo_manager() -> GitRepositoryManager:
    """Get or create repository manager singleton."""
    global _repo_manager
    if _repo_manager is None:
        _repo_manager = GitRepositoryManager()
    return _repo_manager
