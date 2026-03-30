"""
RAG Module for Archon MCP Server

Uses direct database queries instead of heavy service imports.
This avoids the numpy/OpenAI/embedding dependency chain.
"""

import json
import logging
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

logger = logging.getLogger(__name__)


# Input validation utilities
def validate_non_empty_string(value: str, name: str, max_length: int = 500) -> tuple[bool, str]:
    """Validate that a string is non-empty and within length limits."""
    if not value or not isinstance(value, str):
        return False, f"{name} is required and must be a string"
    if len(value.strip()) == 0:
        return False, f"{name} cannot be empty or whitespace only"
    if len(value) > max_length:
        return False, f"{name} exceeds maximum length of {max_length} characters"
    return True, ""


def validate_match_count(value: int, max_allowed: int = 50) -> tuple[bool, str]:
    """Validate match_count parameter."""
    if not isinstance(value, int):
        return False, f"match_count must be an integer, got {type(value).__name__}"
    if value < 1:
        return False, "match_count must be at least 1"
    if value > max_allowed:
        return False, f"match_count cannot exceed {max_allowed}"
    return True, ""


def validate_return_mode(value: str) -> tuple[bool, str]:
    """Validate return_mode parameter."""
    if value not in ("pages", "chunks"):
        return False, f"return_mode must be 'pages' or 'chunks', got '{value}'"
    return True, ""


def validate_uuid(value: str, name: str = "id") -> tuple[bool, str]:
    """Validate UUID format."""
    import re
    if not value or not isinstance(value, str):
        return False, f"{name} is required and must be a string"
    # UUID pattern: 8-4-4-4-12 hex digits
    uuid_pattern = r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
    if not re.match(uuid_pattern, value):
        return False, f"{name} must be a valid UUID format"
    return True, ""


def validate_url(value: str) -> tuple[bool, str]:
    """Validate URL format."""
    if not value or not isinstance(value, str):
        return False, "url is required and must be a string"
    if len(value) > 2048:
        return False, "url exceeds maximum length of 2048 characters"
    # Basic URL validation
    if not (value.startswith('http://') or value.startswith('https://') or value.startswith('file://')):
        return False, "url must start with http://, https://, or file://"
    return True, ""


def register_rag_tools(mcp: FastMCP):
    """Register all RAG tools with the MCP server."""

    @mcp.tool()
    async def rag_get_available_sources(ctx: Context) -> str:
        """
        Get list of available sources in the knowledge base.

        Returns:
            JSON string with available sources
        """
        import traceback
        import sys
        print(f"DEBUG: rag_get_available_sources called", file=sys.stderr)
        try:
            from src.server.services.database import get_database_connector
            
            db = get_database_connector()
            query = """SELECT source_id, source_display_name as name, source_url as url, 
                          summary as description, total_word_count, created_at
                   FROM archon_sources 
                   ORDER BY source_display_name"""
            print(f"DEBUG: about to execute query", file=sys.stderr)
            rows = await db.fetch(query)
            print(f"DEBUG: query returned {len(rows)} rows", file=sys.stderr)
            
            sources = []
            for row in rows:
                source = dict(row)
                if source.get("created_at"):
                    source["created_at"] = source["created_at"].isoformat()
                sources.append(source)
            
            return json.dumps(
                {"success": True, "sources": sources, "count": len(sources)},
                indent=2
            )

        except Exception as e:
            logger.error(f"Error getting sources: {e}")
            logger.error(traceback.format_exc())
            return json.dumps({"success": False, "error": str(e)}, indent=2)

    @mcp.tool()
    async def rag_search_knowledge_base(
        ctx: Context,
        query: str,
        source_id: str | None = None,
        match_count: int = 5,
        return_mode: str = "pages"
    ) -> str:
        """
        Search knowledge base for relevant content using RAG.

        Args:
            query: Search query - Keep it SHORT and FOCUSED (2-5 keywords)
            source_id: Optional source ID filter
            match_count: Max results (default: 5)
            return_mode: "pages" or "chunks"

        Returns:
            JSON string with search results
        """
        try:
            # Input validation
            valid, error_msg = validate_non_empty_string(query, "query", max_length=500)
            if not valid:
                return json.dumps({"success": False, "error": error_msg}, indent=2)

            valid, error_msg = validate_match_count(match_count)
            if not valid:
                return json.dumps({"success": False, "error": error_msg}, indent=2)

            valid, error_msg = validate_return_mode(return_mode)
            if not valid:
                return json.dumps({"success": False, "error": error_msg}, indent=2)

            if source_id is not None:
                valid, error_msg = validate_non_empty_string(source_id, "source_id")
                if not valid:
                    return json.dumps({"success": False, "error": error_msg}, indent=2)

            from src.server.services.database import get_database_connector
            
            db = get_database_connector()
            
            # Simple text search using ILIKE for now
            # In production, this would use vector similarity search
            search_pattern = f"%{query}%"
            
            if source_id:
                rows = await db.fetch(
                    """SELECT pm.id, pm.url, pm.section_title, pm.word_count,
                              c.full_content, pm.source_id
                       FROM archon_page_metadata pm
                       LEFT JOIN archon_page_content c ON c.page_id = pm.id
                       WHERE pm.source_id = $1 
                         AND (pm.section_title ILIKE $2 OR c.full_content ILIKE $2)
                       ORDER BY pm.word_count DESC
                       LIMIT $3""",
                    source_id, search_pattern, match_count
                )
            else:
                rows = await db.fetch(
                    """SELECT pm.id, pm.url, pm.section_title, pm.word_count,
                              c.full_content, pm.source_id
                       FROM archon_page_metadata pm
                       LEFT JOIN archon_page_content c ON c.page_id = pm.id
                       WHERE pm.section_title ILIKE $1 OR c.full_content ILIKE $1
                       ORDER BY pm.word_count DESC
                       LIMIT $2""",
                    search_pattern, match_count
                )
            
            results = []
            for row in rows:
                result = dict(row)
                # Truncate content for readability
                content = result.get("full_content", "")
                if content and len(content) > 500:
                    result["snippet"] = content[:500] + "..."
                else:
                    result["snippet"] = content
                result.pop("full_content", None)  # Remove full content to reduce payload
                results.append(result)
            
            return json.dumps({
                "success": True,
                "results": results,
                "return_mode": return_mode,
                "reranked": False,
                "query": query,
                "count": len(results)
            }, indent=2)

        except Exception as e:
            logger.error(f"Error performing RAG query: {e}")
            return json.dumps({
                "success": False,
                "results": [],
                "error": str(e),
            }, indent=2)

    @mcp.tool()
    async def rag_search_code_examples(
        ctx: Context, query: str, source_id: str | None = None, match_count: int = 5
    ) -> str:
        """
        Search for relevant code examples in the knowledge base.

        Args:
            query: Search query
            source_id: Optional source ID filter
            match_count: Max results (default: 5)

        Returns:
            JSON string with code examples
        """
        try:
            # Input validation
            valid, error_msg = validate_non_empty_string(query, "query", max_length=500)
            if not valid:
                return json.dumps({"success": False, "error": error_msg}, indent=2)

            valid, error_msg = validate_match_count(match_count)
            if not valid:
                return json.dumps({"success": False, "error": error_msg}, indent=2)

            if source_id is not None:
                valid, error_msg = validate_non_empty_string(source_id, "source_id")
                if not valid:
                    return json.dumps({"success": False, "error": error_msg}, indent=2)

            from src.server.services.database import get_database_connector
            
            db = get_database_connector()
            
            search_pattern = f"%{query}%"
            
            if source_id:
                rows = await db.fetch(
                    """SELECT id, source_id, title, description, language, 
                              code_snippet, explanation
                       FROM archon_code_examples
                       WHERE source_id = $1 
                         AND (title ILIKE $2 OR description ILIKE $2 OR code_snippet ILIKE $2)
                       ORDER BY title
                       LIMIT $3""",
                    source_id, search_pattern, match_count
                )
            else:
                rows = await db.fetch(
                    """SELECT id, source_id, title, description, language, 
                              code_snippet, explanation
                       FROM archon_code_examples
                       WHERE title ILIKE $1 OR description ILIKE $1 OR code_snippet ILIKE $1
                       ORDER BY title
                       LIMIT $2""",
                    search_pattern, match_count
                )
            
            results = [dict(row) for row in rows]
            
            return json.dumps({
                "success": True,
                "results": results,
                "reranked": False,
                "count": len(results)
            }, indent=2)

        except Exception as e:
            logger.error(f"Error searching code examples: {e}")
            return json.dumps({
                "success": False,
                "results": [],
                "error": str(e),
            }, indent=2)

    @mcp.tool()
    async def rag_list_pages_for_source(
        ctx: Context, source_id: str, section: str | None = None
    ) -> str:
        """
        List all pages for a given knowledge source.

        Args:
            source_id: Source ID
            section: Optional section filter

        Returns:
            JSON string with pages
        """
        try:
            # Input validation
            valid, error_msg = validate_non_empty_string(source_id, "source_id")
            if not valid:
                return json.dumps({"success": False, "error": error_msg}, indent=2)

            if section is not None:
                valid, error_msg = validate_non_empty_string(section, "section")
                if not valid:
                    return json.dumps({"success": False, "error": error_msg}, indent=2)

            from src.server.services.database import get_database_connector
            
            db = get_database_connector()
            
            if section:
                rows = await db.fetch(
                    """SELECT id, url, section_title, word_count, created_at
                       FROM archon_page_metadata 
                       WHERE source_id = $1 AND section_title = $2
                       ORDER BY section_title""",
                    source_id, section
                )
            else:
                rows = await db.fetch(
                    """SELECT id, url, section_title, word_count, created_at
                       FROM archon_page_metadata 
                       WHERE source_id = $1
                       ORDER BY section_title""",
                    source_id
                )
            
            pages = []
            for row in rows:
                page = dict(row)
                if page.get("created_at"):
                    page["created_at"] = page["created_at"].isoformat()
                pages.append(page)
            
            return json.dumps({
                "success": True,
                "pages": pages,
                "total": len(pages),
                "source_id": source_id,
            }, indent=2)

        except Exception as e:
            logger.error(f"Error listing pages for source {source_id}: {e}")
            return json.dumps({
                "success": False,
                "pages": [],
                "total": 0,
                "source_id": source_id,
                "error": str(e)
            }, indent=2)

    @mcp.tool()
    async def rag_read_full_page(
        ctx: Context, page_id: str | None = None, url: str | None = None
    ) -> str:
        """
        Retrieve full page content from knowledge base.

        Args:
            page_id: Page UUID
            url: Page URL

        Returns:
            JSON string with full page content
        """
        try:
            if not page_id and not url:
                return json.dumps(
                    {"success": False, "error": "Must provide either page_id or url"},
                    indent=2
                )

            from src.server.services.database import get_database_connector
            
            db = get_database_connector()
            
            if page_id:
                rows = await db.fetch(
                    """SELECT pm.*, c.full_content 
                       FROM archon_page_metadata pm
                       LEFT JOIN archon_page_content c ON c.page_id = pm.id
                       WHERE pm.id = $1""",
                    page_id
                )
            else:
                rows = await db.fetch(
                    """SELECT pm.*, c.full_content 
                       FROM archon_page_metadata pm
                       LEFT JOIN archon_page_content c ON c.page_id = pm.id
                       WHERE pm.url = $1""",
                    url
                )
            
            if rows:
                page_data = dict(rows[0])
                # Convert datetime to string
                if page_data.get("created_at"):
                    page_data["created_at"] = page_data["created_at"].isoformat()
                if page_data.get("updated_at"):
                    page_data["updated_at"] = page_data["updated_at"].isoformat()
                return json.dumps({
                    "success": True,
                    "page": page_data,
                }, indent=2)
            else:
                return json.dumps({
                    "success": False,
                    "page": None,
                    "error": "Page not found",
                }, indent=2)

        except Exception as e:
            logger.error(f"Error reading page: {e}")
            return json.dumps({"success": False, "page": None, "error": str(e)}, indent=2)

    logger.info("✓ RAG tools registered (lightweight DB queries)")
