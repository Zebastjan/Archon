# ADR-009: Commit Automation with Staged Review

## Status: **Implemented** (2026-03-24)

## Date: 2026-03-24

## Context

The existing post-commit hook triggers entity sync and embedding generation asynchronously. However:
1. Previous blocking hook attempts failed because agents couldn't respond to prompts
2. We need documentation maintenance, test coverage analysis, and code auditing
3. Agents need structured guidance through the commit process

## Decision

Implement **non-blocking post-commit hook** combined with a **MCP commit tool** that orchestrates staged review.

### Architecture

```
Agent (via MCP tool)
       ↓
commit_with_review() - interactive checklist
       ↓
[Agent reviews each item]
       ↓
git commit (blocking)
       ↓
Post-commit hook (async)
  - Entity sync
  - Embedding generation
  - Doc maintenance (async)
  - Test coverage (async)
  - Audit (async)
```

### MCP Tool: `commit_with_review`

```python
@mcp.tool()
async def commit_with_review(
    message: str,
    skip_checks: list[str] = None
) -> dict[str, Any]:
    """
    Perform staged commit with review checklist.
    
    Steps:
    1. Show changed files
    2. Check: docs updated?
    3. Check: tests pass?
    4. Check: audit clean?
    5. Confirm commit message
    6. Execute git commit
    
    Args:
        message: Commit message
        skip_checks: Optional list of checks to skip
    
    Returns:
        Commit result with checklist status
    """
```

### Checklist Items

1. **Changed Files Review**
   - List modified, added, deleted files
   - Agent confirms expected changes

2. **Documentation Check**
   - Run: `git diff --name-only | grep docs/`
   - If docs changed, prompt: "Did you update related docs?"

3. **Test Coverage Check**
   - Run test suite (fast subset)
   - Report: new tests added? existing tests pass?

4. **Audit Check**
   - Run lightweight audit on changed files
   - Report critical findings

5. **Commit Confirmation**
   - Show final commit message
   - Agent confirms or edits

### Post-Commit Hook (Async Pipeline)

Existing hook remains **non-blocking** (`&` background):

```bash
# .git/hooks/post-commit (existing - keep as-is for sync)
docker exec archon python /archon/scripts/index_commits.py ...

# New: async stages in scripts/commit_pipeline/
scripts/commit_pipeline/
  stage_1_doc_maintenance.py
  stage_2_test_coverage.py  
  stage_3_code_audit.py
```

Each stage:
- Runs asynchronously after commit
- Writes results to `.archon/hooks/last-run.json`
- Non-blocking - never fails commit

### Output: hooks-last-run.json

```json
{
  "commit_sha": "abc1234",
  "stages": {
    "doc_maintenance": {
      "status": "complete",
      "stale_docs": ["docs/OLD.md"],
      "missing_docs": []
    },
    "test_coverage": {
      "status": "complete",
      "new_functions_uncovered": ["foo()", "bar()"],
      "orphaned_tests": []
    },
    "code_audit": {
      "status": "complete",
      "findings": {"critical": 0, "warning": 2}
    }
  },
  "generated_at": "2026-03-24T10:30:00Z"
}
```

## Consequences

### Positive
- Agents get guided through commit process
- Non-blocking hook preserves workflow speed
- Async pipeline handles housekeeping
- Results visible in context bundle

### Negative
- Requires agent to use `commit_with_review` tool
- Async results not immediately visible (available next session)

## Related Decisions

- ADR-012: Per-Commit Context Bundle (includes hook output)
- ADR-014: Worktree and Branch Discipline

## Implementation Checklist

- [x] Create `commit_with_review` MCP tool in worktree module
- [x] Add checklist step functions (docs, tests, audit)
- [x] Create `scripts/commit_pipeline/` structure
- [x] Implement stage_1_doc_maintenance.py
- [x] Implement stage_2_test_coverage.py
- [x] Implement stage_3_code_audit.py
- [x] Update hooks-last-run.json generation
- [ ] Test: complete commit flow with checklist
- [ ] Test: verify async pipeline runs after commit
