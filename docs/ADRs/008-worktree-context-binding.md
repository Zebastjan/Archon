# ADR-008: Worktree-Per-Context Model with CLI Wrapper

## Status: **Implemented** (2026-03-24)

## Date: 2026-03-24

## Context

The MCP server runs inside the container but doesn't automatically bind to the current git worktree context. Agents entering a worktree need automatic context detection without manual configuration.

Requirements:
1. Agent enters a worktree → all tools automatically scoped to that branch/commit
2. Agent can switch worktrees via MCP tool
3. Creating new worktrees should be tool-assisted

## Decision

Implement a **CLI wrapper** (`archon-mcp`) that auto-detects worktree context and passes it to the MCP server.

### Architecture

```
IDE → archon-mcp (wrapper) → MCP Server (inside container)
         ↓
    Detects: git branch, commit, worktree path
         ↓
    Sets: ARCHON_BRANCH, ARCHON_COMMIT, ARCHON_WORKTREE_PATH
```

### Wrapper Script: `archon-mcp`

Location: `scripts/archon-mcp` (installed to PATH)

```bash
#!/bin/bash
# archon-mcp: Auto-detects worktree context and invokes MCP server

set -e

# Detect git context
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
COMMIT=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
WORKTREE_PATH=$(pwd)

# Export for MCP server
export ARCHON_BRANCH="$BRANCH"
export ARCHON_COMMIT="$COMMIT"
export ARCHON_WORKTREE_PATH="$WORKTREE_PATH"
export ARCHON_REPO_ROOT="$REPO_ROOT"

echo "[archon-mcp] Branch: $BRANCH, Commit: ${COMMIT:0:8}"

# Run MCP server with context
exec docker exec -i \
    -e ARCHON_BRANCH="$BRANCH" \
    -e ARCHON_COMMIT="$COMMIT" \
    -e ARCHON_WORKTREE_PATH="$WORKTREE_PATH" \
    archon \
    python -m src.mcp_server.mcp_server_stdio
```

### Worktree Switching Tool

Add MCP tool `worktree_switch`:

```python
@mcp.tool()
async def worktree_switch(target: str) -> dict:
    """
    Switch to a different worktree.
    
    Args:
        target: Branch name, worktree path, or "new/<branch-name>"
    
    Returns:
        Success status and new context info
    """
    # If "new/<branch-name>" - create worktree
    # Otherwise - validate worktree exists and switch
    # Update IDE to point to new MCP endpoint
```

### MCP Server Context Binding

In `mcp_server_stdio.py`:

```python
import os

# At startup - read worktree context
CURRENT_BRANCH = os.getenv("ARCHON_BRANCH", "main")
CURRENT_COMMIT = os.getenv("ARCHON_COMMIT", "")
WORKTREE_PATH = os.getenv("ARCHON_WORKTREE_PATH", "")

# Store in server context for all tools to access
SERVER_CONTEXT = {
    "branch": CURRENT_BRANCH,
    "commit": CURRENT_COMMIT,
    "worktree_path": WORKTREE_PATH,
}

# All search tools automatically filter by CURRENT_BRANCH
# (see ADR-007)
```

### IDE Configuration Update

Update all IDE setup docs to use `archon-mcp` instead of direct docker exec:

```json
{
  "mcpServers": {
    "archon": {
      "command": "archon-mcp",
      "args": []
    }
  }
}
```

## Consequences

### Positive
- Automatic worktree detection - zero configuration for agents
- Branch/commit context available to all MCP tools
- Works with existing single-container architecture
- Supports worktree switching via tool

### Negative
- Requires `archon-mcp` script installation on host
- Must update all IDE configurations
- Container receives env vars but still runs in container context

## Related Decisions

- ADR-007: Version-Scoped Search (uses this branch detection)
- ADR-014: Worktree and Branch Discipline

## Implementation Checklist

- [x] Create `scripts/archon-mcp` wrapper script
- [x] Update `mcp_server_stdio.py` to read env vars
- [x] Add `worktree_switch` MCP tool
- [x] Update IDE setup docs (CLAUDE.md, AGENTS.md, etc.)
- [ ] Test: switch branches, verify search scope changes
- [ ] Test: create new worktree via tool
