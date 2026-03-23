"""
MCP Server for Archon (Microservices Version)

This is the MCP server that uses HTTP calls to other services
instead of importing heavy dependencies directly. This significantly reduces
the container size from 1.66GB to ~150MB.

Modules:
- RAG Module: RAG queries, search, and source management via HTTP
- Project Module: Task and project management via HTTP
- Health & Session: Local operations

Note: Crawling and document upload operations are handled directly by the
API service and frontend, not through MCP tools.
"""

import json
import logging
import os
import sys
import threading
import time
import traceback
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import asyncpg
from dotenv import load_dotenv
from mcp.server.fastmcp import Context, FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

# Add the project root to Python path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Load environment variables from the project root .env file
# NOTE: We don't override existing env vars - Dockerfile ENV takes precedence
project_root = Path(__file__).resolve().parent.parent
dotenv_path = project_root / ".env"
load_dotenv(dotenv_path, override=False)

# Configure logging FIRST before any imports that might use it
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("/tmp/mcp_server.log", mode="a") if os.path.exists("/tmp") else logging.NullHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Import Logfire configuration
from src.server.config.logfire_config import mcp_logger, setup_logfire

# Import service client for HTTP calls
from src.server.services.mcp_service_client import get_mcp_service_client

# Import session management
from src.server.services.mcp_session_manager import get_session_manager

# Global initialization lock and flag
_initialization_lock = threading.Lock()
_initialization_complete = False
_shared_context = None

server_host = "0.0.0.0"  # Listen on all interfaces

# Require ARCHON_MCP_PORT to be set
mcp_port = os.getenv("ARCHON_MCP_PORT")
if not mcp_port:
    raise ValueError(
        "ARCHON_MCP_PORT environment variable is required. "
        "Please set it in your .env file or environment. "
        "Default value: 8051"
    )
server_port = int(mcp_port)


@dataclass
class ArchonContext:
    """
    Context for MCP server.
    No heavy dependencies - just service client for HTTP calls.
    """

    service_client: Any
    health_status: dict = None
    startup_time: float = None

    def __post_init__(self):
        if self.health_status is None:
            self.health_status = {
                "status": "healthy",
                "api_service": False,
                "agents_service": False,
                "last_health_check": None,
            }
        if self.startup_time is None:
            self.startup_time = time.time()


async def perform_health_checks(context: ArchonContext):
    """Perform health checks on dependent services via HTTP and DB connectivity."""
    try:
        # Check dependent services via HTTP
        service_health = await context.service_client.health_check()

        context.health_status["api_service"] = service_health.get("api_service", False)
        context.health_status["agents_service"] = service_health.get("agents_service", False)

        # Check database connectivity directly via archon-server API
        try:
            import httpx
            from urllib.parse import urljoin

            api_health_url = os.getenv("API_SERVICE_URL", "http://archon-server:8181")
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                response = await client.get(urljoin(api_health_url, "/health"))
                if response.status_code == 200:
                    data = response.json()
                    # DB is healthy if archon-server reports ready and schema valid
                    context.health_status["database"] = data.get("ready", False) and data.get("schema_valid", False)
                else:
                    context.health_status["database"] = False
        except Exception as db_e:
            logger.warning(f"Database connectivity check failed: {db_e}")
            context.health_status["database"] = False

        # Overall status - all critical services must be ready
        all_critical_ready = context.health_status["api_service"] and context.health_status.get("database", False)

        context.health_status["status"] = "healthy" if all_critical_ready else "degraded"
        context.health_status["last_health_check"] = datetime.now().isoformat()

        if not all_critical_ready:
            logger.warning(f"Health check failed: {context.health_status}")
        else:
            logger.info("Health check passed - all services healthy including database")

    except Exception as e:
        logger.error(f"Health check error: {e}")
        context.health_status["status"] = "unhealthy"
        context.health_status["database"] = False
        context.health_status["last_health_check"] = datetime.now().isoformat()


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[ArchonContext]:
    """
    Lifecycle manager - no heavy dependencies.
    """
    global _initialization_complete, _shared_context

    # Quick check without lock
    if _initialization_complete and _shared_context:
        logger.info("♻️ Reusing existing context for new SSE connection")
        yield _shared_context
        return

    # Acquire lock for initialization
    with _initialization_lock:
        # Double-check pattern
        if _initialization_complete and _shared_context:
            logger.info("♻️ Reusing existing context for new SSE connection")
            yield _shared_context
            return

        logger.info("🚀 Starting MCP server...")

        try:
            # Initialize session manager
            logger.info("🔐 Initializing session manager...")
            session_manager = get_session_manager()
            logger.info("✓ Session manager initialized")

            # Initialize service client for HTTP calls
            logger.info("🌐 Initializing service client...")
            service_client = get_mcp_service_client()
            logger.info("✓ Service client initialized")

            # Create context
            context = ArchonContext(service_client=service_client)

            # Perform initial health check with retry logic
            max_retries = 10
            retry_delay = 2  # seconds

            for attempt in range(max_retries):
                try:
                    await perform_health_checks(context)

                    # Check if database is connected
                    if context.health_status.get("database", False):
                        logger.info(f"✓ Health check passed on attempt {attempt + 1}")
                        break
                    else:
                        if attempt < max_retries - 1:
                            logger.warning(
                                f"⚠ Database not ready (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay}s..."
                            )
                            await asyncio.sleep(retry_delay)
                            retry_delay = min(retry_delay * 1.5, 10)  # Exponential backoff capped at 10s
                        else:
                            logger.error(f"💥 Database connectivity failed after {max_retries} attempts")
                            raise RuntimeError(
                                "Database connectivity failed - archon-server health check reports DB unavailable"
                            )

                except Exception as health_e:
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"⚠ Health check failed (attempt {attempt + 1}/{max_retries}): {health_e}, retrying..."
                        )
                        await asyncio.sleep(retry_delay)
                        retry_delay = min(retry_delay * 1.5, 10)
                    else:
                        logger.error(f"💥 Health check failed after {max_retries} attempts")
                        raise

            logger.info("✓ MCP server ready")

            # Store context globally
            _shared_context = context
            _initialization_complete = True

            yield context

        except Exception as e:
            logger.error(f"💥 Critical error in lifespan setup: {e}")
            logger.error(traceback.format_exc())
            raise
        finally:
            # Clean up resources
            logger.info("🧹 Cleaning up MCP server...")
            logger.info("✅ MCP server shutdown complete")


# Define MCP instructions for Claude Code and other clients
MCP_INSTRUCTIONS = """
# Archon MCP Server Instructions

## 🚨 CRITICAL RULES (ALWAYS FOLLOW)
1. **Task Management**: ALWAYS use Archon MCP tools for task management.
   - Combine with your local TODO tools for granular tracking

2. **Research First**: Before implementing, use rag_search_knowledge_base and rag_search_code_examples
3. **Task-Driven Development**: Never code without checking current tasks first

## 🎯 Targeted Documentation Search

When searching specific documentation (very common!):
1. **Get available sources**: `rag_get_available_sources()` - Returns list with id, title, url
2. **Find source ID**: Match user's request to source title (e.g., "PydanticAI docs" -> find ID)
3. **Filter search**: `rag_search_knowledge_base(query="...", source_id="src_xxx", match_count=5)`

Examples:
- User: "Search the Supabase docs for vector functions"
  1. Call `rag_get_available_sources()`
  2. Find Supabase source ID from results (e.g., "src_abc123")
  3. Call `rag_search_knowledge_base(query="vector functions", source_id="src_abc123")`

- User: "Find authentication examples in the MCP documentation"
  1. Call `rag_get_available_sources()`
  2. Find MCP docs source ID
  3. Call `rag_search_code_examples(query="authentication", source_id="src_def456")`

IMPORTANT: Always use source_id (not URLs or domain names) for filtering!

## 📋 Core Workflow

### Task Management Cycle
1. **Get current task**: `list_tasks(task_id="...")` 
2. **Search/List tasks**: `list_tasks(query="auth", filter_by="status", filter_value="todo")`
3. **Mark as doing**: `manage_task("update", task_id="...", status="doing")`
4. **Research phase**:
   - `rag_search_knowledge_base(query="...", match_count=5)`
   - `rag_search_code_examples(query="...", match_count=3)`
5. **Implementation**: Code based on research findings
6. **Mark for review**: `manage_task("update", task_id="...", status="review")`
7. **Get next task**: `list_tasks(filter_by="status", filter_value="todo")`

### Consolidated Task Tools (Optimized ~2 tools from 5)
- `list_tasks(query=None, task_id=None, filter_by=None, filter_value=None, per_page=10)`
  - list + search + get in one tool
  - Search with keyword query parameter (optional)
  - task_id parameter for getting single task (full details)
  - Filter by status, project, or assignee
  - **Optimized**: Returns truncated descriptions and array counts (lists only)
  - **Default**: 10 items per page (was 50)
- `manage_task(action, task_id=None, project_id=None, ...)`
  - **Consolidated**: create + update + delete in one tool
  - action: "create" | "update" | "delete"
  - Examples:
    - `manage_task("create", project_id="p-1", title="Fix auth")`
    - `manage_task("update", task_id="t-1", status="doing")`
    - `manage_task("delete", task_id="t-1")`

## 🏗️ Project Management

### Project Tools
- `list_projects(project_id=None, query=None, page=1, per_page=10)`
  - List all projects, search by query, or get specific project by ID
- `manage_project(action, project_id=None, title=None, description=None, github_repo=None)`
  - Actions: "create", "update", "delete"

### Document Tools
- `list_documents(project_id, document_id=None, query=None, document_type=None, page=1, per_page=10)`
  - List project documents, search, filter by type, or get specific document
- `manage_document(action, project_id, document_id=None, title=None, document_type=None, content=None, ...)`
  - Actions: "create", "update", "delete"

## 🔍 Research Patterns

### CRITICAL: Keep Queries Short and Focused!
Vector search works best with 2-5 keywords, NOT long sentences or keyword dumps.

✅ GOOD Queries (concise, focused):
- `rag_search_knowledge_base(query="vector search pgvector")`
- `rag_search_code_examples(query="React useState")`
- `rag_search_knowledge_base(query="authentication JWT")`
- `rag_search_code_examples(query="FastAPI middleware")`

❌ BAD Queries (too long, unfocused):
- `rag_search_knowledge_base(query="how to implement vector search with pgvector in PostgreSQL for semantic similarity matching with OpenAI embeddings")`
- `rag_search_code_examples(query="React hooks useState useEffect useContext useReducer useMemo useCallback")`

### Query Construction Tips:
- Extract 2-5 most important keywords from the user's request
- Focus on technical terms and specific technologies
- Omit filler words like "how to", "implement", "create", "example"
- For multi-concept searches, do multiple focused queries instead of one broad query

## 📊 Task Status Flow
`todo` → `doing` → `review` → `done`
- Only ONE task in 'doing' status at a time
- Use 'review' for completed work awaiting validation
- Mark tasks 'done' only after verification

## 📝 Task Granularity Guidelines

### Project Scope Determines Task Granularity

**For Feature-Specific Projects** (project = single feature):
Create granular implementation tasks:
- "Set up development environment"
- "Install required dependencies"
- "Create database schema"
- "Implement API endpoints"
- "Add frontend components"
- "Write unit tests"
- "Add integration tests"
- "Update documentation"

**For Codebase-Wide Projects** (project = entire application):
Create feature-level tasks:
- "Implement user authentication feature"
- "Add payment processing system"
- "Create admin dashboard"
"""

# Initialize the main FastMCP server with fixed configuration
# Explicitly set host/port from environment to ensure they're respected
try:
    logger.info("🏗️ MCP SERVER INITIALIZATION:")
    logger.info("   Server Name: archon-mcp-server")
    logger.info("   Description: MCP server using HTTP calls")

    # Get host/port from environment with defaults
    mcp_host = os.getenv("FASTMCP_HOST", "0.0.0.0")
    mcp_port = int(os.getenv("FASTMCP_PORT", "8051"))
    logger.info(f"   Host: {mcp_host}, Port: {mcp_port}")

    mcp = FastMCP(
        "archon-mcp-server",
        instructions=MCP_INSTRUCTIONS,
        lifespan=lifespan,
        host=mcp_host,
        port=mcp_port,
    )
    logger.info("✓ FastMCP server instance created successfully")

except Exception as e:
    logger.error(f"✗ Failed to create FastMCP server: {e}")
    logger.error(traceback.format_exc())
    raise


# Health check endpoint
@mcp.tool()
async def health_check(ctx: Context) -> str:
    """
    Check health status of MCP server and dependencies.

    Returns:
        JSON with health status, uptime, and service availability
    """
    try:
        # Try to get the lifespan context
        context = getattr(ctx.request_context, "lifespan_context", None)

        if context is None:
            # Server starting up
            return json.dumps(
                {
                    "success": True,
                    "status": "starting",
                    "message": "MCP server is initializing...",
                    "timestamp": datetime.now().isoformat(),
                }
            )

        # Server is ready - perform health checks
        if hasattr(context, "health_status") and context.health_status:
            await perform_health_checks(context)

            return json.dumps(
                {
                    "success": True,
                    "health": context.health_status,
                    "uptime_seconds": time.time() - context.startup_time,
                    "timestamp": datetime.now().isoformat(),
                }
            )
        else:
            return json.dumps(
                {
                    "success": True,
                    "status": "ready",
                    "message": "MCP server is running",
                    "timestamp": datetime.now().isoformat(),
                }
            )

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return json.dumps(
            {
                "success": False,
                "error": f"Health check failed: {str(e)}",
                "timestamp": datetime.now().isoformat(),
            }
        )


# Session management endpoint
@mcp.tool()
async def session_info(ctx: Context) -> str:
    """
    Get current and active session information.

    Returns:
        JSON with active sessions count and server uptime
    """
    try:
        session_manager = get_session_manager()

        # Build session info
        session_info_data = {
            "active_sessions": session_manager.get_active_session_count(),
            "session_timeout": session_manager.timeout,
        }

        # Add server uptime
        context = getattr(ctx.request_context, "lifespan_context", None)
        if context and hasattr(context, "startup_time"):
            session_info_data["server_uptime_seconds"] = time.time() - context.startup_time

        return json.dumps(
            {
                "success": True,
                "session_management": session_info_data,
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Session info failed: {e}")
        return json.dumps(
            {
                "success": False,
                "error": f"Failed to get session info: {str(e)}",
                "timestamp": datetime.now().isoformat(),
            }
        )


# Import and register modules
def register_modules():
    """Register all MCP tool modules."""
    logger.info("🔧 Registering MCP tool modules...")

    modules_registered = 0

    # Import and register RAG module (HTTP-based version)
    try:
        from src.mcp_server.features.rag import register_rag_tools

        register_rag_tools(mcp)
        modules_registered += 1
        logger.info("✓ RAG module registered (HTTP-based)")
    except ImportError as e:
        logger.warning(f"⚠ RAG module not available: {e}")
    except Exception as e:
        logger.error(f"✗ Error registering RAG module: {e}")
        logger.error(traceback.format_exc())

    # Import and register all feature tools - separated and focused

    # Project Management Tools
    try:
        from src.mcp_server.features.projects import register_project_tools

        register_project_tools(mcp)
        modules_registered += 1
        logger.info("✓ Project tools registered")
    except ImportError as e:
        # Module not found - this is acceptable in modular architecture
        logger.warning(f"⚠ Project tools module not available (optional): {e}")
    except (SyntaxError, NameError, AttributeError) as e:
        # Code errors that should not be ignored
        logger.error(f"✗ Code error in project tools - MUST FIX: {e}")
        logger.error(traceback.format_exc())
        raise  # Re-raise to prevent running with broken code
    except Exception as e:
        # Unexpected errors during registration
        logger.error(f"✗ Failed to register project tools: {e}")
        logger.error(traceback.format_exc())
        # Don't raise - allow other modules to register

    # Task Management Tools
    try:
        from src.mcp_server.features.tasks import register_task_tools

        register_task_tools(mcp)
        modules_registered += 1
        logger.info("✓ Task tools registered")
    except ImportError as e:
        logger.warning(f"⚠ Task tools module not available (optional): {e}")
    except (SyntaxError, NameError, AttributeError) as e:
        logger.error(f"✗ Code error in task tools - MUST FIX: {e}")
        logger.error(traceback.format_exc())
        raise
    except Exception as e:
        logger.error(f"✗ Failed to register task tools: {e}")
        logger.error(traceback.format_exc())

    # Document Management Tools
    try:
        from src.mcp_server.features.documents import register_document_tools

        register_document_tools(mcp)
        modules_registered += 1
        logger.info("✓ Document tools registered")
    except ImportError as e:
        logger.warning(f"⚠ Document tools module not available (optional): {e}")
    except (SyntaxError, NameError, AttributeError) as e:
        logger.error(f"✗ Code error in document tools - MUST FIX: {e}")
        logger.error(traceback.format_exc())
        raise
    except Exception as e:
        logger.error(f"✗ Failed to register document tools: {e}")
        logger.error(traceback.format_exc())

    # Version Management Tools
    try:
        from src.mcp_server.features.documents import register_version_tools

        register_version_tools(mcp)
        modules_registered += 1
        logger.info("✓ Version tools registered")
    except ImportError as e:
        logger.warning(f"⚠ Version tools module not available (optional): {e}")
    except (SyntaxError, NameError, AttributeError) as e:
        logger.error(f"✗ Code error in version tools - MUST FIX: {e}")
        logger.error(traceback.format_exc())
        raise
    except Exception as e:
        logger.error(f"✗ Failed to register version tools: {e}")
        logger.error(traceback.format_exc())

    # Feature Management Tools
    try:
        from src.mcp_server.features.feature_tools import register_feature_tools

        register_feature_tools(mcp)
        modules_registered += 1
        logger.info("✓ Feature tools registered")
    except ImportError as e:
        logger.warning(f"⚠ Feature tools module not available (optional): {e}")
    except (SyntaxError, NameError, AttributeError) as e:
        logger.error(f"✗ Code error in feature tools - MUST FIX: {e}")
        logger.error(traceback.format_exc())
        raise
    except Exception as e:
        logger.error(f"✗ Failed to register feature tools: {e}")
        logger.error(traceback.format_exc())

    # Code Entity Tools (Multi-language code intelligence)
    try:
        from src.mcp_server.features.code_entities import register_code_entity_tools

        register_code_entity_tools(mcp)
        modules_registered += 1
        logger.info("✓ Code entity tools registered")
    except ImportError as e:
        logger.warning(f"⚠ Code entity tools module not available (optional): {e}")
    except (SyntaxError, NameError, AttributeError) as e:
        logger.error(f"✗ Code error in code entity tools - MUST FIX: {e}")
        logger.error(traceback.format_exc())
        raise
    except Exception as e:
        logger.error(f"✗ Failed to register code entity tools: {e}")
        logger.error(traceback.format_exc())

    # Worktree Safety Tools (Branch isolation and conflict prevention)
    try:
        from src.mcp_server.features.worktree import register_worktree_tools

        register_worktree_tools(mcp)
        modules_registered += 1
        logger.info("✓ Worktree safety tools registered")
    except ImportError as e:
        logger.warning(f"⚠ Worktree tools module not available (optional): {e}")
    except (SyntaxError, NameError, AttributeError) as e:
        logger.error(f"✗ Code error in worktree tools - MUST FIX: {e}")
        logger.error(traceback.format_exc())
        raise
    except Exception as e:
        logger.error(f"✗ Failed to register worktree tools: {e}")
        logger.error(traceback.format_exc())

    # Code Audit Tools (Metrics and quality analysis)
    try:
        from src.mcp_server.features.code_audit import register_code_audit_tools

        register_code_audit_tools(mcp)
        modules_registered += 1
        logger.info("✓ Code audit tools registered")
    except ImportError as e:
        logger.warning(f"⚠ Code audit tools module not available (optional): {e}")
    except (SyntaxError, NameError, AttributeError) as e:
        logger.error(f"✗ Code error in code audit tools - MUST FIX: {e}")
        logger.error(traceback.format_exc())
        raise
    except Exception as e:
        logger.error(f"✗ Failed to register code audit tools: {e}")
        logger.error(traceback.format_exc())

    # Code Repository Tools (Create and index repos)
    try:
        from src.mcp_server.features.code_repos import register_code_repos_tools

        register_code_repos_tools(mcp)
        modules_registered += 1
        logger.info("✓ Code repos tools registered")
    except ImportError as e:
        logger.warning(f"⚠ Code repos tools module not available (optional): {e}")
    except (SyntaxError, NameError, AttributeError) as e:
        logger.error(f"✗ Code error in code repos tools - MUST FIX: {e}")
        logger.error(traceback.format_exc())
        raise
    except Exception as e:
        logger.error(f"✗ Failed to register code repos tools: {e}")
        logger.error(traceback.format_exc())

    logger.info(f"📦 Total modules registered: {modules_registered}")

    if modules_registered == 0:
        logger.error("💥 No modules were successfully registered!")
        raise RuntimeError("No MCP modules available")


# Register all modules when this file is imported
try:
    register_modules()
except Exception as e:
    logger.error(f"💥 Critical error during module registration: {e}")
    logger.error(traceback.format_exc())
    raise


# Track server start time at module level for health checks
_server_start_time = time.time()


# Define health endpoint function at module level
async def http_health_endpoint(request: Request):
    """HTTP health check endpoint for monitoring systems."""
    logger.info("Health endpoint called via HTTP")
    try:
        # Try to get the shared context for detailed health info
        if _shared_context and hasattr(_shared_context, "health_status"):
            # Use actual server startup time for consistency with MCP health_check tool
            uptime = time.time() - _shared_context.startup_time
            await perform_health_checks(_shared_context)

            return JSONResponse(
                {
                    "success": True,
                    "health": _shared_context.health_status,
                    "uptime_seconds": uptime,
                    "timestamp": datetime.now().isoformat(),
                }
            )
        else:
            # Server starting up or no MCP connections yet - use module load time as fallback
            uptime = time.time() - _server_start_time
            return JSONResponse(
                {
                    "success": True,
                    "status": "ready",
                    "uptime_seconds": uptime,
                    "message": "MCP server is running (no active connections yet)",
                    "timestamp": datetime.now().isoformat(),
                }
            )
    except Exception as e:
        logger.error(f"HTTP health check failed: {e}", exc_info=True)
        return JSONResponse(
            {
                "success": False,
                "error": f"Health check failed: {str(e)}",
                "uptime_seconds": time.time() - _server_start_time,
                "timestamp": datetime.now().isoformat(),
            },
            status_code=500,
        )


# Register health endpoint using FastMCP's custom_route decorator
try:
    mcp.custom_route("/health", methods=["GET"])(http_health_endpoint)
    logger.info("✓ HTTP /health endpoint registered successfully")
except Exception as e:
    logger.error(f"✗ Failed to register /health endpoint: {e}")
    logger.error(traceback.format_exc())


def main():
    """Main entry point for the MCP server."""
    try:
        # Initialize Logfire first
        setup_logfire(service_name="archon-mcp-server")

        logger.info("🚀 Starting Archon MCP Server")
        logger.info("   Mode: Streamable HTTP")
        logger.info(f"   URL: http://{server_host}:{server_port}/mcp")

        mcp_logger.info("🔥 Logfire initialized for MCP server")
        mcp_logger.info(f"🌟 Starting MCP server - host={server_host}, port={server_port}")

        mcp.run(transport="streamable-http")

    except Exception as e:
        mcp_logger.error(f"💥 Fatal error in main - error={str(e)}, error_type={type(e).__name__}")
        logger.error(f"💥 Fatal error in main: {e}")
        logger.error(traceback.format_exc())
        raise


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("👋 MCP server stopped by user")
    except Exception as e:
        logger.error(f"💥 Unhandled exception: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)
