# ADR-007: Version-Scoped Search as Default Behavior

## Status: **Implemented** (2026-03-24)

## Date: 2026-03-24

## Context

MCP semantic search currently returns results from **ALL commits and branches** in a repository. This pollutes results with stale content - deleted functions, old implementations, and code that no longer exists at HEAD. Agents receive misleading context without knowing it.

Example problem: if `foo()` was deleted in the current commit, searching for "how does foo work" returns the old implementation instead of nothing.

## Decision

MCP code search tools will **default to HEAD of the current worktree's branch**, with explicit opt-in for historical queries.

### Tools to Update

**1. Default Search (HEAD only)**
- `codebase_search_by_semantics(repo_id, query, ...)` - filter to current branch
- `codebase_find_entity(repo_id, name, ...)` - filter to current branch
- `codebase_list_entities_in_file(repo_id, file_path, ...)` - filter to current branch

**2. Historical Search (explicit opt-in)**
- `codebase_search_at_commit(repo_id, commit_sha, query)` - search at specific commit
- `codebase_search_on_branch(repo_id, branch_name, query)` - search on specific branch
- `codebase_history_for_symbol(repo_id, symbol_name)` - entity evolution (already exists)

### Schema Changes Required

```sql
-- Add tracking columns to archon_code_entities
ALTER TABLE archon_code_entities ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE;
ALTER TABLE archon_code_entities ADD COLUMN IF NOT EXISTS branch_name TEXT;
ALTER TABLE archon_code_entities ADD COLUMN IF NOT EXISTS commit_sha TEXT;

-- Index for efficient branch filtering
CREATE INDEX IF NOT EXISTS idx_code_entities_branch 
ON archon_code_entities(repo_id, branch_name, is_deleted);

-- Live view for current branch queries
CREATE OR REPLACE VIEW code_chunks_live AS
SELECT * FROM archon_code_entities 
WHERE is_deleted = false 
AND branch_name = current_setting('app.current_branch', true);
```

### Implementation Notes

1. On MCP server startup, detect current branch (see ADR-008)
2. Store in server context: `current_branch`, `current_commit_sha`
3. All search queries auto-apply filter: `branch_name = current_branch AND is_deleted = false`
4. Historical tools bypass this filter with explicit parameters

## Consequences

### Positive
- Agents get accurate, non-stale search results by default
- No confusion about whether code still exists
- Explicit time-travel when needed via separate tools

### Negative
- Historical queries require explicit tool invocation
- Must update all existing agent prompts that rely on full-history search

## Related Decisions

- ADR-008: Worktree-Per-Context Model (provides branch detection)
- ADR-014: Worktree and Branch Discipline

## Implementation Checklist

- [x] Add columns to archon_code_entities table
- [x] Update codebase_search_by_semantics to filter by branch
- [x] Update codebase_find_entity to filter by branch
- [x] Create codebase_search_at_commit tool
- [x] Create codebase_search_on_branch tool
- [x] Test: deleted function should not appear in default search
- [x] Test: historical tool returns old implementation
