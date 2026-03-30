"""Agents API - PydanticAI agents integrated into the main server

This module provides endpoints for running and streaming PydanticAI agents
directly within the main Archon server, eliminating the need for a separate
agents service.

NOTE: Agents are currently DISABLED. The PydanticAI dependency has been removed
to simplify the codebase. Agents can be re-enabled by reinstalling pydantic-ai
and uncommenting the imports below.
"""

import json
import logging
import os
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/agents", tags=["agents"])

# Try to import agents - they require pydantic-ai which is disabled
try:
    from ...agents.document_agent import DocumentAgent
    from ...agents.rag_agent import RagAgent

    AGENTS_ENABLED = True
except ImportError:
    logger.warning("Agents disabled - pydantic-ai not available")
    DocumentAgent = None
    RagAgent = None
    AGENTS_ENABLED = False


# Request/Response models
class AgentRequest(BaseModel):
    """Request model for agent interactions"""

    agent_type: str  # "document", "rag", etc.
    prompt: str
    context: dict[str, Any] | None = None
    options: dict[str, Any] | None = None


class AgentResponse(BaseModel):
    """Response model for agent interactions"""

    success: bool
    result: Any | None = None
    error: str | None = None
    metadata: dict[str, Any] | None = None


# Agent registry - populated during startup if agents are available
AVAILABLE_AGENTS: dict[str, type] = {}
if AGENTS_ENABLED:
    if DocumentAgent:
        AVAILABLE_AGENTS["document"] = DocumentAgent
    if RagAgent:
        AVAILABLE_AGENTS["rag"] = RagAgent

# Global agents storage - initialized in lifespan
_agents: dict[str, Any] = {}


def get_available_agents() -> list[dict[str, Any]]:
    """Get list of available agent types with their capabilities."""
    if not AGENTS_ENABLED:
        return []

    agents_info = []
    for agent_type, agent_class in AVAILABLE_AGENTS.items():
        try:
            # Create temporary instance to get metadata
            temp_agent = agent_class()
            agents_info.append(
                {
                    "type": agent_type,
                    "name": temp_agent.name,
                    "description": temp_agent.__doc__ or f"{agent_type.capitalize()} agent",
                    "model": temp_agent.model,
                    "capabilities": getattr(temp_agent, "capabilities", []),
                }
            )
        except Exception as e:
            logger.warning(f"Failed to get agent info for {agent_type}: {e}")
    return agents_info


@router.get("/available")
async def list_available_agents() -> dict[str, Any]:
    """List all available agent types and their capabilities."""
    if not AGENTS_ENABLED:
        return {
            "success": False,
            "agents": [],
            "message": "Agents are disabled - pydantic-ai dependency removed",
            "count": 0,
        }

    agents = get_available_agents()
    return {
        "success": True,
        "agents": agents,
        "count": len(agents),
    }


@router.post("/run")
async def run_agent(request: AgentRequest) -> AgentResponse:
    """Run an agent synchronously and return the result."""
    if not AGENTS_ENABLED:
        return AgentResponse(
            success=False,
            error="Agents are disabled - pydantic-ai dependency removed. To enable agents, reinstall pydantic-ai.",
        )

    try:
        agent_type = request.agent_type

        # Check if agent type is available
        if agent_type not in AVAILABLE_AGENTS:
            available = list(AVAILABLE_AGENTS.keys())
            return AgentResponse(
                success=False,
                error=f"Agent type '{agent_type}' not available. Available: {available}",
            )

        # Get or create agent instance
        agent_instance = _agents.get(agent_type)
        if agent_instance is None:
            agent_class = AVAILABLE_AGENTS[agent_type]
            agent_instance = agent_class()
            _agents[agent_type] = agent_instance
            logger.info(f"Initialized {agent_type} agent: {agent_instance.name}")

        # Run the agent
        result = await agent_instance.run(request.prompt, deps=request.context)

        return AgentResponse(
            success=True,
            result=result,
            metadata={
                "agent_type": agent_type,
                "model": agent_instance.model,
            },
        )

    except Exception as e:
        logger.exception(f"Agent run failed: {e}")
        return AgentResponse(
            success=False,
            error=str(e),
        )


@router.post("/stream")
async def stream_agent(request: AgentRequest) -> StreamingResponse:
    """Run an agent and stream the response."""
    if not AGENTS_ENABLED:
        return StreamingResponse(
            iter([b"data: Agents are disabled - pydantic-ai dependency removed\n\n"]),
            media_type="text/event-stream",
        )

    async def event_generator() -> AsyncGenerator[bytes, None]:
        try:
            agent_type = request.agent_type

            # Check if agent type is available
            if agent_type not in AVAILABLE_AGENTS:
                available = list(AVAILABLE_AGENTS.keys())
                yield f"data: Error: Agent type '{agent_type}' not available. Available: {available}\n\n".encode()
                return

            # Get or create agent instance
            agent_instance = _agents.get(agent_type)
            if agent_instance is None:
                agent_class = AVAILABLE_AGENTS[agent_type]
                agent_instance = agent_class()
                _agents[agent_type] = agent_instance

            # Stream the response
            async for chunk in agent_instance.stream(request.prompt, deps=request.context):
                data = json.dumps({"chunk": str(chunk)})
                yield f"data: {data}\n\n".encode()

            # Send completion event
            yield b"data: [DONE]\n\n"

        except Exception as e:
            logger.exception(f"Agent stream failed: {e}")
            error_data = json.dumps({"error": str(e)})
            yield f"data: {error_data}\n\n".encode()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


@router.get("/health")
async def agents_health() -> dict[str, Any]:
    """Health check for agents service."""
    if not AGENTS_ENABLED:
        return {
            "status": "disabled",
            "message": "Agents are disabled - pydantic-ai dependency removed",
            "agents": {},
        }

    agents_status = {}
    for agent_type in AVAILABLE_AGENTS:
        agent_instance = _agents.get(agent_type)
        agents_status[agent_type] = {
            "initialized": agent_instance is not None,
            "model": agent_instance.model if agent_instance else None,
        }

    return {
        "status": "healthy" if agents_status else "uninitialized",
        "agents": agents_status,
    }


async def initialize_agents() -> dict[str, Any]:
    """Initialize agents at startup.

    This function is called during application lifespan to initialize
    all available agents. If agents are disabled, returns empty status.

    Returns:
        Status dictionary with initialized agents
    """
    if not AGENTS_ENABLED:
        logger.info("Agents initialization skipped - pydantic-ai not available")
        return {"status": "disabled", "agents": {}}

    initialized = {}
    for agent_type, agent_class in AVAILABLE_AGENTS.items():
        try:
            agent_instance = agent_class()
            _agents[agent_type] = agent_instance
            initialized[agent_type] = {
                "initialized": True,
                "model": agent_instance.model,
                "name": agent_instance.name,
            }
            logger.info(f"Initialized {agent_type} agent: {agent_instance.name}")
        except Exception as e:
            logger.error(f"Failed to initialize {agent_type} agent: {e}")
            initialized[agent_type] = {"initialized": False, "error": str(e)}

    logger.info(f"Agents initialization complete: {len(initialized)} agents")
    return {"status": "initialized", "agents": initialized}
