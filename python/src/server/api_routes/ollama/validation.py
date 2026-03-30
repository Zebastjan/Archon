"""
Ollama Instance Validation API Routes

Handles instance validation with capability testing:
- Validate Ollama instances
- Check connectivity and model availability
- Assess capabilities
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...config.logfire_config import get_logger
from ...services.llm_provider import validate_provider_instance
from ...services.ollama.model_discovery_service import model_discovery_service

logger = get_logger(__name__)
router = APIRouter()


class InstanceValidationRequest(BaseModel):
    """Request for validating an Ollama instance."""

    instance_url: str = Field(..., description="URL of the Ollama instance")
    instance_type: str | None = Field(None, description="Instance type: chat, embedding, or both")
    timeout_seconds: int | None = Field(30, description="Timeout for validation in seconds")


class InstanceValidationResponse(BaseModel):
    """Response for instance validation."""

    is_valid: bool
    instance_url: str
    response_time_ms: float | None
    models_available: int
    error_message: str | None
    capabilities: dict[str, Any]
    health_status: dict[str, Any]


@router.post("/validate", response_model=InstanceValidationResponse)
async def validate_instance_endpoint(request: InstanceValidationRequest) -> InstanceValidationResponse:
    """
    Validate an Ollama instance with comprehensive capability testing.

    Performs deep validation including connectivity, model availability,
    capability detection, and performance assessment.
    """
    try:
        logger.info(f"Validating Ollama instance: {request.instance_url}")

        # Clean up URL
        instance_url = request.instance_url.rstrip("/")

        # Perform basic validation using the provider service
        validation_result = await validate_provider_instance("ollama", instance_url)

        capabilities = {}
        if validation_result["is_available"]:
            try:
                # Get detailed model information for capability analysis
                models = await model_discovery_service.discover_models(instance_url)

                capabilities = {
                    "total_models": len(models),
                    "chat_models": [m.name for m in models if "chat" in m.capabilities],
                    "embedding_models": [m.name for m in models if "embedding" in m.capabilities],
                    "supported_dimensions": list(set(m.embedding_dimensions for m in models if m.embedding_dimensions)),
                }

            except Exception as e:
                logger.warning(f"Error getting capabilities for {instance_url}: {e}")
                capabilities = {"error": str(e)}

        return InstanceValidationResponse(
            is_valid=validation_result["is_available"],
            instance_url=instance_url,
            response_time_ms=validation_result.get("response_time_ms"),
            models_available=validation_result.get("models_available", 0),
            error_message=validation_result.get("error_message"),
            capabilities=capabilities,
            health_status=validation_result,
        )

    except Exception as e:
        logger.error(f"Error validating instance {request.instance_url}: {e}")
        raise HTTPException(status_code=500, detail=f"Instance validation failed: {str(e)}")
