"""Skills MCP tools for ADR-015.

Provides tools for indexing and managing skills/ directory.
"""

import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from src.server.config.logfire_config import get_logger
from src.server.services.skills_indexing_service import (
    index_all_skills,
    discover_skills,
    delete_skill_chunks,
)

logger = get_logger(__name__)


def register_skills_tools(mcp: FastMCP) -> None:
    """Register skills MCP tools."""
    logger.info("registering_skills_tools")

    @mcp.tool()
    async def skills_index(
        repo_id: str,
        commit_sha: str | None = None,
    ) -> dict[str, Any]:
        """
        Index all skills in the skills/ directory.

        Makes skills searchable via semantic search. Skills are stored
        as document blobs and chunked appropriately.

        Args:
            repo_id: Repository UUID
            commit_sha: Current commit SHA (for version tracking)

        Returns:
            Dict with indexing results:
            - indexed: Number of skills indexed
            - unchanged: Number unchanged (same content hash)
            - errors: Number with errors

        Example:
            >>> await skills_index(repo_id="uuid")
        """
        try:
            from src.mcp_server import worktree_context

            repo_root = worktree_context.get_repo_root() or os.getcwd()
            skills_root = os.path.join(repo_root, "skills")

            results = await index_all_skills(
                repo_id=repo_id,
                commit_sha=commit_sha or worktree_context.get_current_commit(),
                skills_root=skills_root,
            )

            return {
                "success": True,
                "indexed": sum(1 for r in results if r.status == "indexed"),
                "unchanged": sum(1 for r in results if r.status == "unchanged"),
                "errors": sum(1 for r in results if r.status == "error"),
                "results": [
                    {
                        "path": r.path,
                        "status": r.status,
                        "chunks": r.chunks_created,
                        "error": r.error,
                    }
                    for r in results
                ],
            }

        except Exception as e:
            logger.exception("skills_index_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
            }

    @mcp.tool()
    async def skills_discover() -> dict[str, Any]:
        """
        Discover all skill files in the skills/ directory.

        Returns metadata about discovered skills without indexing them.

        Returns:
            Dict with discovered skills:
            - count: Number of skill files found
            - skills: List of skill metadata

        Example:
            >>> await skills_discover()
        """
        try:
            from src.mcp_server import worktree_context

            repo_root = worktree_context.get_repo_root() or os.getcwd()
            skills_root = os.path.join(repo_root, "skills")

            skills = discover_skills(skills_root)

            return {
                "success": True,
                "count": len(skills),
                "skills": [
                    {
                        "path": skill.path,
                        "category": skill.category,
                        "name": skill.name,
                        "size": skill.size,
                        "hash": skill.content_hash[:8],
                    }
                    for skill in skills
                ],
            }

        except Exception as e:
            logger.exception("skills_discover_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
            }

    @mcp.tool()
    async def skills_delete(
        repo_id: str,
        skill_path: str,
    ) -> dict[str, Any]:
        """
        Delete a skill file from the knowledge base.

        Use when a skill file is removed from the repository.

        Args:
            repo_id: Repository UUID
            skill_path: Path to skill file (relative to project root)

        Returns:
            Dict with deletion result

        Example:
            >>> await skills_delete(
            ...     repo_id="uuid",
            ...     skill_path="skills/prompts/old-skill.md"
            ... )
        """
        try:
            deleted = await delete_skill_chunks(repo_id, skill_path)

            return {
                "success": True,
                "chunks_deleted": deleted,
                "path": skill_path,
            }

        except Exception as e:
            logger.exception("skills_delete_failed: %s", str(e))
            return {
                "success": False,
                "error": str(e),
            }

    logger.info("skills_tools_registered")
