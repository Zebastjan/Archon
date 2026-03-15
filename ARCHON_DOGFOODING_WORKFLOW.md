# Archon Dogfooding Workflow: P0/P1 Violations Cleanup

## Overview

We've built infrastructure to systematically review and remediate 785 audit findings in the Archon codebase while maintaining human oversight and judgment.

**Key Principle:** Findings are **candidates for review**, not automatic todos. Human validation required before any changes.

## Current State

- **785 findings queued** for review across the Archon repository
- **Project created:** "Archon P0/P1 Violations Cleanup" (ID: `750913d5-92f6-4478-ab98-f2a79285198d`)
- **All findings** currently in `pending_review` status

### Finding Breakdown

| Rule | Count | Severity | Priority |
|------|-------|----------|----------|
| exception-not-logged | 376 | Warning | High |
| assert-mock-not-verified | 340 | Warning | High |
| assert-missing-in-test | 49 | Warning | Critical |
| broad-except | 20 | Error | Critical |

**Total:** 785 findings

## Infrastructure Components

### 1. Database Layer (Migration 019)

**New Table:** `archon_audit_finding_tasks`
- Links audit findings to work tracking
- Tracks review status: `pending_review`, `confirmed_issue`, `intentional`, `false_positive`, `fixed`, `wont_fix`
- Stores review notes and rationale
- Supports estimated effort tracking

**Views:**
- `archon_findings_pending_review`: Ready for human review
- `archon_audit_work_summary`: Progress tracking

**Functions:**
- `queue_findings_for_review()`: Queue findings without auto-creating tasks
- `review_finding()`: Mark with human decision
- `create_task_from_finding()`: Create task only for confirmed issues

### 2. Service Layer

**File:** `python/src/server/services/audit_workflow_service.py`

```python
from src.server.services.audit_workflow_service import get_audit_workflow_service

service = get_audit_workflow_service()

# Queue findings for review
result = service.queue_findings_for_review(repo_id, project_id)

# Get items pending review
items = service.get_pending_review_items(project_id)

# Mark a finding with decision
service.review_finding(work_item_id, 'confirmed_issue', 'reviewer_name', 'notes')

# Create task from confirmed finding
task_id = service.create_task_from_finding(work_item_id, project_id)

# Track progress
summary = service.get_progress_summary(project_id)
print(f"{summary.percent_reviewed():.1f}% reviewed")
```

### 3. Interactive Review Script

**File:** `scripts/review_audit_findings.py`

```bash
cd /home/zebastjan/dev/archon
uv run python scripts/review_audit_findings.py
```

**Interactive Commands:**
- `y` - Confirmed issue (create task and fix)
- `n` - False positive (pattern matched incorrectly)
- `i` - Intentional (valid code by design)
- `w` - Won't fix (accepted tech debt)
- `s` - Skip for now
- `q` - Quit

## Review Workflow

### Phase 1: Initial Review (Filtering)

**Goal:** Separate real issues from noise

1. Run the interactive review script
2. Review findings in priority order (critical/error first)
3. Mark each finding:
   - **Confirmed issues** → Will create tasks
   - **False positives** → Audit rule needs tuning
   - **Intentional** → Valid by design (document why)
   - **Won't fix** → Accepted tech debt

**Expected time:** 2-3 hours for 785 findings (20-30 seconds each)

### Phase 2: Create Tasks (Only for Confirmed Issues)

**Goal:** Convert confirmed issues to actionable tasks

```python
# For each confirmed issue
service.create_task_from_finding(work_item_id, project_id)
```

**Expected:** ~300-400 confirmed issues (based on typical audit accuracy)

### Phase 3: Execute Fixes

**Goal:** Work through tasks with full worktree safety

1. Each task has worktree context automatically
2. Safety validation before any changes
3. Progress tracked automatically
4. Health scores update as findings are resolved

## Example Usage

### Quick Progress Check

```python
import psycopg2
from src.server.services.audit_workflow_service import get_audit_workflow_service

conn = psycopg2.connect('postgresql://archon:archon_local_dev@localhost:5434/archon')
service = get_audit_workflow_service(conn)

project_id = '750913d5-92f6-4478-ab98-f2a79285198d'
summary = service.get_progress_summary(project_id=project_id)

print(f"Progress: {summary.percent_reviewed():.1f}% reviewed")
print(f"  Total: {summary.total_findings}")
print(f"  Pending: {summary.pending_review}")
print(f"  Confirmed issues: {summary.confirmed_issue}")
print(f"  Intentional: {summary.intentional}")
print(f"  False positives: {summary.false_positive}")
print(f"  Won't fix: {summary.wont_fix}")
```

### Review Specific Finding Types

```python
# Get only broad-except findings (critical security)
items = service.get_pending_review_items(project_id)
critical_items = [i for i in items if i.rule_id == 'broad-except']

for item in critical_items:
    print(f"{item.file_path}:{item.line_start}")
    print(f"  {item.finding_message}")
```

### Bulk Mark False Positives

```python
# If a pattern is clearly wrong, bulk mark
cursor = conn.cursor()
cursor.execute("""
    UPDATE archon_audit_finding_tasks
    SET review_status = 'false_positive',
        reviewed_by = 'bulk_review',
        review_notes = 'Pattern matching incorrectly on this file pattern',
        reviewed_at = NOW()
    WHERE finding_id IN (
        SELECT af.id
        FROM archon_audit_findings af
        JOIN archon_audit_rules ar ON af.rule_id = ar.id
        WHERE ar.rule_id = 'assert-mock-not-verified'
        AND af.file_path LIKE '%/conftest.py'
    )
""")
conn.commit()
```

## Decision Guidelines

### When to Mark as `confirmed_issue`

- **broad-except**: Bare `except:` or `except Exception:` without specific types
- **exception-not-logged**: `except` block that doesn't log (and should)
- **assert-mock-not-verified**: Mock created but no `assert_called()` check
- **assert-missing-in-test**: Test function with no assertions at all

### When to Mark as `false_positive`

- Pattern matched but code is actually correct
- Example: `assertTrue(is_valid)` where `is_valid` is clearly a boolean
- Rule needs tuning for edge cases

### When to Mark as `intentional`

- Pattern violates rule but there's a good reason
- Example: Top-level exception handler that catches-all and re-raises
- Document the rationale in review_notes

### When to Mark as `wont_fix`

- Valid finding but not worth fixing now
- Legacy code being phased out
- Risk of breaking change > benefit of fix
- Document why it's accepted tech debt

## Expected Outcomes

### Conservative Estimate (80% accuracy)
- 628 confirmed issues
- 94 intentional
- 47 false positives
- 16 won't fix

### Tasks Created
- ~628 tasks from confirmed issues
- Prioritized by severity (critical/error first)
- Estimated effort tracked

### Health Score Improvement
- Current: 60/100 (with penalties applied)
- Target: 75/100+ (after fixes)
- Tracks automatically as findings marked `fixed`

## Progress Tracking

### Daily Standup Metrics

```python
# Run daily to see progress
stats = service.get_review_statistics(repo_id='5ee23b74-...')

print("Review Statistics:")
for rule, data in stats['by_rule'].items():
    total = sum(data['statuses'].values())
    reviewed = total - data['statuses'].get('pending_review', 0)
    pct = (reviewed / total * 100) if total > 0 else 0
    print(f"  {rule}: {pct:.0f}% reviewed ({reviewed}/{total})")
```

### Weekly Report

```python
summary = service.get_progress_summary(project_id=project_id)

print(f"Week of {datetime.now().strftime('%Y-%m-%d')}")
print(f"  Reviewed: {summary.percent_reviewed():.1f}%")
print(f"  Fixed: {summary.percent_fixed():.1f}%")
print(f"  Remaining effort: {summary.remaining_estimated_minutes // 60} hours")
```

## Files Created

1. `migration/019_add_audit_finding_work_tracking.sql` - Database infrastructure
2. `python/src/server/services/audit_workflow_service.py` - Service layer
3. `scripts/review_audit_findings.py` - Interactive review tool
4. `ARCHON_DOGFOODING_WORKFLOW.md` - This document

## Next Steps

1. **Start Review:** Run `scripts/review_audit_findings.py`
2. **Filter Findings:** Spend 2-3 hours marking y/n/i/w
3. **Create Tasks:** Generate tasks from confirmed issues
4. **Execute:** Work through tasks systematically
5. **Track:** Watch health score improve from 60 → 75+

## Safety Reminders

✅ **Worktree safety** is active on all tasks  
✅ **Human review required** before any changes  
✅ **Not all findings need fixing** - use judgment  
✅ **Document rationale** for intentional/wont_fix decisions  
✅ **Progress tracked automatically** - no manual bookkeeping needed  

---

**Ready to start?** Run:
```bash
cd /home/zebastjan/dev/archon
uv run python scripts/review_audit_findings.py
```
