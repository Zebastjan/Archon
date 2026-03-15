# Next-Wave Audit Rules: Design Document

## Executive Summary

Based on dogfooding orchestrated_repo_health_check on the OctoFriend repository, this document proposes the next generation of audit rules focused on assertion quality, exception handling, and concurrency safety.

## Phase 3 Dogfooding Results

### Repository: OctoFriend

**Health Score:** 75/100 (Good)  
**Total Files:** 43  
**Total Functions:** 176  
**Classes:** 7  

**Current Findings:**
- 🔴 Critical: 0
- 🟠 Error: 7 (all complexity-related)
- 🟡 Warning: 17 (complexity)
- 🔵 Info: 0

**Top Issues Discovered:**
1. **prompts/system-prompt.ts** - Complexity 51 (critical)
2. **compilers/standard.ts** - Complexity 39 (critical)
3. **compilers/anthropic.ts** - Complexity 31 (critical)
4. **xml.ts** - Complexity 35 (critical)
5. **state.ts** - Complexity 23 (critical)

**Key Observations:**
- All findings are complexity-related (no security or test coverage issues detected)
- Repository uses TypeScript with heavy compiler/prompt logic
- High complexity in LLM interaction code
- Missing: assertion quality checks, exception handling patterns, concurrency analysis

### Tool Usage Comparison

| Scenario | Before | After | Reduction |
|----------|--------|-------|-----------|
| Full audit | 5 calls | 1 call | 80% |
| Security audit | 3 calls | 1 call | 67% |
| Follow-up questions | Re-runs | Reference run_id | ~100% |

## Next-Wave Audit Rule Categories

### Category 1: Assertion Quality (TDD Focus)

**Target:** Improve test reliability and confidence  
**Methodology Tags:** `["tdd", "testing", "quality"]`

#### Proposed Rules

| Rule ID | Severity | Pattern | Rationale | Est. False Pos |
|---------|----------|---------|-----------|----------------|
| `assert-missing-in-test` | warning | Test functions without assertions | Tests should verify behavior | Low |
| `assert-weak-boolean` | info | `assertTrue(result)` without context | Weak assertions don't verify correctness | Low |
| `assert-exception-not-tested` | warning | Test calls function that may throw but no `assertRaises` | Exceptions are part of contract | Medium |
| `assert-equality-on-floats` | warning | `assertEqual(a, b)` where type is float | Floating point comparison issues | Low |
| `assert-mock-not-verified` | warning | Mock created but `assert_called` never used | Mocks should verify interactions | Medium |

**Implementation Priority:** High  
**Implementation Complexity:** Low (pattern matching on test files)  
**Estimated Impact:** Medium-High (improves test suite reliability)

**Example Violation:**
```typescript
// Bad: No assertion
function testProcessData() {
    const result = processData(input);
    // No assertion!
}

// Good: Strong assertion
function testProcessData() {
    const result = processData(input);
    assertEqual(result.expectedValue, result.actualValue);
    assertTrue(result.isValid);
}
```

### Category 2: Exception Handling

**Target:** Prevent silent failures and improve error visibility  
**Methodology Tags:** `["reliability", "debugging", "maintainability"]`

#### Proposed Rules

| Rule ID | Severity | Pattern | Rationale | Est. False Pos |
|---------|----------|---------|-----------|----------------|
| `broad-except` | error | `except:` or `except Exception:` without re-raise | Swallows errors silently | Low |
| `exception-not-logged` | warning | `except` block without logging | Can't debug failures | Medium |
| `exception-ignored` | warning | `except: pass` pattern | Completely ignores errors | Low |
| `async-exception-swallowed` | error | Async function with `try/except` at top level | Async errors need special handling | Medium |
| `error-message-generic` | info | `raise Exception("error")` without details | Generic errors hard to debug | Low |

**Implementation Priority:** High  
**Implementation Complexity:** Low-Medium (pattern matching)  
**Estimated Impact:** High (prevents production incidents)

**Example Violation:**
```typescript
// Bad: Broad exception, not logged
try {
    await processData();
} catch (e) {
    // Silent failure
}

// Good: Specific exception, logged
try {
    await processData();
} catch (e) {
    if (e instanceof ValidationError) {
        logger.error(`Validation failed: ${e.message}`);
        throw new ProcessingError("Data validation failed", e);
    }
    throw e; // Re-raise unexpected
}
```

### Category 3: Concurrency & Race Conditions

**Target:** Prevent race conditions and unsafe shared state  
**Methodology Tags:** `["concurrency", "thread-safety", "async"]`

#### Proposed Rules

| Rule ID | Severity | Pattern | Rationale | Est. False Pos |
|---------|----------|---------|-----------|----------------|
| `shared-mutable-state` | warning | Class variable modified by multiple methods | Risk of race conditions | Medium |
| `async-no-await` | error | `async` function call without `await` | Async function not executed | Low |
| `lock-missing-on-shared` | error | Shared resource accessed without lock/mutex | Classic race condition | Medium |
| `promise-not-awaited` | warning | Promise returned but never awaited | Unhandled async operation | Low |
| `concurrent-modification-detected` | warning | Iterator modified during iteration | Runtime errors | Low |

**Implementation Priority:** Medium  
**Implementation Complexity:** Medium (requires control flow analysis)  
**Estimated Impact:** High (prevents hard-to-debug race conditions)

**Example Violation:**
```typescript
// Bad: Shared mutable state without synchronization
class DataProcessor {
    private cache = new Map(); // Shared across calls
    
    async process(id: string) {
        if (!cache.has(id)) {
            const data = await fetch(id);
            cache.set(id, data); // Race condition!
        }
        return cache.get(id);
    }
}

// Good: Lock-protected access
class DataProcessor {
    private cache = new Map();
    private lock = new AsyncLock();
    
    async process(id: string) {
        return await this.lock.acquire(id, async () => {
            if (!this.cache.has(id)) {
                const data = await fetch(id);
                this.cache.set(id, data);
            }
            return this.cache.get(id);
        });
    }
}
```

## Implementation Priority Matrix

| Category | Priority | Complexity | Impact | Implementation Order |
|----------|----------|------------|--------|---------------------|
| Exception Handling | **P0** | Low | High | **1** |
| Assertion Quality | **P1** | Low | Medium-High | **2** |
| Concurrency Safety | **P2** | Medium | High | **3** |

## Rule Implementation Plan

### Sprint 1: Exception Handling (Week 1-2)

**Rules to implement:**
1. `broad-except` (error) - Already exists, enhance
2. `exception-not-logged` (warning) - NEW
3. `exception-ignored` (warning) - NEW
4. `async-exception-swallowed` (error) - NEW

**Implementation approach:**
- Pattern matching on AST nodes
- Look for `TryStatement` nodes
- Check for bare `except:` or `except Exception:`
- Check for empty or pass-only exception blocks

**Test cases needed:** 5-10 per rule

### Sprint 2: Assertion Quality (Week 3-4)

**Rules to implement:**
1. `assert-missing-in-test` (warning) - NEW
2. `assert-weak-boolean` (info) - NEW
3. `assert-exception-not-tested` (warning) - NEW

**Implementation approach:**
- Identify test files (filename patterns)
- Parse test function AST
- Count assertion statements
- Check assertion strength

**Test cases needed:** 5-10 per rule

### Sprint 3: Concurrency Safety (Week 5-6)

**Rules to implement:**
1. `async-no-await` (error) - NEW
2. `promise-not-awaited` (warning) - NEW
3. `shared-mutable-state` (warning) - NEW

**Implementation approach:**
- Async/await pattern detection
- Variable assignment analysis
- Scope tracking for shared state

**Test cases needed:** 8-12 per rule

## Database Schema Additions

### New Migration: `017_add_next_wave_audit_rules.sql`

```sql
-- Add next-wave rules to archon_audit_rules
INSERT INTO archon_audit_rules (
    rule_id, name, description, category, severity, rule_type,
    configuration, pattern, applies_to, is_builtin, is_active,
    implementation_type, rationale, remediation_guidance,
    methodology_tags, estimated_fix_time_minutes
) VALUES
-- Exception Handling Rules
('exception-not-logged', 'Exception Not Logged', 
 'Exceptions caught but not logged make debugging impossible',
 'reliability', 'warning', 'pattern',
 '{"pattern": "except.*\\n.*[^log]"}', 
 'except\s*.*:\s*\n\s*(?!.*log|print)',
 ARRAY['function', 'method'], TRUE, TRUE,
 'pattern-static', 'Without logs, production errors are invisible',
 'Add logging to exception handlers',
 '["reliability", "debugging"]', 5),

('exception-ignored', 'Exception Ignored', 
 'Empty exception handlers hide errors',
 'reliability', 'warning', 'pattern',
 '{"pattern": "except.*pass"}',
 'except\s*.*:\s*\n\s*pass',
 ARRAY['function', 'method'], TRUE, TRUE,
 'pattern-static', 'Swallowed exceptions cause silent failures',
 'Log the error or remove the handler',
 '["reliability", "debugging"]', 5),

('async-exception-swallowed', 'Async Exception Swallowed',
 'Top-level async try/except without re-raise hides errors',
 'reliability', 'error', 'pattern',
 '{"pattern": "async.*try.*except.*pass"}',
 'async\s+def.*try.*except.*pass',
 ARRAY['function'], TRUE, TRUE,
 'pattern-static', 'Async errors need special handling',
 'Re-raise or properly handle async exceptions',
 '["reliability", "async"]', 15),

-- Assertion Quality Rules
('assert-missing-in-test', 'Missing Assertions in Test',
 'Test functions should have assertions',
 'testing', 'warning', 'pattern',
 '{"check": "has_assertions"}',
 NULL,
 ARRAY['function'], TRUE, TRUE,
 'heuristic-static', 'Tests without assertions verify nothing',
 'Add assertions to verify expected behavior',
 '["tdd", "testing", "quality"]', 10),

('assert-exception-not-tested', 'Exception Not Tested',
 'Functions that may throw should test exception cases',
 'testing', 'warning', 'pattern',
 '{"check": "exception_paths"}',
 NULL,
 ARRAY['function'], TRUE, TRUE,
 'heuristic-static', 'Exception paths are part of the contract',
 'Add tests for error conditions',
 '["tdd", "testing", "quality"]', 15),

-- Concurrency Rules
('async-no-await', 'Async Function Not Awaited',
 'Async function calls must be awaited',
 'concurrency', 'error', 'pattern',
 '{"pattern": "async_call_no_await"}',
 '\b\w+\([^)]*\)(?!\s*await|\s*\.)',
 ARRAY['function', 'method'], TRUE, TRUE,
 'pattern-static', 'Unawaited async calls return promises, not results',
 'Add await to async function calls',
 '["concurrency", "async"]', 5),

('promise-not-awaited', 'Promise Not Awaited',
 'Promise returned but never awaited or handled',
 'concurrency', 'warning', 'pattern',
 '{"pattern": "promise_ignored"}',
 '\b\w+\([^)]*\)\.then\(.*\)(?!\s*await)',
 ARRAY['function', 'method'], TRUE, TRUE,
 'pattern-static', 'Unhandled promises may fail silently',
 'Await promises or handle errors',
 '["concurrency", "async"]', 10),

('shared-mutable-state', 'Shared Mutable State',
 'Class-level variables modified without synchronization',
 'concurrency', 'warning', 'heuristic',
 '{"check": "shared_state"}',
 NULL,
 ARRAY['class', 'method'], TRUE, TRUE,
 'heuristic-static', 'Shared mutable state causes race conditions',
 'Use synchronization or immutable state',
 '["concurrency", "thread-safety"]', 30);
```

## Estimated Impact on OctoFriend

With these new rules applied to OctoFriend:

**Current State:**
- Complexity issues: 24 findings
- Security issues: 0 findings
- Test issues: Unknown (no test file indexing yet)

**Projected New Findings:**
- Exception handling: ~5-10 findings (TypeScript async code)
- Assertion quality: ~10-15 findings (if tests indexed)
- Concurrency: ~3-5 findings (async/await patterns)

**Expected Health Score Impact:**
- Without test coverage: 75 → 70-72 (slight decrease due to new rules)
- With test coverage: 75 → 65-70 (more comprehensive assessment)

## Tool Usage Policy Update

Add to `code_audit_skill.py`:

```markdown
### New Rule Categories

When running audits, new findings may appear in:
- **Exception Handling**: Broad excepts, unlogged errors
- **Assertion Quality**: Missing assertions, weak tests  
- **Concurrency**: Race conditions, unawaited promises

Use `focus="reliability"` to target exception handling issues.
Use `focus="testing"` to target assertion quality (requires test files).
```

## Success Metrics

**Phase 4 Goals:**
1. **Rule Coverage**: 15 new rules implemented (5 per category)
2. **False Positive Rate**: <10% for all rules
3. **Tool Usage**: Maintain 1-call audit flow
4. **Health Score Calibration**: Scores reflect actual code quality

**Measurement:**
- Run `repo_health_check` on 5 repositories
- Track findings by category
- Measure time to resolution
- Survey developer satisfaction

## Conclusion

This next-wave audit rules expansion addresses critical gaps in:
1. **Test reliability** (assertion quality)
2. **Production stability** (exception handling)
3. **Concurrent correctness** (race conditions)

The implementation follows a phased approach (P0→P1→P2) based on complexity and impact, ensuring steady delivery without overwhelming the roadmap.

**Immediate Next Steps:**
1. Create migration `017_add_next_wave_audit_rules.sql`
2. Implement Sprint 1 rules (exception handling)
3. Test on OctoFriend repository
4. Gather feedback and iterate
