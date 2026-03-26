# ADR-015: Agent Recovery and Interruption Handling

## Status: **Proposed** (2026-03-26)

## Date: 2026-03-26

## Context

Agents (particularly OctoFriend) can become stuck or hung during execution:

1. **Test execution is blocking and unguarded**: OctoFriend writes tests, calls them directly without a timeout wrapper, the suite hangs or errors in a way that doesn't return control, and the agent has no escape hatch.

2. **No agent recovery skill**: There are prompts for `session-bootstrap`, `branch-discipline`, and `leverage-mcp-tools` — but nothing for *"I am stuck / session is hung / how do I recover a dirty state"*.

3. **Previous blocking hook attempts failed**: ADR-009 noted that *"previous blocking hook attempts failed because agents couldn't respond to prompts"* and the fix was making everything async and non-blocking. The same principle hasn't been extended to general test execution.

4. **Manual recovery is the norm**: Currently, users hit Escape and manually tell the agent what went wrong. This is inefficient and error-prone.

## Decision

Implement **non-blocking command execution with recovery prompts**:

### Architecture

```
Agent (via MCP tool)
       ↓
run_with_timeout(command, timeout, output_file)
       ↓
[Command executes with timeout]
       ↓
Results written to .archon/hooks/run-results.json
       ↓
Agent reads results and proceeds
       ↓
If failure: Read session-recovery.md for guidance
```

### Components

1. **Generic Command Runner**: `run_with_timeout()` MCP tool
   - Wraps any command with configurable timeout
   - Writes pass/fail + output to `.archon/hooks/run-results.json`
   - Always returns control to caller regardless of outcome
   - Prevents agent from ever being "trapped" by a hanging process

2. **Session Recovery Prompt**: `skills/prompts/session-recovery.md`
   - Agent-facing prompt template for detecting and recovering from hung states
   - Instructions for using `worktree_validate_safe_to_work()` at session start
   - Escalation path when previous session left dirty state

3. **OctoFriend IDE Setup**: `skills/ide-setup/octofriend.md`
   - System prompt directives that mandate context bundle reading
   - Tool usage instructions for semantic search before file reading
   - Integration of recovery prompt into session start

4. **Context Bundle Integration**: Ensure `.archon/context/STATUS.md` is read first
   - Agent should read STATUS.md before doing anything else
   - Provides immediate context without manual git commands

### MCP Tool: `run_with_timeout`

```python
@mcp.tool()
async def run_with_timeout(
    command: str,
    timeout: int = 300,
    output_file: str = ".archon/hooks/run-results.json"
) -> dict[str, Any]:
    """
    Run a command with timeout protection.

    Wraps any command with a configurable timeout and writes results
    to a JSON file. Always returns control to the caller, preventing
    agent from being trapped by hanging processes.

    Args:
        command: Shell command to execute
        timeout: Timeout in seconds (default: 300)
        output_file: Path to write results JSON

    Returns:
        Dict with command result:
        - success: Whether command completed
        - exit_code: Process exit code
        - stdout: Command output
        - stderr: Error output
        - timeout: Whether command timed out
    """
```

### Session Detection at Startup

Agents should run this sequence at session start:

```python
# 1. Read context bundle (if exists)
# .archon/context/STATUS.md

# 2. Validate worktree state
safe = await worktree_validate_safe_to_work()

# 3. If not safe, read recovery prompt
if not safe["is_safe"]:
    # Read skills/prompts/session-recovery.md
    # Follow recovery instructions
```

## Consequences

### Positive

1. **Non-blocking execution**: Agents never trapped by hanging processes
2. **Recovery guidance**: Clear instructions for handling hung/dirty states
3. **Consistent session start**: Context bundle read first, always
4. **Extensible**: Generic wrapper works for any command (pytest, jest, nim tests, etc.)

### Negative

1. **Additional tool complexity**: Another MCP tool to maintain
2. **Agent must be trained**: System prompt must mandate using these tools
3. **Requires OctoFriend integration**: System prompt modification needed

### Risks

1. **Timeout too short**: Commands that legitimately take longer may timeout
   - Mitigation: Make timeout configurable, default to 300s
2. **Agent ignores recovery prompt**: If not mandated in system prompt
   - Mitigation: Include in OctoFriend system prompt directly
3. **Context bundle not generated**: If post-commit hook fails
   - Mitigation: Generate bundle on-demand if missing

## Implementation Plan

1. Create `run_with_timeout()` MCP tool
2. Create `skills/prompts/session-recovery.md`
3. Create `skills/ide-setup/octofriend.md` with system prompt directives
4. Update `skills/prompts/session-bootstrap.md` with recovery references
5. Test with OctoFriend

## References

- ADR-009: Commit Automation Pipeline (non-blocking pattern)
- ADR-012: Per-Commit Context Bundle (context generation)
- ADR-014: Worktree and Branch Discipline (worktree validation)
