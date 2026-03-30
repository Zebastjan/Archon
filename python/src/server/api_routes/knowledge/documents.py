"""
Document Upload and Ingestion API Routes

Handles document upload and text/markdown ingestion:
- File upload with progress tracking
- Text document ingestion
- Markdown document ingestion
"""

import asyncio
import json
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ...config.logfire_config import get_logger, safe_logfire_error, safe_logfire_info
from .models import IngestMarkdownRequest, IngestTextRequest

logger = get_logger(__name__)
router = APIRouter()


class DocumentUploadResponse(BaseModel):
    """Response model for document upload."""

    success: bool
    progressId: str
    message: str
    filename: str


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    tags: str | None = Form(None),
    knowledge_type: str = Form("technical"),
    extract_code_examples: bool = Form(True),
) -> dict[str, Any]:
    """Upload and process a document with progress tracking."""

    try:
        # DETAILED LOGGING: Track knowledge_type parameter flow
        safe_logfire_info(
            f"📋 UPLOAD: Starting document upload | filename={file.filename} | content_type={file.content_type} | knowledge_type={knowledge_type}"
        )

        # Generate unique progress ID
        progress_id = str(asyncio.get_running_loop().time()) + str(hash(file.filename))[:8]

        # Parse tags
        try:
            tag_list = json.loads(tags) if tags else []
            if tag_list is None:
                tag_list = []
            # Validate tags is a list of strings
            if not isinstance(tag_list, list):
                raise HTTPException(status_code=422, detail={"error": "tags must be a JSON array of strings"})
            if not all(isinstance(tag, str) for tag in tag_list):
                raise HTTPException(status_code=422, detail={"error": "tags must be a JSON array of strings"})
        except json.JSONDecodeError as ex:
            raise HTTPException(status_code=422, detail={"error": f"Invalid tags JSON: {str(ex)}"})

        # Read file content immediately to avoid closed file issues
        file_content = await file.read()
        file_metadata = {
            "filename": file.filename,
            "content_type": file.content_type,
            "size": len(file_content),
        }

        # Store document using document ingestion service
        from ...services.document_ingestion_service import get_document_ingestion_service

        service = get_document_ingestion_service()
        result = await service.ingest_document(
            file_content=file_content,
            filename=file_metadata["filename"],
            content_type=file_metadata["content_type"],
            tags=tag_list,
            knowledge_type=knowledge_type,
            extract_code_examples=extract_code_examples,
        )

        if result["success"]:
            safe_logfire_info(f"Document uploaded successfully | progress_id={progress_id} | filename={file.filename}")
            return {
                "success": True,
                "progressId": progress_id,
                "message": "Document uploaded successfully",
                "filename": file.filename,
                "source_id": result["source_id"],
                "chunks_stored": result["chunks_stored"],
            }
        else:
            raise HTTPException(status_code=500, detail={"error": result.get("error", "Upload failed")})

    except HTTPException:
        raise
    except Exception as e:
        safe_logfire_error(
            f"Failed to upload document | error={str(e)} | filename={getattr(file, 'filename', 'unknown')} | error_type={type(e).__name__}"
        )
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.post("/ingest/text")
async def ingest_text_document(request: IngestTextRequest) -> dict[str, Any]:
    """Ingest plain text into the knowledge base."""
    try:
        from ...services.document_ingestion_service import get_document_ingestion_service

        service = get_document_ingestion_service()
        result = await service.ingest_text(
            content=request.content,
            title=request.title,
            source_url=request.source_url,
            metadata={"tags": request.tags},
            chunk_size=request.chunk_size,
            chunk_overlap=request.chunk_overlap,
        )

        if result["success"]:
            return {
                "success": True,
                "source_id": result["source_id"],
                "title": result["title"],
                "chunks_stored": result["chunks_stored"],
                "chunks_total": result["chunks_total"],
            }
        else:
            raise HTTPException(status_code=500, detail={"error": result.get("error", "Ingestion failed")})

    except HTTPException:
        raise
    except Exception as e:
        safe_logfire_error(f"Text ingestion failed | error={str(e)} | title={request.title}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.post("/ingest/markdown")
async def ingest_markdown_document(request: IngestMarkdownRequest) -> dict[str, Any]:
    """Ingest Markdown document with code block extraction."""
    try:
        from ...services.document_ingestion_service import get_document_ingestion_service

        service = get_document_ingestion_service()
        result = await service.ingest_markdown(
            content=request.content,
            title=request.title,
            source_url=request.source_url,
            extract_code=request.extract_code,
        )

        if result["success"]:
            return {
                "success": True,
                "source_id": result["source_id"],
                "title": result["title"],
                "chunks_stored": result["chunks_stored"],
                "chunks_total": result["chunks_total"],
                "code_examples_count": result.get("code_examples_count", 0),
            }
        else:
            raise HTTPException(status_code=500, detail={"error": result.get("error", "Ingestion failed")})

    except HTTPException:
        raise
    except Exception as e:
        safe_logfire_error(f"Markdown ingestion failed | error={str(e)} | title={request.title}")
        raise HTTPException(status_code=500, detail={"error": str(e)})
