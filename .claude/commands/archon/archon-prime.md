---
name: prime
description: |
  Prime Claude Code with deep context for a specific part of the Archon codebase.

  Usage: /prime "<service>" "<special focus>"
  Examples:
  /prime "frontend" "Focus on UI components and React"
  /prime "server" "Focus on FastAPI and backend services"
  /prime "knowledge" "Focus on RAG and knowledge management"
argument-hint: <service> <Specific focus>
---

You're about to work on the Archon V2 Beta codebase. This is a code intelligence platform with MCP tools for AI agents. It uses a single-container architecture with embedded PostgreSQL. Here's what you need to know:

## Today's Focus area

Today we are focusing on: $ARGUMENTS
And pay special attention to: $ARGUMENTS

## Decision

Think hard and make an intelligent decision about which key files you need to read and create a todo list.
If you discover something you need to look deeper at or imports from files you need context from, append it to the todo list during the priming process. The goal is to get key understandings of the codebase so you are ready to make code changes to that part of the codebase.

## Architecture Overview

### Frontend (port 3737) - React + TypeScript + Vite

```
archon-ui-main/
├── src/
│   ├── App.tsx                    # Main app component with routing and providers
│   ├── index.tsx                  # React entry point with theme and settings
│   ├── components/
│   │   ├── layouts/               # Layout components (MainLayout, SideNavigation)
│   │   ├── knowledge-base/        # Knowledge management UI (documents, items, search)
│   │   ├── project-tasks/         # Project and task management components
│   │   ├── prp/                   # Product Requirements Prompt viewer components
│   │   ├── mcp/                   # MCP client management and testing UI
│   │   ├── settings/              # Settings panels (API keys, features, RAG config)
│   │   └── ui/                    # Reusable UI components (buttons, cards, inputs)
│   ├── services/                  # API client services for backend communication
│   │   ├── knowledgeBaseService.ts    # Knowledge item CRUD and search operations
│   │   ├── projectService.ts          # Project and task management API calls
│   │   ├── mcpService.ts              # MCP server communication and tool execution
│   │   └── socketIOService.ts         # Real-time WebSocket event handling
│   ├── hooks/                     # Custom React hooks for state and effects
│   ├── contexts/                  # React contexts (Settings, Theme, Toast)
│   └── pages/                     # Main page components for routing
```

### Backend Server (port 8181) - FastAPI + Socket.IO

```
python/src/server/
├── main.py                        # FastAPI app initialization and routing setup
├── socketio_app.py               # Socket.IO server configuration and namespaces
├── config/
│   ├── config.py                 # Environment variables and app configuration
│   └── service_discovery.py     # Service URL resolution for Docker/local
├── api_routes/                      # API route handlers (thin wrappers)
│   ├── knowledge_api.py         # Knowledge base endpoints (upload, search)
│   ├── projects_api.py          # Project and task management endpoints
│   ├── mcp_api.py              # MCP tool execution and health checks
│   └── socketio_handlers.py    # Socket.IO event handlers and broadcasts
├── services/                     # Business logic layer
│   ├── knowledge/
│   │   ├── knowledge_item_service.py       # Knowledge item CRUD operations
│   │   └── code_extraction_service.py      # Extract code examples from docs
│   ├── projects/
│   │   ├── project_service.py              # Project management logic
│   │   ├── task_service.py                 # Task lifecycle and status management
│   │   └── versioning_service.py           # Document version control
│   ├── search/
│   │   └── vector_search_service.py        # Semantic search with pgvector
│   ├── documents/
│   │   ├── local_document_service.py       # Document processing (Dockling)
│   │   ├── chunking_service.py             # Document chunking
│   │   └── summarization_service.py        # Document summarization
│   ├── embeddings/
│   │   └── embedding_service.py            # OpenAI embeddings generation
│   └── storage/
│       ├── code_storage/                   # Code storage modules
│       └── document_storage_service.py     # Document chunking and storage
└── exceptions.py               # Custom exception hierarchy
```

### MCP Server (STDIO via `docker exec`) - Model Context Protocol

```
python/src/mcp_server/
├── mcp_server_stdio.py         # MCP server with STDIO transport
└── features/                   # MCP tool implementations
    ├── project_tools.py        # Project and task MCP tools
    ├── code_tools.py           # Code search tools
    └── search_tools.py         # RAG query and search tools
```

## Key Files to Read for Context

### When working on Frontend

Key files to consider:

- `archon-ui-main/src/App.tsx` - Main app structure and routing
- `archon-ui-main/src/services/knowledgeBaseService.ts` - API call patterns
- `archon-ui-main/src/services/socketIOService.ts` - Real-time events

### When working on Backend

Key files to consider:

- `python/src/server/main.py` - FastAPI app setup
- `python/src/server/services/knowledge/knowledge_item_service.py` - Service pattern example
- `python/src/server/api_routes/knowledge_api.py` - API endpoint pattern
- `python/src/server/exceptions.py` - Exception hierarchy

### When working on MCP

Key files to consider:

- `python/src/mcp_server/mcp_server_stdio.py` - MCP server implementation
- `python/src/mcp_server/features/` - Tool implementations

### When working on RAG

Key files to consider:

- `python/src/server/services/search/vector_search_service.py` - Vector search logic
- `python/src/server/services/embeddings/embedding_service.py` - Embedding generation
- `python/src/mcp_server/features/search_tools.py` - RAG tools

### When working on Document Processing

Key files to consider:

- `python/src/server/services/documents/local_document_service.py` - Document processing (Dockling)
- `python/src/server/services/documents/chunking_service.py` - Document chunking
- `python/src/server/services/documents/summarization_service.py` - Document summarization

### When working on Projects/Tasks

Key files to consider:

- `python/src/server/services/projects/project_service.py` - Project management
- `python/src/server/services/projects/task_service.py` - Task lifecycle
- `python/src/mcp_server/features/project_tools.py` - MCP project tools

## Development Patterns

### Error Handling (Beta Philosophy)

Following CLAUDE.md principles:

**Fail Fast & Loud (where errors MUST bubble up):**
- Service initialization errors - Crash immediately
- Configuration errors - Stop the system
- Database connection failures - Expose them
- Authentication failures - Be visible
- Data corruption - Never silently accept bad data

**Complete but Log Clearly (batch operations):**
- Background tasks - Complete the job, log failures per item
- Batch operations - Process what you can, report what failed
- WebSocket events - Don't crash on single event failure

**Example pattern:**
```python
# BAD - Silent failure
try:
    result = risky_operation()
except Exception:
    return None

# GOOD - Detailed error with context
try:
    result = risky_operation()
except SpecificError as e:
    logger.error(f"Operation failed at step X: {e}", exc_info=True)
    raise  # Let it bubble up!
```

### Service Layer Patterns

Services follow these patterns:

1. **Thin API routes** - Routes just validate and call services
2. **Service layer** - Business logic lives in services
3. **Exception hierarchy** - Custom exceptions from `exceptions.py`
4. **Type hints** - All functions have proper type hints
5. **Async first** - Services use async/await patterns

### MCP Tool Patterns

MCP tools:

1. **STDIO transport** - No HTTP/SSE, uses STDIO via `docker exec`
2. **Consistent patterns** - All tools follow same structure
3. **Error propagation** - Detailed errors back to IDE
4. **Version-scoped** - Search respects current git branch

## Context Collection

Now collect context for the specific focus area. Focus on:

1. **Service structure** - How services are organized
2. **API patterns** - How routes and services connect
3. **Error handling** - Current patterns in this area
4. **Test coverage** - Existing tests you can reference

Create a todo list of files to read based on the focus area, then execute it systematically.