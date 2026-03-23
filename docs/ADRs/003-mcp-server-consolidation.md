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

### Claude Code Note

Claude Code requires using the `claude mcp add` CLI command rather than manual JSON editing:

```bash
claude mcp add --transport stdio --scope user archon -- docker exec -i archon python -m src.mcp_server.mcp_server_stdio
```

- `--scope user` makes it available in all projects
- Use `--scope project` for per-project configuration
- Full restart of Claude Code required after adding

### Lessons Learned (2026-03-23)

1. **CLI-first for Claude Code**: Manual JSON editing doesn't work reliably. Always use `claude mcp add`.

2. **Multiple config locations**: Old SSE/HTTP configs accumulated in many locations:
   - `~/.config/claude/mcp-config.json`
   - `~/.config/claude/mcp_config.json`
   - `~/.claude-code/mcp-config.json`
   - `~/.octofriend/mcp.json`
   - Project-level `.mcp.json` files
   - `~/.claude.json` (project entries)

3. **Scope matters**: Use `--scope user` for global availability, `--scope project` for per-project.

4. **Full restart required**: IDEs need complete restart to pick up new MCP configuration.

## Related Decisions

- ADR-004: Single-Container Architecture
- ADR-005: Code Intelligence with BGE-M3 Embeddings
