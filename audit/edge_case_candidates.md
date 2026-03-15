# Edge-Case Candidates for Audit Triage Validation

This document contains candidate edge-case findings for validating the Liquid 8B triage workflow.

**Date:** March 13, 2026  
**Total Findings:** 785 pending review  
**Categories:** security (376), testing (389), maintainability (20)

---

## Category: INTENTIONAL (i) - Valid by Design

These findings represent patterns that are deliberately used and should not be "fixed."

### 1. Rate Limit Handler Broad-Except

| Field | Value |
|-------|-------|
| **work_item_id** | `30fd5e59-bd18-4247-81aa-c997583c7414` |
| **file** | `python/src/agents/base_agent.py:99` |
| **rule** | `broad-except` (maintainability, error) |
| **code** | `except Exception as e:` inside `execute_with_rate_limit()` |
| **proposed_label** | `i` - Intentional |
| **rationale** | Catches Exception to inspect error type for rate limiting; non-rate-limit errors are immediately re-raised at line 123. This is the correct pattern for detecting specific error conditions. |

### 2. Mock Verification Through Return Values (test_agent_executor)

| Field | Value |
|-------|-------|
| **work_item_id** | `247bf13e-e8c9-482f-9398-f665c4c98459` |
| **file** | `python/tests/agent_work_orders/test_agent_executor.py:116` |
| **rule** | `assert-mock-not-verified` (testing, warning) |
| **code** | `mock_process = MagicMock()` used with `mock_process.communicate = AsyncMock(...)` |
| **proposed_label** | `i` - Intentional |
| **rationale** | Mock is verified through its configured return value (communicate) and returncode assertions, not through assert_called. This is a valid pytest pattern for async subprocess testing. |

### 3. Mock Verification Through Return Values (test_github_integration)

| Field | Value |
|-------|-------|
| **work_item_id** | `c6b8d27a-754d-4e37-a9bd-6238a97d479e` |
| **file** | `python/tests/agent_work_orders/test_github_integration.py:17` |
| **rule** | `assert-mock-not-verified` (testing, warning) |
| **code** | `mock_process = MagicMock()` used in async test with communicate configured |
| **proposed_label** | `i` - Intentional |
| **rationale** | Same pattern as #2 - mock subprocess behavior is verified through return value assertions and returncode checks, not assert_called. Standard pytest-mock pattern. |

---

## Category: WON'T FIX (w) - Accepted Tech Debt

These findings represent issues that are valid but not worth fixing due to effort/benefit ratio.

### 4. Script Utility Exception Handling

| Field | Value |
|-------|-------|
| **work_item_id** | `cbd2f232-2799-40dc-b818-13451e2f1c08` |
| **file** | `python/scripts/index_repos_simple.py:189` |
| **rule** | `exception-not-logged` (security, warning) |
| **code** | `except Exception as e: errors.append({"file": file_path, "error": str(e)})` |
| **proposed_label** | `w` - Won't Fix |
| **rationale** | This is a one-off indexing script. Errors are collected in a list and reported at the end (line 235). Adding logging would add complexity with minimal benefit for a development utility. |

### 5. Entity Insert Error Handling

| Field | Value |
|-------|-------|
| **work_item_id** | `2564cbec-eb17-4ed1-b103-af0af2ef9b56` |
| **file** | `python/scripts/index_repos_simple.py:216` |
| **rule** | `exception-not-logged` (security, warning) |
| **code** | `except Exception as e: errors.append({"file": file_path, "error": f"Entity insert: {e}"})` |
| **proposed_label** | `w` - Won't Fix |
| **rationale** | Same script as #4. Database insertion errors are collected and reported in batch. This is acceptable for a development/indexing utility. |

---

## Category: FALSE POSITIVE (n) - Pattern Doesn't Apply

These findings are cases where the rule incorrectly matched the code pattern.

### 6. Test with Assertions (False Positive)

| Field | Value |
|-------|-------|
| **work_item_id** | `32c82dfe-7423-45af-b290-8fda7ccbff29` |
| **file** | `python/tests/chunking/test_chunker_api.py:33` |
| **rule** | `assert-missing-in-test` (testing, warning) |
| **code** | `def test_invalid_strategy_raises_error():` with `with pytest.raises(ChunkingStrategyError)` |
| **proposed_label** | `n` - False Positive |
| **rationale** | This test DOES have an assertion - `pytest.raises()` is an assertion context manager. The rule likely only detects assertXxx() calls and misses pytest.raises() patterns. |

### 7. Abstract Interface Test (False Positive)

| Field | Value |
|-------|-------|
| **work_item_id** | `3e36448b-711c-4a7a-8b6f-4cb59f451594` |
| **file** | `python/tests/chunking/test_chunker_api.py:75` |
| **rule** | `assert-missing-in-test` (testing, warning) |
| **code** | `def test_chunk_is_abstract():` with `with pytest.raises(TypeError)` |
| **proposed_label** | `n` - False Positive |
| **rationale** | Same as #6 - test uses `pytest.raises(TypeError)` which IS an assertion. The rule needs to be updated to detect pytest.raises() patterns. |

---

## Category: CONFIRMED (y) - Must Fix (Control Group)

These are clear issues that should be fixed, serving as a control group for the model.

### 8. Unlogged Exception in Core Agent Logic

| Field | Value |
|-------|-------|
| **work_item_id** | `07a7e0f3-5a67-4f4e-8000-a648d8022613` |
| **file** | `python/src/agents/base_agent.py:134` |
| **rule** | `exception-not-logged` (security, warning) |
| **code** | Line 134 mentioned but exception handling at line 222: `except Exception as e: self.logger.error(...)` then `raise` |
| **proposed_label** | `y` - Confirmed Issue |
| **rationale** | Actually wait - this IS logged at line 223. Need to re-verify. The finding at line 134 might be a different issue. |

### 9. Document Agent Broad-Except (Confirmed)

| Field | Value |
|-------|-------|
| **work_item_id** | `a5971793-8599-4ba3-b224-6df1e14088c1` |
| **file** | `python/src/agents/document_agent.py:192` |
| **rule** | `broad-except` (maintainability, error) |
| **code** | Exception handling in document processing |
| **proposed_label** | `y` - Confirmed Issue |
| **rationale** | Document processing should catch specific exceptions (IOError, UnicodeDecodeError, etc.) rather than broad Exception. This is production code where specificity matters. |

---

## Summary Table

| # | Label | Category | Finding | Confidence |
|---|-------|----------|---------|------------|
| 1 | i | maintainability/broad-except | Rate limit handler | High |
| 2 | i | testing/assert-mock-not-verified | Async mock pattern | High |
| 3 | i | testing/assert-mock-not-verified | Async mock pattern | High |
| 4 | w | security/exception-not-logged | Script utility | Medium |
| 5 | w | security/exception-not-logged | Script utility | Medium |
| 6 | n | testing/assert-missing-in-test | pytest.raises pattern | High |
| 7 | n | testing/assert-missing-in-test | pytest.raises pattern | High |
| 8 | y | security/exception-not-logged | Core logic verification | Medium |
| 9 | y | maintainability/broad-except | Document agent | High |

**Next Steps:**
1. Review these candidates
2. After approval, run Liquid 8B auto-triage on these same findings
3. Compare model decisions vs. human judgments
4. Proceed to full triage if accuracy ≥ 70%
