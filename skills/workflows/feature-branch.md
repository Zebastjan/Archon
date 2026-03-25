# Feature Branch Workflow

## Creating a New Feature

1. **Create worktree** for the feature:
   ```python
   await worktree_create("feature/my-feature", "main")
   ```

2. **Restart MCP** from new worktree path (following instructions)

3. **Start working** - MCP auto-detects branch

## Working on Feature

- All code search scoped to current branch
- Use `commit_with_review()` for structured commits
- Generate context bundle with `generate_context_bundle()`

## When Done

1. **Push changes** via normal git commands
2. **Create PR** from feature branch
3. **Switch back** to main:
   ```python
   await worktree_push()  # Save position
   await worktree_switch("main")
   ```

## Multiple Features

Work on multiple features simultaneously using worktrees:
- Each feature gets its own worktree
- MCP tools auto-scope to each branch
- No context pollution between features

## Tips

- Always `worktree_push()` before switching
- Use `worktree_pop()` to return to previous position
- Check `worktree_validate_safe_to_work()` before starting work
- Generate context bundle for documentation maintenance
