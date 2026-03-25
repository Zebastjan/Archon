# Test Coverage Skill

Analyzes test coverage gaps when source code changes.

## What It Does

After each commit, checks test coverage:
- Are there new functions without tests?
- Do existing tests pass?
- Are there test files that don't match source files?

## When It Triggers

- When Python source files in `python/src/` change
- When test files in `python/tests/` change

## What It Reports

### Pass
- Tests pass and coverage is adequate
- No new untested functions

### Warning
- Source code changed but no test files updated
- New functions may not have test coverage
- Pytest collection had issues

### Error
- Pytest failed to run
- Test files have syntax errors

### Skip
- No Python files changed

## How to Respond

### When Status is "Warning"

1. **Source changed without test update**:
   - Review what functions were added/modified
   - Add or update tests to cover new code
   - Run tests locally: `pytest python/tests/ -v`

2. **Coverage gaps detected**:
   - Check which modules lack tests
   - Create test files for untested modules
   - Focus on critical paths first

## Example Output

```json
{
  "status": "warning",
  "details": {
    "source_files_changed": 2,
    "test_files_changed": 0,
    "modules_with_changes": ["auth", "user"],
    "pytest_collection": "57 items collected"
  },
  "issues": ["Source code changed but no test files updated"],
  "recommendations": ["Consider adding tests for new/changed functionality"]
}
```

## Best Practices

1. **Write tests for new functions**: Every public function should have at least one test
2. **Update tests when changing behavior**: Existing tests may need updates
3. **Test edge cases**: Don't just test the happy path
4. **Use real tests, not stubs**: Tests should verify actual behavior

## Related Skills

- [Doc Maintenance Skill](doc-maintenance.md)
- [Code Audit Skill](code-audit.md)
