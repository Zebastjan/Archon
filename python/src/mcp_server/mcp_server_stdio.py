#!/usr/bin/env python3
"""
MCP Server for Archon (STDIO Transport)

Standalone stdio server for OctoFriend - shares tools with HTTP server
but doesn't require HTTP-specific configuration.
"""

import os
import sys
import logging
import traceback
from pathlib import Path
from dotenv import load_dotenv

# Load environment from project root .env if it exists
project_root = Path(__file__).resolve().parent.parent
dotenv_path = project_root / ".env"
if dotenv_path.exists():
    load_dotenv(dotenv_path, override=True)

# Configure logging to stderr (stdout is reserved for stdio protocol)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# Import FastMCP
try:
    from mcp.server.fastmcp import FastMCP
    logger.info("✓ FastMCP imported")
except ImportError as e:
    logger.error(f"Failed to import FastMCP: {e}")
    logger.error("Make sure to run with: uv run --group mcp")
    sys.exit(1)

# Use Archon's default MCP instructions
# We don't import from mcp_server.py to avoid HTTP-specific dependencies
MCP_INSTRUCTIONS = """
# Archon MCP Server Instructions

## 🚨 CRITICAL RULES (ALWAYS FOLLOW)
1. **Task Management**: ALWAYS use Archon MCP tools for task management.
2. **Research First**: Before implementing, use rag_search_knowledge_base and rag_search_code_examples
3. **Task-Driven Development**: Never code without checking current tasks first

## 🔍 Research Patterns
- Keep queries short and focused (2-5 keywords)
- Use `rag_search_knowledge_base()` for documentation searches
- Use `rag_search_code_examples()` for code patterns

## 📋 Core Workflow
1. Check tasks with `list_tasks()`
2. Research with RAG tools
3. Implement based on findings
4. Update task status

For full documentation, see Archon project documentation.
"""
logger.info("✓ Using default MCP instructions")

# Create a standalone FastMCP server for stdio
logger.info("Creating FastMCP server instance for stdio...")
mcp = FastMCP(
    "archon-mcp-server-stdio",
    instructions=MCP_INSTRUCTIONS,
)
logger.info("✓ FastMCP server created")

# Register all tool modules (same as HTTP server)
logger.info("Registering MCP tool modules...")

def register_modules():
    """Register all MCP tool modules."""
    modules_registered = 0

    # RAG Module
    try:
        from features.rag import register_rag_tools
        register_rag_tools(mcp)
        modules_registered += 1
        logger.info("✓ RAG tools registered")
    except Exception as e:
        logger.warning(f"⚠ Could not register RAG tools: {e}")

    # Project Management
    try:
        from features.projects import register_project_tools
        register_project_tools(mcp)
        modules_registered += 1
        logger.info("✓ Project tools registered")
    except Exception as e:
        logger.warning(f"⚠ Could not register project tools: {e}")

    # Task Management
    try:
        from features.tasks import register_task_tools
        register_task_tools(mcp)
        modules_registered += 1
        logger.info("✓ Task tools registered")
    except Exception as e:
        logger.warning(f"⚠ Could not register task tools: {e}")

    # Document Management
    try:
        from features.documents import register_document_tools
        register_document_tools(mcp)
        modules_registered += 1
        logger.info("✓ Document tools registered")
    except Exception as e:
        logger.warning(f"⚠ Could not register document tools: {e}")

    # Version Management
    try:
        from features.documents import register_version_tools
        register_version_tools(mcp)
        modules_registered += 1
        logger.info("✓ Version tools registered")
    except Exception as e:
        logger.warning(f"⚠ Could not register version tools: {e}")

    # Feature Tools
    try:
        from features.feature_tools import register_feature_tools
        register_feature_tools(mcp)
        modules_registered += 1
        logger.info("✓ Feature tools registered")
    except Exception as e:
        logger.warning(f"⚠ Could not register feature tools: {e}")

    # Code Entity Tools
    try:
        from features.code_entities import register_code_entity_tools
        register_code_entity_tools(mcp)
        modules_registered += 1
        logger.info("✓ Code entity tools registered")
    except Exception as e:
        logger.warning(f"⚠ Could not register code entity tools: {e}")

    # Worktree Tools
    try:
        from features.worktree import register_worktree_tools
        register_worktree_tools(mcp)
        modules_registered += 1
        logger.info("✓ Worktree tools registered")
    except Exception as e:
        logger.warning(f"⚠ Could not register worktree tools: {e}")

    # Code Audit Tools
    try:
        from features.code_audit import register_code_audit_tools
        register_code_audit_tools(mcp)
        modules_registered += 1
        logger.info("✓ Code audit tools registered")
    except Exception as e:
        logger.warning(f"⚠ Could not register code audit tools: {e}")

    logger.info(f"📦 Registered {modules_registered} tool modules")
    return modules_registered

# Register modules at startup
try:
    count = register_modules()
    if count == 0:
        logger.warning("No tool modules registered - server will have limited functionality")
except Exception as e:
    logger.error(f"Error during module registration: {e}")
    logger.error(traceback.format_exc())


def main():
    """Main entry point for stdio MCP server."""
    logger.info("🚀 Starting Archon MCP Server (STDIO mode)")
    logger.info("   Transport: STDIO (for OctoFriend and other stdio clients)")

    try:
        # Run with stdio transport (default for FastMCP)
        mcp.run()
    except Exception as e:
        logger.error(f"Server error: {e}")
        logger.error(traceback.format_exc())
        raise


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("👋 Server stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)
