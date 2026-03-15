"""
Versioning Service Module for Archon

This module provides core business logic for document versioning operations
that can be shared between MCP tools and FastAPI endpoints.
"""

# Removed direct logging import - using unified config
from datetime import datetime
from typing import Any

from ...config.logfire_config import get_logger
from ..database import get_database_connector

logger = get_logger(__name__)


class VersioningService:
    """Service class for document versioning operations"""

    def __init__(self):
        """Initialize versioning service"""
        pass

    async def create_version(
        self,
        project_id: str,
        field_name: str,
        content: dict[str, Any],
        change_summary: str = None,
        change_type: str = "update",
        document_id: str = None,
        created_by: str = "system",
    ) -> tuple[bool, dict[str, Any]]:
        """
        Create a version snapshot for a project JSONB field.

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            db = get_database_connector()
            import json

            # Get current highest version number for this project/field
            existing_versions = await db.fetch(
                """
                SELECT version_number FROM archon_document_versions
                WHERE project_id = $1 AND field_name = $2
                ORDER BY version_number DESC
                LIMIT 1
                """,
                project_id,
                field_name
            )

            next_version = 1
            if existing_versions:
                next_version = existing_versions[0]["version_number"] + 1

            # Create new version record
            result = await db.fetch(
                """
                INSERT INTO archon_document_versions
                (project_id, field_name, version_number, content, change_summary, change_type, document_id, created_by, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING *
                """,
                project_id,
                field_name,
                next_version,
                json.dumps(content),
                change_summary or f"{change_type.capitalize()} {field_name}",
                change_type,
                document_id,
                created_by,
                datetime.now().isoformat()
            )

            if result:
                return True, {
                    "version": dict(result[0]),
                    "project_id": project_id,
                    "field_name": field_name,
                    "version_number": next_version,
                }
            else:
                return False, {"error": "Failed to create version snapshot"}

        except Exception as e:
            logger.error(f"Error creating version: {e}")
            return False, {"error": f"Error creating version: {str(e)}"}

    async def list_versions(self, project_id: str, field_name: str = None) -> tuple[bool, dict[str, Any]]:
        """
        Get version history for project JSONB fields.

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            db = get_database_connector()

            # Build query
            if field_name:
                result = await db.fetch(
                    """
                    SELECT * FROM archon_document_versions
                    WHERE project_id = $1 AND field_name = $2
                    ORDER BY version_number DESC
                    """,
                    project_id,
                    field_name
                )
            else:
                result = await db.fetch(
                    """
                    SELECT * FROM archon_document_versions
                    WHERE project_id = $1
                    ORDER BY version_number DESC
                    """,
                    project_id
                )

            if result is not None:
                return True, {
                    "project_id": project_id,
                    "field_name": field_name,
                    "versions": [dict(r) for r in result],
                    "total_count": len(result),
                }
            else:
                return False, {"error": "Failed to retrieve version history"}

        except Exception as e:
            logger.error(f"Error getting version history: {e}")
            return False, {"error": f"Error getting version history: {str(e)}"}

    async def get_version_content(
        self, project_id: str, field_name: str, version_number: int
    ) -> tuple[bool, dict[str, Any]]:
        """
        Get the content of a specific version.

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            db = get_database_connector()

            # Query for specific version
            result = await db.fetch(
                """
                SELECT * FROM archon_document_versions
                WHERE project_id = $1 AND field_name = $2 AND version_number = $3
                """,
                project_id,
                field_name,
                version_number
            )

            if result:
                version = dict(result[0])
                return True, {
                    "version": version,
                    "content": version["content"],
                    "field_name": field_name,
                    "version_number": version_number,
                }
            else:
                return False, {"error": f"Version {version_number} not found for {field_name}"}

        except Exception as e:
            logger.error(f"Error getting version content: {e}")
            return False, {"error": f"Error getting version content: {str(e)}"}

    async def restore_version(
        self, project_id: str, field_name: str, version_number: int, restored_by: str = "system"
    ) -> tuple[bool, dict[str, Any]]:
        """
        Restore a project JSONB field to a specific version.

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            db = get_database_connector()
            import json

            # Get the version to restore
            version_result = await db.fetch(
                """
                SELECT * FROM archon_document_versions
                WHERE project_id = $1 AND field_name = $2 AND version_number = $3
                """,
                project_id,
                field_name,
                version_number
            )

            if not version_result:
                return False, {
                    "error": f"Version {version_number} not found for {field_name} in project {project_id}"
                }

            version_to_restore = dict(version_result[0])
            content_to_restore = version_to_restore["content"]

            # Get current content to create backup
            current_project = await db.fetch(
                f"SELECT {field_name} FROM archon_projects WHERE id = $1",
                project_id
            )

            if current_project:
                current_content = current_project[0].get(field_name, {})

                # Create backup version before restore
                backup_result = await self.create_version(
                    project_id=project_id,
                    field_name=field_name,
                    content=current_content,
                    change_summary=f"Backup before restoring to version {version_number}",
                    change_type="backup",
                    created_by=restored_by,
                )

                if not backup_result[0]:
                    logger.warning(f"Failed to create backup version: {backup_result[1]}")

            # Restore the content to project
            restore_result = await db.fetch(
                f"""
                UPDATE archon_projects
                SET {field_name} = $1, updated_at = $2
                WHERE id = $3
                RETURNING *
                """,
                json.dumps(content_to_restore),
                datetime.now().isoformat(),
                project_id
            )

            if restore_result:
                # Create restore version record
                restore_version_result = await self.create_version(
                    project_id=project_id,
                    field_name=field_name,
                    content=content_to_restore,
                    change_summary=f"Restored to version {version_number}",
                    change_type="restore",
                    created_by=restored_by,
                )

                return True, {
                    "project_id": project_id,
                    "field_name": field_name,
                    "restored_version": version_number,
                    "restored_by": restored_by,
                }
            else:
                return False, {"error": "Failed to restore version"}

        except Exception as e:
            logger.error(f"Error restoring version: {e}")
            return False, {"error": f"Error restoring version: {str(e)}"}
