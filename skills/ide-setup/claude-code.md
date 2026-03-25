# Claude Code Setup for Archon

## MCP Configuration

Add to `~/.claude-code/mcp-config.json`:

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

## Installation

1. Ensure `scripts/archon-mcp` is in your PATH (or use full path)
2. The script auto-detects git worktree context

## Usage

1. Ensure you're in the correct worktree for your task
2. Start Claude Code - MCP auto-connects
3. Tools automatically scoped to current branch

## Troubleshooting

- **Wrong branch?** Run `worktree_get_current_info()`
- **Need to switch?** Run `worktree_switch("branch-name")` or `worktree_create("feature/name")`
- **See all worktrees?** Run `worktree_list()` or `worktree_list_all()`

## Key Commands

| Action | Command |
|--------|---------|
| Check current context | `worktree_get_current_info()` |
| Safe to work? | `worktree_validate_safe_to_work()` |
| List worktrees | `worktree_list_all()` |
| Create new branch | `worktree_create("feature/name")` |
| Switch branch | `worktree_switch("branch-name")` |
| Save position | `worktree_push()` |
| Return to previous | `worktree_pop()` |
| Generate context | `generate_context_bundle()` |
| Commit with review | `commit_with_review(message="...")` |

## Search

Code search tools automatically scope to current branch HEAD:
- `codebase_find_entity(name)` - Find at HEAD
- `codebase_search_by_semantics(query)` - Semantic search at HEAD
- `codebase_search_at_commit(commit_sha, query)` - Historical search
- `codebase_search_on_branch(branch_name, query)` - Search specific branch
