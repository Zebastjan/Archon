"""
Shared tool registration for Archon MCP Server.

This module contains the common tool registration logic that can be used
by both stdio and HTTP MCP server implementations.
"""

import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)


def register_all_tool_modules(mcp: FastMCP) -> int:
    """Register all MCP tool modules with the given FastMCP instance.

    Args:
        mcp: FastMCP instance to register tools with

    Returns:
        Number of tool modules successfully registered
    """
    modules_registered = 0

    # RAG Module
    try:
        from .features.rag import register_rag_tools

        register_rag_tools(mcp)
        modules_registered += 1
        logger.info("✓ RAG tools registered")
    except Exception as e:
        logger.warning(f"⚠ Could not register RAG tools: {e}")

    # Project Management
    try:
        from .features.projects import register_project_tools

        register_project_tools(mcp)
        modules_registered += 1
        logger.info("✓ Project tools registered")
    except Exception as e:
        logger.warning(f"⚠ Could not register project tools: {e}")

    # Task Management
    try:
        from .features.tasks import register_task_tools

        register_task_tools(mcp)
        modules_registered += 1
        logger.info("✓ Task tools registered")
    except Exception as e:
        logger.warning(f"⚠ Could not register task tools: {e}")

    # Document Management
    try:
        from .features.documents import register_document_tools

        register_document_tools(mcp)
        modules_registered += 1
        logger.info("✓ Document tools registered")
    except Exception as e:
        logger.warning(f"⚠ Could not register document tools: {e}")

    # Version Management
    try:
        from .features.documents import register_version_tools

        register_version_tools(mcp)
        modules_registered += 1
        logger.info("✓ Version tools registered")
    except Exception as e:
        logger.warning(f"⚠ Could not register version tools: {e}")

    # Feature Tools
    try:
        from .features.feature_tools import register_feature_tools

        register_feature_tools(mcp)
        modules_registered += 1
        logger.info("✓ Feature tools registered")
    except Exception as e:
        logger.warning(f"⚠ Could not register feature tools: {e}")

    # Code Entity Tools
    try:
        from .features.code_entities import register_code_entity_tools

        register_code_entity_tools(mcp)
        modules_registered += 1
        logger.info("✓ Code entity tools registered")
    except Exception as e:
        logger.warning(f"⚠ Could not register code entity tools: {e}")

    # Worktree Tools
    try:
        from .features.worktree import register_worktree_tools

        register_worktree_tools(mcp)
        modules_registered += 1
        logger.info("✓ Worktree tools registered")
    except Exception as e:
        logger.warning(f"⚠ Could not register worktree tools: {e}")

    # Code Audit Tools
    try:
        from .features.code_audit import register_code_audit_tools

        register_code_audit_tools(mcp)
        modules_registered += 1
        logger.info("✓ Code audit tools registered")
    except Exception as e:
        logger.warning(f"⚠ Could not register code audit tools: {e}")

    # Reindex Tools (ADR-016)
    try:
        from .features.reindex_tools import register_reindex_tools

        register_reindex_tools(mcp)
        modules_registered += 1
        logger.info("✓ Reindex tools registered")
    except Exception as e:
        logger.warning(f"⚠ Could not register reindex tools: {e}")

    # Skills Tools (ADR-015)
    try:
        from .features.skills_tools import register_skills_tools

        register_skills_tools(mcp)
        modules_registered += 1
        logger.info("✓ Skills tools registered")
    except Exception as e:
        logger.warning(f"⚠ Could not register skills tools: {e}")

    logger.info(f"📦 Registered {modules_registered} tool modules")
    return modules_registered
