# Findings by Category - 'y' (Must Fix) Candidates

This document breaks down the 774 findings labeled 'y' by rule category to prioritize review efforts.

## Summary
- **Total 'y' findings**: 774 findings (98.6% of all findings)
- **Rules**: 4 distinct audit rules
- **Categories**: Security (366), Testing (388), Maintainability (20)

## Breakdown by Rule

### 1. Exception Not Logged (366 findings)
- **Rule ID**: `exception-not-logged`
- **Category**: Security
- **Count**: 366 findings (47.3% of 'y' findings)
- **Average Confidence**: 0.93
- **Description**: Exception handlers that don't log errors, creating security and observability risks

### 2. Mock Not Verified (340 findings)
- **Rule ID**: `assert-mock-not-verified`
- **Category**: Testing
- **Count**: 340 findings (43.9% of 'y' findings)
- **Average Confidence**: N/A
- **Description**: Mock objects created but never verified with assert_called

### 3. Missing Assertions in Test (48 findings)
- **Rule ID**: `assert-missing-in-test`
- **Category**: Testing
- **Count**: 48 findings (6.2% of 'y' findings)
- **Average Confidence**: N/A
- **Description**: Test functions without any assertions (may include false positives like pytest.raises)

### 4. Broad Exception Handler (20 findings)
- **Rule ID**: `broad-except`
- **Category**: Maintainability
- **Count**: 20 findings (2.6% of 'y' findings)
- **Average Confidence**: 0.93
- **Description**: Broad `except Exception` handlers that may hide specific errors

## Priority Order for Review

Based on ambiguity and risk assessment:

### High Priority (Low Ambiguity)
1. **Mock Not Verified** - Clear pattern, easy to validate
   - 340 findings
   - Check if mock is actually used and needs verification
   - Many may be intentional (test helpers, setup code)

2. **Missing Assertions in Test** - Some false positives expected
   - 48 findings
   - Need to distinguish real missing assertions from pytest.raises patterns
   - Based on edge case, we know pytest.raises is a false positive pattern

### Medium Priority (Context Dependent)
3. **Broad Exception Handler** - Requires judgment
   - 20 findings
   - Some may be intentional (like our confirmed edge cases)
   - Need to evaluate if specific exception types would be better

### Lower Priority (High Volume, Complex)
4. **Exception Not Logged** - Highest volume, requires careful judgment
   - 366 findings
   - Many may be intentional (configuration errors, external APIs)
   - Based on edge cases, environment variable parsing is often acceptable

## Recommended Batch Processing Order

1. **Batch 01**: Mock Not Verified (first 30 findings)
2. **Batch 02**: Mock Not Verified (next 30 findings)
3. **Batch 03**: Missing Assertions in Test (all 48 findings)
4. **Batch 04**: Broad Exception Handler (all 20 findings)
5. **Batch 05-15**: Exception Not Logged (in batches of 30-40)

This order starts with the clearest patterns to build momentum and establish review criteria before tackling the high-volume exception logging findings.
