"""
Knowledge API Request/Response Models

Pydantic models for knowledge API endpoints.
"""

from pydantic import BaseModel, Field


class KnowledgeItemRequest(BaseModel):
    """Request model for creating/updating knowledge items."""

    url: str
    knowledge_type: str = "technical"
    tags: list[str] = []
    update_frequency: int = 7
    max_depth: int = 2  # Maximum crawl depth (1-5)
    extract_code_examples: bool = True  # Whether to extract code examples
    use_new_pipeline: bool = True  # Whether to use the new restartable pipeline

    class Config:
        schema_extra = {
            "example": {
                "url": "https://example.com",
                "knowledge_type": "technical",
                "tags": ["documentation"],
                "update_frequency": 7,
                "max_depth": 2,
                "extract_code_examples": True,
                "use_new_pipeline": True,
            }
        }


class IngestTextRequest(BaseModel):
    """Request model for ingesting text documents."""

    content: str
    title: str
    source_url: str | None = None
    tags: list[str] = []
    chunk_size: int = 512
    chunk_overlap: int = 50


class IngestMarkdownRequest(BaseModel):
    """Request model for ingesting markdown documents."""

    content: str
    title: str
    source_url: str | None = None
    tags: list[str] = []
    extract_code: bool = True
    chunk_size: int = 512
    chunk_overlap: int = 50


class RagQueryRequest(BaseModel):
    """Request model for RAG queries."""

    query: str
    source: str | None = None
    match_count: int = 5
    return_mode: str = "chunks"  # "chunks" or "pages"


class DocumentSearchRequest(BaseModel):
    """Request model for document search."""

    query: str
    top_k: int = 5
    similarity_threshold: float = 0.7
