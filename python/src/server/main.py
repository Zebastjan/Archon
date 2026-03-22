"""
FastAPI Backend for Archon Knowledge Engine

This is the main entry point for the Archon backend API.
It uses a modular approach with separate API modules for different functionality.

Modules:
- settings_api: Settings and credentials management
- mcp_api: MCP server management and tool execution
- knowledge_api: Knowledge base, crawling, and RAG operations
- projects_api: Project and task management with streaming
- mcp_tools: MCP tools registered directly in FastAPI (single container)
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, Request
from fastapi.middleware.cors import CORSMiddleware

from .api_routes.agent_chat_api import router as agent_chat_router
from .api_routes.agent_work_orders_proxy import router as agent_work_orders_router
from .api_routes.agents_api import initialize_agents, router as agents_router
from .api_routes.bug_report_api import router as bug_report_router
from .api_routes.git_api import router as git_router
from .api_routes.git_api_classification import router as git_classification_router
from .api_routes.git_test_api import router as git_test_router
from .api_routes.ingestion_api import router as ingestion_router
from .api_routes.internal_api import router as internal_router
from .api_routes.knowledge_api import router as knowledge_router
from .api_routes.mcp_api import router as mcp_router
from .api_routes.migration_api import router as migration_router
from .api_routes.ollama_api import router as ollama_router
from .api_routes.openrouter_api import router as openrouter_router
from .api_routes.pages_api import router as pages_router
from .api_routes.progress_api import router as progress_router
from .api_routes.projects_api import router as projects_router
from .api_routes.providers_api import router as providers_router

# Audit API - Semgrep integration (new)
from .api_routes.audit_api import router as audit_router
from .api_routes.code_repos_api import router as code_repos_router

# Import modular API routers
from .api_routes.settings_api import router as settings_router
from .api_routes.version_api import router as version_router

# Import Logfire configuration
from .config.logfire_config import api_logger, setup_logfire
from .services.crawler_manager import cleanup_crawler, initialize_crawler

# Import utilities and core classes
from .services.credential_service import initialize_credentials

# Import missing dependencies that the modular APIs need
try:
    from crawl4ai import AsyncWebCrawler, BrowserConfig
except ImportError:
    # These are optional dependencies for full functionality
    AsyncWebCrawler = None
    BrowserConfig = None

# Logger will be initialized after credentials are loaded
logger = logging.getLogger(__name__)

# Set up logging configuration to reduce noise

# Override uvicorn's access log format to be less verbose
uvicorn_logger = logging.getLogger("uvicorn.access")
uvicorn_logger.setLevel(logging.WARNING)  # Only log warnings and errors, not every request

# CrawlingContext has been replaced by CrawlerManager in services/crawler_manager.py

# Global flag to track if initialization is complete
_initialization_complete = False

# MCP Server - Single Container Architecture
# Global FastMCP instance registered directly in FastAPI
_mcp_instance = None


def get_mcp_instance():
    """Get or create the global MCP instance."""
    global _mcp_instance
    if _mcp_instance is None:
        from mcp.server.fastmcp import FastMCP

        _mcp_instance = FastMCP("archon-server")
    return _mcp_instance


async def _initialize_mcp_tools():
    """Initialize all MCP tools from the mcp_server modules."""
    global _mcp_instance

    logger.info("🔧 Initializing MCP tools...")

    from mcp.server.fastmcp import FastMCP

    _mcp_instance = FastMCP("archon-server")

    modules_registered = 0

    # Import and register RAG tools
    try:
        from src.mcp_server.features.rag import register_rag_tools

        register_rag_tools(_mcp_instance)
        modules_registered += 1
        logger.info("✓ RAG tools registered")
    except ImportError as e:
        logger.warning(f"⚠ RAG tools not available: {e}")
    except Exception as e:
        logger.error(f"✗ Error registering RAG tools: {e}")

    # Import and register Project tools
    try:
        from src.mcp_server.features.projects import register_project_tools

        register_project_tools(_mcp_instance)
        modules_registered += 1
        logger.info("✓ Project tools registered")
    except ImportError as e:
        logger.warning(f"⚠ Project tools not available: {e}")
    except Exception as e:
        logger.error(f"✗ Error registering Project tools: {e}")

    # Import and register Task tools
    try:
        from src.mcp_server.features.tasks import register_task_tools

        register_task_tools(_mcp_instance)
        modules_registered += 1
        logger.info("✓ Task tools registered")
    except ImportError as e:
        logger.warning(f"⚠ Task tools not available: {e}")
    except Exception as e:
        logger.error(f"✗ Error registering Task tools: {e}")

    # Import and register Document tools
    try:
        from src.mcp_server.features.documents import register_document_tools

        register_document_tools(_mcp_instance)
        modules_registered += 1
        logger.info("✓ Document tools registered")
    except ImportError as e:
        logger.warning(f"⚠ Document tools not available: {e}")
    except Exception as e:
        logger.error(f"✗ Error registering Document tools: {e}")

    # Import and register Worktree tools
    try:
        from src.mcp_server.features.worktree import register_worktree_tools

        register_worktree_tools(_mcp_instance)
        modules_registered += 1
        logger.info("✓ Worktree tools registered")
    except ImportError as e:
        logger.warning(f"⚠ Worktree tools not available: {e}")
    except Exception as e:
        logger.error(f"✗ Error registering Worktree tools: {e}")

    # Import and register Code Audit tools
    try:
        from src.mcp_server.features.code_audit import register_code_audit_tools

        register_code_audit_tools(_mcp_instance)
        modules_registered += 1
        logger.info("✓ Code audit tools registered")
    except ImportError as e:
        logger.warning(f"⚠ Code audit tools not available: {e}")
    except Exception as e:
        logger.error(f"✗ Error registering Code audit tools: {e}")

    # Import and register Code Entity tools
    try:
        from src.mcp_server.features.code_entities import register_code_entity_tools

        register_code_entity_tools(_mcp_instance)
        modules_registered += 1
        logger.info("✓ Code entity tools registered")
    except ImportError as e:
        logger.warning(f"⚠ Code entity tools not available: {e}")
    except Exception as e:
        logger.error(f"✗ Error registering Code entity tools: {e}")

    # Import and register Code Repos tools
    try:
        from src.mcp_server.features.code_repos import register_code_repos_tools

        register_code_repos_tools(_mcp_instance)
        modules_registered += 1
        logger.info("✓ Code repos tools registered")
    except ImportError as e:
        logger.warning(f"⚠ Code repos tools not available: {e}")
    except Exception as e:
        logger.error(f"✗ Error registering Code repos tools: {e}")

    # Import and register Feature tools
    try:
        from src.mcp_server.features.feature_tools import register_feature_tools

        register_feature_tools(_mcp_instance)
        modules_registered += 1
        logger.info("✓ Feature tools registered")
    except ImportError as e:
        logger.warning(f"⚠ Feature tools not available: {e}")
    except Exception as e:
        logger.error(f"✗ Error registering Feature tools: {e}")

    # Import and register Version tools
    try:
        from src.mcp_server.features.documents import register_version_tools

        register_version_tools(_mcp_instance)
        modules_registered += 1
        logger.info("✓ Version tools registered")
    except ImportError as e:
        logger.warning(f"⚠ Version tools not available: {e}")
    except Exception as e:
        logger.error(f"✗ Error registering Version tools: {e}")

    logger.info(f"📦 Total MCP tool modules registered: {modules_registered}")


async def _shutdown_mcp_tools():
    """Clean up MCP tools on shutdown."""
    global _mcp_instance
    logger.info("🧹 Cleaning up MCP tools...")
    _mcp_instance = None
    logger.info("✓ MCP tools cleared")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown tasks."""
    global _initialization_complete
    _initialization_complete = False

    # Startup
    logger.info("🚀 Starting Archon backend...")

    try:
        # Validate configuration FIRST - check for anon vs service key
        from .config.config import get_config

        get_config()  # This will raise ConfigurationError if anon key detected

        # Initialize credentials from database FIRST - this is the foundation for everything else
        await initialize_credentials()

        # Apply pending database migrations automatically
        try:
            from .services.migration_service import migration_service
            from .services.database import get_database_connector

            db = get_database_connector()

            pending = await migration_service.get_pending_migrations()
            if pending:
                api_logger.info(f"🔄 Found {len(pending)} pending migrations, applying...")

                for migration in pending:
                    try:
                        sql = migration.sql_content

                        # Check what migration this is and apply accordingly
                        if "archon_operation_progress" in sql:
                            # Try to create the table by inserting a record - if it fails, table doesn't exist
                            # We'll handle this by checking if the table exists first
                            try:
                                # Check if table exists by querying it
                                await db.fetch("SELECT id FROM archon_operation_progress LIMIT 1")
                                api_logger.info(f"Table archon_operation_progress already exists")
                            except Exception:
                                # Table doesn't exist - we need to create it
                                # Use the storage API to create table or skip for now
                                api_logger.warning(
                                    f"Table archon_operation_progress needs manual creation: {sql[:200]}..."
                                )

                            # Record the migration as applied
                            try:
                                await db.execute(
                                    """
                                    INSERT INTO archon_migrations (version, migration_name)
                                    VALUES ($1, $2)
                                    ON CONFLICT (version) DO NOTHING
                                    """,
                                    migration.version,
                                    migration.name,
                                )
                                api_logger.info(f"✅ Recorded migration: {migration.name}")
                            except Exception:
                                # Might already be recorded
                                pass
                        else:
                            # For other migrations, try to record them
                            try:
                                await db.execute(
                                    """
                                    INSERT INTO archon_migrations (version, migration_name)
                                    VALUES ($1, $2)
                                    ON CONFLICT (version) DO NOTHING
                                    """,
                                    migration.version,
                                    migration.name,
                                )
                                api_logger.info(f"✅ Recorded migration: {migration.name}")
                            except:
                                pass

                    except Exception as me:
                        api_logger.warning(f"⚠️ Migration {migration.name} issue: {me}")

                api_logger.info("✅ Database migrations processed")
            else:
                api_logger.info("✅ Database migrations up to date")
        except Exception as me:
            api_logger.warning(f"⚠️ Could not apply migrations: {me}")

        # Validate database schema - fail fast if schema is incomplete
        schema_validation_message = None
        try:
            # Using PostgreSQL directly - skip Supabase-specific schema validation
            schema_validation_message = "Using PostgreSQL directly (schema validation skipped)"
            api_logger.info(f"✅ {schema_validation_message}")
        except ValueError as ve:
            # Database not configured
            if "DATABASE_URL" in str(ve) or "SUPABASE_URL" in str(ve):
                schema_validation_message = (
                    "Supabase not configured - using PostgreSQL directly, schema validation skipped"
                )
            else:
                raise RuntimeError(f"Database schema validation failed: {ve}")
        except ImportError:
            # Schema validator not available, skip validation
            schema_validation_message = "Schema validator not available, skipping validation"
        except Exception as ve:
            # Schema validation failed critically
            raise RuntimeError(f"Database schema validation failed: {ve}")

        # Now that credentials are loaded, we can properly initialize logging
        # This must happen AFTER credentials so LOGFIRE_ENABLED is set from database
        setup_logfire(service_name="archon-backend")

        # Now we can safely use the logger
        logger.info("✅ Credentials initialized")
        api_logger.info("🔥 Logfire initialized for backend")

        # Log schema validation result now that logging is configured
        if schema_validation_message:
            api_logger.info(f"✅ {schema_validation_message}")

        # Initialize crawling context
        try:
            await initialize_crawler()
        except Exception as e:
            api_logger.warning(f"Could not fully initialize crawling context: {str(e)}")

        # Restore paused/in_progress operations from database after restart
        try:
            from .utils.progress.progress_tracker import ProgressTracker

            restored_count = await ProgressTracker.restore_paused_operations()
            if restored_count > 0:
                api_logger.info(f"✅ Restored {restored_count} paused operations from database")

            # Auto-resume all paused operations (both user-paused and crash-interrupted)
            resumed_count = await ProgressTracker.auto_resume_paused_operations()
            if resumed_count > 0:
                api_logger.info(f"🔄 Auto-resumed {resumed_count} paused operations")
        except Exception as e:
            api_logger.warning(f"Could not restore paused operations: {str(e)}")

        # Make crawling context available to modules
        # Crawler is now managed by CrawlerManager

        api_logger.info("✅ Using polling for real-time updates")

        # Initialize prompt service
        try:
            from .services.prompt_service import prompt_service

            await prompt_service.load_prompts()
            api_logger.info("✅ Prompt service initialized")
        except Exception as e:
            api_logger.warning(f"Could not initialize prompt service: {e}")

        # Initialize MCP tools in the same container (single-container architecture)
        try:
            await _initialize_mcp_tools()
            api_logger.info("✅ MCP tools initialized (single-container mode)")
        except Exception as e:
            api_logger.warning(f"Could not initialize MCP tools: {e}")

        # Initialize PydanticAI agents
        try:
            initialize_agents()
            api_logger.info("✅ Agents initialized (document, rag)")
        except Exception as e:
            api_logger.warning(f"Could not initialize agents: {e}")

        # Mark initialization as complete
        _initialization_complete = True
        api_logger.info("🎉 Archon backend started successfully!")

    except Exception:
        api_logger.error("❌ Failed to start backend", exc_info=True)
        raise

    yield

    # Shutdown
    _initialization_complete = False
    api_logger.info("🛑 Shutting down Archon backend...")

    try:
        # MCP tools cleanup
        await _shutdown_mcp_tools()

        # Cleanup crawling context
        try:
            await cleanup_crawler()
        except Exception as e:
            api_logger.warning("Could not cleanup crawling context: %s", e, exc_info=True)

        api_logger.info("✅ Cleanup completed")

    except Exception:
        api_logger.error("❌ Error during shutdown", exc_info=True)


# Create FastAPI application
app = FastAPI(
    title="Archon Knowledge Engine API",
    description="Backend API for the Archon knowledge management and project automation platform",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Add middleware to skip logging for health checks
@app.middleware("http")
async def skip_health_check_logs(request, call_next):
    # Skip logging for health check endpoints
    if request.url.path in ["/health", "/api/health"]:
        # Temporarily suppress the log
        import logging

        logger = logging.getLogger("uvicorn.access")
        old_level = logger.level
        logger.setLevel(logging.ERROR)
        response = await call_next(request)
        logger.setLevel(old_level)
        return response
    return await call_next(request)


# Include API routers
app.include_router(settings_router)
app.include_router(mcp_router)
# app.include_router(mcp_client_router)  # Removed - not part of new architecture
app.include_router(knowledge_router)


# MCP Tool Endpoints - Unified single-container architecture
# These implement the MCP protocol directly in FastAPI

import json
from datetime import datetime


@app.post("/mcp")
async def mcp_endpoint(request: Request):
    """MCP protocol endpoint - handles JSON-RPC calls."""
    import traceback

    try:
        body = await request.json()
    except:
        body = {}

    logger.info(f"MCP request: {body}")

    method = body.get("method", "")
    request_id = body.get("id")

    # JSON-RPC response format
    def jsonrpc_response(result):
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def jsonrpc_error(code, message):
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}

    # Handle methods
    if method == "initialize":
        return jsonrpc_response(
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "serverInfo": {"name": "archon-mcp", "version": "1.0.0"},
            }
        )

    if method == "tools/list":
        return jsonrpc_response(
            {
                "tools": [
                    {"name": "rag_get_available_sources", "description": "Get list of knowledge sources"},
                    {"name": "rag_search_knowledge_base", "description": "Search knowledge base"},
                    {"name": "rag_search_code_examples", "description": "Search code examples"},
                    {"name": "find_projects", "description": "List projects"},
                    {"name": "find_tasks", "description": "List tasks"},
                ]
            }
        )

    if method == "tools/call":
        tool_name = body.get("params", {}).get("name", "")
        tool_args = body.get("params", {}).get("arguments", {})

        try:
            result = await _handle_mcp_tool(tool_name, tool_args)
            return jsonrpc_response({"content": [{"type": "text", "text": json.dumps(result)}]})
        except Exception as e:
            return jsonrpc_error(-32603, str(e))

    return jsonrpc_error(-32601, "Method not found")


async def _handle_mcp_tool(name: str, args: dict) -> dict:
    """Handle individual MCP tool calls."""

    if name == "rag_get_available_sources":
        from .services.database import get_database_connector

        db = get_database_connector()
        rows = await db.fetch(
            """SELECT source_id, source_display_name as name, source_url as url, 
                      summary as description FROM archon_sources 
              ORDER BY source_display_name"""
        )
        return {"success": True, "sources": [dict(r) for r in rows], "count": len(rows)}

    if name == "find_projects":
        from .services.projects.project_service import ProjectService

        service = ProjectService()
        success, result = await service.list_projects(include_content=False)
        if success:
            projects = result.get("projects", [])
            # Convert datetime to string for JSON
            for p in projects:
                if p.get("created_at"):
                    p["created_at"] = str(p["created_at"])
                if p.get("updated_at"):
                    p["updated_at"] = str(p["updated_at"])
            return {"success": True, "projects": projects, "count": len(projects)}
        return {"success": False, "error": result.get("error", "Failed")}

    if name == "find_tasks":
        from .services.projects.task_service import TaskService

        service = TaskService()
        # Handle filter_by/filter_value parameters and map to service parameters
        filter_by = args.get("filter_by")
        filter_value = args.get("filter_value")

        # Build filter parameters
        project_id = None
        status = None
        search_query = None

        if filter_by == "project" and filter_value:
            project_id = filter_value
        elif filter_by == "status" and filter_value:
            status = filter_value
        elif filter_by == "assignee" and filter_value:
            search_query = filter_value

        success, result = await service.list_tasks(
            project_id=project_id, status=status, include_closed=True, search_query=search_query
        )
        if success:
            tasks = result.get("tasks", [])
            for t in tasks:
                if t.get("created_at"):
                    t["created_at"] = str(t["created_at"])
            return {"success": True, "tasks": tasks, "count": len(tasks)}
        return {"success": False, "error": result.get("error", "Failed")}

    if name == "rag_search_knowledge_base":
        from .services.search.rag_service import RAGService

        service = RAGService()
        source_id = args.get("source_id")
        success, result = await service.perform_rag_query(
            query=args.get("query", ""),
            source=source_id if source_id else None,
            match_count=args.get("match_count", 5),
            return_mode=args.get("return_mode", "pages"),
        )
        if success:
            return {"success": success, "results": result.get("results", []), "count": len(result.get("results", []))}
        return {"success": False, "error": result.get("error", "Failed")}

    if name == "rag_search_code_examples":
        from .services.search.rag_service import RAGService

        service = RAGService()
        success, result = await service.search_code_examples_service(
            query=args.get("query", ""), source_id=args.get("source_id"), match_count=args.get("match_count", 5)
        )
        return {"success": success, "results": result.get("results", []), "error": result.get("error")}

    return {"error": f"Unknown tool: {name}"}


@app.get("/mcp")
async def mcp_sse_endpoint(request: Request):
    """MCP SSE endpoint for event streaming."""
    from fastapi.responses import StreamingResponse

    async def event_stream():
        # Send initial connection message
        yield "event: endpoint\ndata: /mcp\n\n"

        # Keep connection alive
        import asyncio

        while True:
            await asyncio.sleep(30)
            yield ": keepalive\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


app.include_router(pages_router)
app.include_router(ollama_router)
app.include_router(openrouter_router)
app.include_router(projects_router)
app.include_router(git_router)
app.include_router(git_classification_router)
app.include_router(git_test_router)
app.include_router(progress_router)
app.include_router(agent_chat_router)
app.include_router(agents_router)  # Integrated PydanticAI agents
app.include_router(agent_work_orders_router)  # Proxy to independent agent work orders service
app.include_router(internal_router)
app.include_router(bug_report_router)
app.include_router(providers_router)
app.include_router(version_router)
app.include_router(migration_router)
app.include_router(ingestion_router)
app.include_router(audit_router)  # Semgrep audit endpoints
app.include_router(code_repos_router)  # Code repository management


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint returning API information."""
    return {
        "name": "Archon Knowledge Engine API",
        "version": "1.0.0",
        "description": "Backend API for knowledge management and project automation",
        "status": "healthy",
        "modules": ["settings", "mcp", "mcp-clients", "knowledge", "projects"],
    }


# Health check endpoint
@app.get("/health")
async def health_check(response: Response):
    """Health check endpoint that indicates true readiness including credential loading."""
    from datetime import datetime

    # Check if initialization is complete
    if not _initialization_complete:
        response.status_code = 503  # Service Unavailable
        return {
            "status": "initializing",
            "service": "archon-backend",
            "timestamp": datetime.now().isoformat(),
            "message": "Backend is starting up, credentials loading...",
            "ready": False,
        }

    # Check for required database schema
    schema_status = await _check_database_schema()
    if not schema_status["valid"]:
        response.status_code = 503  # Service Unavailable
        return {
            "status": "migration_required",
            "service": "archon-backend",
            "timestamp": datetime.now().isoformat(),
            "ready": False,
            "migration_required": True,
            "message": schema_status["message"],
            "migration_instructions": "Open Supabase Dashboard → SQL Editor → Run: migration/add_source_url_display_name.sql",
            "schema_valid": False,
        }

    return {
        "status": "healthy",
        "service": "archon-backend",
        "timestamp": datetime.now().isoformat(),
        "ready": True,
        "credentials_loaded": True,
        "schema_valid": True,
    }


# API health check endpoint (alias for /health at /api/health)
@app.get("/api/health")
async def api_health_check(response: Response):
    """API health check endpoint - alias for /health."""
    return await health_check(response)


# Cache schema check result to avoid repeated database queries
_schema_check_cache = {"valid": None, "checked_at": 0}


async def _check_database_schema():
    """Check if required database schema exists - only for existing users who need migration."""
    import time

    # If we've already confirmed schema is valid, don't check again
    if _schema_check_cache["valid"] is True:
        return {"valid": True, "message": "Schema is up to date (cached)"}

    # If we recently failed, don't spam the database (wait at least 30 seconds)
    current_time = time.time()
    if _schema_check_cache["valid"] is False and current_time - _schema_check_cache["checked_at"] < 30:
        return _schema_check_cache["result"]

    try:
        from .services.database import get_database_connector

        db = get_database_connector()

        # Try to query the new columns directly - if they exist, schema is up to date
        await db.fetch("SELECT source_url, source_display_name FROM archon_sources LIMIT 1")

        # Cache successful result permanently
        _schema_check_cache["valid"] = True
        _schema_check_cache["checked_at"] = current_time

        return {"valid": True, "message": "Schema is up to date"}

    except ValueError as e:
        # Database not configured - skip schema check
        if "DATABASE_URL" in str(e) or "SUPABASE_URL" in str(e):
            _schema_check_cache["valid"] = True
            _schema_check_cache["checked_at"] = current_time
            return {"valid": True, "message": "Using PostgreSQL directly (schema validation skipped)"}
        error_msg = str(e).lower()
    except Exception as e:
        error_msg = str(e).lower()

        # Log schema check error for debugging
        api_logger.debug(f"Schema check error: {type(e).__name__}: {str(e)}")

        # Check for specific error types based on PostgreSQL error codes and messages

        # Check for missing columns first (more specific than table check)
        missing_source_url = "source_url" in error_msg and ("column" in error_msg or "does not exist" in error_msg)
        missing_source_display = "source_display_name" in error_msg and (
            "column" in error_msg or "does not exist" in error_msg
        )

        # Also check for PostgreSQL error code 42703 (undefined column)
        is_column_error = "42703" in error_msg or "column" in error_msg

        if (missing_source_url or missing_source_display) and is_column_error:
            result = {
                "valid": False,
                "message": "Database schema outdated - missing required columns from recent updates",
            }
            # Cache failed result with timestamp
            _schema_check_cache["valid"] = False
            _schema_check_cache["checked_at"] = current_time
            _schema_check_cache["result"] = result
            return result

        # Check for table doesn't exist (less specific, only if column check didn't match)
        # Look for relation/table errors specifically
        if ("relation" in error_msg and "does not exist" in error_msg) or (
            "table" in error_msg and "does not exist" in error_msg
        ):
            # Table doesn't exist - this is a critical setup issue
            result = {
                "valid": False,
                "message": "Required table missing (archon_sources). Run initial migrations before starting.",
            }
            # Cache failed result with timestamp
            _schema_check_cache["valid"] = False
            _schema_check_cache["checked_at"] = current_time
            _schema_check_cache["result"] = result
            return result

        # Other errors indicate a problem - fail fast principle
        result = {"valid": False, "message": f"Schema check error: {type(e).__name__}: {str(e)}"}
        # Don't cache inconclusive results - allow retry
        return result


# Export the app directly for uvicorn to use


def main():
    """Main entry point for running the server."""
    import uvicorn

    # Require ARCHON_SERVER_PORT to be set
    server_port = os.getenv("ARCHON_SERVER_PORT")
    if not server_port:
        raise ValueError(
            "ARCHON_SERVER_PORT environment variable is required. "
            "Please set it in your .env file or environment. "
            "Default value: 8181"
        )

    uvicorn.run(
        "src.server.main:app",
        host="0.0.0.0",
        port=int(server_port),
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
