"""Git repository initialization utilities."""

import os
import subprocess
from typing import List, Tuple


def initialize_git_repository(
    repo_path: str,
    create_commit: bool = False,
    commit_message: str = "Initial commit",
    author_name: str | None = None,
    author_email: str | None = None,
) -> Tuple[bool, str | None]:
    """
    Initialize a new Git repository in the specified directory.

    Args:
        repo_path: Absolute path to the directory
        create_commit: Whether to create an initial commit
        commit_message: Message for the initial commit
        author_name: Git author name (uses git config default if None)
        author_email: Git author email (uses git config default if None)

    Returns:
        (success, error_message)
    """
    try:
        # Validate directory exists
        if not os.path.exists(repo_path):
            return False, f"Directory does not exist: {repo_path}"

        if not os.path.isdir(repo_path):
            return False, f"Path is not a directory: {repo_path}"

        # Check if already a Git repo
        git_dir = os.path.join(repo_path, ".git")
        if os.path.isdir(git_dir):
            return False, "Directory is already a Git repository"

        # Run git init
        result = subprocess.run(
            ["git", "init"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return False, f"git init failed: {result.stderr}"

        # Optionally create initial commit
        if create_commit:
            # Set author if provided (for this operation only)
            env = os.environ.copy()
            if author_name:
                env["GIT_AUTHOR_NAME"] = author_name
                env["GIT_COMMITTER_NAME"] = author_name
            if author_email:
                env["GIT_AUTHOR_EMAIL"] = author_email
                env["GIT_COMMITTER_EMAIL"] = author_email

            # Add all files
            add_result = subprocess.run(
                ["git", "add", "."],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
            )

            if add_result.returncode != 0:
                return False, f"git add failed: {add_result.stderr}"

            # Create commit
            commit_result = subprocess.run(
                ["git", "commit", "-m", commit_message],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
            )

            if commit_result.returncode != 0:
                # It's OK if there's nothing to commit
                if "nothing to commit" not in commit_result.stdout.lower():
                    return False, f"git commit failed: {commit_result.stderr}"

        return True, None

    except subprocess.TimeoutExpired:
        return False, "Git operation timed out"
    except Exception as e:
        return False, f"Unexpected error during git init: {str(e)}"


def get_repository_branches(repo_path: str) -> List[str]:
    """
    Get all local branches in a git repository.

    Args:
        repo_path: Absolute path to the git repository

    Returns:
        List of branch names
    """
    try:
        # Validate directory exists
        if not os.path.exists(repo_path):
            return []

        git_dir = os.path.join(repo_path, ".git")
        if not os.path.isdir(git_dir):
            return []

        # Get all local branches
        result = subprocess.run(
            ["git", "branch", "--format=%(refname:short)"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return []

        # Parse output - one branch per line
        branches = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
        return sorted(branches)

    except subprocess.TimeoutExpired:
        return []
    except Exception:
        return []
