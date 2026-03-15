"""
Document Service Module for Archon

This module provides core business logic for document operations within projects
that can be shared between MCP tools and FastAPI endpoints.
"""

import uuid

# Removed direct logging import - using unified config
from datetime import datetime
from typing import Any

from ...config.logfire_config import get_logger
from ..database import get_database_connector

logger = get_logger(__name__)


class DocumentService:
    """Service class for document operations within projects"""

    def __init__(self):
        """Initialize document service"""
        pass

    async def add_document(
        self,
        project_id: str,
        document_type: str,
        title: str,
        content: dict[str, Any] = None,
        tags: list[str] = None,
        author: str = None,
    ) -> tuple[bool, dict[str, Any]]:
        """
        Add a new document to a project's docs JSONB field.

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            db = get_database_connector()
            import json

            # Get current project
            project_response = await db.fetch(
                "SELECT docs FROM archon_projects WHERE id = $1",
                project_id
            )

            if not project_response:
                return False, {"error": f"Project with ID {project_id} not found"}

            current_docs = project_response[0].get("docs", [])

            # Create new document entry
            new_doc = {
                "id": str(uuid.uuid4()),
                "document_type": document_type,
                "title": title,
                "content": content or {},
                "tags": tags or [],
                "status": "draft",
                "version": "1.0",
            }

            if author:
                new_doc["author"] = author

            # Add to docs array
            updated_docs = current_docs + [new_doc]

            # Update project
            response = await db.fetch(
                "UPDATE archon_projects SET docs = $1 WHERE id = $2 RETURNING *",
                json.dumps(updated_docs),
                project_id
            )

            if response:
                return True, {
                    "document": {
                        "id": new_doc["id"],
                        "project_id": project_id,
                        "document_type": new_doc["document_type"],
                        "title": new_doc["title"],
                        "status": new_doc["status"],
                        "version": new_doc["version"],
                    }
                }
            else:
                return False, {"error": "Failed to add document to project"}

        except Exception as e:
            logger.error(f"Error adding document: {e}")
            return False, {"error": f"Error adding document: {str(e)}"}

    async def list_documents(self, project_id: str, include_content: bool = False) -> tuple[bool, dict[str, Any]]:
        """
        List all documents in a project's docs JSONB field.

        Args:
            project_id: The project ID
            include_content: If True, includes full document content.
                           If False (default), returns metadata only.

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            db = get_database_connector()
            response = await db.fetch(
                "SELECT docs FROM archon_projects WHERE id = $1",
                project_id
            )

            if not response:
                return False, {"error": f"Project with ID {project_id} not found"}

            docs = response[0].get("docs", [])

            # Format documents for response
            documents = []
            for doc in docs:
                if include_content:
                    # Return full document
                    documents.append(doc)
                else:
                    # Return metadata only
                    documents.append({
                        "id": doc.get("id"),
                        "document_type": doc.get("document_type"),
                        "title": doc.get("title"),
                        "status": doc.get("status"),
                        "version": doc.get("version"),
                        "tags": doc.get("tags", []),
                        "author": doc.get("author"),
                        "created_at": doc.get("created_at"),
                        "updated_at": doc.get("updated_at"),
                        "stats": {
                            "content_size": len(str(doc.get("content", {})))
                        }
                    })

            return True, {
                "project_id": project_id,
                "documents": documents,
                "total_count": len(documents),
            }

        except Exception as e:
            logger.error(f"Error listing documents: {e}")
            return False, {"error": f"Error listing documents: {str(e)}"}

    async def get_document(self, project_id: str, doc_id: str) -> tuple[bool, dict[str, Any]]:
        """
        Get a specific document from a project's docs JSONB field.

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            db = get_database_connector()
            response = await db.fetch(
                "SELECT docs FROM archon_projects WHERE id = $1",
                project_id
            )

            if not response:
                return False, {"error": f"Project with ID {project_id} not found"}

            docs = response[0].get("docs", [])

            # Find the specific document
            document = None
            for doc in docs:
                if doc.get("id") == doc_id:
                    document = doc
                    break

            if document:
                return True, {"document": document}
            else:
                return False, {
                    "error": f"Document with ID {doc_id} not found in project {project_id}"
                }

        except Exception as e:
            logger.error(f"Error getting document: {e}")
            return False, {"error": f"Error getting document: {str(e)}"}

    async def update_document(
        self,
        project_id: str,
        doc_id: str,
        update_fields: dict[str, Any],
        create_version: bool = True,
    ) -> tuple[bool, dict[str, Any]]:
        """
        Update a document in a project's docs JSONB field.

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            db = get_database_connector()
            import json

            # Get current project docs
            project_response = await db.fetch(
                "SELECT docs FROM archon_projects WHERE id = $1",
                project_id
            )

            if not project_response:
                return False, {"error": f"Project with ID {project_id} not found"}

            current_docs = project_response[0].get("docs", [])

            # Create version snapshot if requested
            if create_version and current_docs:
                try:
                    from .versioning_service import VersioningService

                    versioning = VersioningService()

                    change_summary = self._build_change_summary(doc_id, update_fields)
                    await versioning.create_version(
                        project_id=project_id,
                        field_name="docs",
                        content=current_docs,
                        change_summary=change_summary,
                        change_type="update",
                        document_id=doc_id,
                        created_by=update_fields.get("author", "system"),
                    )
                except Exception as version_error:
                    logger.warning(
                        f"Version creation failed for document {doc_id}: {version_error}"
                    )

            # Make a copy to modify
            docs = current_docs.copy()

            # Find and update the document
            updated = False
            for i, doc in enumerate(docs):
                if doc.get("id") == doc_id:
                    # Update allowed fields
                    if "title" in update_fields:
                        docs[i]["title"] = update_fields["title"]
                    if "content" in update_fields:
                        docs[i]["content"] = update_fields["content"]
                    if "status" in update_fields:
                        docs[i]["status"] = update_fields["status"]
                    if "tags" in update_fields:
                        docs[i]["tags"] = update_fields["tags"]
                    if "author" in update_fields:
                        docs[i]["author"] = update_fields["author"]
                    if "version" in update_fields:
                        docs[i]["version"] = update_fields["version"]

                    docs[i]["updated_at"] = datetime.now().isoformat()
                    updated = True
                    break

            if not updated:
                return False, {
                    "error": f"Document with ID {doc_id} not found in project {project_id}"
                }

            # Update the project
            response = await db.fetch(
                """
                UPDATE archon_projects
                SET docs = $1, updated_at = $2
                WHERE id = $3
                RETURNING *
                """,
                json.dumps(docs),
                datetime.now().isoformat(),
                project_id
            )

            if response:
                # Find the updated document to return
                updated_doc = None
                for doc in docs:
                    if doc.get("id") == doc_id:
                        updated_doc = doc
                        break

                return True, {"document": updated_doc}
            else:
                return False, {"error": "Failed to update document"}

        except Exception as e:
            logger.error(f"Error updating document: {e}")
            return False, {"error": f"Error updating document: {str(e)}"}

    async def delete_document(self, project_id: str, doc_id: str) -> tuple[bool, dict[str, Any]]:
        """
        Delete a document from a project's docs JSONB field.

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            db = get_database_connector()
            import json

            # Get current project docs
            project_response = await db.fetch(
                "SELECT docs FROM archon_projects WHERE id = $1",
                project_id
            )

            if not project_response:
                return False, {"error": f"Project with ID {project_id} not found"}

            docs = project_response[0].get("docs", [])

            # Remove the document
            original_length = len(docs)
            docs = [doc for doc in docs if doc.get("id") != doc_id]

            if len(docs) == original_length:
                return False, {
                    "error": f"Document with ID {doc_id} not found in project {project_id}"
                }

            # Update the project
            response = await db.fetch(
                """
                UPDATE archon_projects
                SET docs = $1, updated_at = $2
                WHERE id = $3
                RETURNING *
                """,
                json.dumps(docs),
                datetime.now().isoformat(),
                project_id
            )

            if response:
                return True, {"project_id": project_id, "doc_id": doc_id}
            else:
                return False, {"error": "Failed to delete document"}

        except Exception as e:
            logger.error(f"Error deleting document: {e}")
            return False, {"error": f"Error deleting document: {str(e)}"}

    def _build_change_summary(self, doc_id: str, update_fields: dict[str, Any]) -> str:
        """Build a human-readable change summary"""
        changes = []
        if "title" in update_fields:
            changes.append(f"title to '{update_fields['title']}'")
        if "content" in update_fields:
            changes.append("content")
        if "status" in update_fields:
            changes.append(f"status to '{update_fields['status']}'")

        if changes:
            return f"Updated document '{doc_id}': {', '.join(changes)}"
        else:
            return f"Updated document '{doc_id}'"
