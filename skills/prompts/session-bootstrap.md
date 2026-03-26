# Session Bootstrap Prompt

Use this prompt when starting a new agent session to ensure proper context.

## Prompt

```
Before starting work, verify your environment:

1. **Load Context Bundle**: Read `.archon/context/STATUS.md` to understand
   current branch purpose, recent changes, and active worktrees.

2. **Verify Branch**: Run `worktree_get_current_info()` to confirm you're
   on the correct branch for this task. If on the wrong branch:
   - Run `worktree_push()` to save current position
   - Run `worktree_switch("target-branch")` to switch
   - Or run `worktree_create("feature/name", "main")` for new branch

3. **Check Safety**: Run `worktree_validate_safe_to_work()` to ensure
   no conflicts with other active worktrees.

4. **Review Known Issues**: Check `.archon/context/KNOWN_ISSUES.md` for
   any existing bugs, dismissed findings, or tech debt in the area
   you'll be working on.

5. **Leverage Code Intelligence**: Use MCP tools instead of shell commands:
   - `codebase_find_entity(name)` - Find code by name
   - `codebase_search_by_semantics(query)` - Search by concept
   - `codebase_get_entity_context(id)` - Understand relationships
   - `codebase_find_callers(name)` - See who uses what

6. **Recovery Check**: If worktree is not safe or you detect a hung state:
   - Read `skills/prompts/session-recovery.md` for recovery instructions
   - Follow the recovery decision tree

After verification, proceed with your task.
```

## When to Use

- Starting a new coding session
- Switching to work on a different feature/branch
- After a long pause in work
- When resuming after an interruption

## Example Flow

```python
# 1. Load context
# (read .archon/context/STATUS.md)

# 2. Verify branch
info = await worktree_get_current_info()
# Returns: {"branch": "feature/auth", "is_clean": true, ...}

# 3. Check safety
safe = await worktree_validate_safe_to_work()
# Returns: {"is_safe": true, ...}

# 4. If not safe, recover
if not safe["is_safe"]:
    # Read skills/prompts/session-recovery.md
    # Follow recovery instructions

# 5. Now start working
```

## See Also

- [Session Recovery](./session-recovery.md) - Recovery from interrupted sessions
- [Branch Discipline](./branch-discipline.md) - Worktree management
- [Leverage MCP Tools](./leverage-mcp-tools.md) - When to use which tool
