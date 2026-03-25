"""
Worktree Context for MCP Tools

Provides access to current branch/commit context detected at MCP server startup.
This enables code search tools to automatically scope to the current branch.
"""

import os

# Module-level context - populated at MCP server startup
_context = {
    "branch": os.getenv("ARCHON_BRANCH", "main"),
    "commit": os.getenv("ARCHON_COMMIT", ""),
    "worktree_path": os.getenv("ARCHON_WORKTREE_PATH", ""),
    "repo_root": os.getenv("ARCHON_REPO_ROOT", ""),
}


def get_current_branch() -> str:
    """Get current branch name."""
    return _context.get("branch", "main")


def get_current_commit() -> str:
    """Get current commit SHA."""
    return _context.get("commit", "")


def get_current_worktree_path() -> str:
    """Get current worktree path."""
    return _context.get("worktree_path", "")


def get_repo_root() -> str:
    """Get git repository root path."""
    return _context.get("repo_root", "")


def get_worktree_context() -> dict:
    """Get full worktree context."""
    return _context.copy()


def set_worktree_context(branch: str = None, commit: str = None, worktree_path: str = None, repo_root: str = None):
    """Set worktree context (used when switching worktrees)."""
    global _context
    if branch is not None:
        _context["branch"] = branch
    if commit is not None:
        _context["commit"] = commit
    if worktree_path is not None:
        _context["worktree_path"] = worktree_path
    if repo_root is not None:
        _context["repo_root"] = repo_root


def is_valid_context() -> bool:
    """Check if worktree context is valid."""
    return _context.get("branch") not in (None, "", "unknown")
