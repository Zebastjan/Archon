"""
Git Repository Service

Handles git repository operations including registration, commit syncing,
file tree navigation, and content retrieval. Integrates with archon_git_repositories,
archon_git_commits, and archon_git_files tables.
"""

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from git import Repo
from git.exc import GitError as GitPythonError
from supabase import Client

from ...config.logfire_config import get_logger
from ..client_manager import get_supabase_client

logger = get_logger(__name__)

# Git configuration
# Email storage: Set ARCHON_GIT_STORE_EMAILS=false to omit author/committer emails (PII compliance)
STORE_COMMIT_EMAILS = os.getenv("ARCHON_GIT_STORE_EMAILS", "true").lower() == "true"

# Maximum commits to sync in one operation (prevents OOM with large repos)
DEFAULT_MAX_COMMITS = 10000


class GitError(Exception):
    """Base exception for git-related errors."""

    def __init__(self, message: str, repo_path: str | None = None, **kwargs):
        """
        Initialize git error with context.

        Args:
            message: Error description
            repo_path: Path to repository that failed
            **kwargs: Additional metadata
        """
        self.repo_path = repo_path
        self.metadata = kwargs
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for JSON serialization."""
        return {
            "error_type": self.__class__.__name__,
            "message": str(self),
            "repo_path": self.repo_path,
            "metadata": self.metadata,
        }


class GitRepositoryNotFoundError(GitError):
    """Raised when repository path does not exist or is not a git repository."""

    pass


class GitBranchNotFoundError(GitError):
    """Raised when specified branch does not exist in repository."""

    pass


class GitCommitNotFoundError(GitError):
    """Raised when specified commit SHA does not exist."""

    pass


class GitFileNotFoundError(GitError):
    """Raised when file path does not exist at specified commit."""

    pass


# File extension sets for binary/text detection
BINARY_EXTENSIONS = {
    # Images
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".ico",
    ".svg",
    ".webp",
    # Videos
    ".mp4",
    ".avi",
    ".mov",
    ".wmv",
    ".flv",
    ".webm",
    # Audio
    ".mp3",
    ".wav",
    ".ogg",
    ".flac",
    # Archives
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".7z",
    ".rar",
    # Executables
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".bin",
    # Documents
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    # Fonts
    ".ttf",
    ".otf",
    ".woff",
    ".woff2",
    # Others
    ".pyc",
    ".pyo",
    ".class",
    ".o",
    ".a",
    ".lib",
}

TEXT_EXTENSIONS = {
    # Programming languages
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".c",
    ".cpp",
    ".cc",
    ".h",
    ".hpp",
    ".cs",
    ".go",
    ".rs",
    ".rb",
    ".php",
    ".swift",
    ".kt",
    ".scala",
    ".r",
    ".m",
    ".sh",
    ".bash",
    ".zsh",
    # Web
    ".html",
    ".htm",
    ".css",
    ".scss",
    ".sass",
    ".less",
    ".vue",
    ".svelte",
    # Data formats
    ".json",
    ".xml",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    # Documentation
    ".md",
    ".markdown",
    ".rst",
    ".txt",
    ".tex",
    # Config
    ".gitignore",
    ".gitattributes",
    ".dockerignore",
    ".editorconfig",
    # Build/Package
    ".makefile",
    ".cmake",
    ".gradle",
    ".maven",
}

# Sensitive filenames that should never be indexed
SENSITIVE_FILENAMES = {
    ".env",
    ".env.local",
    ".env.development",
    ".env.production",
    ".env.test",
    ".secrets",
    ".secret",
    "credentials",
    "credentials.json",
    "secret.json",
    "secrets.yaml",
    "id_rsa",
    "id_dsa",
    "id_ed25519",
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    "oauth_token",
    "access_token",
}

# Language detection mapping (file extension -> language name)
LANGUAGE_MAPPING = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".c": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".h": "C/C++ Header",
    ".hpp": "C++ Header",
    ".cs": "C#",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".scala": "Scala",
    ".r": "R",
    ".m": "Objective-C",
    ".sh": "Shell",
    ".bash": "Bash",
    ".zsh": "Zsh",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "Sass",
    ".less": "Less",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".json": "JSON",
    ".xml": "XML",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".md": "Markdown",
    ".markdown": "Markdown",
    ".rst": "reStructuredText",
    ".tex": "LaTeX",
    ".sql": "SQL",
    ".dockerfile": "Dockerfile",
    ".makefile": "Makefile",
}


class GitRepositoryService:
    """Service for managing git repositories and their metadata."""

    def __init__(self, supabase_client: Client | None = None):
        """
        Initialize git repository service.

        Args:
            supabase_client: Optional Supabase client instance
        """
        self.supabase_client = supabase_client or get_supabase_client()

    def _validate_repository(self, repo_path: str) -> Repo:
        """
        Validate that path is a valid git repository.

        Args:
            repo_path: Path to repository

        Returns:
            GitPython Repo instance

        Raises:
            GitRepositoryNotFoundError: If path is not a valid git repository
        """
        if not os.path.exists(repo_path):
            raise GitRepositoryNotFoundError(
                f"Repository path does not exist: {repo_path}", repo_path=repo_path
            )

        if not os.path.isdir(repo_path):
            raise GitRepositoryNotFoundError(
                f"Repository path is not a directory: {repo_path}", repo_path=repo_path
            )

        git_dir = os.path.join(repo_path, ".git")
        if not os.path.exists(git_dir):
            raise GitRepositoryNotFoundError(
                f"No .git directory found at: {repo_path}", repo_path=repo_path
            )

        try:
            repo = Repo(repo_path)
            if repo.bare:
                raise GitRepositoryNotFoundError(
                    f"Repository is bare (not supported): {repo_path}", repo_path=repo_path
                )
            return repo
        except GitPythonError as e:
            raise GitRepositoryNotFoundError(
                f"Failed to open git repository at {repo_path}: {e}",
                repo_path=repo_path,
                original_error=str(e),
            ) from e

    def detect_language(self, file_path: str) -> str | None:
        """
        Detect programming language from file extension.

        Args:
            file_path: Path to file

        Returns:
            Language name or None if unknown
        """
        ext = Path(file_path).suffix.lower()

        # Special case: Dockerfile
        file_name = Path(file_path).name.lower()
        if file_name == "dockerfile" or file_name.startswith("dockerfile."):
            return "Dockerfile"

        # Special case: Makefile
        if file_name == "makefile" or file_name.startswith("makefile."):
            return "Makefile"

        return LANGUAGE_MAPPING.get(ext)

    def should_index_file(self, file_path: str) -> bool:
        """
        Determine if file should be indexed (skip binaries and sensitive files).

        Args:
            file_path: Path to file

        Returns:
            True if file should be indexed, False if binary or sensitive
        """
        file_name = Path(file_path).name.lower()

        # Skip sensitive files (credentials, secrets, keys)
        for sensitive_pattern in SENSITIVE_FILENAMES:
            if file_name == sensitive_pattern or file_name.startswith(sensitive_pattern):
                return False

        ext = Path(file_path).suffix.lower()

        # Skip files with sensitive extensions
        if ext in {".pem", ".key", ".p12", ".pfx"}:
            return False

        # Explicitly known binary
        if ext in BINARY_EXTENSIONS:
            return False

        # Explicitly known text
        if ext in TEXT_EXTENSIONS:
            return True

        # Files without extension - check name patterns
        file_name = Path(file_path).name.lower()
        if file_name in {"dockerfile", "makefile", "readme", "license", "changelog"}:
            return True

        # Unknown extension - default to indexing (can be refined later)
        return True

    def get_current_branch(self, repo_path: str) -> str:
        """
        Get the currently active branch name.

        Args:
            repo_path: Path to repository

        Returns:
            Current branch name

        Raises:
            GitRepositoryNotFoundError: If repository is invalid
            GitError: If unable to determine branch
        """
        repo = self._validate_repository(repo_path)

        try:
            if repo.head.is_detached:
                raise GitError(
                    "Repository is in detached HEAD state", repo_path=repo_path
                )
            return repo.active_branch.name
        except GitError:
            raise
        except Exception as e:
            raise GitError(
                f"Failed to get current branch: {e}", repo_path=repo_path, original_error=str(e)
            ) from e

    def get_current_commit_sha(self, repo_path: str, branch: str | None = None) -> str:
        """
        Get the HEAD commit SHA for a branch.

        Args:
            repo_path: Path to repository
            branch: Branch name (defaults to current branch)

        Returns:
            Commit SHA (40-character hex string)

        Raises:
            GitRepositoryNotFoundError: If repository is invalid
            GitBranchNotFoundError: If branch does not exist
            GitError: If unable to get commit SHA
        """
        repo = self._validate_repository(repo_path)

        try:
            if branch is None:
                branch = self.get_current_branch(repo_path)

            # Check if branch exists
            if branch not in repo.heads:
                available_branches = [head.name for head in repo.heads]
                raise GitBranchNotFoundError(
                    f"Branch '{branch}' not found. Available branches: {available_branches}",
                    repo_path=repo_path,
                    branch=branch,
                    available_branches=available_branches,
                )

            branch_ref = repo.heads[branch]
            return branch_ref.commit.hexsha
        except GitBranchNotFoundError:
            raise
        except Exception as e:
            raise GitError(
                f"Failed to get commit SHA for branch '{branch}': {e}",
                repo_path=repo_path,
                branch=branch,
                original_error=str(e),
            ) from e

    def register_repository(
        self, repo_path: str, source_id: str, config: dict | None = None
    ) -> tuple[bool, dict[str, Any]]:
        """
        Register a git repository and create initial metadata.

        Args:
            repo_path: Path to local git repository
            source_id: Associated source_id in archon_sources
            config: Optional repository configuration (branch filters, file patterns, etc.)

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            # Validate repository
            repo = self._validate_repository(repo_path)

            # Extract repository metadata
            repo_url = repo_path  # For local repos, use path as URL
            repo_name = Path(repo_path).name
            owner = None  # Could be extracted from remote URL if configured

            # Get default branch (try common names)
            default_branch = None
            for branch_name in ["main", "master", "develop"]:
                if branch_name in repo.heads:
                    default_branch = branch_name
                    break

            if default_branch is None and repo.heads:
                default_branch = repo.heads[0].name

            if default_branch is None:
                raise GitError(
                    "Repository has no branches", repo_path=repo_path
                )

            # Get current HEAD SHA
            current_head_sha = self.get_current_commit_sha(repo_path, default_branch)

            # Prepare repository data
            repo_data = {
                "source_id": source_id,
                "repo_url": repo_url,
                "repo_name": repo_name,
                "owner": owner,
                "default_branch": default_branch,
                "current_head_sha": current_head_sha,
                "crawl_status": "pending",
                "config": config or {},
                "created_at": datetime.now(UTC).isoformat(),
                "updated_at": datetime.now(UTC).isoformat(),
            }

            # Insert into database
            response = (
                self.supabase_client.table("archon_git_repositories")
                .insert(repo_data)
                .execute()
            )

            if not response.data:
                logger.error("Failed to register repository - database returned no data")
                return False, {"error": "Failed to register repository"}

            repo_record = response.data[0]
            repo_id = repo_record["id"]

            logger.info(
                f"Registered git repository: {repo_name} (id={repo_id}, branch={default_branch})"
            )

            return True, {
                "repo_id": repo_id,
                "repo_name": repo_name,
                "default_branch": default_branch,
                "current_head_sha": current_head_sha,
            }

        except GitError:
            raise
        except Exception as e:
            logger.error(f"Error registering repository: {e}")
            raise GitError(
                f"Failed to register repository: {e}", repo_path=repo_path, original_error=str(e)
            ) from e

    def sync_commits(
        self, repo_id: str, branch_name: str, max_commits: int | None = None
    ) -> tuple[bool, dict[str, Any]]:
        """
        Read git log and populate archon_git_commits table.

        Args:
            repo_id: UUID of repository in archon_git_repositories
            branch_name: Branch name to sync commits from
            max_commits: Optional limit on number of commits to sync

        Returns:
            Tuple of (success, result_dict with commit_count)
        """
        repo_path: str | None = None
        try:
            # Get repository record
            repo_response = (
                self.supabase_client.table("archon_git_repositories")
                .select("*")
                .eq("id", repo_id)
                .execute()
            )

            if not repo_response.data:
                return False, {"error": f"Repository not found: {repo_id}"}

            repo_record = repo_response.data[0]
            repo_path = str(repo_record["repo_url"])

            # Validate repository
            repo = self._validate_repository(repo_path)

            # Check if branch exists
            if branch_name not in repo.heads:
                available_branches = [head.name for head in repo.heads]
                raise GitBranchNotFoundError(
                    f"Branch '{branch_name}' not found. Available: {available_branches}",
                    repo_path=repo_path,
                    branch=branch_name,
                    available_branches=available_branches,
                )

            # Get commits from branch (cap to prevent OOM)
            branch_ref = repo.heads[branch_name]
            if max_commits is None or max_commits > DEFAULT_MAX_COMMITS:
                max_commits = DEFAULT_MAX_COMMITS
                logger.info(f"Capping commit sync to {DEFAULT_MAX_COMMITS} for branch '{branch_name}'")

            commits = list(repo.iter_commits(branch_ref, max_count=max_commits))

            # Prepare commit data for batch insert
            commit_records = []
            for commit in commits:
                commit_data = {
                    "repo_id": repo_id,
                    "commit_sha": commit.hexsha,
                    "parent_shas": [parent.hexsha for parent in commit.parents],
                    "author_name": commit.author.name,
                    "author_date": datetime.fromtimestamp(commit.authored_date, tz=UTC).isoformat(),
                    "committer_name": commit.committer.name,
                    "commit_date": datetime.fromtimestamp(commit.committed_date, tz=UTC).isoformat(),
                    "message": commit.message.strip(),
                    "branches": [branch_name],
                    "tags": [],  # Tags can be populated separately if needed
                    "created_at": datetime.now(UTC).isoformat(),
                }

                # Conditionally include emails based on configuration (PII compliance)
                if STORE_COMMIT_EMAILS:
                    commit_data["author_email"] = commit.author.email
                    commit_data["committer_email"] = commit.committer.email
                else:
                    commit_data["author_email"] = None
                    commit_data["committer_email"] = None

                commit_records.append(commit_data)

            # Use RPC function to upsert commits with branch array merging
            if commit_records:
                BATCH_SIZE = 500
                inserted_count = 0

                # Process commits in batches
                for i in range(0, len(commit_records), BATCH_SIZE):
                    batch = commit_records[i : i + BATCH_SIZE]

                    # Call RPC function for each commit to properly merge branches array
                    for commit_data in batch:
                        try:
                            self.supabase_client.rpc(
                                "upsert_git_commit_with_branch_merge",
                                {
                                    "p_repo_id": commit_data["repo_id"],
                                    "p_commit_sha": commit_data["commit_sha"],
                                    "p_author_name": commit_data["author_name"],
                                    "p_author_email": commit_data["author_email"],
                                    "p_commit_date": commit_data["commit_date"],
                                    "p_message": commit_data["message"],
                                    "p_branches": commit_data["branches"],
                                },
                            ).execute()
                            inserted_count += 1
                        except Exception as e:
                            logger.error(f"Failed to upsert commit {commit_data['commit_sha']}: {e}")
                            continue

                    logger.debug(f"Upserted batch {i // BATCH_SIZE + 1}: {len(batch)} commits with branch merging")

                logger.info(f"Synced {inserted_count} commits for branch '{branch_name}'")
            else:
                inserted_count = 0
                logger.warning(f"No commits found for branch '{branch_name}'")

            # Update repository crawl status
            self.supabase_client.table("archon_git_repositories").update(
                {
                    "last_crawled_at": datetime.now(UTC).isoformat(),
                    "crawl_status": "completed",
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            ).eq("id", repo_id).execute()

            return True, {
                "commit_count": inserted_count,
                "branch": branch_name,
            }

        except GitError:
            raise
        except Exception as e:
            logger.error(f"Error syncing commits: {e}")
            # Update crawl status to failed
            try:
                self.supabase_client.table("archon_git_repositories").update(
                    {
                        "crawl_status": "failed",
                        "crawl_error": {"error": str(e), "timestamp": datetime.now(UTC).isoformat()},
                        "updated_at": datetime.now(UTC).isoformat(),
                    }
                ).eq("id", repo_id).execute()
            except Exception as update_error:
                logger.error(f"Failed to update crawl status: {update_error}")

            raise GitError(
                f"Failed to sync commits: {e}", repo_path=repo_path or "unknown", original_error=str(e)
            ) from e

    def get_file_tree(
        self, repo_id: str, commit_sha: str, path_prefix: str = ""
    ) -> tuple[bool, dict[str, Any]]:
        """
        List files at a specific commit.

        Args:
            repo_id: UUID of repository
            commit_sha: Commit SHA to read from
            path_prefix: Optional path prefix to filter results

        Returns:
            Tuple of (success, result_dict with files list)
        """
        repo_path: str | None = None
        try:
            # Get repository record
            repo_response = (
                self.supabase_client.table("archon_git_repositories")
                .select("*")
                .eq("id", repo_id)
                .execute()
            )

            if not repo_response.data:
                return False, {"error": f"Repository not found: {repo_id}"}

            repo_record = repo_response.data[0]
            repo_path = str(repo_record["repo_url"])

            # Validate repository
            repo = self._validate_repository(repo_path)

            # Get commit
            try:
                commit = repo.commit(commit_sha)
            except Exception as e:
                raise GitCommitNotFoundError(
                    f"Commit not found: {commit_sha}",
                    repo_path=repo_path,
                    commit_sha=commit_sha,
                    original_error=str(e),
                ) from e

            # List files in commit tree
            files = []
            for item in commit.tree.traverse():
                # Type guard: only process blob items
                if hasattr(item, "type") and item.type == "blob":  # Only files, not directories  # type: ignore
                    # Extract path and convert to string
                    item_path = str(item.path) if hasattr(item, "path") else ""  # type: ignore
                    if not item_path:
                        continue

                    # Filter by path prefix if provided
                    if path_prefix and not item_path.startswith(path_prefix):
                        continue

                    file_info = {
                        "file_path": item_path,
                        "file_name": Path(item_path).name,
                        "file_extension": Path(item_path).suffix.lower(),
                        "blob_sha": item.hexsha if hasattr(item, "hexsha") else "",  # type: ignore
                        "file_size": item.size if hasattr(item, "size") else 0,  # type: ignore
                        "language": self.detect_language(item_path),
                        "is_binary": not self.should_index_file(item_path),
                    }
                    files.append(file_info)

            return True, {
                "files": files,
                "file_count": len(files),
                "commit_sha": commit_sha,
            }

        except GitError:
            raise
        except Exception as e:
            logger.error(f"Error getting file tree: {e}")
            raise GitError(
                f"Failed to get file tree: {e}",
                repo_path=repo_path or "unknown",
                commit_sha=commit_sha,
                original_error=str(e),
            ) from e

    def get_file_content(
        self, repo_id: str, commit_sha: str, file_path: str
    ) -> tuple[bool, dict[str, Any]]:
        """
        Read file content at a specific commit via git.

        Args:
            repo_id: UUID of repository
            commit_sha: Commit SHA to read from
            file_path: Path to file within repository

        Returns:
            Tuple of (success, result_dict with content and metadata)
        """
        repo_path_str: str | None = None
        try:
            # Get repository record
            repo_response = (
                self.supabase_client.table("archon_git_repositories")
                .select("*")
                .eq("id", repo_id)
                .execute()
            )

            if not repo_response.data:
                return False, {"error": f"Repository not found: {repo_id}"}

            repo_record = repo_response.data[0]
            repo_path_str = str(repo_record["repo_url"])

            # Validate repository
            repo = self._validate_repository(repo_path_str)

            # Get commit
            try:
                commit = repo.commit(commit_sha)
            except Exception as e:
                raise GitCommitNotFoundError(
                    f"Commit not found: {commit_sha}",
                    repo_path=repo_path_str,
                    commit_sha=commit_sha,
                    original_error=str(e),
                ) from e

            # Get file blob from commit tree
            try:
                blob = commit.tree / file_path
            except KeyError as e:
                raise GitFileNotFoundError(
                    f"File not found in commit: {file_path}",
                    repo_path=repo_path_str,
                    commit_sha=commit_sha,
                    file_path=file_path,
                ) from e

            # Check if binary
            is_binary = not self.should_index_file(file_path)

            if is_binary:
                return False, {
                    "error": f"Cannot read binary file: {file_path}",
                    "is_binary": True,
                }

            # Read content
            try:
                content = blob.data_stream.read().decode("utf-8")
            except UnicodeDecodeError:
                logger.warning(f"Failed to decode file as UTF-8: {file_path}")
                return False, {
                    "error": f"File is not valid UTF-8: {file_path}",
                    "is_binary": True,
                }

            return True, {
                "content": content,
                "file_path": file_path,
                "file_size": blob.size,
                "blob_sha": blob.hexsha,
                "language": self.detect_language(file_path),
                "commit_sha": commit_sha,
            }

        except GitError:
            raise
        except Exception as e:
            logger.error(f"Error reading file content: {e}")
            raise GitError(
                f"Failed to read file content: {e}",
                repo_path=repo_path_str or "unknown",
                commit_sha=commit_sha,
                file_path=file_path,
                original_error=str(e),
            ) from e
