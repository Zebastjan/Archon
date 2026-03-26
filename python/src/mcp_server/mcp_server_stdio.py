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

# Worktree context - populated at startup
WORKTREE_CONTEXT = {
    "branch": os.getenv("ARCHON_BRANCH", "main"),
    "commit": os.getenv("ARCHON_COMMIT", ""),
    "worktree_path": os.getenv("ARCHON_WORKTREE_PATH", ""),
    "repo_root": os.getenv("ARCHON_REPO_ROOT", ""),
}

# Log worktree context at startup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

if WORKTREE_CONTEXT["branch"] != "main" or WORKTREE_CONTEXT["commit"]:
    logger.info(
        f"[Worktree] Branch: {WORKTREE_CONTEXT['branch']}, Commit: {WORKTREE_CONTEXT['commit'][:8] if WORKTREE_CONTEXT['commit'] else 'unknown'}"
    )

# Load environment from project root .env if it exists
project_root = Path(__file__).resolve().parent.parent
dotenv_path = project_root / ".env"
if dotenv_path.exists():
    load_dotenv(dotenv_path, override=True)

# Populate worktree_context module for tools to use
try:
    from src.mcp_server import worktree_context as wt_ctx

    wt_ctx.set_worktree_context(
        branch=os.getenv("ARCHON_BRANCH", "main"),
        commit=os.getenv("ARCHON_COMMIT", ""),
        worktree_path=os.getenv("ARCHON_WORKTREE_PATH", ""),
        repo_root=os.getenv("ARCHON_REPO_ROOT", ""),
    )
    logger.info(f"✓ Worktree context loaded: branch={wt_ctx.get_current_branch()}")
except Exception as e:
    logger.warning(f"Could not load worktree context: {e}")

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


# Worktree context for tools
def get_worktree_context():
    """Get current worktree context."""
    return WORKTREE_CONTEXT


# Use Archon's default MCP instructions
# We don't import from mcp_server.py to avoid HTTP-specific dependencies
MCP_INSTRUCTIONS = f"""
# Archon MCP Server Instructions

## 🚨 CRITICAL RULES (ALWAYS FOLLOW)
1. **Task Management**: ALWAYS use Archon MCP tools for task management.
2. **Research First**: Before implementing, use rag_search_knowledge_base and rag_search_code_examples
3. **Task-Driven Development**: Never code without checking current tasks first

## 🌿 Worktree Context
- **Current Branch**: {WORKTREE_CONTEXT["branch"]}
- **Current Commit**: {WORKTREE_CONTEXT["commit"][:8] if WORKTREE_CONTEXT["commit"] else "unknown"}
- All code search tools automatically scope to this branch

## 🔍 Research Patterns
- Keep queries short and focused (2-5 keywords)
- Use `rag_search_knowledge_base()` for documentation searches
- Use `rag_search_code_examples()` for code patterns

## 📋 Core Workflow
1. Check current context: `worktree_get_current_info()`
2. Check tasks: `list_tasks()`
3. Research with RAG tools
4. Implement based on findings
5. Commit with: `commit_with_review()`

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

# Register all tool modules using shared registration
logger.info("Registering MCP tool modules...")

try:
    from src.mcp_server.tool_registration import register_all_tool_modules

    count = register_all_tool_modules(mcp)
    if count == 0:
        logger.warning("No tool modules registered - server will have limited functionality")
except Exception as e:
    logger.error(f"Error during module registration: {e}")
    logger.error(traceback.format_exc())


def main():
    """Main entry point for stdio MCP server."""
    logger.info("🚀 Starting Archon MCP Server (STDIO mode)")
    logger.info("   Transport: STDIO (for OctoFriend and other stdio clients)")

    # Initialize file watcher if enabled
    try:
        from src.server.services.file_watcher_config import get_watcher_config

        watcher_config = get_watcher_config()
        if watcher_config.enabled:
            logger.info(f"👁️ File watcher enabled (debounce: {watcher_config.debounce_ms}ms)")
        else:
            logger.info("👁️ File watcher disabled in config")
    except Exception as e:
        logger.warning(f"Could not initialize file watcher config: {e}")

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
