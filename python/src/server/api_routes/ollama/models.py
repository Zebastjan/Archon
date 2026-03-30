"""
Ollama Model Management API Routes

Handles model discovery and storage:
- Discover models from Ollama instances
- Store discovered models with compatibility assessment
- Retrieve stored models
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field

from ...config.logfire_config import get_logger
from ...services.ollama.model_discovery_service import model_discovery_service

logger = get_logger(__name__)
router = APIRouter()


class ModelDiscoveryRequest(BaseModel):
    """Request for model discovery."""

    instance_urls: list[str] = Field(..., description="List of Ollama instance URLs")
    include_capabilities: bool = Field(True, description="Include model capability detection")
    cache_ttl: int | None = Field(300, description="Cache TTL in seconds")


class ModelDiscoveryResponse(BaseModel):
    """Response for model discovery."""

    total_models: int
    chat_models: list[dict[str, Any]]
    embedding_models: list[dict[str, Any]]
    host_status: dict[str, dict[str, Any]]
    discovery_errors: list[str]
    unique_model_names: list[str]


class StoredModelInfo(BaseModel):
    """Stored model information with Archon compatibility assessment."""

    name: str
    host: str
    model_type: str  # 'chat', 'embedding', 'multimodal'
    size_mb: int | None
    context_length: int | None
    parameters: str | None
    capabilities: list[str]
    archon_compatibility: str  # 'full', 'partial', 'limited'
    compatibility_features: list[str]
    limitations: list[str]
    performance_rating: str | None  # 'high', 'medium', 'low'
    description: str | None
    last_updated: str
    embedding_dimensions: int | None = None  # Dimensions for embedding models


class ModelListResponse(BaseModel):
    """Response containing discovered and stored models."""

    models: list[StoredModelInfo]
    total_count: int
    instances_checked: int
    last_discovery: str | None
    cache_status: str


class ModelDiscoveryAndStoreRequest(BaseModel):
    """Request for discovering and storing models with detailed info."""

    instance_urls: list[str] = Field(..., description="List of Ollama instance URLs")
    force_refresh: bool = Field(False, description="Force refresh even if cached data exists")


@router.get("/models", response_model=ModelDiscoveryResponse)
async def discover_models_endpoint(
    instance_urls: list[str] = Query(..., description="Ollama instance URLs"),
    include_capabilities: bool = Query(True, description="Include capability detection"),
    fetch_details: bool = Query(False, description="Fetch comprehensive model details via /api/show"),
    background_tasks: BackgroundTasks = None,
) -> ModelDiscoveryResponse:
    """
    Discover models from multiple Ollama instances with capability detection.

    This endpoint provides comprehensive model discovery across distributed Ollama
    deployments with automatic capability classification and health monitoring.
    """
    try:
        logger.info(f"Starting model discovery for {len(instance_urls)} instances with fetch_details={fetch_details}")

        # Validate instance URLs
        valid_urls = []
        for url in instance_urls:
            try:
                # Basic URL validation
                if not url.startswith(("http://", "https://")):
                    logger.warning(f"Invalid URL format: {url}")
                    continue
                valid_urls.append(url.rstrip("/"))
            except Exception as e:
                logger.warning(f"Error validating URL {url}: {e}")

        if not valid_urls:
            raise HTTPException(status_code=400, detail="No valid instance URLs provided")

        # Perform model discovery with optional detailed fetching
        discovery_result = await model_discovery_service.discover_models_from_multiple_instances(
            valid_urls, fetch_details=fetch_details
        )

        logger.info(f"Discovery complete: {discovery_result['total_models']} models found")

        return ModelDiscoveryResponse(
            total_models=discovery_result["total_models"],
            chat_models=discovery_result["chat_models"],
            embedding_models=discovery_result["embedding_models"],
            host_status=discovery_result["host_status"],
            discovery_errors=discovery_result["discovery_errors"],
            unique_model_names=discovery_result["unique_model_names"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in model discovery: {e}")
        raise HTTPException(status_code=500, detail=f"Model discovery failed: {str(e)}")
