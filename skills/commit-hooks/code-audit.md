# Code Audit Skill

Runs light code audit on changed files after each commit.

## What It Does

After each commit, scans changed Python files for:
- TODO/FIXME comments
- Broad exception handling (`except:` or `except Exception:`)
- Hardcoded secrets patterns
- Ruff linting issues (if available)

## When It Triggers

- When Python source files in `python/src/` change
- Excludes test files from audit

## What It Reports

### Pass
- No issues found in changed files

### Warning
- TODO/FIXME comments found
- Ruff warnings detected
- Broad exception handling

### Critical
- Hardcoded secrets patterns detected
- `password =`, `secret =`, `api_key =`

### Skip
- No Python files changed

## How to Respond

### When Status is "Critical"

**Hardcoded secrets detected**:
1. Immediately remove the hardcoded value
2. Use environment variables instead
3. Consider rotating the exposed secret
4. Review if secret was committed to git history

### When Status is "Warning"

1. **TODO/FIXME found**:
   - Create a task to address the TODO
   - Or remove if no longer relevant

2. **Broad exception handling**:
   - Catch specific exceptions instead
   - Example: `except ValueError:` instead of `except:`

3. **Ruff warnings**:
   - Run `ruff check --fix` to auto-fix
   - Review and apply fixes

## Example Output

```json
{
  "status": "warning",
  "details": {
    "files_audited": 2,
    "ruff": "Not available or timed out"
  },
  "findings": {
    "critical": 0,
    "error": 0,
    "warning": 1,
    "info": 2
  }
}
```

## Best Practices

1. **Never commit secrets**: Use `.env` files or secret managers
2. **Handle specific exceptions**: Avoid bare `except:` clauses
3. **Address TODOs promptly**: Don't let them accumulate
4. **Run ruff locally**: `ruff check python/src/`

## Related Skills

- [Doc Maintenance Skill](doc-maintenance.md)
- [Test Coverage Skill](test-coverage.md)
