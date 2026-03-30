"""
Knowledge API Routes Package

This package contains all knowledge management API routes, split by concern:
- items: Knowledge item CRUD operations
- documents: Document upload and ingestion
- search: RAG queries and code example search
- sources: Knowledge source management
- admin: Health checks and database metrics
"""

from fastapi import APIRouter

from . import admin, documents, items, models, search, sources

# Create main router
router = APIRouter(tags=["knowledge"])

# Include all sub-routers
router.include_router(items.router)
router.include_router(documents.router)
router.include_router(search.router)
router.include_router(sources.router)
router.include_router(admin.router)

__all__ = ["router", "models"]
