# ADR-011: Audit Feedback Loop and Learning Mechanism

## Status: **Implemented** (2026-03-24)

## Date: 2026-03-24

## Context

ADR-010's Layer 3 - correlation engine to learn from audit history. When a finding was dismissed as "false positive" or "won't fix" and later a real bug occurs in the same location/pattern, the system should flag this for review.

## Decision

Implement **on-demand** feedback loop (not at commit time).

### Database Schema

```sql
-- Extend archon_audit_findings with outcome tracking
ALTER TABLE archon_audit_findings ADD COLUMN IF NOT EXISTS resolution_note TEXT;
ALTER TABLE archon_audit_findings ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMP;

-- New table: audit outcomes
CREATE TABLE archon_audit_outcomes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    finding_id UUID REFERENCES archon_audit_findings(id) ON DELETE CASCADE,
    outcome_type TEXT NOT NULL,  -- bug_filed, bug_hit_production, validated_correct
    outcome_at TIMESTAMP DEFAULT NOW(),
    notes TEXT,
    related_issue_id TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- New table: learning events
CREATE TABLE archon_audit_learning_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    finding_id UUID REFERENCES archon_audit_findings(id) ON DELETE CASCADE,
    outcome_id UUID REFERENCES archon_audit_outcomes(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,  -- false_negative, dismissed_then_hit, correct_dismissal
    retrospective_task_id UUID REFERENCES archon_tasks(id),
    correlation_data JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);
```

### MCP Tools

**1. Track Outcome**

```python
@mcp.tool()
async def audit_track_outcome(
    finding_id: str,
    outcome_type: str,  # bug_filed, bug_hit_production, validated_correct
    notes: str = "",
    related_issue_id: str = None
) -> dict:
    """
    Record the outcome of a dismissed finding.
    
    When a finding that was marked 'false_positive' or 'wont_fix' 
    later results in a real bug, record the correlation.
    """
```

**2. Query Retrospectives**

```python
@mcp.tool()
async def audit_get_retrospectives() -> dict:
    """
    Get all correlation events where dismissed findings
    were later validated as real issues.
    
    Returns:
        List of learning events with context
    """
```

**3. Check Correlation (On-Demand)**

```python
@mcp.tool()
async def audit_check_correlation(
    file_path: str,
    function_name: str = None
) -> dict:
    """
    Check if there are any dismissed findings related to 
    this file/function before marking new issue as bug.
    
    Called when: new bug found, before closing as "won't fix"
    """
```

### Correlation Logic

```
When new bug is filed:
1. Extract: file_path, function_name, error_category
2. Query: archon_audit_findings 
   WHERE file_path = :path 
   AND status IN ('false_positive', 'wont_fix')
   AND category = :category
3. If matches found:
   - Create archon_audit_outcomes (bug_filed)
   - Create archon_audit_learning_events (dismissed_then_hit)
   - Generate retrospective task
4. Return: "WARNING: Similar issue was previously dismissed"
```

### Retrospective Task Generation

When correlation detected:

```python
# Auto-create task for review
task = await archon_manage_task(
    action="create",
    project_id=current_project,
    title=f"Retro: Dismissed finding became real bug in {file_path}",
    description=f"Finding in {file_path} was dismissed but now real bug filed. "
                f"Review our dismissal logic.",
    feature="audit-retrospective",
    priority="high"
)
```

### When to Trigger

- **On-demand only** (not at commit time):
  - When agent marks finding as "false_positive" or "wont_fix"
  - When new bug/ticket is filed
  - When production incident occurs
  - Manual trigger: `audit_check_correlation(file_path, function)`

### Not Triggered At:
- Commit time (adds overhead)
- Every audit run (too noisy)

## Consequences

### Positive
- Self-improving audit system
- Tracks dismissal accuracy
- Generates review tasks for blind spots

### Negative
- Requires agents to use tracking tools
- Additional database storage

## Related Decisions

- ADR-010: Intelligent Code Auditing System
- ADR-009: Commit-Automation Pipeline

## Implementation Checklist

- [x] Add columns to archon_audit_findings
- [x] Create archon_audit_outcomes table
- [x] Create archon_audit_learning_events table
- [x] Implement audit_track_outcome tool
- [x] Implement audit_get_retrospectives tool
- [x] Implement audit_check_correlation tool
- [x] Add retrospective task generation
- [x] Test: dismiss finding → file bug → get retrospective
