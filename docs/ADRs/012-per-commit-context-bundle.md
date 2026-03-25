# ADR-012: Per-Commit Context Bundle

## Status: **Implemented** (2026-03-25)

## Date: 2026-03-24

## Context

Every new agent session starts with zero context about project state. This creates warm-up overhead and leads to agents working from stale assumptions.

## Decision

Generate `.archon/context/` directory **on-change** (not every commit).

### Directory Structure

```
.archon/
  context/
    STATUS.md          # What's happening now - branch purpose, recent changes
    QUICKSTART.md      # How to spin up project at this commit
    AGENTS.md          # MCP server config, available tools
    ARCHITECTURE.md    # Current architecture summary (from ADRs)
    CHANGES.md         # AI-enhanced changelog (what changed + why)
    KNOWN_ISSUES.md    # Open bugs, dismissed findings, tech debt
  hooks/
    last-run.json      # Output of commit hook pipeline
  context-stack.json   # Active worktrees (see ADR-014)
```

### Generation Trigger

Generate when files in these directories change:
- `docs/ADRs/` - architecture changes
- `python/src/` - code changes
- `docs/` - documentation changes
- `.git/hooks/` - hook changes

NOT generated on:
- Test file changes
- Build artifacts
- Only documentation changes (unless in docs/ADRs/)

### Generation Script

`scripts/generate_context_bundle.py`:

```python
def generate_context_bundle():
    """Generate context bundle files."""
    
    # STATUS.md
    status = {
        "branch": get_current_branch(),
        "purpose": get_branch_purpose(),  # From branch naming or PR
        "recent_commits": get_recent_commits(5),
        "active_worktrees": list_worktrees(),
    }
    render("status.md.j2", status)
    
    # CHANGES.md - AI-enhanced
    changes = get_uncommitted_changes()
    ai_summary = ollama.summarize(changes)  # "why" this change matters
    render("changes.md.j2", {**changes, "ai_summary": ai_summary})
    
    # ARCHITECTURE.md - from ADRs
    adrs = load_adrs()
    render("architecture.md.j2", {"adrs": adrs})
    
    # KNOWN_ISSUES.md
    issues = {
        "open_bugs": query_bugs(),
        "dismissed_findings": query_dismissed_audit_findings(),
        "tech_debt": query_tech_debt(),
    }
    render("known_issues.md.j2", issues)
```

### Content Templates

**STATUS.md:**
```markdown
# Archon Status

## Current Branch: feature/new-auth
**Purpose**: Add version-scoped search

## Recent Changes
- abc1234 - Add version-scoped search ADR
- def5678 - Implement worktree binding

## Active Worktrees
- main (stable)
- feature/new-auth (this branch)

## Quick Commands
- Run tests: make test
- Start MCP: archon-mcp
- Commit: use commit_with_review() tool
```

**CHANGES.md:**
```markdown
# Changes Since Last Release

## Uncommitted (this branch)

### Added
- `docs/ADRs/007-version-scoped-search.md` - Version-scoped search ADR

### Modified
- `python/src/mcp_server/features/code_entities/tools.py`

## AI Summary
This change adds version-scoped search as the default behavior
for MCP code search tools. The goal is to prevent agents from
receiving stale code context from deleted functions.
```

### Integration with Hook Pipeline

Post-commit hook runs async stages → writes `.archon/hooks/last-run.json` → triggers context bundle generation if needed.

### Usage

1. **New agent session**: Paste `STATUS.md` into context
2. **External query**: Attach `STATUS.md` + `CHANGES.md`
3. **Debugging**: Check `KNOWN_ISSUES.md`

## Consequences

### Positive
- Instant context for new agents
- Version-controlled (branch-specific)
- On-change generation reduces noise

### Negative
- Additional storage in repo
- Must maintain templates

## Related Decisions

- ADR-009: Commit-Automation Pipeline (hooks output)
- ADR-014: Worktree and Branch Discipline (context-stack)

## Implementation Checklist

- [x] Create `.archon/context/` directory structure
- [x] Create templates in `scripts/context_templates/`
- [x] Implement `scripts/generate_context_bundle.py`
- [x] Integrate with post-commit hook (on-change detection)
- [x] Update STATUS.md with current branch info
- [x] Test: generate on code change (test_context_bundle.py)
- [x] Test: don't generate on test-only change (test_context_bundle.py)
