"""
MCP API endpoints for Archon

Provides status and configuration endpoints for the MCP service.
MCP is now integrated into the main server process (single container architecture).
"""

import os
from typing import Any

from fastapi import APIRouter, HTTPException

from ..config.logfire_config import api_logger, safe_set_attribute, safe_span

router = APIRouter(prefix="/api/mcp", tags=["mcp"])


@router.get("/status")
async def get_status():
    """Get MCP service status.

    MCP is now part of the main server process, so this returns the local status.
    """
    with safe_span("api_mcp_status") as span:
        safe_set_attribute(span, "endpoint", "/api/mcp/status")
        safe_set_attribute(span, "method", "GET")

        # MCP is in-process now, so it's always running if the server is running
        status = {
            "status": "running",
            "uptime": None,
            "logs": [],
            "mode": "in-process",
            "message": "MCP is integrated into the main server process",
        }

        api_logger.debug(f"MCP status checked - in-process mode")
        safe_set_attribute(span, "status", status["status"])

        return status


@router.get("/config")
async def get_mcp_config():
    """Get MCP server configuration."""
    with safe_span("api_get_mcp_config") as span:
        safe_set_attribute(span, "endpoint", "/api/mcp/config")
        safe_set_attribute(span, "method", "GET")

        try:
            api_logger.info("Getting MCP server configuration")

            # MCP is now part of the main server, so it uses the same port
            server_port = int(os.getenv("ARCHON_SERVER_PORT", "8181"))

            config = {
                "host": os.getenv("ARCHON_HOST", "localhost"),
                "port": server_port,
                "transport": "in-process",
                "mode": "single-container",
            }

            # Get model choice from database
            try:
                from ..services.credential_service import credential_service

                model_choice = await credential_service.get_credential("MODEL_CHOICE", "gpt-4o-mini")
                config["model_choice"] = model_choice
            except Exception:
                # Fallback to default model
                config["model_choice"] = "gpt-4o-mini"

            api_logger.info("MCP configuration (in-process mode)")
            safe_set_attribute(span, "host", config["host"])
            safe_set_attribute(span, "port", config["port"])
            safe_set_attribute(span, "transport", "in-process")
            safe_set_attribute(span, "model_choice", config.get("model_choice", "gpt-4o-mini"))

            return config
        except Exception as e:
            api_logger.error("Failed to get MCP configuration", exc_info=True)
            safe_set_attribute(span, "error", str(e))
            raise HTTPException(status_code=500, detail={"error": str(e)}) from e


@router.get("/clients")
async def get_mcp_clients():
    """Get connected MCP clients with type detection."""
    with safe_span("api_mcp_clients") as span:
        safe_set_attribute(span, "endpoint", "/api/mcp/clients")
        safe_set_attribute(span, "method", "GET")

        try:
            # TODO: Implement real client detection in the future
            api_logger.debug("Getting MCP clients - returning empty array")

            return {"clients": [], "total": 0}
        except Exception as e:
            api_logger.error(f"Failed to get MCP clients - error={str(e)}")
            safe_set_attribute(span, "error", str(e))
            return {"clients": [], "total": 0, "error": str(e)}


@router.get("/sessions")
async def get_mcp_sessions():
    """Get MCP session information."""
    with safe_span("api_mcp_sessions") as span:
        safe_set_attribute(span, "endpoint", "/api/mcp/sessions")
        safe_set_attribute(span, "method", "GET")

        try:
            # Basic session info
            session_info = {
                "active_sessions": 0,  # TODO: Implement real session tracking
                "session_timeout": 3600,  # 1 hour default
                "mode": "in-process",
            }

            api_logger.debug(f"MCP session info - sessions={session_info.get('active_sessions')}")
            safe_set_attribute(span, "active_sessions", session_info.get("active_sessions"))

            return session_info
        except Exception as e:
            api_logger.error(f"Failed to get MCP sessions - error={str(e)}")
            safe_set_attribute(span, "error", str(e))
            raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/health")
async def mcp_health():
    """Health check for MCP service."""
    with safe_span("api_mcp_health") as span:
        safe_set_attribute(span, "endpoint", "/api/mcp/health")
        safe_set_attribute(span, "method", "GET")

        # MCP is in-process, so if this endpoint is reachable, MCP is healthy
        result = {"status": "healthy", "service": "mcp", "mode": "in-process"}
        safe_set_attribute(span, "status", "healthy")

        return result
