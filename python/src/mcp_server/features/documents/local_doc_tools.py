"""Local Document Management MCP Tools

MCP tools for managing local documents in the knowledge base.
"""

import json
import logging
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

logger = logging.getLogger(__name__)


def register_local_document_tools(mcp: FastMCP):
    """Register local document management tools with the MCP server."""

    @mcp.tool()
    async def local_doc_ingest_text(
        ctx: Context,
        title: str,
        content: str,
        source_url: str | None = None,
        tags: list[str] | None = None,
    ) -> str:
        """Ingest a text document into the local knowledge base.

        Args:
            title: Document title
            content: Document content/text
            source_url: Optional source URL
            tags: Optional list of tags

        Returns:
            JSON string with result
        """
        try:
            # Input validation
            if not title or not isinstance(title, str):
                return json.dumps({"success": False, "error": "title is required and must be a string"}, indent=2)
            
            if not content or not isinstance(content, str):
                return json.dumps({"success": False, "error": "content is required and must be a string"}, indent=2)

            from src.server.services.document_ingestion_service import get_document_ingestion_service
            
            service = get_document_ingestion_service()
            result = await service.ingest_text(
                content=content,
                title=title,
                source_url=source_url,
                metadata={"tags": tags or []},
            )
            
            if result["success"]:
                return json.dumps({
                    "success": True,
                    "source_id": result["source_id"],
                    "message": f"Document '{title}' ingested successfully",
                    "chunks_stored": result.get("chunks_stored", 0),
                }, indent=2)
            else:
                return json.dumps({"success": False, "error": result.get("error", "Ingestion failed")}, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to ingest text document: {e}")
            return json.dumps({"success": False, "error": str(e)}, indent=2)

    @mcp.tool()
    async def local_doc_delete(ctx: Context, source_id: str) -> str:
        """Delete a local document from the knowledge base.

        Args:
            source_id: The source ID of the document to delete

        Returns:
            JSON string with result
        """
        try:
            # Input validation
            if not source_id or not isinstance(source_id, str):
                return json.dumps({"success": False, "error": "source_id is required"}, indent=2)

            from src.server.services.source_management_service import SourceManagementService
            
            service = SourceManagementService()
            success, result = service.delete_source(source_id)
            
            if success:
                return json.dumps({
                    "success": True,
                    "message": f"Document {source_id} deleted successfully",
                }, indent=2)
            else:
                return json.dumps({"success": False, "error": result.get("error", "Deletion failed")}, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to delete document {source_id}: {e}")
            return json.dumps({"success": False, "error": str(e)}, indent=2)

    @mcp.tool()
    async def local_doc_list(ctx: Context) -> str:
        """List all local documents in the knowledge base.

        Returns:
            JSON string with documents list
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
            
            return json.dumps({
                "success": True,
                "documents": documents,
                "count": len(documents),
            }, indent=2)
            
        except Exception as e:
            logger.error(f"Failed to list documents: {e}")
            return json.dumps({"success": False, "error": str(e)}, indent=2)

    @mcp.tool()
    async def local_doc_get(ctx: Context, source_id: str) -> str:
        """Get details of a specific local document.

        Args:
            source_id: The source ID of the document

        Returns:
            JSON string with document details
        """
        try:
            # Input validation
            if not source_id or not isinstance(source_id, str):
                return json.dumps({"success": False, "error": "source_id is required"}, indent=2)

            from src.server.services.database import get_database_connector
            
            db = get_database_connector()
            row = await db.fetch_one(
                """SELECT source_id, source_display_name, source_url, 
                          total_word_count, created_at, summary
                   FROM archon_sources 
                   WHERE source_id = $1""",
                source_id
            )
            
            if row:
                doc = dict(row)
                if doc.get("created_at"):
                    doc["created_at"] = doc["created_at"].isoformat()
                return json.dumps({"success": True, "document": doc}, indent=2)
            else:
                return json.dumps({"success": False, "error": "Document not found"}, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to get document {source_id}: {e}")
            return json.dumps({"success": False, "error": str(e)}, indent=2)

    logger.info("✓ Local document tools registered")
