"""
Adapter layer to run Git tests against GitRepositoryService.
"""

import codecs
import subprocess
from pathlib import Path
from typing import Any


def _decode_git_escaped_filename(escaped: str) -> str:
    r"""
    Decode git's C-style escaped filenames.
    
    Git escapes non-ASCII characters as \NNN octal sequences.
    Example: "\346\226\207\344\273\266.txt" -> "文件.txt"
    """
    # Remove surrounding quotes if present
    if escaped.startswith('"') and escaped.endswith('"'):
        escaped = escaped[1:-1]
    
    # Decode octal escape sequences
    try:
        # Replace \NNN with actual bytes then decode as UTF-8
        decoded = codecs.decode(escaped, 'unicode_escape')
        return decoded
    except (UnicodeDecodeError, ValueError):
        return escaped


class GitTestAdapter:
    """
    Adapter layer to run Git tests against GitRepositoryService.

    Translates Git CLI commands to service method calls and validates outputs.
    """

    def __init__(self, repo_path: Path, service: Any, repo_id: str):
        """
        Initialize adapter.

        Args:
            repo_path: Path to test repository
            service: GitRepositoryService instance
            repo_id: Repository ID in database
        """
        self.repo_path = Path(repo_path)
        self.service = service
        self.repo_id = repo_id

        if not self.repo_path.exists():
            raise ValueError(f"Repository path does not exist: {repo_path}")

        if not (self.repo_path / ".git").exists():
            raise ValueError(f"Not a Git repository: {repo_path}")

    def git_command(self, *args: str) -> str:
        """
        Run a git command via CLI for comparison.

        Args:
            *args: Git command arguments (e.g., "log", "--oneline")

        Returns:
            Command output as string
        """
        result = subprocess.run(
            ["git", *args],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode != 0:
            raise RuntimeError(f"Git command failed: git {' '.join(args)}\n{result.stderr}")

        return result.stdout.strip()

    def get_commit_sha(self, ref: str = "HEAD") -> str:
        """
        Get commit SHA for a ref.

        Args:
            ref: Git ref (e.g., "HEAD", "main", "abc123")

        Returns:
            Full commit SHA
        """
        return self.git_command("rev-parse", ref)

    def get_branch_name(self) -> str:
        """Get current branch name."""
        return self.git_command("branch", "--show-current")

    def list_branches(self) -> list[str]:
        """List all branches."""
        output = self.git_command("branch", "--format=%(refname:short)")
        return [line.strip() for line in output.split("\n") if line.strip()]

    def get_file_content_cli(self, file_path: str, ref: str = "HEAD") -> str:
        """Get file content via git CLI."""
        return self.git_command("show", f"{ref}:{file_path}")

    def get_file_content_service(self, file_path: str, commit_sha: str) -> str:
        """Get file content via GitRepositoryService."""
        success, result = self.service.get_file_content(
            repo_id=self.repo_id,
            commit_sha=commit_sha,
            file_path=file_path
        )
        if not success:
            raise RuntimeError(f"Failed to get file content: {result.get('error', 'Unknown error')}")
        return result["content"]

    def get_file_tree_cli(self, ref: str = "HEAD") -> list[str]:
        """Get file tree via git CLI."""
        output = self.git_command("ls-tree", "-r", "--name-only", "-z", ref)
        # -z flag gives null-separated output with unescaped filenames
        if "\x00" in output:
            # Using -z flag, split by null
            return [line.strip() for line in output.split("\x00") if line.strip()]
        else:
            # Fallback: decode escaped filenames manually
            lines = [line.strip() for line in output.split("\n") if line.strip()]
            return [_decode_git_escaped_filename(line) for line in lines]

    def get_file_tree_service(self, commit_sha: str) -> list[str]:
        """Get file tree via GitRepositoryService."""
        success, result = self.service.get_file_tree(
            repo_id=self.repo_id,
            commit_sha=commit_sha
        )
        if not success:
            raise RuntimeError(f"Failed to get file tree: {result.get('error', 'Unknown error')}")
        return [f["file_path"] for f in result["files"]]

    def assert_file_content_matches(self, file_path: str, commit_sha: str):
        """Assert that service returns same content as git CLI."""
        cli_content = self.get_file_content_cli(file_path, commit_sha)
        service_content = self.get_file_content_service(file_path, commit_sha)

        # Strip trailing whitespace to handle newline differences
        cli_stripped = cli_content.rstrip()
        service_stripped = service_content.rstrip()

        assert cli_stripped == service_stripped, (
            f"File content mismatch for {file_path} at {commit_sha[:7]}\n"
            f"Expected (git):\n{cli_content}\n"
            f"Got (service):\n{service_content}"
        )

    def assert_file_tree_matches(self, commit_sha: str):
        """Assert that service returns same file tree as git CLI."""
        cli_tree = set(self.get_file_tree_cli(commit_sha))
        service_tree = set(self.get_file_tree_service(commit_sha))

        assert service_tree == cli_tree, (
            f"File tree mismatch at {commit_sha[:7]}\n"
            f"Missing in service: {cli_tree - service_tree}\n"
            f"Extra in service: {service_tree - cli_tree}"
        )
