# Session Recovery Prompt

Use this prompt when starting a new agent session after a previous session was interrupted, hung, or left in a dirty state.

## Prompt

```
You are recovering from a previous session that was interrupted or left in an inconsistent state.

Before starting work, perform recovery checks:

1. **Detect Hung State**: Check if a previous process is still running:
   - Look for lock files or incomplete operations
   - Check if git operations were interrupted (rebase, merge, cherry-pick)
   - Verify no stale test processes are running

2. **Validate Worktree**: Run `worktree_validate_safe_to_work()` to check:
   - Is the worktree clean?
   - Are there uncommitted changes from a previous session?
   - Is another worktree working on the same files?

3. **Load Context Bundle**: Read `.archon/context/STATUS.md` to understand:
   - What was the previous session working on?
   - What changes were made?
   - What was the last commit?

4. **Recovery Actions**:
   - If uncommitted changes exist:
     - Read the changes with `git diff`
     - Determine if they should be committed, stashed, or discarded
     - Ask the user if unclear

   - If interrupted git operation:
     - Complete or abort the operation (rebase --continue, merge --abort, etc.)
     - Document what happened in commit message

   - If stale test processes:
     - Kill them if safe (pkill -f pytest, etc.)
     - Clean up any temporary files

5. **Resume or Restart**:
   - If context is clear: Resume the task from STATUS.md
   - If context is unclear: Ask the user what to do next
   - If worktree is unsafe: Escalate to user immediately

After recovery, proceed with your task using the recovered context.
```

## When to Use

- Starting a new session after a crash or hang
- Detecting dirty worktree at session start
- When `worktree_validate_safe_to_work()` returns unsafe
- After an interrupted test run or build

## Recovery Decision Tree

```
Start Session
    ↓
Read .archon/context/STATUS.md
    ↓
Run worktree_validate_safe_to_work()
    ↓
Is worktree safe?
├─ Yes → Resume from STATUS.md context
└─ No → Check what's wrong
    ├─ Uncommitted changes?
    │   ├─ Read git diff
    │   ├─ Ask user: commit/stash/discard?
    │   └─ Execute user's choice
    ├─ Interrupted git operation?
    │   ├─ Complete or abort operation
    │   └─ Document in commit message
    ├─ Stale processes?
    │   ├─ Kill safely
    │   └─ Clean temp files
    └─ Other issue?
        └─ Escalate to user
```

## Example Recovery Flow

```python
# 1. Load context (if exists)
# Read .archon/context/STATUS.md

# 2. Validate worktree
safe = await worktree_validate_safe_to_work()

# 3. If not safe, investigate
if not safe["is_safe"]:
    issues = safe.get("issues", [])
    
    if "uncommitted_changes" in issues:
        # Read git diff and decide
        diff = shell("git diff")
        # Ask user or auto-commit with descriptive message
        
    if "interrupted_operation" in issues:
        # Check git status for rebase/merge state
        status = shell("git status")
        # Complete or abort based on state

# 4. Resume work
# Continue from STATUS.md context
```

## Escalation Paths

| Situation | Action |
|-----------|--------|
| Simple uncommitted changes | Auto-commit with descriptive message |
| Complex changes | Ask user before proceeding |
| Interrupted rebase | Complete or abort, then document |
| Unknown state | Escalate to user immediately |
| Multiple worktrees active | Warn user about potential conflicts |

## See Also

- [Session Bootstrap](./session-bootstrap.md) - Normal session start
- [Branch Discipline](./branch-discipline.md) - Worktree management
- [ADR-015: Agent Recovery](../../docs/ADRs/015-agent-recovery-interruption.md) - Full design
