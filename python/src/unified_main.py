"""
Unified Archon Server - Single Entry Point

Combines FastAPI server and MCP server into one process.
- API routes available at /api/*
- MCP tools available via SSE at /mcp
- Direct Python imports - no HTTP overhead
- LOCAL PostgreSQL only (no Docker)
"""

import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.server.config.yaml_config import load_config, ConfigError, get_config

# Load config early (fail fast on bad config)
try:
    config = load_config()
except ConfigError as e:
    print(f"Configuration Error: {e}")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.server.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(config.paths.logs / "archon.log")
    ]
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("🚀 Starting Unified Archon Server")
    
    # Ensure local PostgreSQL is running
    if config.database.is_local:
        from src.local_postgres import LocalPostgres
        pg = LocalPostgres()
        
        if not pg.is_installed():
            logger.error("PostgreSQL not installed. Run: python -m src.local_postgres")
            print(pg.get_install_instructions())
            sys.exit(1)
        
        if not pg.start():
            logger.error("Failed to start PostgreSQL")
            sys.exit(1)
    
    # Initialize database connection pool
    from src.server.services.database import initialize_database
    await initialize_database()
    logger.info("✓ Database initialized")
    
    yield
    
    # Cleanup
    logger.info("🛑 Shutting down Unified Archon Server")


# Create main application
app = FastAPI(
    title="Archon Unified Server",
    description="FastAPI + MCP combined server",
    version="0.1.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Import and register API routes
# =============================================================================

from src.server.api_routes import projects_router, knowledge_router, settings_router

app.include_router(projects_router, prefix="/api/projects", tags=["projects"])
app.include_router(knowledge_router, prefix="/api/knowledge", tags=["knowledge"])
app.include_router(settings_router, prefix="/api/settings", tags=["settings"])


# =============================================================================
# Import MCP tools directly (no HTTP layer)
# =============================================================================

from src.mcp_server.features.projects.project_tools import register_project_tools
from src.mcp_server.features.tasks.task_tools import register_task_tools
from src.mcp_server.features.documents.document_tools import register_document_tools
from src.mcp_server.features.rag.rag_tools import register_rag_tools
from src.mcp_server.features.code_audit.code_audit_tools import register_code_audit_tools
from src.mcp_server.features.code_entities.tools import register_code_entity_tools
from src.mcp_server.features.worktree.worktree_tools import register_worktree_tools
from src.mcp_server.features.code_repos.code_repos_tools import register_code_repos_tools


# Create MCP instance integrated with FastAPI
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("archon-unified")

# Register all MCP tools directly
register_project_tools(mcp)
register_task_tools(mcp)
register_document_tools(mcp)
register_rag_tools(mcp)
register_code_audit_tools(mcp)
register_code_entity_tools(mcp)
register_worktree_tools(mcp)
register_code_repos_tools(mcp)

logger.info(f"✓ All MCP tools registered")

logger.info("✓ All MCP tools registered")


# Mount MCP SSE endpoint
from mcp.server.sse import SseServerTransport

sse_transport = SseServerTransport("/mcp/messages")


@app.get("/mcp")
async def mcp_sse_endpoint(request):
    """MCP SSE endpoint."""
    async with sse_transport.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        await mcp._server.run(
            streams[0],
            streams[1],
            mcp._server.create_initialization_options()
        )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "mode": "unified"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.unified_main:app",
        host="0.0.0.0",
        port=8181,
        reload=True
    )
