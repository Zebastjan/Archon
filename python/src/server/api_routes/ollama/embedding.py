"""
Ollama Embedding API Routes

Handles embedding routing and configuration:
- Analyze optimal embedding routes
- Get available embedding routes
- Clear embedding cache
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ...config.logfire_config import get_logger
from ...services.ollama.embedding_router import embedding_router
from ...services.ollama.model_discovery_service import model_discovery_service

logger = get_logger(__name__)
router = APIRouter()


class EmbeddingRouteRequest(BaseModel):
    """Request for embedding routing analysis."""

    model_name: str = Field(..., description="Name of the embedding model")
    instance_url: str = Field(..., description="URL of the Ollama instance")
    text_sample: str | None = Field(None, description="Optional text sample for optimization")


class EmbeddingRouteResponse(BaseModel):
    """Response for embedding routing."""

    target_column: str
    model_name: str
    instance_url: str
    dimensions: int
    confidence: float
    fallback_applied: bool
    routing_strategy: str
    performance_score: float | None


@router.post("/embedding/route", response_model=EmbeddingRouteResponse)
async def analyze_embedding_route_endpoint(request: EmbeddingRouteRequest) -> EmbeddingRouteResponse:
    """
    Analyze optimal routing for embedding operations.

    Determines the best database column, dimension handling, and performance
    characteristics for a specific model and instance combination.
    """
    try:
        logger.info(f"Analyzing embedding route for {request.model_name} on {request.instance_url}")

        # Get routing decision from the embedding router
        routing_decision = await embedding_router.route_embedding(
            model_name=request.model_name, instance_url=request.instance_url, text_content=request.text_sample
        )

        # Calculate performance score
        performance_score = embedding_router._calculate_performance_score(routing_decision.dimensions)

        return EmbeddingRouteResponse(
            target_column=routing_decision.target_column,
            model_name=routing_decision.model_name,
            instance_url=routing_decision.instance_url,
            dimensions=routing_decision.dimensions,
            confidence=routing_decision.confidence,
            fallback_applied=routing_decision.fallback_applied,
            routing_strategy=routing_decision.routing_strategy,
            performance_score=performance_score,
        )

    except Exception as e:
        logger.error(f"Error analyzing embedding route: {e}")
        raise HTTPException(status_code=500, detail=f"Embedding route analysis failed: {str(e)}")


@router.get("/embedding/routes")
async def get_available_embedding_routes_endpoint(
    instance_urls: list[str] = Query(..., description="Ollama instance URLs"),
    sort_by_performance: bool = Query(True, description="Sort by performance score"),
) -> dict[str, Any]:
    """
    Get all available embedding routes across multiple instances.

    Provides a comprehensive view of embedding capabilities with performance
    rankings and routing recommendations for optimal throughput.
    """
    try:
        logger.info(f"Getting embedding routes for {len(instance_urls)} instances")

        # Get available routes
        routes = await embedding_router.get_available_embedding_routes(instance_urls)

        # Convert to response format
        route_data = []
        for route in routes:
            route_data.append(
                {
                    "model_name": route.model_name,
                    "instance_url": route.instance_url,
                    "dimensions": route.dimensions,
                    "column_name": route.column_name,
                    "performance_score": route.performance_score,
                    "index_type": embedding_router.get_optimal_index_type(route.dimensions),
                }
            )

        # Group by dimension for analysis
        dimension_stats = {}
        for route in routes:
            dim = route.dimensions
            if dim not in dimension_stats:
                dimension_stats[dim] = {"count": 0, "models": [], "avg_performance": 0}
            dimension_stats[dim]["count"] += 1
            dimension_stats[dim]["models"].append(route.model_name)
            dimension_stats[dim]["avg_performance"] += route.performance_score

        # Calculate averages
        for dim_data in dimension_stats.values():
            if dim_data["count"] > 0:
                dim_data["avg_performance"] /= dim_data["count"]

        return {
            "total_routes": len(routes),
            "routes": route_data,
            "dimension_analysis": dimension_stats,
            "routing_statistics": embedding_router.get_routing_statistics(),
        }

    except Exception as e:
        logger.error(f"Error getting embedding routes: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get embedding routes: {str(e)}")


@router.delete("/cache")
async def clear_ollama_cache_endpoint() -> dict[str, str]:
    """Clear Ollama service caches."""
    try:
        # Clear model discovery cache
        model_discovery_service._discovery_cache.clear()

        # Clear embedding router cache
        embedding_router.clear_cache()

        logger.info("Ollama caches cleared successfully")
        return {"status": "success", "message": "Ollama caches cleared"}
    except Exception as e:
        logger.error(f"Error clearing Ollama cache: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")
