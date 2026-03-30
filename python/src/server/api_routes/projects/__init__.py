"""
Projects API Routes Package

This package contains all project and task management API routes:
- projects: Project CRUD operations
- tasks: Task management
- admin: Health checks and utilities
"""

from fastapi import APIRouter

from . import admin, projects, tasks

# Create main router with prefix
router = APIRouter(prefix="/api", tags=["projects"])

# Include all sub-routers
router.include_router(projects.router)
router.include_router(tasks.router)
router.include_router(admin.router)

__all__ = ["router"]
