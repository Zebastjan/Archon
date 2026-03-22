"""
Consolidated document management tools for Archon MCP Server.

Uses direct service imports instead of HTTP calls.
"""

import json
import logging
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from src.mcp_server.utils.error_handling import MCPErrorFormatter
from src.server.services.projects.document_service import DocumentService

logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE = 10


def optimize_document_response(doc: dict) -> dict:
    """Optimize document object for MCP response."""
    doc = doc.copy()
    if "content" in doc:
        del doc["content"]
    return doc


def register_document_tools(mcp: FastMCP):
    """Register consolidated document management tools with the MCP server."""
    
    service = DocumentService()

    @mcp.tool()
    async def find_documents(
        ctx: Context,
        project_id: str,
        document_id: str | None = None,
        query: str | None = None,
        document_type: str | None = None,
        page: int = 1,
        per_page: int = DEFAULT_PAGE_SIZE,
    ) -> str:
        """
        Find and search documents (consolidated: list + search + get).
        
        Args:
            project_id: Project UUID (required)
            document_id: Get specific document (returns full content)
            query: Search in title/content
            document_type: Filter by type
            page: Page number
            per_page: Items per page
        
        Returns:
            JSON array of documents or single document
        """
        try:
            # Single document get mode
            if document_id:
                success, result = await service.get_document(project_id, document_id)
                if success:
                    return json.dumps({"success": True, "document": result["document"]})
                else:
                    return MCPErrorFormatter.format_error(
                        error_type="not_found",
                        message=result.get("error", f"Document {document_id} not found"),
                        http_status=404,
                    )

            # List mode
            success, result = await service.list_documents(
                project_id=project_id,
                include_content=False
            )
            
            if success:
                documents = result.get("documents", [])
                
                # Apply type filter
                if document_type:
                    documents = [d for d in documents if d.get("document_type") == document_type]
                
                # Apply search
                if query:
                    query_lower = query.lower()
                    documents = [
                        d for d in documents
                        if query_lower in d.get("title", "").lower()
                    ]
                
                # Apply pagination
                start_idx = (page - 1) * per_page
                end_idx = start_idx + per_page
                paginated = documents[start_idx:end_idx]
                
                # Optimize responses
                optimized = [optimize_document_response(d) for d in paginated]
                
                return json.dumps({
                    "success": True,
                    "documents": optimized,
                    "count": len(optimized),
                    "total": len(documents),
                    "project_id": project_id,
                    "query": query,
                    "document_type": document_type
                })
            else:
                return MCPErrorFormatter.format_error(
                    "server_error",
                    result.get("error", "Failed to list documents")
                )

        except Exception as e:
            logger.error(f"Error listing documents: {e}", exc_info=True)
            return MCPErrorFormatter.from_exception(e, "list documents")

    @mcp.tool()
    async def manage_document(
        ctx: Context,
        action: str,
        project_id: str,
        document_id: str | None = None,
        title: str | None = None,
        document_type: str | None = None,
        content: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        author: str | None = None,
    ) -> str:
        """
        Manage documents (consolidated: create/update/delete).
        
        Args:
            action: "create" | "update" | "delete"
            project_id: Project UUID
            document_id: Document UUID for update/delete
            title: Document title
            document_type: spec/design/note/prp/api/guide
            content: Structured JSON content
            tags: List of tags
            author: Document author name
        
        Returns: {success: bool, document?: object, message: string}
        """
        try:
            if action == "create":
                if not title or not document_type:
                    return MCPErrorFormatter.format_error(
                        "validation_error",
                        "title and document_type required for create"
                    )
                
                success, result = await service.add_document(
                    project_id=project_id,
                    document_type=document_type,
                    title=title,
                    content=content or {},
                    tags=tags or [],
                    author=author or "User",
                )
                
                if success:
                    document = result.get("document", {})
                    return json.dumps({
                        "success": True,
                        "document": document,
                        "document_id": document.get("id"),
                        "message": "Document created successfully"
                    })
                else:
                    return MCPErrorFormatter.format_error(
                        "creation_failed",
                        result.get("error", "Failed to create document")
                    )

            elif action == "update":
                if not document_id:
                    return MCPErrorFormatter.format_error(
                        "validation_error",
                        "document_id required for update"
                    )
                
                update_fields = {}
                if title is not None:
                    update_fields["title"] = title
                if content is not None:
                    update_fields["content"] = content
                if tags is not None:
                    update_fields["tags"] = tags
                if author is not None:
                    update_fields["author"] = author
                
                if not update_fields:
                    return MCPErrorFormatter.format_error(
                        "validation_error",
                        "No fields to update"
                    )
                
                success, result = await service.update_document(
                    project_id=project_id,
                    doc_id=document_id,
                    update_fields=update_fields,
                )
                
                if success:
                    document = result.get("document")
                    return json.dumps({
                        "success": True,
                        "document": document,
                        "message": "Document updated successfully"
                    })
                else:
                    return MCPErrorFormatter.format_error(
                        "update_failed",
                        result.get("error", "Failed to update document")
                    )

            elif action == "delete":
                if not document_id:
                    return MCPErrorFormatter.format_error(
                        "validation_error",
                        "document_id required for delete"
                    )
                
                success, result = await service.delete_document(
                    project_id=project_id,
                    doc_id=document_id
                )
                
                if success:
                    return json.dumps({
                        "success": True,
                        "message": "Document deleted successfully"
                    })
                else:
                    return MCPErrorFormatter.format_error(
                        "delete_failed",
                        result.get("error", "Failed to delete document")
                    )

            else:
                return MCPErrorFormatter.format_error(
                    "invalid_action",
                    f"Unknown action: {action}"
                )

        except Exception as e:
            logger.error(f"Error managing document ({action}): {e}", exc_info=True)
            return MCPErrorFormatter.from_exception(e, f"{action} document")
