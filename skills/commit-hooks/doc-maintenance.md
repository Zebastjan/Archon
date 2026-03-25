# Documentation Maintenance Skill

Automatically checks for documentation drift when code changes.

## What It Does

After each commit, checks if documentation needs updates:
- Are there new functions without docstrings?
- Do ADRs need status updates?
- Is the context bundle stale?
- Have tool changes affected skill documentation?

## When It Triggers

- When Python source files in `python/src/` change
- When ADRs are added or modified
- When skill files are modified

## What It Reports

### Pass
- Documentation is up-to-date
- No action needed

### Warning
- Code changed but no docs updated
- ADRs in "Proposed" or "Draft" status
- Context bundle is older than 24 hours
- Tool changes may require skill updates

### Error
- Could not check documentation

## How to Respond

### When Status is "Warning"

1. **Code changed without doc update**:
   - Review if docstrings need updates
   - Check if README or API docs need changes
   - Update relevant documentation

2. **ADRs pending**:
   - Review pending ADRs
   - Update status to "Accepted" or "Implemented"
   - Mark checklists as complete

3. **Context bundle stale**:
   - Run `generate_context_bundle()` to refresh
   - Or commit a code change to trigger auto-generation

4. **Skill drift detected**:
   - Review affected skills in `skills/` directory
   - Update tool signatures if changed
   - Verify examples still work

## Example Output

```json
{
  "status": "warning",
  "details": {
    "changed_files": ["python/src/mcp_server/tools.py"],
    "code_files_changed": 1,
    "doc_files_changed": 0,
    "skill_drift": {
      "tool_files_changed": ["python/src/mcp_server/tools.py"],
      "affected_skills": ["skills/mcp/version-scoped-search.md"],
      "recommendations": ["Review skills/mcp/version-scoped-search.md for accuracy"]
    }
  },
  "issues": ["Code changed but no documentation updated"],
  "recommendations": ["Consider updating relevant documentation"]
}
```

## Related Skills

- [Test Coverage Skill](test-coverage.md)
- [Code Audit Skill](code-audit.md)
