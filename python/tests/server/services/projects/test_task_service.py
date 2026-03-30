"""Tests for TaskService.

Covers happy path, error cases, and edge cases for task CRUD operations.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.server.services.projects.task_service import TaskService


@pytest.fixture
def task_service():
    """Create a TaskService instance."""
    return TaskService()


@pytest.fixture
def mock_db():
    """Create a mock database connector."""
    mock = AsyncMock()
    return mock


class TestTaskService:
    """Test suite for TaskService."""

    def test_validate_status_valid(self, task_service):
        """Test validating valid statuses."""
        for status in ["todo", "doing", "review", "done"]:
            success, error = task_service.validate_status(status)
            assert success is True
            assert error == ""

    def test_validate_status_invalid(self, task_service):
        """Test validating invalid status."""
        success, error = task_service.validate_status("invalid")

        assert success is False
        assert "invalid" in error.lower()
        assert "todo" in error  # Should list valid options

    def test_validate_assignee_valid(self, task_service):
        """Test validating valid assignee."""
        success, error = task_service.validate_assignee("john.doe")

        assert success is True
        assert error == ""

    def test_validate_assignee_empty(self, task_service):
        """Test validating empty assignee."""
        success, error = task_service.validate_assignee("")

        assert success is False
        assert "assignee" in error.lower()

    def test_validate_assignee_whitespace(self, task_service):
        """Test validating whitespace-only assignee."""
        success, error = task_service.validate_assignee("   ")

        assert success is False
        assert "assignee" in error.lower()

    def test_validate_priority_valid(self, task_service):
        """Test validating valid priorities."""
        for priority in ["low", "medium", "high", "critical"]:
            success, error = task_service.validate_priority(priority)
            assert success is True
            assert error == ""

    def test_validate_priority_invalid(self, task_service):
        """Test validating invalid priority."""
        success, error = task_service.validate_priority("urgent")

        assert success is False
        assert "urgent" in error.lower()
        assert "high" in error  # Should list valid options

    @pytest.mark.asyncio
    async def test_create_task_success(self, task_service, mock_db):
        """Test creating a task with valid data."""
        with patch("src.server.services.projects.task_service.get_database_connector", return_value=mock_db):
            mock_db.fetchrow.return_value = {
                "id": "test-task-id",
                "project_id": "test-project-id",
                "title": "Test Task",
                "description": "Test Description",
                "status": "todo",
                "assignee": "john.doe",
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }

            success, result = await task_service.create_task(
                project_id="test-project-id", title="Test Task", description="Test Description", assignee="john.doe"
            )

            assert success is True
            assert "task" in result
            assert result["task"]["title"] == "Test Task"

    @pytest.mark.asyncio
    async def test_create_task_invalid_status(self, task_service):
        """Test creating a task with invalid status."""
        success, result = await task_service.create_task(
            project_id="test-project-id", title="Test Task", status="invalid-status"
        )

        assert success is False
        assert "error" in result
        assert "status" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_get_task_success(self, task_service, mock_db):
        """Test getting an existing task."""
        with patch("src.server.services.projects.task_service.get_database_connector", return_value=mock_db):
            mock_db.fetchrow.return_value = {
                "id": "test-task-id",
                "project_id": "test-project-id",
                "title": "Test Task",
                "status": "todo",
                "created_at": datetime.now(),
            }

            success, result = await task_service.get_task("test-task-id")

            assert success is True
            assert "task" in result
            assert result["task"]["id"] == "test-task-id"

    @pytest.mark.asyncio
    async def test_get_task_not_found(self, task_service, mock_db):
        """Test getting a non-existent task."""
        with patch("src.server.services.projects.task_service.get_database_connector", return_value=mock_db):
            mock_db.fetchrow.return_value = None

            success, result = await task_service.get_task("non-existent-id")

            assert success is False
            assert "error" in result
            assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_update_task_status(self, task_service, mock_db):
        """Test updating task status."""
        with patch("src.server.services.projects.task_service.get_database_connector", return_value=mock_db):
            mock_db.fetchrow.return_value = {
                "id": "test-task-id",
                "status": "doing",
                "updated_at": datetime.now(),
            }

            success, result = await task_service.update_task(task_id="test-task-id", status="doing")

            assert success is True
            assert "task" in result
            assert result["task"]["status"] == "doing"

    @pytest.mark.asyncio
    async def test_delete_task_success(self, task_service, mock_db):
        """Test deleting a task."""
        with patch("src.server.services.projects.task_service.get_database_connector", return_value=mock_db):
            mock_db.execute.return_value = None

            success, result = await task_service.delete_task("test-task-id")

            assert success is True
            assert "message" in result
