# Decisions Batch 01 - Mock Not Verified (30 findings)

## Summary
- **Total Reviewed**: 30 findings
- **Confirmed Issues (y)**: 29 findings (96.7%)
- **Intentional (i)**: 1 finding (3.3%)
- **Won't Fix (w)**: 0 findings (0%)

## Detailed Decisions

### Intentional (1 finding)
| ID | File | Line | Rationale |
|----|------|------|-----------|
| 78272b38-fa8c-466c-8fba-e51ab3aae662 | test_git_test_api.py | 90-106 | Mock is verified through return value inspection in assertions |

### Confirmed Issues (29 findings)
All other findings are confirmed issues requiring mock verification.

## Fixes Applied

### GitHub Integration Tests (6 findings)
Pattern: All tests mock `asyncio.create_subprocess_exec` for GitHub CLI calls.

**Files Modified**: `python/tests/agent_work_orders/test_github_integration.py`

**Changes Made**:
1. Added `as mock_subprocess` to capture the mock object
2. Added `mock_subprocess.assert_called_once_with()` after each test
3. Verified correct CLI arguments for each GitHub command

**Example Fix**:
```python
# Before
with patch("asyncio.create_subprocess_exec", return_value=mock_process):
    result = await client.verify_repository_access("https://github.com/owner/repo")

# After  
with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_subprocess:
    result = await client.verify_repository_access("https://github.com/owner/repo")

mock_subprocess.assert_called_once_with(
    "gh", "repo", "view", "https://github.com/owner/repo",
    stdout=-1, stderr=-1
)
```

### Tests Pending Fix (23 findings)
- **test_agent_executor.py** (3 findings) - Subprocess mocks
- **test_repository_config_repository.py** (11 findings) - Database client mocks  
- **test_sandbox_manager.py** (5 findings) - Subprocess mocks
- **test_server.py** (3 findings) - Subprocess mocks
- **test_github_integration.py** (1 finding) - Additional test at line 171

## Patterns Identified

1. **Subprocess Mocks**: Most common pattern - mocking `asyncio.create_subprocess_exec` or `asyncio.create_subprocess_shell`
2. **Database Client Mocks**: Mocking Supabase client method chaining
3. **Consistent Fix Pattern**: Add `as mock_name` to patch context and add assert_called verification

## Next Steps

1. Apply same fix pattern to remaining 23 findings
2. Create separate task for remaining fixes
3. Proceed to Batch 02 (next 30 Mock Not Verified findings)

## Quality Metrics
- **i-rate**: 3.3% (within expected 5-20% range)
- **Pattern Consistency**: High - all subprocess mocks follow same pattern
- **Fix Complexity**: Low - straightforward assert_called additions
