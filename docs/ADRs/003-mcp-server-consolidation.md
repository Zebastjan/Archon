# ADR-003: MCP Server Consolidation to STDIO Transport

## Status: Accepted

## Date: 2026-03-23

## Context

Archon had multiple fragmented MCP server implementations causing confusion and instability:
- `mcp_server.py` - HTTP/SSE on port 8051 (legacy)
- `mcp_server_stdio.py` - STDIO transport (preferred)
- `unified_main.py` - Combined FastAPI + MCP (dead code)
- MCP code embedded in `server/main.py`

This created:
- Port conflicts and dual-server complexity
- Inconsistent tool registration across implementations
- IDE configuration drift (Windsurf, ClaudeCode, OctoFriend, OpenCode all different)
- Maintenance burden with 4 implementations to keep in sync

## Decision

We will use a **single stdio-based MCP server** (`mcp_server_stdio.py`) as the sole implementation:

### Implementation Details
- **Transport**: STDIO (recommended by MCP spec for local servers)
- **Startup**: On-demand via `docker exec` from IDEs
- **Tool Registration**: Shared module (`tool_registration.py`) for consistency
- **Port**: None exposed (not network-accessible)

### Why STDIO over HTTP/SSE?
1. **Simpler**: No network configuration, no port conflicts
2. **More Secure**: No exposed network endpoints
3. **Official Recommendation**: MCP spec prefers stdio for local servers
4. **Lower Latency**: Direct process communication
5. **IDE Standard**: All major IDEs support stdio natively

### Removed Implementations
- `mcp_server.py` → deprecated (archived)
- `unified_main.py` → deleted
- MCP code from `server/main.py` → removed

## Consequences

### Positive
- Single source of truth for MCP tools
- No port conflicts
- Consistent IDE configuration
- Easier to maintain and debug
- All 9 tool modules now register correctly

### Negative
- IDEs must use `docker exec` pattern (minor change)
- No remote MCP access (intentional - local-only design)

## IDE Configuration Standard

All IDEs now use:
```json
{
  "command": "docker",
  "args": ["exec", "-i", "archon", "python", "-m", "src.mcp_server.mcp_server_stdio"],
  "type": "stdio"
}
```

## Related Decisions

- ADR-004: Single-Container Architecture
- ADR-005: Code Intelligence with BGE-M3 Embeddings
