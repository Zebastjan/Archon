"""
Tests for GitRepositoryService

These tests verify the core functionality of the git repository service
including repository validation, commit syncing, and file operations.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.server.services.git import (
    GitBranchNotFoundError,
    GitError,
    GitRepositoryNotFoundError,
    GitRepositoryService,
)


class TestGitRepositoryService:
    """Test suite for GitRepositoryService"""

    @pytest.fixture
    def mock_supabase_client(self):
        """Create a mock Supabase client."""
        return MagicMock()

    @pytest.fixture
    def service(self, mock_supabase_client):
        """Create a GitRepositoryService instance with mocked client."""
        return GitRepositoryService(supabase_client=mock_supabase_client)

    def test_detect_language_python(self, service):
        """Test language detection for Python files."""
        assert service.detect_language("test.py") == "Python"
        assert service.detect_language("/path/to/script.py") == "Python"

    def test_detect_language_javascript(self, service):
        """Test language detection for JavaScript files."""
        assert service.detect_language("app.js") == "JavaScript"
        assert service.detect_language("component.jsx") == "JavaScript"

    def test_detect_language_typescript(self, service):
        """Test language detection for TypeScript files."""
        assert service.detect_language("app.ts") == "TypeScript"
        assert service.detect_language("component.tsx") == "TypeScript"

    def test_detect_language_dockerfile(self, service):
        """Test language detection for Dockerfile."""
        assert service.detect_language("Dockerfile") == "Dockerfile"
        assert service.detect_language("Dockerfile.dev") == "Dockerfile"

    def test_detect_language_makefile(self, service):
        """Test language detection for Makefile."""
        assert service.detect_language("Makefile") == "Makefile"
        assert service.detect_language("makefile") == "Makefile"

    def test_detect_language_unknown(self, service):
        """Test language detection for unknown extensions."""
        assert service.detect_language("test.xyz") is None

    def test_should_index_file_text(self, service):
        """Test file indexing for text files."""
        assert service.should_index_file("script.py") is True
        assert service.should_index_file("app.js") is True
        assert service.should_index_file("README.md") is True
        assert service.should_index_file("config.json") is True

    def test_should_index_file_binary(self, service):
        """Test file indexing for binary files."""
        assert service.should_index_file("image.png") is False
        assert service.should_index_file("video.mp4") is False
        assert service.should_index_file("archive.zip") is False
        assert service.should_index_file("document.pdf") is False

    def test_should_index_file_special_names(self, service):
        """Test file indexing for special file names."""
        assert service.should_index_file("Dockerfile") is True
        assert service.should_index_file("Makefile") is True
        assert service.should_index_file("README") is True

    def test_validate_repository_not_found(self, service):
        """Test repository validation with non-existent path."""
        with pytest.raises(GitRepositoryNotFoundError) as exc_info:
            service._validate_repository("/nonexistent/path")
        assert "does not exist" in str(exc_info.value)

    def test_validate_repository_not_git(self, service, tmp_path):
        """Test repository validation with non-git directory."""
        with pytest.raises(GitRepositoryNotFoundError) as exc_info:
            service._validate_repository(str(tmp_path))
        assert "No .git directory found" in str(exc_info.value)

    @patch("src.server.services.git.git_repository_service.Repo")
    def test_get_current_branch(self, mock_repo_class, service, tmp_path):
        """Test getting current branch name."""
        # Create .git directory
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Setup mock
        mock_repo = MagicMock()
        mock_repo.bare = False
        mock_repo.head.is_detached = False
        mock_repo.active_branch.name = "main"
        mock_repo_class.return_value = mock_repo

        result = service.get_current_branch(str(tmp_path))
        assert result == "main"

    @patch("src.server.services.git.git_repository_service.Repo")
    def test_get_current_branch_detached(self, mock_repo_class, service, tmp_path):
        """Test getting current branch when in detached HEAD state."""
        # Create .git directory
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Setup mock for detached HEAD
        mock_repo = MagicMock()
        mock_repo.bare = False
        mock_repo.head.is_detached = True
        mock_repo_class.return_value = mock_repo

        with pytest.raises(GitError) as exc_info:
            service.get_current_branch(str(tmp_path))
        assert "detached HEAD" in str(exc_info.value)

    @patch("src.server.services.git.git_repository_service.Repo")
    def test_get_current_commit_sha(self, mock_repo_class, service, tmp_path):
        """Test getting current commit SHA."""
        # Create .git directory
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Setup mock
        mock_repo = MagicMock()
        mock_repo.bare = False
        mock_repo.head.is_detached = False
        mock_repo.active_branch.name = "main"

        mock_branch = MagicMock()
        mock_commit = MagicMock()
        mock_commit.hexsha = "abc123def456"
        mock_branch.commit = mock_commit

        # Mock heads to behave like GitPython's IterableList
        mock_heads = MagicMock()
        mock_heads.__getitem__ = MagicMock(return_value=mock_branch)
        mock_heads.__contains__ = MagicMock(return_value=True)
        mock_repo.heads = mock_heads
        mock_repo_class.return_value = mock_repo

        result = service.get_current_commit_sha(str(tmp_path), "main")
        assert result == "abc123def456"

    @patch("src.server.services.git.git_repository_service.Repo")
    def test_get_current_commit_sha_branch_not_found(self, mock_repo_class, service, tmp_path):
        """Test getting commit SHA for non-existent branch."""
        # Create .git directory
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Setup mock
        mock_repo = MagicMock()
        mock_repo.bare = False

        # Mock heads to behave like GitPython's IterableList (empty)
        mock_heads = MagicMock()
        mock_heads.__contains__ = MagicMock(return_value=False)
        mock_heads.__iter__ = MagicMock(return_value=iter([]))
        mock_repo.heads = mock_heads
        mock_repo_class.return_value = mock_repo

        with pytest.raises(GitBranchNotFoundError) as exc_info:
            service.get_current_commit_sha(str(tmp_path), "nonexistent")
        assert "Branch 'nonexistent' not found" in str(exc_info.value)

    def test_error_to_dict(self):
        """Test GitError serialization to dictionary."""
        error = GitError("Test error", repo_path="/test/path", test_key="test_value")
        error_dict = error.to_dict()

        assert error_dict["error_type"] == "GitError"
        assert error_dict["message"] == "Test error"
        assert error_dict["repo_path"] == "/test/path"
        assert error_dict["metadata"]["test_key"] == "test_value"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
