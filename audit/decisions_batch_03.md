# Decisions Batch 03 - Mock Not Verified (30 findings)

## Summary
- **Total Reviewed**: 30 findings
- **Confirmed Issues (y)**: 7 findings (23.3%)
- **Intentional (i)**: 23 findings (76.7%)
- **Won't Fix (w)**: 0 findings (0%)

## Detailed Decisions

### Intentional (23 findings)
All MCP service mocks that are verified through return value inspection by checking mock attributes like `mock_mcp._tools` or `mock_supabase_client.data`.

### Confirmed Issues (7 findings)
| ID | File | Line | Rationale |
|----|------|------|-----------|
| 4700802b-3641-48aa-ad4f-39c8b98cc417 | test_code_entity_tools.py | 502 | Service mock needs assert_called verification |
| b4246eb9-6b8b-4ae4-b2ab-b026a42f813c | test_code_entity_tools.py | 571 | Service mock needs assert_called verification |
| 2e0e48e2-13d0-4356-8e73-b4fa2644938d | test_code_entity_tools.py | 649 | Service mock needs assert_called verification |
| 3ae83d1d-02d5-4bf2-91fa-8c4b1b9a7f50 | test_code_entity_tools.py | 719 | Service mock needs assert_called verification |
| 827df877-8876-47a4-b48e-57e1fac1ba02 | test_code_entity_tools.py | 816 | Service mock needs assert_called verification |
| 22a97593-f9ca-4702-8f67-889aba396408 | test_code_entity_tools.py | 865 | Service mock needs assert_called verification |
| fc56b947-87a2-4fa1-84cb-3f4a1dfabd4b | test_async_source_summary.py | 265 | Service mock needs assert_called verification |

## Patterns Identified

1. **MCP Service Mocks**: 23 findings are intentional - they verify mocks by checking internal state (`mock._tools`) rather than assert_called
2. **Code Entity Tools**: 6 confirmed issues in test_code_entity_tools.py need proper mock verification
3. **High i-rate Expected**: This batch aligns with the updated mental model - service/DB mocks expect 20-30% i-rate

## Tests Pending Fix (7 findings)
- **test_code_entity_tools.py** (6 findings) - Service mocks
- **test_async_source_summary.py** (1 finding) - Service mock

## Quality Metrics
- **i-rate**: 76.7% (high but expected for MCP service mocks verified through return values)
- **Pattern Consistency**: Very high - all MCP mocks follow same verification pattern
- **Fix Complexity**: Low - straightforward assert_called additions

## Next Steps
1. Apply fixes to 7 confirmed issues
2. Proceed to Batch 04 (next 30 Mock Not Verified findings)
