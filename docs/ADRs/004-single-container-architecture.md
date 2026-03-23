# ADR-004: Single-Container Architecture

## Status: Accepted

## Date: 2026-03-23

## Context

Archon originally used a microservices architecture with multiple Docker containers:
- `archon-ui` - Frontend (port 3737)
- `archon-server` - API (port 8181)
- `archon-mcp` - MCP Server (port 8051)
- `archon-agents` - AI Agents (port 8052)
- `archon-agent-work-orders` - Workflow engine (port 8053)
- `archon-postgres` - Database

This created significant operational challenges:
- Complex docker-compose configuration with multiple profiles
- Service synchronization overhead
- Port conflict management
- Difficult debugging across service boundaries
- High resource usage from multiple containers
- Complex deployment and scaling

## Decision

We will use a **single-container architecture** with PostgreSQL embedded:

### Implementation Details
- **Single Container**: All services (API, MCP, Agents) run in one container
- **Embedded Database**: PostgreSQL runs in the same container
- **Port Exposure**: Only port 8181 (API server)
- **MCP Access**: Via stdio transport (docker exec), not network

### Architecture Diagram
```
┌─────────────────────────────────────────────┐
│           Docker Container                  │
│  ┌─────────────────────────────────────┐   │
│  │   Main FastAPI Server (port 8181)   │   │
│  │   - API routes                      │   │
│  │   - MCP tools registered            │   │
│  │   - PydanticAI agents               │   │
│  └─────────────────────────────────────┘   │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │   PostgreSQL (embedded)             │   │
│  │   - Application data                │   │
│  │   - Code entities                   │   │
│  │   - Knowledge base                  │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

### Why Single Container?
1. **Simpler Operations**: One container to manage
2. **Lower Overhead**: No inter-service HTTP calls
3. **Easier Debugging**: Single log stream, one stack trace
4. **Direct Imports**: Full type safety, no serialization
5. **Faster Development**: Hot reload works reliably

### Migration Path
- Removed multi-service docker-compose profiles
- Updated Dockerfile to run single server process
- MCP now accessed via `docker exec` (stdio)
- Database connection uses localhost (not network)

## Consequences

### Positive
- Simpler deployment and operations
- No port conflicts
- Lower resource usage
- Faster startup time
- Easier local development

### Negative
- Cannot scale services independently
- Single point of failure (mitigated by container restarts)
- No horizontal scaling (acceptable for local use)

## Related Decisions

- ADR-003: MCP Server Consolidation to STDIO Transport
- ADR-005: Code Intelligence with BGE-M3 Embeddings
