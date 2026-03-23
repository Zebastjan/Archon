# ADR-006: Documentation Cleanup and Archive Strategy

## Status: Accepted

## Date: 2026-03-23

## Context

Archon had 70+ documentation files accumulated over its development history, including:
- Multiple phase implementation summaries (PHASE_1_*, PHASE_2_*)
- Stale status reports (IMPLEMENTATION_STATUS.md, PROJECT_STATUS_NOW.md)
- Old audit results and triage reports
- Migration notes no longer relevant
- Duplicate setup guides

This created several problems:
- Semantic search (RAG) returns stale/outdated results
- Confusion about current state vs historical decisions
- Difficulty finding relevant documentation
- Inconsistent information across files

## Decision

We will **delete stale documentation** from the working tree, keeping only current, accurate docs:

### Documentation to Keep
- `README.md` - Project overview and quick start
- `CLAUDE.md` - Agent instructions and conventions
- `CONTRIBUTING.md` - Contribution guidelines
- `docs/ADRs/` - Current Architecture Decision Records
- Core setup guides in `docs/` - after updating

### Documentation to Delete
All files that are:
- Implementation summaries (PHASE_*.md)
- Status reports (IMPLEMENTATION_*.md, PROJECT_STATUS_*.md)
- Old audit/triage results (*_AUDIT_*.md, *_TRIAGE_*.md)
- Completed milestone reports (MILESTONE_*.md, PHASE*_COMPLETE.md)
- Temporary investigation docs (*_INVESTIGATION.md, *_NOTES.md)

### Rationale
- Git commit history preserves all historical documentation
- Can retrieve any deleted file via `git show <commit>:<file>`
- Semantic search should only index current, accurate information
- Reduces confusion about project state

## Consequences

### Positive
- Cleaner documentation tree
- Semantic search returns only current info
- Clearer distinction between current state and history
- Easier to maintain documentation

### Negative
- Must use git to access historical docs
- Some context lost if someone doesn't know to check git history

## Related Decisions

- ADR-003: MCP Server Consolidation to STDIO Transport
- ADR-004: Single-Container Architecture
- ADR-005: Code Intelligence with BGE-M3 Embeddings
