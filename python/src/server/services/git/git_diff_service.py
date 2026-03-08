"""Git diff service for structured diff generation and analysis.

This service provides structured diff information with function-level context,
making it suitable for both human code review and AI agent reasoning.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from git import Repo
from git.diff import Diff

from .git_repository_service import GitError, GitRepositoryService

logger = logging.getLogger(__name__)


@dataclass
class DiffHunk:
    """A single diff hunk (continuous block of changes)."""

    old_start: int  # Starting line in old file
    old_lines: int  # Number of lines in old file
    new_start: int  # Starting line in new file
    new_lines: int  # Number of lines in new file
    context: str  # Function/class context where change occurred
    diff_text: str  # Raw diff text for this hunk
    additions: int  # Lines added in this hunk
    deletions: int  # Lines deleted in this hunk


@dataclass
class FileDiff:
    """Structured diff for a single file."""

    path: str
    old_path: str | None  # For renamed files
    status: str  # "added", "deleted", "modified", "renamed"
    language: str | None
    additions: int
    deletions: int
    hunks: list[DiffHunk]
    is_binary: bool


@dataclass
class StructuredDiff:
    """Complete structured diff between two commits."""

    from_commit: str
    to_commit: str
    files_changed: int
    additions: int
    deletions: int
    files: list[FileDiff]


class GitDiffService:
    """Service for generating structured Git diffs."""

    def __init__(self, repo_service: GitRepositoryService):
        """Initialize with a repository service for shared functionality."""
        self.repo_service = repo_service

    def get_diff(
        self, repo_path: str, from_sha: str, to_sha: str, file_path: str | None = None
    ) -> StructuredDiff:
        """
        Get structured diff between two commits.

        Args:
            repo_path: Path to Git repository
            from_sha: Starting commit SHA
            to_sha: Ending commit SHA
            file_path: Optional path to specific file (filters diff to one file)

        Returns:
            StructuredDiff with file-level and hunk-level details

        Raises:
            GitError: If repository, commits, or diff generation fails
        """
        try:
            repo = Repo(repo_path)

            # Get commits
            from_commit = repo.commit(from_sha)
            to_commit = repo.commit(to_sha)

            # Get diff
            if file_path:
                # Diff specific file only
                diffs = from_commit.diff(to_commit, paths=[file_path], create_patch=True)
            else:
                # Diff all files
                diffs = from_commit.diff(to_commit, create_patch=True)

            # Parse diffs into structured format
            file_diffs: list[FileDiff] = []
            total_additions = 0
            total_deletions = 0

            for diff_item in diffs:
                file_diff = self._parse_file_diff(diff_item)
                file_diffs.append(file_diff)
                total_additions += file_diff.additions
                total_deletions += file_diff.deletions

            return StructuredDiff(
                from_commit=from_sha,
                to_commit=to_sha,
                files_changed=len(file_diffs),
                additions=total_additions,
                deletions=total_deletions,
                files=file_diffs,
            )

        except Exception as e:
            logger.error(f"Error generating diff: {e}")
            raise GitError(
                f"Failed to generate diff: {e}",
                repo_path=repo_path,
                original_error=str(e),
            ) from e

    def _parse_file_diff(self, diff: Diff) -> FileDiff:
        """Parse a Git diff object into structured FileDiff."""
        # Determine file path and status
        if diff.new_file:
            path = diff.b_path or ""
            old_path = None
            status = "added"
        elif diff.deleted_file:
            path = diff.a_path or ""
            old_path = None
            status = "deleted"
        elif diff.renamed_file:
            path = diff.b_path or ""
            old_path = diff.a_path
            status = "renamed"
        else:
            path = diff.b_path or diff.a_path or ""
            old_path = None
            status = "modified"

        # Detect language
        language = self.repo_service.detect_language(path) if path else None

        # Check if binary
        is_binary = diff.b_blob is not None and diff.b_blob.mime_type.startswith("application/")

        # Parse hunks if not binary
        hunks: list[DiffHunk] = []
        additions = 0
        deletions = 0

        if not is_binary and diff.diff:
            # Decode diff text
            try:
                diff_text = diff.diff.decode("utf-8")
            except UnicodeDecodeError:
                logger.warning(f"Could not decode diff for {path} as UTF-8")
                diff_text = diff.diff.decode("utf-8", errors="replace")

            # Parse hunks from diff text
            hunks, additions, deletions = self._parse_hunks(diff_text)

        return FileDiff(
            path=path,
            old_path=old_path,
            status=status,
            language=language,
            additions=additions,
            deletions=deletions,
            hunks=hunks,
            is_binary=is_binary,
        )

    def _parse_hunks(self, diff_text: str) -> tuple[list[DiffHunk], int, int]:
        """
        Parse diff hunks from unified diff text.

        Returns:
            Tuple of (hunks, total_additions, total_deletions)
        """
        hunks: list[DiffHunk] = []
        total_additions = 0
        total_deletions = 0

        # Regex to match hunk headers: @@ -old_start,old_lines +new_start,new_lines @@ context
        hunk_pattern = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@ ?(.*)?")

        lines = diff_text.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i]
            match = hunk_pattern.match(line)

            if match:
                old_start = int(match.group(1))
                old_lines = int(match.group(2) or 1)
                new_start = int(match.group(3))
                new_lines = int(match.group(4) or 1)
                context = match.group(5) or ""

                # Collect hunk lines until next hunk or end
                hunk_lines = [line]
                i += 1
                hunk_additions = 0
                hunk_deletions = 0

                while i < len(lines) and not hunk_pattern.match(lines[i]):
                    hunk_line = lines[i]
                    hunk_lines.append(hunk_line)

                    # Count additions/deletions
                    if hunk_line.startswith("+") and not hunk_line.startswith("+++"):
                        hunk_additions += 1
                    elif hunk_line.startswith("-") and not hunk_line.startswith("---"):
                        hunk_deletions += 1

                    i += 1

                hunks.append(
                    DiffHunk(
                        old_start=old_start,
                        old_lines=old_lines,
                        new_start=new_start,
                        new_lines=new_lines,
                        context=context.strip(),
                        diff_text="\n".join(hunk_lines),
                        additions=hunk_additions,
                        deletions=hunk_deletions,
                    )
                )

                total_additions += hunk_additions
                total_deletions += hunk_deletions
            else:
                i += 1

        return hunks, total_additions, total_deletions
