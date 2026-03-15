"""
Project Creation Service Module for Archon

This module handles the complex project creation workflow including
AI-assisted documentation generation and progress tracking.
"""

# Removed direct logging import - using unified config
from datetime import UTC, datetime
from typing import Any

from ...config.logfire_config import get_logger
from ..database import get_database_connector

logger = get_logger(__name__)


class ProjectCreationService:
    """Service class for advanced project creation with AI assistance"""

    def __init__(self):
        """Initialize project creation service"""
        pass

    async def create_project_with_ai(
        self,
        progress_id: str,
        title: str,
        description: str | None = None,
        github_repo: str | None = None,
        **kwargs,
    ) -> tuple[bool, dict[str, Any]]:
        """
        Create a project with AI-assisted documentation generation.

        Args:
            progress_id: Progress tracking identifier
            title: Project title
            description: Project description
            github_repo: GitHub repository URL
            **kwargs: Additional project data

        Returns:
            Tuple of (success, result_dict)
        """
        logger.info(
            f"🏗️ [PROJECT-CREATION] Starting create_project_with_ai for progress_id: {progress_id}, title: {title}"
        )
        try:
            # Database setup step

            # Create basic project structure
            project_data = {
                "title": title,
                "description": description or "",
                "github_repo": github_repo,
                "created_at": datetime.now(UTC).isoformat(),
                "updated_at": datetime.now(UTC).isoformat(),
                "docs": [],  # Empty docs array to start - PRD will be added here by DocumentAgent
                "features": kwargs.get("features", {}),
                "data": kwargs.get("data", {}),
            }

            # Add any additional fields from kwargs
            for key in ["pinned"]:
                if key in kwargs:
                    project_data[key] = kwargs[key]

            # Create the project in database
            db = get_database_connector()
            import json

            response = await db.fetch(
                """
                INSERT INTO archon_projects
                (title, description, github_repo, created_at, updated_at, docs, features, data, pinned)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING *
                """,
                project_data["title"],
                project_data["description"],
                project_data.get("github_repo"),
                project_data["created_at"],
                project_data["updated_at"],
                json.dumps(project_data["docs"]),
                json.dumps(project_data["features"]),
                json.dumps(project_data["data"]),
                project_data.get("pinned", False),
            )

            if not response:
                raise RuntimeError(f"Insert returned no data for project '{title}'")

            project_id = response[0]["id"]
            logger.info(f"Created project {project_id} in database")

            # AI processing step

            # Generate AI documentation if API key is available
            ai_success = await self._generate_ai_documentation(
                progress_id, project_id, title, description, github_repo
            )

            # Final success - fetch complete project data
            final_project_response = await db.fetch(
                "SELECT * FROM archon_projects WHERE id = $1",
                project_id
            )

            if final_project_response:
                final_project = dict(final_project_response[0])

                # Prepare project data for frontend
                project_data_for_frontend = {
                    "id": final_project["id"],
                    "title": final_project["title"],
                    "description": final_project.get("description", ""),
                    "github_repo": final_project.get("github_repo"),
                    "created_at": final_project["created_at"],
                    "updated_at": final_project["updated_at"],
                    "docs": final_project.get("docs", []),  # PRD documents will be here
                    "features": final_project.get("features", {}),
                    "data": final_project.get("data", {}),
                    "pinned": final_project.get("pinned", False),
                    "technical_sources": [],  # Empty initially
                    "business_sources": [],  # Empty initially
                }


                return True, {
                    "project_id": project_id,
                    "project": project_data_for_frontend,
                    "ai_documentation_generated": ai_success,
                }
            else:
                # Fallback if we can't fetch the project

                return True, {"project_id": project_id, "ai_documentation_generated": ai_success}

        except Exception as e:
            logger.error(
                f"🚨 [PROJECT-CREATION] Project creation failed for progress_id={progress_id}, title={title}: {e}",
                exc_info=True,
            )
            return False, {"error": str(e)}

    async def _generate_ai_documentation(
        self,
        progress_id: str,
        project_id: str,
        title: str,
        description: str | None,
        github_repo: str | None,
    ) -> bool:
        """
        Generate AI documentation for the project.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if LLM provider is configured
            from ..credential_service import credential_service
            provider_config = await credential_service.get_active_provider("llm")

            if not provider_config:
                # No LLM provider configured, skip AI documentation
                return False

            # Import DocumentAgent (lazy import to avoid startup issues)
            from ...agents.document_agent import DocumentAgent



            # Initialize DocumentAgent
            document_agent = DocumentAgent()

            # Generate comprehensive PRD using conversation
            prd_request = f"Create a PRD document titled '{title} - Product Requirements Document' for a project called '{title}'"
            if description:
                prd_request += f" with the following description: {description}"
            if github_repo:
                prd_request += f" (GitHub repo: {github_repo})"

            # Create a progress callback for the document agent
            async def agent_progress_callback(update_data):
                pass  # Progress tracking removed

            # Run the document agent to create PRD
            agent_result = await document_agent.run_conversation(
                user_message=prd_request,
                project_id=project_id,
                user_id="system",
                progress_callback=agent_progress_callback,
            )

            if agent_result.success:

                return True
            else:
                return False

        except Exception as ai_error:
            logger.warning(f"AI generation failed, continuing with basic project: {ai_error}")

            return False
