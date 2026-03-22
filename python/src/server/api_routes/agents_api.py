"""
Agents API - PydanticAI agents integrated into the main server

This module provides endpoints for running and streaming PydanticAI agents
directly within the main Archon server, eliminating the need for a separate
agents service.
"""

import json
import logging
import os
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Import agents directly - they now use services instead of HTTP MCP calls
from ...agents.document_agent import DocumentAgent
from ...agents.rag_agent import RagAgent

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/agents", tags=["agents"])


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


# Agent registry - populated during startup
AVAILABLE_AGENTS: dict[str, type] = {
    "document": DocumentAgent,
    "rag": RagAgent,
}

# Global agents storage - initialized in lifespan
_agents: dict[str, Any] = {}


def initialize_agents():
    """
    Initialize agents configuration (agents are created lazily on first use).

    This allows the server to start without OpenAI API keys.
    Agents will be instantiated when first requested.
    """
    global _agents

    # Mark agents as available but don't instantiate yet
    _agents = {}
    for name, agent_class in AVAILABLE_AGENTS.items():
        # Store agent class and config for lazy instantiation
        model_key = f"{name.upper()}_AGENT_MODEL"
        model = os.getenv(model_key, "openai:gpt-4o-mini")
        _agents[name] = {
            "class": agent_class,
            "model": model,
            "instance": None,  # Will be created on first use
        }
        logger.info(f"Registered {name} agent (model: {model}) - lazy initialization")

    return _agents


def get_agent(name: str):
    """
    Get or create an agent instance (lazy initialization).

    Args:
        name: Agent name (e.g., "document", "rag")

    Returns:
        Agent instance or None if not available
    """
    global _agents

    if name not in _agents:
        return None

    agent_info = _agents[name]

    # If it's already an instance, return it
    if agent_info.get("instance") is not None:
        return agent_info["instance"]

    # Lazy initialization - create the agent now
    try:
        agent_class = agent_info["class"]
        model = agent_info["model"]
        instance = agent_class(model=model)
        _agents[name]["instance"] = instance
        logger.info(f"Lazy-initialized {name} agent")
        return instance
    except Exception as e:
        logger.error(f"Failed to lazy-initialize {name} agent: {e}")
        return None


def get_agents():
    """Get the agents registry."""
    return _agents


@router.get("/health")
async def health_check():
    """Health check endpoint for agents"""
    return {
        "status": "healthy",
        "service": "agents",
        "agents_available": list(_agents.keys()),
        "agents_initialized": len(_agents),
    }


@router.post("/run", response_model=AgentResponse)
async def run_agent(request: AgentRequest):
    """
    Run a specific agent with the given prompt.

    The agent will use services directly (not HTTP calls) for data operations.
    Agents are lazily initialized on first use.
    """
    try:
        # Get or create the requested agent (lazy initialization)
        agent = get_agent(request.agent_type)

        if agent is None:
            raise HTTPException(
                status_code=400, detail=f"Unknown agent type: {request.agent_type}. Available: {list(_agents.keys())}"
            )

        # Prepare dependencies based on agent type
        if request.agent_type == "rag":
            from ...agents.rag_agent import RagDependencies

            deps = RagDependencies(
                source_filter=request.context.get("source_filter") if request.context else None,
                match_count=request.context.get("match_count", 5) if request.context else 5,
                project_id=request.context.get("project_id") if request.context else None,
                user_id=request.context.get("user_id") if request.context else None,
            )
        elif request.agent_type == "document":
            from ...agents.document_agent import DocumentDependencies

            deps = DocumentDependencies(
                project_id=request.context.get("project_id") if request.context else None,
                user_id=request.context.get("user_id") if request.context else None,
                current_document_id=request.context.get("current_document_id") if request.context else None,
            )
        else:
            # Default dependencies
            from ...agents.base_agent import ArchonDependencies

            deps = ArchonDependencies()

        # Run the agent
        result = await agent.run(request.prompt, deps)

        return AgentResponse(
            success=True,
            result=result,
            metadata={"agent_type": request.agent_type, "model": agent.model},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running {request.agent_type} agent: {e}")
        return AgentResponse(success=False, error=str(e))


@router.get("/list")
async def list_agents():
    """List all available agents and their capabilities"""
    agents_info = {}

    for name, agent_info in _agents.items():
        # Handle both lazy init dicts and instantiated agents
        if isinstance(agent_info, dict):
            # Lazy init mode - get from config dict
            agent_class = agent_info.get("class")
            model = agent_info.get("model")
            instance = agent_info.get("instance")

            agents_info[name] = {
                "name": name,
                "model": model,
                "description": agent_class.__doc__ if agent_class else "No description available",
                "available": True,
                "initialized": instance is not None,
            }
        else:
            # Direct instance (shouldn't happen with lazy init, but handle for backwards compat)
            agents_info[name] = {
                "name": agent_info.name,
                "model": agent_info.model,
                "description": agent_info.__class__.__doc__ or "No description available",
                "available": True,
                "initialized": True,
            }

    return {"agents": agents_info, "total": len(agents_info)}


@router.post("/{agent_type}/stream")
async def stream_agent(agent_type: str, request: AgentRequest):
    """
    Stream responses from an agent using Server-Sent Events (SSE).

    This endpoint streams the agent's response in real-time, allowing
    for a more interactive experience.

    Agents are lazily initialized on first use.
    """
    # Get or create the requested agent (lazy initialization)
    agent = get_agent(agent_type)

    if agent is None:
        raise HTTPException(
            status_code=400, detail=f"Unknown agent type: {agent_type}. Available: {list(_agents.keys())}"
        )

    async def generate() -> AsyncGenerator[str, None]:
        try:
            # Prepare dependencies based on agent type
            if agent_type == "rag":
                from ...agents.rag_agent import RagDependencies

                deps = RagDependencies(
                    source_filter=request.context.get("source_filter") if request.context else None,
                    match_count=request.context.get("match_count", 5) if request.context else 5,
                    project_id=request.context.get("project_id") if request.context else None,
                    user_id=request.context.get("user_id") if request.context else None,
                )
            elif agent_type == "document":
                from ...agents.document_agent import DocumentDependencies

                deps = DocumentDependencies(
                    project_id=request.context.get("project_id") if request.context else None,
                    user_id=request.context.get("user_id") if request.context else None,
                    current_document_id=request.context.get("current_document_id") if request.context else None,
                )
            else:
                # Default dependencies
                from ...agents.base_agent import ArchonDependencies

                deps = ArchonDependencies()

            # Use PydanticAI's run_stream method
            async with agent.run_stream(request.prompt, deps) as stream:
                # Stream text chunks as they arrive
                async for chunk in stream.stream_text():
                    event_data = json.dumps({"type": "stream_chunk", "content": chunk})
                    yield f"data: {event_data}\n\n"

                # Get the final structured result
                try:
                    final_result = await stream.get_data()
                    event_data = json.dumps({"type": "stream_complete", "content": final_result})
                    yield f"data: {event_data}\n\n"
                except Exception:
                    # If we can't get structured data, just send completion
                    event_data = json.dumps({"type": "stream_complete", "content": ""})
                    yield f"data: {event_data}\n\n"

        except Exception as e:
            logger.error(f"Error streaming {agent_type} agent: {e}")
            event_data = json.dumps({"type": "error", "error": str(e)})
            yield f"data: {event_data}\n\n"

    # Return SSE response
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable Nginx buffering
        },
    )
