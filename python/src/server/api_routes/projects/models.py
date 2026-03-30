"""
Projects API Request/Response Models

Pydantic models for projects and tasks API endpoints.
"""

from typing import Any

from pydantic import BaseModel


class CreateProjectRequest(BaseModel):
    """Request model for creating a new project."""

    title: str
    description: str | None = None
    github_repo: str | None = None
    docs: list[Any] | None = None
    features: list[Any] | None = None
    data: list[Any] | None = None
    technical_sources: list[str] | None = None  # List of knowledge source IDs
    business_sources: list[str] | None = None  # List of knowledge source IDs
    pinned: bool | None = None  # Whether this project should be pinned to top


class UpdateProjectRequest(BaseModel):
    """Request model for updating a project."""

    title: str | None = None
    description: str | None = None
    github_repo: str | None = None
    docs: list[Any] | None = None
    features: list[Any] | None = None
    data: list[Any] | None = None
    technical_sources: list[str] | None = None
    business_sources: list[str] | None = None
    pinned: bool | None = None


class CreateTaskRequest(BaseModel):
    """Request model for creating a new task."""

    project_id: str
    title: str
    description: str | None = None
    status: str | None = "todo"
    assignee: str | None = "User"
    task_order: int | None = 0
    priority: str | None = "medium"
    feature: str | None = None


class UpdateTaskRequest(BaseModel):
    """Request model for updating a task."""

    title: str | None = None
    description: str | None = None
    status: str | None = None
    assignee: str | None = None
    task_order: int | None = None
    priority: str | None = None
    feature: str | None = None


class TaskStatusUpdateRequest(BaseModel):
    """Request model for updating task status (MCP compatible)."""

    status: str
