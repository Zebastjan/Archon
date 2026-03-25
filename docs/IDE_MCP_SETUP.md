# IDE MCP Setup Guide

This guide covers how to connect various IDEs to the Archon MCP server using STDIO transport (per ADR-003).

## Prerequisites

- Docker container `archon` must be running
- The `scripts/archon-mcp` wrapper script must be executable and accessible

## Recommended: Worktree-Aware Wrapper

The `archon-mcp` wrapper automatically detects the current git branch and commit, enabling version-scoped search. This is the recommended approach.

```bash
# Make sure it's executable
chmod +x scripts/archon-mcp

# Test it
./scripts/archon-mcp --help
```

## Claude Code

### Method: CLI (Recommended with wrapper)

```bash
claude mcp add --transport stdio --scope user archon -- /path/to/archon/scripts/archon-mcp
```

### Method: CLI (Legacy - no worktree awareness)

```bash
claude mcp add --transport stdio --scope user archon -- docker exec -i archon python -m src.mcp_server.mcp_server_stdio
```

- `--scope user` makes it available in all projects
- Use `--scope project` for per-project (run from project directory)

### Verify

```bash
claude mcp list
```

Should show: `archon: ...archon-mcp - ✓ Connected`

### Troubleshooting

- Full restart of Claude Code required after adding
- If not showing, check with `/mcp` command inside Claude Code

## Windsurf

### Worktree-Aware (Recommended)

```json
{
  "mcpServers": {
    "archon": {
      "command": "/path/to/archon/scripts/archon-mcp",
      "args": [],
      "type": "stdio"
    }
  }
}
```

### Legacy

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

### Worktree-Aware (Recommended)

```json
{
  "mcpServers": {
    "archon": {
      "command": "/path/to/archon/scripts/archon-mcp",
      "args": [],
      "type": "stdio",
      "enabled": true
    }
  }
}
```

### Legacy

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

### Worktree-Aware (Recommended)

```json5
{
  mcpServers: {
    archon: {
      command: "/path/to/archon/scripts/archon-mcp",
      args: [],
      type: "stdio",
    },
  },
}
```

### Legacy

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

### Worktree-Aware (Recommended)

```jsonc
{
  "mcp": {
    "archon": {
      "type": "local",
      "command": ["/path/to/archon/scripts/archon-mcp"],
      "enabled": true
    }
  }
}
```

### Legacy

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
# Worktree-aware
./scripts/archon-mcp

# Legacy
docker exec -i archon python -m src.mcp_server.mcp_server_stdio
```

## Worktree Context

When using the wrapper, the MCP server automatically:

1. Detects current branch: `git rev-parse --abbrev-ref HEAD`
2. Detects current commit: `git rev-parse HEAD`
3. Passes these to the MCP server via environment variables
4. All code search tools automatically scope to the current branch

Use `worktree_get_current_info()` to see current context, and `worktree_switch("branch-name")` to get instructions for switching worktrees.

## Related

- [ADR-003: MCP Server Consolidation to STDIO Transport](../ADRs/003-mcp-server-consolidation.md)
- [ADR-008: Worktree-Per-Context Model](../ADRs/008-worktree-context-binding.md)
