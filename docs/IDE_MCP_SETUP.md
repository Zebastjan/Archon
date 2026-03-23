# IDE MCP Setup Guide

This guide covers how to connect various IDEs to the Archon MCP server using STDIO transport (per ADR-003).

## Prerequisites

- Docker container `archon` must be running
- MCP server module: `src.mcp_server.mcp_server_stdio`

## Claude Code

### Method: CLI (Recommended)

Use the `claude mcp add` command to add the MCP server:

```bash
claude mcp add --transport stdio --scope user archon -- docker exec -i archon python -m src.mcp_server.mcp_server_stdio
```

- `--scope user` makes it available in all projects
- Use `--scope project` for per-project (run from project directory)

### Verify

```bash
claude mcp list
```

Should show: `archon: docker exec -i archon python -m src.mcp_server.mcp_server_stdio - ✓ Connected`

### Troubleshooting

- Full restart of Claude Code required after adding
- If not showing, check with `/mcp` command inside Claude Code

## Windsurf

Project-level config in `.windsurf/mcp.json`:

```json
{
  "mcpServers": {
    "archon": {
      "command": "docker",
      "args": ["exec", "-i", "archon", "python", "-m", "src.mcp_server.mcp_server_stdio"],
      "type": "stdio"
    }
  }
}
```

## Cursor

Project-level config in `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "archon": {
      "command": "docker",
      "args": ["exec", "-i", "archon", "python", "-m", "src.mcp_server.mcp_server_stdio"],
      "type": "stdio",
      "enabled": true
    }
  }
}
```

## OctoFriend

Project-level config in `.octofriend/octofriend.json5`:

```json5
{
  mcpServers: {
    archon: {
      command: "docker",
      args: ["exec", "-i", "archon", "python", "-m", "src.mcp_server.mcp_server_stdio"],
      type: "stdio",
    },
  },
}
```

## OpenCode

Project-level config in `.opencode/opencode.jsonc`:

```jsonc
{
  "mcp": {
    "archon": {
      "type": "local",
      "command": ["docker", "exec", "-i", "archon", "bash", "-c", "cd /app/src/mcp_server && python mcp_server_stdio.py"],
      "enabled": true
    }
  }
}
```

## Common Issues

### Old Config Files

Multiple old config files may exist with deprecated SSE/HTTP configs:

- `~/.config/claude/mcp-config.json`
- `~/.config/claude/mcp_config.json`
- `~/.claude-code/mcp-config.json`
- `~/.octofriend/mcp.json`

These should be updated to use stdio or removed.

### Container Not Running

Verify the archon container is running:

```bash
docker ps --filter "name=archon"
```

### MCP Server Test

Test the MCP server manually:

```bash
docker exec archon python -m src.mcp_server.mcp_server_stdio
```

## Related

- [ADR-003: MCP Server Consolidation to STDIO Transport](../ADRs/003-mcp-server-consolidation.md)
