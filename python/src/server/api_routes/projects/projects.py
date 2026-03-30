"""
Project Management API Routes

Handles project CRUD operations:
- List, create, update, delete projects
- Project features
- Project health checks
"""

import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Response
from fastapi import status as http_status

from ...config.logfire_config import get_logger, logfire
from ...services.projects import ProjectService, SourceLinkingService
from ...utils.etag_utils import check_etag, generate_etag
from ...utils.service_result_handler import handle_service_result
from .models import CreateProjectRequest, UpdateProjectRequest

logger = get_logger(__name__)
router = APIRouter()


@router.get("/projects")
async def list_projects(
    response: Response, include_content: bool = True, if_none_match: str | None = Header(None)
) -> dict[str, Any]:
    """
    List all projects.

    Args:
        include_content: If True (default), returns full project content.
                        If False, returns lightweight metadata with statistics.
    """
    try:
        logfire.debug(f"Listing all projects | include_content={include_content}")

        # Use ProjectService to get projects with include_content parameter
        project_service = ProjectService()
        success, result = await project_service.list_projects(include_content=include_content)

        if not success:
            raise HTTPException(status_code=500, detail=result)

        # Only format with sources if we have full content
        if include_content:
            # Use SourceLinkingService to format projects with sources
            source_service = SourceLinkingService()
            formatted_projects = await source_service.format_projects_with_sources(result["projects"])
        else:
            # Lightweight response doesn't need source formatting
            formatted_projects = result["projects"]

        # Monitor response size for optimization validation
        response_json = json.dumps(formatted_projects)
        response_size = len(response_json)

        # Log response metrics
        logfire.debug(
            f"Projects listed successfully | count={len(formatted_projects)} | "
            f"size_bytes={response_size} | include_content={include_content}"
        )

        # Log large responses at debug level (>100KB is worth noting, but normal for project data)
        if response_size > 100000:
            logfire.debug(
                f"Large response size | size_bytes={response_size} | "
                f"include_content={include_content} | project_count={len(formatted_projects)}"
            )

        # Generate ETag from stable data (excluding timestamp)
        etag_data = {"projects": formatted_projects, "count": len(formatted_projects)}
        current_etag = generate_etag(etag_data)

        # Generate response with timestamp for polling
        response_data = {
            "projects": formatted_projects,
            "timestamp": datetime.utcnow().isoformat(),
            "count": len(formatted_projects),
        }

        # Check if client's ETag matches
        if check_etag(if_none_match, current_etag):
            response.status_code = http_status.HTTP_304_NOT_MODIFIED
            response.headers["ETag"] = current_etag
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
            return None

        # Set headers
        response.headers["ETag"] = current_etag
        response.headers["Last-Modified"] = datetime.utcnow().isoformat()
        response.headers["Cache-Control"] = "no-cache, must-revalidate"

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Failed to list projects | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.post("/projects")
async def create_project(request: CreateProjectRequest) -> dict[str, Any]:
    """Create a new project with streaming progress."""
    # Validate title
    if not request.title:
        raise HTTPException(status_code=422, detail="Title is required")

    if not request.title.strip():
        raise HTTPException(status_code=422, detail="Title cannot be empty")

    try:
        logfire.info(f"Creating new project | title={request.title} | github_repo={request.github_repo}")

        # Prepare kwargs for additional project fields
        kwargs = {}
        if request.pinned is not None:
            kwargs["pinned"] = request.pinned
        if request.features:
            kwargs["features"] = request.features
        if request.data:
            kwargs["data"] = request.data

        # Create project directly with AI assistance
        from ...services.projects.project_creation_service import ProjectCreationService

        creation_service = ProjectCreationService()

        # Prepare source IDs
        technical_sources = request.technical_sources or []
        business_sources = request.business_sources or []

        success, result = await creation_service.create_project_with_ai(
            title=request.title,
            description=request.description,
            github_repo=request.github_repo,
            docs=request.docs,
            technical_sources=technical_sources,
            business_sources=business_sources,
            **kwargs,
        )

        if not success:
            logfire.error(f"Project creation failed | error={result}")
            raise HTTPException(status_code=500, detail=result)

        project = result["project"]
        progress_id = result.get("progress_id")

        logfire.info(f"Project created successfully | project_id={project['id']} | progress_id={progress_id}")

        return {
            "message": "Project creation started",
            "project": project,
            "progress_id": progress_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Project creation failed | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.get("/projects/{project_id}")
async def get_project(project_id: str) -> dict[str, Any]:
    """Get a specific project by ID."""
    try:
        logfire.debug(f"Getting project | project_id={project_id}")

        # Use ProjectService to get the project
        project_service = ProjectService()
        success, result = await project_service.get_project(project_id)

        result = handle_service_result(success, result, resource_type="project", resource_id=project_id)

        project = result["project"]

        # Format project with sources using SourceLinkingService
        source_service = SourceLinkingService()
        formatted_project = await source_service.format_project_with_sources(project)

        logfire.debug(
            f"Project retrieved successfully | project_id={project_id} | "
            f"technical_sources={len(formatted_project.get('technical_sources', []))} | "
            f"business_sources={len(formatted_project.get('business_sources', []))}"
        )

        return formatted_project

    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Failed to get project | error={str(e)} | project_id={project_id}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.put("/projects/{project_id}")
async def update_project(project_id: str, request: UpdateProjectRequest) -> dict[str, Any]:
    """Update a project with comprehensive Logfire monitoring."""
    try:
        from ...utils import get_supabase_client

        supabase_client = get_supabase_client()

        # Build update fields from request
        update_fields = {}
        if request.title is not None:
            update_fields["title"] = request.title
        if request.description is not None:
            update_fields["description"] = request.description
        if request.github_repo is not None:
            update_fields["github_repo"] = request.github_repo
        if request.docs is not None:
            update_fields["docs"] = request.docs
        if request.features is not None:
            update_fields["features"] = request.features
        if request.data is not None:
            update_fields["data"] = request.data
        if request.pinned is not None:
            update_fields["pinned"] = request.pinned

        # Create version snapshots for JSONB fields before updating
        if update_fields:
            try:
                from ...services.projects.versioning_service import VersioningService

                versioning_service = VersioningService(supabase_client)

                # Get current project for comparison
                project_service = ProjectService(supabase_client)
                success, current_result = await project_service.get_project(project_id)

                if success and current_result.get("project"):
                    current_project = current_result["project"]
                    version_count = 0

                    # Create versions for updated JSONB fields
                    for field_name in ["docs", "features", "data"]:
                        if field_name in update_fields:
                            current_content = current_project.get(field_name, {})
                            new_content = update_fields[field_name]

                            # Only create version if content actually changed
                            if current_content != new_content:
                                v_success, _ = await versioning_service.create_version(
                                    project_id=project_id,
                                    field_name=field_name,
                                    content=current_content,
                                    change_summary=f"Updated {field_name} via API",
                                    change_type="update",
                                    created_by="api_user",
                                )
                                if v_success:
                                    version_count += 1

                    logfire.info(f"Created {version_count} version snapshots before update")
            except ImportError:
                logfire.warning("VersioningService not available - skipping version snapshots")
            except Exception as e:
                logfire.warning(f"Failed to create version snapshots: {e}")
                # Don't fail the update, just log the warning

        # Use ProjectService to update the project
        project_service = ProjectService(supabase_client)
        success, result = await project_service.update_project(project_id, update_fields)

        result = handle_service_result(success, result, resource_type="project", resource_id=project_id)

        project = result["project"]

        # Handle source updates using SourceLinkingService
        source_service = SourceLinkingService(supabase_client)

        if request.technical_sources is not None or request.business_sources is not None:
            source_success, source_result = await source_service.update_project_sources(
                project_id=project_id,
                technical_sources=request.technical_sources,
                business_sources=request.business_sources,
            )

            if source_success:
                logfire.info(
                    f"Project sources updated | project_id={project_id} | "
                    f"technical_success={source_result.get('technical_success', 0)} | "
                    f"business_success={source_result.get('business_success', 0)}"
                )
            else:
                logfire.warning(f"Failed to update some sources: {source_result}")

        # Format project response with sources using SourceLinkingService
        formatted_project = await source_service.format_project_with_sources(project)

        logfire.info(f"Project updated successfully | project_id={project_id} | title={project.get('title')}")

        return formatted_project

    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Project update failed | project_id={project_id} | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str) -> dict[str, Any]:
    """Delete a project and all its tasks."""
    try:
        logfire.info(f"Deleting project | project_id={project_id}")

        # Use ProjectService to delete the project
        project_service = ProjectService()
        success, result = await project_service.delete_project(project_id)

        result = handle_service_result(success, result, resource_type="project", resource_id=project_id)

        logfire.info(
            f"Project deleted successfully | project_id={project_id} | deleted_tasks={result.get('deleted_tasks', 0)}"
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Failed to delete project | error={str(e)} | project_id={project_id}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.get("/projects/{project_id}/features")
async def get_project_features(project_id: str) -> dict[str, Any]:
    """Get features for a specific project."""
    try:
        logfire.debug(f"Getting project features | project_id={project_id}")

        # Use ProjectService to get the project
        project_service = ProjectService()
        success, result = await project_service.get_project(project_id)

        result = handle_service_result(success, result, resource_type="project", resource_id=project_id)

        features = result["project"].get("features", [])

        logfire.debug(f"Project features retrieved | project_id={project_id} | feature_count={len(features)}")

        return {"project_id": project_id, "features": features}

    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Failed to get project features | error={str(e)} | project_id={project_id}")
        raise HTTPException(status_code=500, detail={"error": str(e)})
