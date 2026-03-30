"""Tests for ProjectService.

Covers happy path, error cases, and edge cases for CRUD operations.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.server.services.projects.project_service import ProjectService


@pytest.fixture
def project_service():
    """Create a ProjectService instance."""
    return ProjectService()


@pytest.fixture
def mock_db():
    """Create a mock database connector."""
    mock = AsyncMock()
    return mock


class TestProjectService:
    """Test suite for ProjectService."""

    @pytest.mark.asyncio
    async def test_create_project_success(self, project_service, mock_db):
        """Test creating a project with valid data."""
        with patch("src.server.services.projects.project_service.get_database_connector", return_value=mock_db):
            mock_db.fetchrow.return_value = {
                "id": "test-project-id",
                "title": "Test Project",
                "github_repo": None,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }

            success, result = await project_service.create_project(title="Test Project", github_repo=None)

            assert success is True
            assert "project" in result
            assert result["project"]["title"] == "Test Project"

    @pytest.mark.asyncio
    async def test_create_project_empty_title(self, project_service):
        """Test creating a project with empty title fails validation."""
        success, result = await project_service.create_project(title="")

        assert success is False
        assert "error" in result
        assert "title" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_create_project_whitespace_title(self, project_service):
        """Test creating a project with whitespace-only title fails."""
        success, result = await project_service.create_project(title="   ")

        assert success is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_create_project_with_github_repo(self, project_service, mock_db):
        """Test creating a project with GitHub repo."""
        with patch("src.server.services.projects.project_service.get_database_connector", return_value=mock_db):
            mock_db.fetchrow.return_value = {
                "id": "test-project-id",
                "title": "Test Project",
                "github_repo": "https://github.com/user/repo",
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }

            success, result = await project_service.create_project(
                title="Test Project", github_repo="https://github.com/user/repo"
            )

            assert success is True
            assert result["project"]["github_repo"] == "https://github.com/user/repo"

    @pytest.mark.asyncio
    async def test_get_project_success(self, project_service, mock_db):
        """Test getting an existing project."""
        with patch("src.server.services.projects.project_service.get_database_connector", return_value=mock_db):
            mock_db.fetchrow.return_value = {
                "id": "test-project-id",
                "title": "Test Project",
                "github_repo": None,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }

            success, result = await project_service.get_project("test-project-id")

            assert success is True
            assert "project" in result
            assert result["project"]["id"] == "test-project-id"

    @pytest.mark.asyncio
    async def test_get_project_not_found(self, project_service, mock_db):
        """Test getting a non-existent project."""
        with patch("src.server.services.projects.project_service.get_database_connector", return_value=mock_db):
            mock_db.fetchrow.return_value = None

            success, result = await project_service.get_project("non-existent-id")

            assert success is False
            assert "error" in result
            assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_list_projects_success(self, project_service, mock_db):
        """Test listing projects."""
        with patch("src.server.services.projects.project_service.get_database_connector", return_value=mock_db):
            mock_db.fetch.return_value = [
                {
                    "id": "project-1",
                    "title": "Project 1",
                    "created_at": datetime.now(),
                },
                {
                    "id": "project-2",
                    "title": "Project 2",
                    "created_at": datetime.now(),
                },
            ]

            success, result = await project_service.list_projects()

            assert success is True
            assert "projects" in result
            assert len(result["projects"]) == 2

    @pytest.mark.asyncio
    async def test_update_project_success(self, project_service, mock_db):
        """Test updating a project."""
        with patch("src.server.services.projects.project_service.get_database_connector", return_value=mock_db):
            mock_db.fetchrow.return_value = {
                "id": "test-project-id",
                "title": "Updated Title",
                "github_repo": None,
                "updated_at": datetime.now(),
            }

            success, result = await project_service.update_project(project_id="test-project-id", title="Updated Title")

            assert success is True
            assert "project" in result
            assert result["project"]["title"] == "Updated Title"

    @pytest.mark.asyncio
    async def test_delete_project_success(self, project_service, mock_db):
        """Test deleting a project."""
        with patch("src.server.services.projects.project_service.get_database_connector", return_value=mock_db):
            mock_db.execute.return_value = None

            success, result = await project_service.delete_project("test-project-id")

            assert success is True
            assert "message" in result

    @pytest.mark.asyncio
    async def test_create_project_database_error(self, project_service, mock_db):
        """Test handling database errors during project creation."""
        with patch("src.server.services.projects.project_service.get_database_connector", return_value=mock_db):
            mock_db.fetchrow.side_effect = Exception("Database connection failed")

            success, result = await project_service.create_project(title="Test Project")

            assert success is False
            assert "error" in result
