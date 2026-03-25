# ADR-013: Skills & Prompts as First-Class Documentation

## Status: Proposed

## Date: 2026-03-24

## Context

Skills, workflows, and prompts for AI agents are scattered. When tool APIs change, skills become stale. No enforcement that skills track code changes.

## Decision

Create `skills/` directory version-controlled with code.

### Directory Structure

```
skills/
  commit-hooks/
    doc-maintenance.md      # Stage 1: Doc drift detection
    test-coverage.md        # Stage 2: Coverage gap analysis  
    code-audit-light.md     # Stage 3: Light audit patterns
  mcp/
    search-usage-guide.md   # How to use code search tools
    version-scoped-search.md # NEW: branch/commit filtering
    time-travel-guide.md    # NEW: querying historical code
  workflows/
    feature-branch.md       # Branch naming, worktree creation
    zig-zag-workflow.md     # Context switching pattern
    pr-prep.md             # Pre-PR checklist
  ide-setup/
    claude-code.md
    windsurf.md
    opencode.md
    octofriend.md
  prompts/
    session-bootstrap.md    # Prompt to bootstrap agent
    branch-discipline.md    # Remind agent of branch rules
    audit-meta-review.md    # Prompt for meta-audit step
```

### Skill Templates

**skills/mcp/version-scoped-search.md:**
```markdown
# Version-Scoped Search Guide

## Default Behavior
All code search tools automatically scope to HEAD of current branch.
Deleted functions will NOT appear in results.

## Tools

### Default Search (HEAD only)
- `codebase_search_by_semantics(repo_id, query)` 
- `codebase_find_entity(repo_id, name)`
- `codebase_list_entities_in_file(repo_id, file_path)`

### Historical Search (explicit)
- `codebase_search_at_commit(repo_id, commit_sha, query)` 
- `codebase_search_on_branch(repo_id, branch_name, query)`
- `codebase_entity_evolution(repo_id, entity_name)`

## Examples

### Find current implementation
```python
# Returns only code at HEAD
result = await codebase_find_entity(
    repo_id="...",
    name="my_function"
)
```

### Find historical implementation
```python
# Returns code at specific commit
result = await codebase_search_at_commit(
    repo_id="...",
    commit_sha="abc1234",
    query="my_function"
)
```
```

**skills/workflows/zig-zag-workflow.md:**
```markdown
# Zig-Zag Workflow

When working on Branch A and need to address Branch B:

## Steps

1. **Stash or commit** work on Branch A
2. **Check active worktrees**: `worktree_list_all()`
3. **Switch worktree**:
   - If Branch B worktree exists: `worktree_switch("branch-b")`
   - If new: `worktree_switch("new/branch-b")`
4. **Work on Branch B** - MCP auto-binds to Branch B HEAD
5. **Return to Branch A**: `worktree_switch("branch-a")`
6. **Resume** - MCP re-checks HEAD

## Context Stack

Use context stack to track your path:
- `worktree_push()` - save current context
- `worktree_pop()` - restore previous context

## Anti-Patterns

- DON'T: Modify code in two branches simultaneously
- DON'T: Commit without using `commit_with_review()`
- DON'T: Search without understanding current branch context
```

### Enforcement

**Commit Hook Stage 1 Enhancement:**
```python
# In scripts/commit_hooks/stage_1_doc_maintenance.py

def check_skill_drift():
    """Check if tool changes require skill updates."""
    
    changed_files = get_changed_files()
    
    # Check if MCP tools changed
    tool_files = [f for f in changed_files if f.startswith("python/src/mcp_server/")]
    if tool_files:
        # Find related skills
        affected_skills = map_tools_to_skills(tool_files)
        if affected_skills:
            # Flag for update
            return {
                "action_required": "Update skills",
                "files": affected_skills,
                "reason": "Tool signatures changed"
            }
```

### IDE Integration

Each IDE setup skill includes exact MCP config:

**skills/ide-setup/opencode.md:**
```markdown
# OpenCode Setup

## MCP Configuration

Add to `~/.config/opencode/mcp-config.json`:

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

## Usage

1. Ensure you're in correct worktree
2. Start OpenCode - MCP auto-connects
3. Tools automatically scoped to current branch

## Troubleshooting

- Wrong branch? Run `worktree_get_current_info()`
- Need to switch? Run `worktree_switch("branch-name")`
```

## Consequences

### Positive
- Canonical documentation for agent workflows
- Skills versioned with code
- IDE-specific setup in one place

### Negative
- Maintenance burden
- Must remember to update skills with tool changes

## Related Decisions

- ADR-007: Version-Scoped Search (has skill guide)
- ADR-008: Worktree-Per-Context (has workflow skill)
- ADR-009: Commit-Automation Pipeline (has hook skills)

## Implementation Checklist

- [x] Create `skills/` directory structure
- [x] Write commit-hook skills (doc, test, audit)
- [x] Write MCP usage guides (version-scoped-search)
- [x] Write workflow guides (zig-zag, feature-branch)
- [x] Write IDE setup guides (opencode, claude-code)
- [x] Write prompt templates (session-bootstrap, branch-discipline, leverage-mcp-tools)
- [x] Add skill drift detection to commit hook
- [x] Test: update tool → skill flagged for update (test_worktree_integration.py)
