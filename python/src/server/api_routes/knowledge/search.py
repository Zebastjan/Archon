"""
Search and RAG API Routes

Handles RAG queries and code example search:
- RAG query endpoint
- Code examples search
- Knowledge item search
"""

from typing import Any

from fastapi import APIRouter, HTTPException

from ...config.logfire_config import get_logger, safe_logfire_error
from ...services.search.rag_service import RAGService
from .models import RagQueryRequest

logger = get_logger(__name__)
router = APIRouter()


@router.post("/knowledge-items/search")
async def search_knowledge_items(request: RagQueryRequest) -> dict[str, Any]:
    """Search knowledge items - alias for RAG query."""
    # Validate query
    if not request.query:
        raise HTTPException(status_code=422, detail="Query is required")

    if not request.query.strip():
        raise HTTPException(status_code=422, detail="Query cannot be empty")

    # Delegate to the RAG query handler
    return await perform_rag_query(request)


@router.post("/rag/query")
async def perform_rag_query(request: RagQueryRequest) -> dict[str, Any]:
    """Perform a RAG query on the knowledge base using service layer."""
    # Validate query
    if not request.query:
        raise HTTPException(status_code=422, detail="Query is required")

    if not request.query.strip():
        raise HTTPException(status_code=422, detail="Query cannot be empty")

    try:
        # Use RAGService for unified RAG query with return_mode support
        search_service = RAGService()
        success, result = await search_service.perform_rag_query(
            query=request.query, source=request.source, match_count=request.match_count, return_mode=request.return_mode
        )

        if success:
            # Add success flag to match expected API response format
            result["success"] = True
            return result
        else:
            raise HTTPException(status_code=500, detail={"error": result.get("error", "RAG query failed")})
    except HTTPException:
        raise
    except Exception as e:
        safe_logfire_error(f"RAG query failed | error={str(e)} | query={request.query[:50]} | source={request.source}")
        raise HTTPException(status_code=500, detail={"error": f"RAG query failed: {str(e)}"})


@router.post("/rag/code-examples")
async def search_code_examples(request: RagQueryRequest) -> dict[str, Any]:
    """Search for code examples relevant to the query using dedicated code examples service."""
    try:
        # Use RAGService for code examples search
        search_service = RAGService()
        success, result = await search_service.search_code_examples_service(
            query=request.query,
            source_id=request.source,  # This is Optional[str] which matches the method signature
            match_count=request.match_count,
        )

        if success:
            # Add success flag and reformat to match expected API response format
            return {
                "success": True,
                "results": result.get("results", []),
                "reranked": result.get("reranking_applied", False),
                "error": None,
            }
        else:
            raise HTTPException(
                status_code=500,
                detail={"error": result.get("error", "Code examples search failed")},
            )
    except HTTPException:
        raise
    except Exception as e:
        safe_logfire_error(
            f"Code examples search failed | error={str(e)} | query={request.query[:50]} | source={request.source}"
        )
        raise HTTPException(status_code=500, detail={"error": f"Code examples search failed: {str(e)}"})


@router.post("/code-examples")
async def search_code_examples_simple(request: RagQueryRequest) -> dict[str, Any]:
    """Search for code examples - simplified endpoint at /api/code-examples."""
    # Delegate to the existing endpoint handler
    return await search_code_examples(request)
