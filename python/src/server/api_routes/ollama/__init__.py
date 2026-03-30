"""
Ollama API Routes Package

Provides endpoints for Ollama LLM management:
- models: Model discovery and management
- health: Instance health monitoring
- validation: Instance validation
- embedding: Embedding routing and configuration
"""

from fastapi import APIRouter

from . import embedding, health, models, validation

# Create main router with prefix
router = APIRouter(prefix="/api/ollama", tags=["ollama"])

# Include all sub-routers
router.include_router(models.router)
router.include_router(health.router)
router.include_router(validation.router)
router.include_router(embedding.router)

__all__ = ["router"]
