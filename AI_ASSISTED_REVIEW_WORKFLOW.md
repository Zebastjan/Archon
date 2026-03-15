# AI-Assisted Audit Finding Review Workflow

## Overview

We've added AI-assisted triage to reduce the manual load of reviewing 785 audit findings while maintaining human oversight and judgment.

## Workflow Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  785 Audit Findings (archon repository)                     │
│  • exception-not-logged: 376                                 │
│  • assert-mock-not-verified: 340                             │
│  • assert-missing-in-test: 49                                │
│  • broad-except: 20                                          │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────┐
        │  Step 1: Auto-Triage (Liquid 8B)     │
        │  - Batch 20-50 findings at a time    │
        │  - Call local kahnwong/lfm2:8b-a1b   │
        │  - Store suggestions as 'y/n/i/w'    │
        │  - Store rationale (10-20 words)     │
        │  - Mark status = 'auto_suggested'    │
        └──────────────────────────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────┐
        │  Step 2: Human Review (Fast Correct)  │
        │  - Shows AI suggestion: y/n/i/w       │
        │  - Shows AI rationale                  │
        │  - Use Enter to accept                 │
        │  - Use 1/2/3/4 to override             │
        │  - Final status confirmed              │
        └──────────────────────────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────┐
        │  Step 3: Task Creation (Confirmed)    │
        │  - Only for 'y' (confirmed_issue)     │
        │  - Worktree safety validation         │
        │  - Track progress                     │
        │  - Health score improvements          │
        └──────────────────────────────────────┘
```

## Scripts

### 1. Auto-Triage Script

**File:** `scripts/auto_triage_audit_findings.py`

**Usage:**
```bash
cd /home/zebastjan/dev/archon
uv run python scripts/auto_triage_audit_findings.py <project_id> --batch-size 20
```

**What it does:**
1. Fetches next 20 findings in `pending_review` status
2. Structures each finding with:
   - Rule ID, name, category, severity
   - File path, line numbers, message
   - Code context (snippet)
   - Rule rationale and guidance
3. Sends batch to local Liquid 8B via Ollama API
4. Parses JSON response with decisions:
   ```json
   [
     {"finding_id": "uuid", "decision": "y", "rationale": "Security risk - fix"},
     {"finding_id": "uuid", "decision": "n", "rationale": "False match - is boolean"},
     {"finding_id": "uuid", "decision": "i", "rationale": "Valid top-level handler"},
     {"finding_id": "uuid", "decision": "w", "rationale": "Legacy, not worth cost"}
   ]
   ```
5. Stores suggestions in database:
   - `suggested_label` = y/n/i/w
   - `suggested_rationale` = AI explanation
   - `review_status` = 'auto_suggested'

**Repeat until all findings processed** (~16 batches for 785 findings)

### 2. Human Review CLI (Updated)

**File:** `scripts/review_audit_findings.py`

**Usage:**
```bash
cd /home/zebastjan/dev/archon
uv run python scripts/review_audit_findings.py
```

**Updated Commands:**
- **Enter** = Accept AI suggestion
- **1** = Override to YES (must fix)
- **2** = Override to NO (false positive)
- **3** = Override to INTENTIONAL
- **4** = Override to WONT FIX
- **y/n/i/w/s/q** = Manual decision (unchanged)

**Shows when AI suggestion exists:**
```
🤖 AI Suggestion: YES - fix this
   Rationale: Security risk - should use specific exception type
```

## Database Schema

### New Columns Added (Migration 019 + Update)

```sql
ALTER TABLE archon_audit_finding_tasks ADD COLUMN
  suggested_label TEXT,           -- AI suggested decision (y/n/i/w)
  suggested_rationale TEXT,       -- AI rationale (10-20 words)
  review_status TEXT DEFAULT 'pending_review';
```

### Review Status Flow

```
pending_review 
  ↓ (auto-triage with Liquid 8B)
auto_suggested
  ↓ (human accepts or overrides)
[confirmed_issue | intentional | false_positive | wont_fix]
  ↓
fixed (when task completed)
```

## Liquid 8B Prompt Template

```python
"""
You are a code quality expert reviewing audit findings. For each finding, decide:

y = confirmed_issue (must fix - real problem)
n = false_positive (not actually a problem)
i = intentional (valid code by design)
w = wont_fix (not worth fixing - accepted tech debt)
s = skip (not enough context)

Respond with JSON:
[
  {"finding_id": "uuid", "decision": "y", "rationale": "short"},
  ...
]

Guidelines:
- Security violations: Default to y unless clearly intentional
- Test assertions: Default to y if test has no assertions
- Mark 'n' only when pattern clearly doesn't apply
- Mark 'i' for unusual but valid patterns
- Mark 'w' when effort > benefit
- When uncertain, use 's'
"""
```

## Expected Efficiency Gains

### Without AI-Assisted Review
- Per finding: 20-30 seconds to read, analyze, decide
- 785 findings × 25 seconds = **~5.5 hours** of manual classification

### With AI-Assisted Review  
- AI triage: ~1 minute per 20 findings (batch processing) = **~40 minutes**
- Human review: 2-3 seconds each to accept/override = **~0.8 hours**
- **Total time: ~2 hours** (vs 5.5 hours)
- **Savings: ~3.5 hours**
- **Throughput: 3x faster**

### Quality Expectations

Based on typical classification accuracy for 4-class problems:
- **Liquid 8B accuracy estimate:** 70-80%
- **Human correction needed:** 20-30% of findings
- **Time to correct errors:** ~2 seconds each vs 25 seconds each from scratch

**Result:** You're correcting mistakes, not doing the initial classification.

## Usage Example

### Initial Setup

```bash
# First run auto-triage
cd /home/zebastjan/dev/archon
uv run python scripts/auto_triage_audit_findings.py \
  750913d5-92f6-4478-ab98-f2a79285198d \
  --batch-size 20

# Will process in batches (~16 runs needed)
# Each run takes ~1-2 minutes for 20 findings
```

### Review Session

```bash
# Now review with AI suggestions visible
uv run python scripts/review_audit_findings.py

# Shows:
# Finding 1 of 785 [error] broad-except
# File: python/src/agents/document_agent.py:185
# Message: Broad exception handler: use specific exception types
# 🤖 AI Suggestion: YES - fix this
#    Rationale: Security risk - hiding bugs
#
# Decision [Enter/y/n/i/w/s/q]: y
# ✅ Marked as confirmed_issue
```

### Progress Tracking

```python
from src.server.services.audit_workflow_service import get_audit_workflow_service

service = get_audit_workflow_service()
summary = service.get_progress_summary(project_id='750913d5-...')

print(f'{summary.percent_reviewed():.1f}% reviewed')
print(f'  Pending review: {summary.pending_review}')
print(f'  AI suggestions accepted: {summary.confirmed_issue}')
print(f'  Overrides applied: manual track via review_notes')
```

## Safety Features

✅ **Human always in control** - AI only suggests, human decides  
✅ **Rationale visible** - See why AI suggested what it did  
✅ **Fast override** - Enter accepts, 1/2/3/4 overrides  
✅ **Worktree safety** - Only creates tasks for confirmed issues  
✅ **Audit trail** - All accepted/override decisions tracked  
✅ **Progressive refinement** - Model learns from corrections  

## Next Steps

1. **Run auto-triage** - Process all 785 findings with Liquid 8B (~2 hours)
2. **Review a sample** - Validate AI quality on first 50 findings
3. **Calibrate if needed** - Adjust prompt or decision thresholds
4. **Full review** - Press Enter/override for remaining 785 findings
5. **Create tasks** - Only for confirmed "y" decisions
6. **Execute fixes** - Use Windsurf Cascade on confirmed issues

## Integration with Windsurf Cascade

Once findings are reviewed and confirmed as "y" (must fix):

1. Export subset of confirmed issues
2. Batch-send to Windsurf Cascade
3. One Cascade run per 10-20 files
4. Accept/patch as group
5. Mark findings as "fixed" automatically

Credits consumed = number of Cascade runs (not internal tool calls)

## Files Modified/Created

1. `migration/019_add_audit_finding_work_tracking.sql` - + columns for suggestions
2. `scripts/auto_triage_audit_findings.py` - **NEW** AI triage script
3. `scripts/review_audit_findings.py` - **UPDATED** shows AI suggestions
4. `python/src/server/services/audit_workflow_service.py` - **UPDATED** query includes suggestions
5. `AI_ASSISTED_REVIEW_WORKFLOW.md` - This document

## Summary

By combining **Liquid 8B auto-triage** with **fast human correction**, we can:

- Reduce review time from ~5.5 hours to ~2 hours (**3.5x faster**)
- Maintain human oversight on every decision
- Scale to larger codebases (10,000+ findings) efficiently
- Keep the "findings are candidates, not commands" principle

**Ready to start?** Run:
```bash
uv run python scripts/auto_triage_audit_findings.py 750913d5-92f6-4478-ab98-f2a79285198d
```
