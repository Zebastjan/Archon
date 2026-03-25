# ADR-014: Worktree and Branch Discipline

## Status: **Implemented** (2026-03-24)

## Date: 2026-03-24

## Context

Zig-zag workflows (working on Feature A, pivot to Feature B, return to A) cause:
- Mixed uncommitted changes
- Confused agent context
- Polluted search results

We need structured workflow for worktree management.

## Decision

Enforce **worktree-per-context** model with structured switching.

### Core Rules

1. **One worktree = one active work item**
   - Each branch gets its own git worktree
   - MCP server in each worktree auto-binds to that branch (ADR-008)

2. **Never work directly on main/stable**
   - All work on feature branches
   - Feature branches created as worktrees

3. **Structured switching only**
   - Use MCP tools for all branch/worktree operations
   - No manual `git checkout` while MCP is running

### Context Stack

Track active worktrees in `.archon/context-stack.json`:

```json
{
  "stack": [
    {"branch": "main", "worktree_path": "/home/user/archon"},
    {"branch": "feature/search", "worktree_path": "/home/user/archon/.worktrees/feature-search"},
    {"branch": "fix/bug-123", "worktree_path": "/home/user/archon/.worktrees/fix-bug-123"}
  ],
  "current": 2,
  "pushed_at": "2026-03-24T10:30:00Z"
}
```

### MCP Tools for Context Management

```python
@mcp.tool()
async def worktree_push() -> dict:
    """
    Push current worktree context to stack.
    
    Use before switching to another worktree to preserve
    your current position.
    """
    
@mcp.tool()
async def worktree_pop() -> dict:
    """
    Pop previous worktree context from stack.
    
    Returns to previous worktree and reloads MCP context.
    """

@mcp.tool()
async def worktree_list() -> dict:
    """
    List all active worktrees.
    """
```

### Worktree Switching Flow

```
Agent on Branch A (worktree A)
        |
        v
worktree_push() - saves Branch A to stack
        |
        v
worktree_switch("branch-b")
        |
        v
[IDE reconnects MCP with new branch context]
        |
        v
Agent works on Branch B (worktree B)
        |
        v
worktree_pop() - returns to Branch A
        |
        v
[IDE reconnects MCP with Branch A context]
        |
        v
Agent continues on Branch A
```

### Creating New Worktrees

```python
@mcp.tool()
async def worktree_create(
    branch_name: str,
    base_branch: str = "main"
) -> dict:
    """
    Create new worktree for a branch.
    
    Args:
        branch_name: Name of branch to create
        base_branch: Branch to create from (default: main)
    
    Creates:
        - New git branch from base_branch
        - New worktree at .worktrees/<branch-name>
        - Auto-switches to new worktree
    """
```

### Agent Onboarding Flow

When agent starts:

```python
# 1. Detect current worktree context
context = await worktree_get_current_info()
# Returns: {branch, commit, worktree_path, is_clean}

# 2. Load context bundle
status = read_file(".archon/context/STATUS.md")

# 3. Validate safe to work
validation = await worktree_validate_safe_to_work()

# 4. If not safe (conflicts), resolve first
if not validation.is_safe:
    # Resolve conflicts before proceeding
```

### Anti-Patterns (Enforced)

| Anti-Pattern | Why Bad | Prevention |
|-------------|---------|------------|
| Manual git checkout while MCP running | Breaks context binding | Tools check git state |
| Multiple uncommitted changes across worktrees | Lost context | Validation warns |
| Search from wrong branch | Stale results | Auto-scoped to current |
| Commit without review | Broken builds | commit_with_review required |

### IDE Commands Reference

| Action | Command |
|--------|---------|
| Check current | `worktree_get_current_info()` |
| Create new branch | `worktree_create("feature/name")` |
| Switch branch | `worktree_switch("branch-name")` |
| Save position | `worktree_push()` |
| Return to previous | `worktree_pop()` |
| List all | `worktree_list_all()` |
| Safe to work? | `worktree_validate_safe_to_work()` |

## Consequences

### Positive
- Clean isolation between work contexts
- No mixed changes
- Search always scoped correctly
- Structured fallback path (stack)

### Negative
- Requires discipline
- More disk space (worktrees)
- Must reconnect MCP on switch

## Related Decisions

- ADR-007: Version-Scoped Search (benefits from discipline)
- ADR-008: Worktree-Per-Context Model (implementation)
- ADR-009: Commit-Automation Pipeline (commit_with_review)

## Implementation Checklist

- [x] Add worktree_push() tool
- [x] Add worktree_pop() tool
- [x] Add worktree_create() tool
- [x] Implement context-stack.json management
- [x] Update IDE setup docs with worktree commands
- [x] Add skill: workflows/zig-zag-workflow.md
- [ ] Test: push → switch → pop flow
- [ ] Test: create new worktree via tool
- [ ] Test: validation prevents conflicting work
