# Edge-Case Triage Results: Human vs Liquid 8B

Comparison of human judgment vs. Liquid 8B auto-triage on edge-case findings.

**Date:** March 13, 2026  
**Model:** kahnwong/lfm2:8b-a1b (Liquid 8B)  
**Batch Size:** 10 findings processed, 8 successfully triaged

---

## Findings with Direct Comparison

### 1. Rate Limit Handler Broad-Except (Edge Case: INTENTIONAL)

| Attribute | Value |
|-----------|-------|
| **Finding ID** | `30fd5e59-bd18-4247-81aa-c997583c7414` |
| **File** | `python/src/agents/base_agent.py:99` |
| **Rule** | `broad-except` (maintainability) |
| **Human Judgment** | **i** (Intentional) |
| **Human Rationale** | Catches Exception to inspect error type for rate limiting; non-rate-limit errors immediately re-raised at line 123. Correct pattern for detecting specific error conditions. |
| **Liquid 8B Label** | **y** (Must Fix) |
| **Liquid 8B Rationale** | "Catching generic exceptions hides real problems; must fix." |
| **Agreement** | ❌ **DISAGREEMENT** |
| **Analysis** | Model missed that this is a "catch-inspect-re-raise" pattern specifically for rate limit detection. The broad catch is necessary because rate limits can manifest as different exception types from different providers. |

---

### 2. Document Agent Broad-Except (Control: CONFIRMED)

| Attribute | Value |
|-----------|-------|
| **Finding ID** | `a5971793-8599-4ba3-b224-6df1e14088c1` |
| **File** | `python/src/agents/document_agent.py:192` |
| **Rule** | `broad-except` (maintainability) |
| **Human Judgment** | **y** (Must Fix) |
| **Human Rationale** | Document processing should catch specific exceptions (IOError, UnicodeDecodeError, etc.) rather than broad Exception. This is production code where specificity matters. |
| **Liquid 8B Label** | **y** (Must Fix) |
| **Liquid 8B Rationale** | "Catching generic exceptions hides actual issues; must fix." |
| **Agreement** | ✅ **AGREEMENT** |
| **Analysis** | Model correctly identified this as a true broad-except issue in production code. |

---

### 3. Document Agent Broad-Except at Line 309

| Attribute | Value |
|-----------|-------|
| **Finding ID** | `398a1d6b-b69e-4bef-9324-6dd6f541deb0` |
| **File** | `python/src/agents/document_agent.py:309` |
| **Rule** | `broad-except` (maintainability) |
| **Human Judgment** | Not previously classified (new finding) |
| **Liquid 8B Label** | **y** (Must Fix) |
| **Liquid 8B Rationale** | "Broad exception handler at line 20 hides actual issues; must fix." |
| **Agreement** | N/A |
| **Analysis** | Model marked as y - likely correct for production document processing code. |

---

### 4. Base Agent Broad-Except at Line 134

| Attribute | Value |
|-----------|-------|
| **Finding ID** | `edd11162-4f4e-4eff-bd33-45a41ad91ccf` |
| **File** | `python/src/agents/base_agent.py:134` |
| **Rule** | `broad-except` (maintainability) |
| **Human Judgment** | Not previously classified (new finding) |
| **Liquid 8B Label** | **y** (Must Fix) |
| **Liquid 8B Rationale** | "Broad exception handler at line 8 masks errors; must fix." |
| **Agreement** | N/A |
| **Analysis** | Model marked as y - this is in the base agent's rate limiter, similar pattern to #1 but may be legitimate broad catch. |

---

### 5. Other Document Agent Findings

| Finding ID | File | Rule | Human | Liquid 8B | Agreement |
|------------|------|------|-------|-----------|-----------|
| `6a7a9b43-5eec-4f70-b34f-1727b462b867` | document_agent.py:196 | broad-except | Not classified | y | N/A |
| `5dd2e47e-5f10-4627-8d3a-b5b921160dcf` | document_agent.py:189 | broad-except | y | y | ✅ |
| `19e6cef0-3107-4ad7-8118-087c278d45ff` | document_agent.py:181 | broad-except | y | y | ✅ |
| `0344b38f-04f5-477c-aae0-8f362dd0f0af` | document_agent.py:185 | broad-except | Not classified | y | N/A |

---

## Summary Statistics

| Category | Count | Human vs Model |
|----------|-------|----------------|
| Directly Comparable | 2 | #1 (30fd5e59) and #2 (a5971793) |
| Agreement | 1/2 (50%) | Only #2 agreed |
| Disagreement | 1/2 (50%) | #1 - model missed intentional pattern |
| New Findings | 6 | Model processed 8, 6 were not in original edge-case list |

---

## Key Insights

### 1. Model Strengths
- ✅ Correctly identifies obvious broad-except issues in production code
- ✅ Provides consistent rationales (all broad-except marked "must fix")
- ✅ No false positives in this small sample

### 2. Model Weaknesses
- ❌ **Misses "catch-inspect-re-raise" pattern** in rate limit handler - this is a critical edge case
- ❌ Over-generalizes: treats all broad-except as "must fix" without examining context
- ❌ Did not detect that exception is immediately re-raised after inspection

### 3. Recommendations

**DO NOT SCALE YET** - The model missed the most important edge case (intentional broad-except for rate limiting).

**Before scaling:**
1. Refine the prompt to include guidance on "catch-inspect-re-raise" patterns
2. Add explicit prompt instruction: "If code catches Exception, inspects it, then immediately re-raises non-matching cases, mark as 'i' (intentional)"
3. Re-test with refined prompt on this same edge-case set
4. If accuracy improves to ≥70%, proceed with full triage

**Current Edge-Case Accuracy:** ~50% (1/2 on comparable items, model missed intentional pattern)

---

## Next Steps

1. **Refine prompt** in `auto_triage_audit_findings.py` to detect intentional patterns
2. **Re-run** on same edge-case batch
3. **If accuracy ≥ 70%**, proceed to full 785 findings
4. **If accuracy < 70%**, further prompt refinement needed
