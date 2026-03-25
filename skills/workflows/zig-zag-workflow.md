# Zig-Zag Workflow

When working on Branch A and need to address Branch B:

## Steps

1. **Stash or commit** work on Branch A
2. **Check active worktrees**: `worktree_list()` or `worktree_list_all()`
3. **Switch worktree**:
   - If Branch B worktree exists: `worktree_switch("branch-b")`
   - If new: `worktree_create("branch-b", "main")`
4. **Work on Branch B** - MCP auto-binds to Branch B HEAD
5. **Return to Branch A**: `worktree_pop()` (if you used `worktree_push()`)
6. **Resume** - MCP re-checks HEAD

## Context Stack

Use context stack to track your path:
- `worktree_push()` - save current context before switching
- `worktree_pop()` - restore previous context

## Examples

### Starting from Branch A, need to check Branch B temporarily

```python
# You're on feature/auth working on authentication
# Someone reports a bug on feature/search

# 1. Save your position
await worktree_push()
# Result: {"success": true, "stack_size": 1, "pushed": {"branch": "feature/auth", ...}}

# 2. Switch to Branch B
await worktree_switch("feature/search")
# Result: {"success": true, "action_required": "restart_mcp", ...}

# 3. (After MCP restart) Do quick review on Branch B

# 4. Return to Branch A
await worktree_pop()
# Result: {"success": true, "popped": {"branch": "feature/search", ...}}

# 5. Resume work on feature/auth
```

### Creating new worktree for new branch

```python
# Start new feature from current branch
await worktree_create("feature/new-feature", "main")
# Result: {"success": true, "worktree_path": "/path/.worktrees/feature-new-feature", ...}

# Now restart MCP and start working
```

## Anti-Patterns

- **DON'T**: Modify code in two branches simultaneously
- **DON'T**: Commit without using `commit_with_review()`
- **DON'T**: Search without understanding current branch context
- **DON'T**: Use manual `git checkout` while MCP is running (breaks context binding)

## IDE Commands Reference

| Action | Command |
|--------|---------|
| Check current | `worktree_get_current_info()` |
| Create new branch | `worktree_create("feature/name")` |
| Switch branch | `worktree_switch("branch-name")` |
| Save position | `worktree_push()` |
| Return to previous | `worktree_pop()` |
| List all | `worktree_list_all()` |
| Safe to work? | `worktree_validate_safe_to_work()` |