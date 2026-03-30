"""Local Document Management API Routes

API endpoints for managing local documents in the knowledge base.
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/local-documents", tags=["local-documents"])


class DocumentIngestRequest(BaseModel):
    """Request model for document ingestion."""
    title: str
    content: str
    source_url: Optional[str] = None
    tags: List[str] = []


class DocumentResponse(BaseModel):
    """Response model for document operations."""
    success: bool
    source_id: Optional[str] = None
    message: str
    chunks_stored: int = 0


@router.post("/ingest-text", response_model=DocumentResponse)
async def ingest_text_document(request: DocumentIngestRequest):
    """Ingest a text document into the local knowledge base.
    
    Args:
        request: Document ingest request with title, content, and optional metadata
        
    Returns:
        DocumentResponse with success status and source_id
    """
    try:
        from src.server.services.document_ingestion_service import get_document_ingestion_service
        
        service = get_document_ingestion_service()
        result = await service.ingest_text(
            content=request.content,
            title=request.title,
            source_url=request.source_url,
            metadata={"tags": request.tags},
        )
        
        if result["success"]:
            return DocumentResponse(
                success=True,
                source_id=result["source_id"],
                message=f"Document '{request.title}' ingested successfully",
                chunks_stored=result.get("chunks_stored", 0)
            )
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Ingestion failed"))
            
    except Exception as e:
        logger.error(f"Failed to ingest text document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest-file", response_model=DocumentResponse)
async def ingest_file_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    tags: str = Form("[]"),
):
    """Ingest a file document into the local knowledge base.
    
    Args:
        file: Uploaded file
        title: Optional document title (defaults to filename)
        tags: JSON string of tags
        
    Returns:
        DocumentResponse with success status and source_id
    """
    try:
        import json
        from src.server.services.document_ingestion_service import get_document_ingestion_service
        from src.server.utils.document_parser import extract_text_from_document
        
        tag_list = json.loads(tags) if tags else []
        doc_title = title or file.filename
        
        # Read file content
        content = await file.read()
        
        # Extract text based on file type
        extracted_text = extract_text_from_document(content, file.filename, file.content_type)
        
        service = get_document_ingestion_service()
        result = await service.ingest_text(
            content=extracted_text,
            title=doc_title,
            source_url=f"file://{file.filename}",
            metadata={"tags": tag_list, "filename": file.filename},
        )
        
        if result["success"]:
            return DocumentResponse(
                success=True,
                source_id=result["source_id"],
                message=f"File '{file.filename}' ingested successfully",
                chunks_stored=result.get("chunks_stored", 0)
            )
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "File ingestion failed"))
            
    except Exception as e:
        logger.error(f"Failed to ingest file document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{source_id}")
async def delete_local_document(source_id: str):
    """Delete a local document from the knowledge base.
    
    Args:
        source_id: The source ID of the document to delete
        
    Returns:
        Success status and message
    """
    try:
        from src.server.services.source_management_service import SourceManagementService
        
        service = SourceManagementService()
        success, result = service.delete_source(source_id)
        
        if success:
            return {"success": True, "message": f"Document {source_id} deleted successfully"}
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Deletion failed"))
            
    except Exception as e:
        logger.error(f"Failed to delete document {source_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_local_documents():
    """List all local documents in the knowledge base.
    
    Returns:
        List of document metadata
    """
    try:
        from src.server.services.database import get_database_connector
        
        db = get_database_connector()
        rows = await db.fetch(
            """SELECT source_id, source_display_name, source_url, 
                      total_word_count, created_at, summary
               FROM archon_sources 
               WHERE source_url LIKE 'file://%' OR source_url IS NULL
               ORDER BY created_at DESC"""
        )
        
        documents = []
        for row in rows:
            doc = dict(row)
            if doc.get("created_at"):
                doc["created_at"] = doc["created_at"].isoformat()
            documents.append(doc)
        
        return {"success": True, "documents": documents, "count": len(documents)}
        
    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))
