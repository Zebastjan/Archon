"""
Project Service Module for Archon

This module provides core business logic for project operations that can be
shared between MCP tools and FastAPI endpoints. It follows the pattern of
separating business logic from transport-specific code.
"""

# Removed direct logging import - using unified config
from datetime import datetime
from typing import Any

from ...config.logfire_config import get_logger
from ..database import get_database_connector

logger = get_logger(__name__)


class ProjectService:
    """Service class for project operations"""

    def __init__(self):
        """Initialize project service"""
        pass

    async def create_project(self, title: str, github_repo: str = None) -> tuple[bool, dict[str, Any]]:
        """
        Create a new project with optional PRD and GitHub repo.

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            # Validate inputs
            if not title or not isinstance(title, str) or len(title.strip()) == 0:
                return False, {"error": "Project title is required and must be a non-empty string"}

            # Create project data
            project_data = {
                "title": title.strip(),
                "docs": [],  # Will add PRD document after creation
                "features": [],
                "data": [],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }

            if github_repo and isinstance(github_repo, str) and len(github_repo.strip()) > 0:
                project_data["github_repo"] = github_repo.strip()

            # Insert project
            db = get_database_connector()
            import json

            response = await db.fetch(
                """
                INSERT INTO archon_projects
                (title, docs, features, data, created_at, updated_at, github_repo)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING *
                """,
                project_data["title"],
                json.dumps(project_data["docs"]),
                json.dumps(project_data["features"]),
                json.dumps(project_data["data"]),
                project_data["created_at"],
                project_data["updated_at"],
                project_data.get("github_repo")
            )

            if not response:
                logger.error("Database returned empty data for project creation")
                return False, {"error": "Failed to create project - database returned no data"}

            project = dict(response[0])
            project_id = project["id"]
            logger.info(f"Project created successfully with ID: {project_id}")

            return True, {
                "project": {
                    "id": project_id,
                    "title": project["title"],
                    "github_repo": project.get("github_repo"),
                    "created_at": project["created_at"],
                }
            }

        except Exception as e:
            logger.error(f"Error creating project: {e}")
            return False, {"error": f"Database error: {str(e)}"}

    async def list_projects(self, include_content: bool = True) -> tuple[bool, dict[str, Any]]:
        """
        List all projects.

        Args:
            include_content: If True (default), includes docs, features, data fields.
                           If False, returns lightweight metadata only with counts.

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            db = get_database_connector()

            # Fetch all projects ordered by creation date
            response = await db.fetch(
                "SELECT * FROM archon_projects ORDER BY created_at DESC"
            )

            projects = []
            if include_content:
                # Current behavior - maintain backward compatibility
                for project in response:
                    projects.append({
                        "id": str(project["id"]),
                        "title": project["title"],
                        "github_repo": project.get("github_repo"),
                        "created_at": project["created_at"],
                        "updated_at": project["updated_at"],
                        "pinned": project.get("pinned", False),
                        "description": project.get("description", ""),
                        "docs": project.get("docs", []),
                        "features": project.get("features", []),
                        "data": project.get("data", []),
                    })
            else:
                # Lightweight response for MCP - fetch all data but only return metadata + stats
                # FIXED: N+1 query problem - now using single query
                for project in response:
                    # Calculate counts from fetched data (no additional queries)
                    docs_count = len(project.get("docs", []))
                    features_count = len(project.get("features", []))
                    has_data = bool(project.get("data", []))

                    # Return only metadata + stats, excluding large JSONB fields
                    projects.append({
                        "id": str(project["id"]),
                        "title": project["title"],
                        "github_repo": project.get("github_repo"),
                        "created_at": project["created_at"],
                        "updated_at": project["updated_at"],
                        "pinned": project.get("pinned", False),
                        "description": project.get("description", ""),
                        "stats": {
                            "docs_count": docs_count,
                            "features_count": features_count,
                            "has_data": has_data
                        }
                    })

            return True, {"projects": projects, "total_count": len(projects)}

        except Exception as e:
            logger.error(f"Error listing projects: {e}")
            return False, {"error": f"Error listing projects: {str(e)}"}

    async def get_project(self, project_id: str) -> tuple[bool, dict[str, Any]]:
        """
        Get a specific project by ID.

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            db = get_database_connector()

            # Get project
            response = await db.fetch(
                "SELECT * FROM archon_projects WHERE id = $1",
                project_id
            )

            if response:
                project = dict(response[0])
                
                # Convert UUID to string for JSON serialization
                project["id"] = str(project["id"])

                # Get linked sources
                technical_sources = []
                business_sources = []

                try:
                    # Get source IDs from project_sources table
                    sources_response = await db.fetch(
                        "SELECT source_id, notes FROM archon_project_sources WHERE project_id = $1",
                        project["id"]
                    )

                    # Collect source IDs by type
                    technical_source_ids = []
                    business_source_ids = []

                    for source_link in sources_response:
                        if source_link.get("notes") == "technical":
                            technical_source_ids.append(source_link["source_id"])
                        elif source_link.get("notes") == "business":
                            business_source_ids.append(source_link["source_id"])

                    # Fetch full source objects
                    if technical_source_ids:
                        # Build IN clause for PostgreSQL
                        placeholders = ", ".join(f"${i+1}" for i in range(len(technical_source_ids)))
                        tech_sources_response = await db.fetch(
                            f"SELECT * FROM archon_sources WHERE source_id IN ({placeholders})",
                            *technical_source_ids
                        )
                        technical_sources = [dict(row) for row in tech_sources_response]

                    if business_source_ids:
                        # Build IN clause for PostgreSQL
                        placeholders = ", ".join(f"${i+1}" for i in range(len(business_source_ids)))
                        biz_sources_response = await db.fetch(
                            f"SELECT * FROM archon_sources WHERE source_id IN ({placeholders})",
                            *business_source_ids
                        )
                        business_sources = [dict(row) for row in biz_sources_response]

                except Exception as e:
                    logger.warning(
                        f"Failed to retrieve linked sources for project {project['id']}: {e}"
                    )

                # Add sources to project data
                project["technical_sources"] = technical_sources
                project["business_sources"] = business_sources

                return True, {"project": project}
            else:
                return False, {"error": f"Project with ID {project_id} not found"}

        except Exception as e:
            logger.error(f"Error getting project: {e}")
            return False, {"error": f"Error getting project: {str(e)}"}

    async def delete_project(self, project_id: str) -> tuple[bool, dict[str, Any]]:
        """
        Delete a project and all its associated tasks.

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            db = get_database_connector()

            # First, check if project exists
            check_response = await db.fetch(
                "SELECT id FROM archon_projects WHERE id = $1",
                project_id
            )
            if not check_response:
                return False, {"error": f"Project with ID {project_id} not found"}

            # Get task count for reporting
            tasks_response = await db.fetch(
                "SELECT id FROM archon_tasks WHERE project_id = $1",
                project_id
            )
            tasks_count = len(tasks_response) if tasks_response else 0

            # Delete the project (tasks will be deleted by cascade)
            await db.execute(
                "DELETE FROM archon_projects WHERE id = $1",
                project_id
            )

            # For DELETE operations, success is indicated by no error
            return True, {
                "project_id": project_id,
                "deleted_tasks": tasks_count,
                "message": "Project deleted successfully",
            }

        except Exception as e:
            logger.error(f"Error deleting project: {e}")
            return False, {"error": f"Error deleting project: {str(e)}"}

    async def get_project_features(self, project_id: str) -> tuple[bool, dict[str, Any]]:
        """
        Get features from a project's features JSONB field.

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            db = get_database_connector()

            response = await db.fetch(
                "SELECT features FROM archon_projects WHERE id = $1",
                project_id
            )

            if not response:
                return False, {"error": "Project not found"}

            features = response[0].get("features", [])

            # Extract feature labels for dropdown options
            feature_options = []
            for feature in features:
                if isinstance(feature, dict) and "data" in feature and "label" in feature["data"]:
                    feature_options.append({
                        "id": feature.get("id", ""),
                        "label": feature["data"]["label"],
                        "type": feature["data"].get("type", ""),
                        "feature_type": feature.get("type", "page"),
                    })

            return True, {"features": feature_options, "count": len(feature_options)}

        except Exception as e:
            logger.error(f"Error getting project features: {e}")
            return False, {"error": f"Error getting project features: {str(e)}"}

    async def update_project(
        self, project_id: str, update_fields: dict[str, Any]
    ) -> tuple[bool, dict[str, Any]]:
        """
        Update a project with specified fields.

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            db = get_database_connector()
            import json

            # Build update data
            update_data = {"updated_at": datetime.now().isoformat()}

            # Add allowed fields
            allowed_fields = [
                "title",
                "description",
                "github_repo",
                "docs",
                "features",
                "data",
                "technical_sources",
                "business_sources",
                "pinned",
            ]

            for field in allowed_fields:
                if field in update_fields:
                    # Serialize JSONB fields
                    if field in ["docs", "features", "data"]:
                        update_data[field] = json.dumps(update_fields[field])
                    else:
                        update_data[field] = update_fields[field]

            # Handle pinning logic - only one project can be pinned at a time
            if update_fields.get("pinned") is True:
                # Unpin any other pinned projects first
                unpin_response = await db.fetch(
                    "UPDATE archon_projects SET pinned = $1 WHERE id != $2 AND pinned = $3 RETURNING *",
                    False, project_id, True
                )
                logger.debug(f"Unpinned {len(unpin_response or [])} other projects before pinning {project_id}")

            # Build dynamic UPDATE query
            set_clauses = []
            params = []
            param_count = 1

            for key, value in update_data.items():
                set_clauses.append(f"{key} = ${param_count}")
                params.append(value)
                param_count += 1

            params.append(project_id)

            # Update the target project
            response = await db.fetch(
                f"UPDATE archon_projects SET {', '.join(set_clauses)} WHERE id = ${param_count} RETURNING *",
                *params
            )

            if response and len(response) > 0:
                project = dict(response[0])
                return True, {"project": project, "message": "Project updated successfully"}
            else:
                # If update didn't return data, fetch the project to ensure it exists and get current state
                get_response = await db.fetch(
                    "SELECT * FROM archon_projects WHERE id = $1",
                    project_id
                )
                if get_response and len(get_response) > 0:
                    project = dict(get_response[0])
                    return True, {"project": project, "message": "Project updated successfully"}
                else:
                    return False, {"error": f"Project with ID {project_id} not found"}

        except Exception as e:
            logger.error(f"Error updating project: {e}")
            return False, {"error": f"Error updating project: {str(e)}"}
