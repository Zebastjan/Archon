# Archon Integration Instructions

You have access to Archon MCP tools for code intelligence. Use them to work more efficiently.

## Session Start Protocol

Before starting any task, follow this sequence:

1. **Read Context Bundle**: Read `.archon/context/STATUS.md` to understand:
   - Current branch purpose and recent changes
   - Active worktrees and their tasks
   - Known issues in the area you're working on

2. **Validate Worktree**: Run `worktree_validate_safe_to_work()` to ensure:
   - No conflicts with other active worktrees
   - No uncommitted changes from previous sessions
   - Safe to proceed with your task

3. **If Unsafe**: Read `skills/prompts/session-recovery.md` for recovery instructions

## Code Exploration Protocol

When looking for code, use MCP tools BEFORE reading raw files:

1. **Find by Name**: Use `codebase_find_entity(name)` when you know approximately what something is called

2. **Find by Concept**: Use `codebase_search_by_semantics(query)` when you know what you want but not the exact name

3. **Understand Context**: Use `codebase_get_entity_context(id)` after finding an entity to see its relationships

4. **Find Callers**: Use `codebase_find_callers(name)` to see what depends on a function

## Test Execution Protocol

When running tests or any potentially long-running command:

1. **Use Timeout Wrapper**: Use `run_with_timeout(command, timeout)` instead of running commands directly
2. **Check Results**: Read results from `.archon/hooks/run-results.json`
3. **If Timeout**: The command took too long - consider running a smaller subset

## Recovery Protocol

If you get stuck or hung:

1. Check `.archon/hooks/run-results.json` for the last command output
2. Read `skills/prompts/session-recovery.md` for recovery instructions
3. Use `worktree_validate_safe_to_work()` to check worktree state
4. If dirty state detected, ask the user what to do

## Key MCP Tools

| Tool | Purpose | When to Use |
|------|---------|-------------|
| `codebase_find_entity(name)` | Find code by name | You know what something is called |
| `codebase_search_by_semantics(query)` | Find code by concept | You know what you want, not the name |
| `codebase_get_entity_context(id)` | Understand relationships | After finding an entity |
| `codebase_find_callers(name)` | Find what calls something | Understanding dependencies |
| `worktree_validate_safe_to_work()` | Check worktree state | Session start |
| `run_with_timeout(cmd, timeout)` | Run command safely | Any potentially long command |
