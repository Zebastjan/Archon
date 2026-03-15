# Phase 1: Super-Tools Implementation Summary

## Overview

Successfully implemented Phase 1 of the roadmap: creating super-tools to reduce cloud tool-call usage and improve local orchestration.

## 1. Super-Tool: `repo_health_check`

### File: `python/src/mcp_server/features/code_audit/repo_health_super_tool.py`

### Function Signature
```python
def run_repo_health_check(
    repo_id: str,
    focus: Literal["full", "security", "tdd", "docs", "maintainability"] | None = None,
    ruleset: str | None = None,
    skip_worktree_validation: bool = False,
) -> dict[str, Any]:
```

### What It Does (Internally)

**Single tool call replaces:**
1. ❌ `worktree_validate_safe_to_work()` 
2. ❌ `code_audit_calculate_metrics()`
3. ❌ `code_audit_run()`
4. ❌ `code_audit_get_findings()`
5. ❌ `code_audit_get_summary()`

**With:**
1. ✅ `repo_health_check(repo_id, focus="security")` → returns everything

### Internal Orchestration

```python
# Step 1: Worktree safety (hidden from model)
validation = worktree_service.validate_safe_to_work(...)
if not validation.is_safe:
    return {"success": False, "safety_issues": ...}

# Step 2: Calculate metrics
metrics = metrics_service.calculate_repo_metrics(repo_id)

# Step 3: Run audit with appropriate ruleset
ruleset = FOCUS_RULESETS.get(focus)  # Pre-defined rulesets
findings_count, run_id = metrics_service.run_audit(repo_id, ruleset)

# Step 4: Get findings
findings = metrics_service.get_audit_findings(repo_id, ...)

# Step 5: Aggregate results
category_scores = _calculate_category_scores(metrics, findings)
highlights = _generate_highlights(findings)
recommendations = _generate_recommendations(metrics, findings, focus)

# Return unified response
return {
    "success": True,
    "health_score": metrics.health_score,  # 0-100
    "per_category_scores": category_scores,
    "highlights": highlights,  # Top 10 findings
    "recommendations": recommendations,
    "run_id": run_id,
    "metrics_summary": {...},
    "findings_summary": {...},
}
```

### Focus Modes

| Focus | Ruleset | Use Case |
|-------|---------|----------|
| `full` | All active rules | Complete health assessment |
| `security` | 6 security rules | Security audit only |
| `tdd` | 3 methodology rules | Test coverage audit |
| `docs` | 3 documentation rules | Documentation audit |
| `maintainability` | 9 maintainability rules | Code quality audit |

### Response Schema

```json
{
    "success": true,
    "health_score": 78,
    "per_category_scores": {
        "overall": 78,
        "security": 85,
        "complexity": 72,
        "maintainability": 80,
        "documentation": 65
    },
    "highlights": [
        {
            "rule_id": "hardcoded-secrets",
            "severity": "critical",
            "description": "API key found in config.py",
            "file": "config.py",
            "line": 42,
            "fix_summary": "Move to environment variables"
        }
    ],
    "recommendations": [
        "Address 3 critical security findings immediately",
        "Refactor highest complexity function (complexity: 51)",
        "Add more comments (current ratio 288:1, target 4-10:1)"
    ],
    "run_id": "uuid-for-traceability",
    "metrics_summary": {...},
    "findings_summary": {
        "total": 24,
        "critical": 3,
        "error": 7,
        "warning": 12,
        "info": 2
    },
    "focus": "security",
    "safety_validated": true
}
```

## 2. MCP Tool Registration

### File: `python/src/mcp_server/features/code_audit/code_audit_tools.py`

Added new MCP tool:

```python
@mcp.tool()
async def repo_health_check(
    repo_id: str,
    focus: str | None = None,
    ruleset: str | None = None,
) -> dict[str, Any]:
    """Run comprehensive repository health check (SUPER-TOOL)."""
```

**Tool Benefits:**
- Single call instead of 4-5 separate calls
- Internal worktree safety validation (no separate safety tool call)
- Focus modes for targeted audits
- Pre-defined rulesets reduce need for manual rule selection

## 3. Updated Skills with Tool Usage Policy

### File: `python/src/mcp_server/skills/code_audit_skill.py`

### Added Policy Section

```markdown
## ⚠️ CRITICAL: Tool Usage Policy

### DO:
- ✅ Use `repo_health_check` as the PRIMARY tool for all audit requests
- ✅ Call it ONCE per user request (includes metrics + audit + safety)
- ✅ Reference previous results for follow-up questions
- ✅ Request fresh audit ONLY when user explicitly says "run again"

### DON'T:
- ❌ Call `code_audit_calculate_metrics` and `code_audit_run` separately
- ❌ Re-run audits for every follow-up question
- ❌ Call worktree safety tools separately (handled internally)
- ❌ Make multiple audit calls for the same request

### Tool Selection Guide:

**For MOST requests, use `repo_health_check`:**
- "Audit this repo" → `repo_health_check(repo_id, focus="full")`
- "Check security issues" → `repo_health_check(repo_id, focus="security")`
- "How's code quality?" → `repo_health_check(repo_id, focus="full")`

### Example: Good vs Bad Usage

❌ BAD (3 tool calls):
1. code_audit_calculate_metrics(repo_id)
2. worktree_validate_safe_to_work(repo_id)
3. code_audit_run(repo_id)

✅ GOOD (1 tool call):
1. repo_health_check(repo_id)  # Does all of above internally
```

### Updated Workflows

**New (Recommended):**
```
Use repo_health_check(repo_id, focus) for ALL audit requests:

- focus="full" → Complete health assessment
- focus="security" → Security-only audit
- focus="tdd" → Test coverage audit
- focus="docs" → Documentation audit
- focus="maintainability" → Code quality audit
```

**Legacy (Not Recommended):**
```
Only use if explicitly requested:
1. code_audit_calculate_metrics(repo_id) - metrics only
2. code_audit_run(repo_id, ruleset) - audit only
Note: repo_health_check combines both + worktree safety
```

## 4. Hidden Safety Integration

The `repo_health_check` tool internally validates worktree safety before any operations:

```python
# Inside run_repo_health_check():

if not skip_worktree_validation:
    worktree_service = get_worktree_service()
    validation = worktree_service.validate_safe_to_work(...)
    
    if not validation.is_safe:
        return {
            "success": False,
            "error": "Worktree safety validation failed",
            "safety_issues": validation.issues,
            "safety_warnings": validation.warnings,
        }
```

**Benefit:** Safety is automatic - no separate tool call needed.

## 5. Service Layer Updates

### File: `python/src/server/services/code_metrics_service.py`

**Changed:**
- **From:** Supabase client
- **To:** Direct PostgreSQL via psycopg2

**Why:** 
- Reduces dependency on external Supabase service
- Better for local orchestration
- Lower latency for database operations

**Migration:**
```python
# Old:
from src.server.utils import get_supabase_client
self.supabase = supabase_client or get_supabase_client()

# New:
import psycopg2
self._connection_string = os.getenv("ARCHON_DATABASE_URL", "...")
```

## 6. Test Coverage

### New Tests: `python/tests/mcp_server/features/code_audit/test_repo_health_super_tool.py`

**13 tests covering:**
- Focus rulesets definition
- Successful health check execution
- Worktree safety failure handling
- Security focus mode
- Custom ruleset support
- Category score calculation
- Highlights generation (sorted by severity)
- Recommendations generation
- Tool usage policy compliance

**Run Tests:**
```bash
cd python && uv run pytest tests/mcp_server/features/code_audit/test_repo_health_super_tool.py -v
```

## Files Created/Modified

### New Files
1. `python/src/mcp_server/features/code_audit/repo_health_super_tool.py` - Super-tool implementation
2. `python/tests/mcp_server/features/code_audit/test_repo_health_super_tool.py` - Tests

### Modified Files
1. `python/src/mcp_server/features/code_audit/code_audit_tools.py` - Added MCP tool wrapper
2. `python/src/mcp_server/skills/code_audit_skill.py` - Added usage policy
3. `python/src/server/services/code_metrics_service.py` - Switched to PostgreSQL

## Tool Usage Reduction

### Before (Multiple Calls)

```
User: "Audit this repo"

Agent:
1. worktree_validate_safe_to_work(repo_id) → 1 call
2. code_audit_calculate_metrics(repo_id) → 1 call
3. code_audit_run(repo_id) → 1 call
4. code_audit_get_findings(repo_id) → 1 call
5. code_audit_get_summary(repo_id) → 1 call

Total: 5 tool calls
```

### After (Single Call)

```
User: "Audit this repo"

Agent:
1. repo_health_check(repo_id, focus="full") → 1 call
   (Internally does all of above)

Total: 1 tool call (80% reduction)
```

## Next Steps (Phase 2 & 3)

### Phase 2: Local Orchestrator Model

1. **Select local model** (7-14B, RTX 3060 compatible)
2. **Define orchestration API:**
   ```python
   class LocalOrchestrator:
       def run_repo_health_check(self, repo_id, focus):
           # Calls Python services directly
           return run_repo_health_check(repo_id, focus)
       
       def plan_refactors(self, repo_id, run_id):
           # Uses audit findings to propose tasks
           pass
   ```
3. **Wire into MCP:**
   - Option A: HTTP service that MCP calls
   - Option B: CLI wrapper

### Phase 3: Dogfooding & Tuning

1. **Run on Archon/Cephalosage repo**
2. **Compare tool-call counts**
3. **Tune skill instructions**
4. **CI integration**

## Summary

✅ **Super-tool created:** `repo_health_check` combines 5 operations into 1
✅ **Safety hidden:** Worktree validation automatic, no separate call
✅ **Skills updated:** Clear tool usage policy with DO/DON'T guidelines
✅ **Tests added:** 13 tests for super-tool functionality
✅ **Service migrated:** From Supabase to direct PostgreSQL

**Tool Usage Reduction: 80%** (5 calls → 1 call per audit request)

Ready for Phase 2: Local orchestrator model implementation.
