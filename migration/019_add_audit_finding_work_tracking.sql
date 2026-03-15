-- Migration 019: Audit Finding Work Tracking
-- Adds infrastructure to track manual review and remediation of audit findings
-- Includes support for marking findings as intentional/false-positive

-- =============================================================================
-- JOIN TABLE: Link audit findings to tasks for tracking remediation work
-- =============================================================================

CREATE TABLE IF NOT EXISTS archon_audit_finding_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    finding_id UUID NOT NULL REFERENCES archon_audit_findings(id) ON DELETE CASCADE,
    task_id UUID REFERENCES archon_tasks(id) ON DELETE SET NULL,  -- NULL if finding handled without task
    project_id UUID,  -- For grouping related finding work
    
    -- Review status (findings start as 'pending_review', not auto-tasks)
    review_status TEXT NOT NULL DEFAULT 'pending_review' 
        CHECK (review_status IN (
            'pending_review',      -- Needs human review
            'confirmed_issue',     -- Confirmed: needs fix
            'intentional',         -- Confirmed: intentional (document why)
            'false_positive',      -- Pattern matched but not actually a problem
            'fixed',               -- Fix completed
            'wont_fix'             -- Valid finding but won't fix (tech debt accepted)
        )),
    
    -- Review metadata
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    review_notes TEXT,  -- Why marked as intentional/false_positive/wont_fix
    
    -- Fix tracking
    fix_strategy TEXT CHECK (fix_strategy IN (
        'simple_edit',         -- Single file edit
        'refactor_function',   -- Refactor a function
        'add_tests',           -- Add missing tests
        'add_docs',            -- Add documentation
        'complex_refactor',    -- Multi-file refactoring
        'requires_design'      -- Needs architectural decision
    )),
    estimated_effort_minutes INTEGER CHECK (estimated_effort_minutes >= 0),
    
    -- Context for reviewer
    file_context TEXT,  -- Surrounding code for quick review
    suggested_action TEXT,  -- AI or system suggestion
    
    -- Tracking
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for efficient queries
CREATE INDEX idx_audit_finding_tasks_finding_id ON archon_audit_finding_tasks(finding_id);
CREATE INDEX idx_audit_finding_tasks_task_id ON archon_audit_finding_tasks(task_id);
CREATE INDEX idx_audit_finding_tasks_project_id ON archon_audit_finding_tasks(project_id);
CREATE INDEX idx_audit_finding_tasks_review_status ON archon_audit_finding_tasks(review_status);
CREATE INDEX idx_audit_finding_tasks_created_at ON archon_audit_finding_tasks(created_at);

-- =============================================================================
-- VIEW: Findings ready for human review (pending_review status)
-- =============================================================================

CREATE OR REPLACE VIEW archon_findings_pending_review AS
SELECT 
    aft.id as work_item_id,
    aft.review_status,
    aft.review_notes,
    af.id as finding_id,
    af.file_path,
    af.line_start,
    af.line_end,
    af.message as finding_message,
    af.severity,
    ar.rule_id,
    ar.name as rule_name,
    ar.category,
    ar.rationale,
    ar.remediation_guidance,
    ar.example_violation,
    ar.example_fix,
    aft.file_context,
    aft.suggested_action,
    aft.estimated_effort_minutes,
    aft.created_at as queued_at
FROM archon_audit_finding_tasks aft
JOIN archon_audit_findings af ON aft.finding_id = af.id
JOIN archon_audit_rules ar ON af.rule_id = ar.id
WHERE aft.review_status = 'pending_review'
ORDER BY 
    CASE af.severity 
        WHEN 'critical' THEN 1 
        WHEN 'error' THEN 2 
        WHEN 'warning' THEN 3 
        ELSE 4 
    END,
    aft.created_at;

-- =============================================================================
-- VIEW: Work summary by project/status
-- =============================================================================

CREATE OR REPLACE VIEW archon_audit_work_summary AS
SELECT 
    project_id,
    review_status,
    COUNT(*) as count,
    SUM(estimated_effort_minutes) as total_estimated_minutes,
    MIN(created_at) as first_queued,
    MAX(updated_at) as last_updated
FROM archon_audit_finding_tasks
GROUP BY project_id, review_status;

-- =============================================================================
-- FUNCTION: Queue findings for review (creates work items, NOT tasks)
-- =============================================================================

CREATE OR REPLACE FUNCTION queue_findings_for_review(
    p_repo_id UUID,
    p_project_id UUID DEFAULT NULL,
    p_rule_filter TEXT[] DEFAULT NULL,  -- Optional: only queue specific rules
    p_max_findings INTEGER DEFAULT 100  -- Safety limit
)
RETURNS TABLE (
    work_items_created INTEGER,
    findings_skipped_already_queued INTEGER,
    rule_breakdown JSONB
) AS $$
DECLARE
    v_created INTEGER := 0;
    v_skipped INTEGER := 0;
    v_breakdown JSONB := '{}';
    rec RECORD;
BEGIN
    -- Insert work items for findings that don't have them yet
    FOR rec IN 
        SELECT 
            af.id as finding_id,
            ar.rule_id,
            ar.category,
            af.severity,
            af.file_path,
            af.line_start,
            af.message
        FROM archon_audit_findings af
        JOIN archon_audit_rules ar ON af.rule_id = ar.id
        WHERE af.repo_id = p_repo_id
        AND af.status = 'open'
        AND NOT EXISTS (
            SELECT 1 FROM archon_audit_finding_tasks aft 
            WHERE aft.finding_id = af.id
        )
        AND (p_rule_filter IS NULL OR ar.rule_id = ANY(p_rule_filter))
        ORDER BY 
            CASE af.severity 
                WHEN 'critical' THEN 1 
                WHEN 'error' THEN 2 
                WHEN 'warning' THEN 3 
                ELSE 4 
            END,
            af.created_at
        LIMIT p_max_findings
    LOOP
        INSERT INTO archon_audit_finding_tasks (
            finding_id,
            project_id,
            review_status,
            suggested_action,
            file_context
        ) VALUES (
            rec.finding_id,
            p_project_id,
            'pending_review',
            CASE rec.rule_id
                WHEN 'assert-mock-not-verified' THEN 'Add assert_called() or assert_called_once() to verify mock usage'
                WHEN 'assert-missing-in-test' THEN 'Add assertions to verify expected behavior'
                WHEN 'broad-except' THEN 'Replace with specific exception types'
                WHEN 'exception-not-logged' THEN 'Add logging to exception handler'
                ELSE 'Review finding and determine appropriate fix'
            END,
            'Line ' || rec.line_start || ': ' || LEFT(rec.message, 100)
        );
        
        v_created := v_created + 1;
        
        -- Build breakdown (convert to int, add 1, convert back to jsonb)
        v_breakdown := jsonb_set(
            v_breakdown,
            ARRAY[rec.rule_id],
            to_jsonb(COALESCE((v_breakdown->>rec.rule_id)::int, 0) + 1)
        );
    END LOOP;
    
    -- Count skipped (already have work items)
    SELECT COUNT(*) INTO v_skipped
    FROM archon_audit_findings af
    WHERE af.repo_id = p_repo_id
    AND af.status = 'open'
    AND EXISTS (
        SELECT 1 FROM archon_audit_finding_tasks aft 
        WHERE aft.finding_id = af.id
    );
    
    RETURN QUERY SELECT v_created, v_skipped, v_breakdown;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- FUNCTION: Review a finding (mark with decision)
-- =============================================================================

CREATE OR REPLACE FUNCTION review_finding(
    p_work_item_id UUID,
    p_decision TEXT,  -- confirmed_issue, intentional, false_positive, wont_fix
    p_reviewed_by TEXT,
    p_notes TEXT DEFAULT NULL
)
RETURNS BOOLEAN AS $$
BEGIN
    -- Validate decision
    IF p_decision NOT IN ('confirmed_issue', 'intentional', 'false_positive', 'wont_fix') THEN
        RAISE EXCEPTION 'Invalid decision: %. Must be confirmed_issue, intentional, false_positive, or wont_fix', p_decision;
    END IF;
    
    UPDATE archon_audit_finding_tasks
    SET 
        review_status = p_decision,
        reviewed_by = p_reviewed_by,
        reviewed_at = NOW(),
        review_notes = p_notes,
        updated_at = NOW()
    WHERE id = p_work_item_id;
    
    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- FUNCTION: Create task from confirmed finding
-- =============================================================================

CREATE OR REPLACE FUNCTION create_task_from_finding(
    p_work_item_id UUID,
    p_project_id UUID,
    p_assignee TEXT DEFAULT 'User'
)
RETURNS UUID AS $$
DECLARE
    v_task_id UUID;
    v_finding RECORD;
    v_work_item RECORD;
BEGIN
    -- Get work item and finding details
    SELECT aft.*, af.file_path, af.line_start, af.line_end, af.message,
           ar.rule_id, ar.name as rule_name, ar.category, ar.remediation_guidance
    INTO v_work_item
    FROM archon_audit_finding_tasks aft
    JOIN archon_audit_findings af ON aft.finding_id = af.id
    JOIN archon_audit_rules ar ON af.rule_id = ar.id
    WHERE aft.id = p_work_item_id
    AND aft.review_status = 'confirmed_issue';
    
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Work item % not found or not confirmed as issue', p_work_item_id;
    END IF;
    
    -- Insert task
    INSERT INTO archon_tasks (
        project_id,
        title,
        description,
        status,
        assignee,
        priority,
        feature,
        task_order,
        created_at,
        updated_at
    ) VALUES (
        p_project_id,
        'Fix: ' || v_work_item.rule_name || ' in ' || split_part(v_work_item.file_path, '/', -1),
        '**Finding:** ' || v_work_item.message || E'\n\n' ||
        '**File:** ' || v_work_item.file_path || ' (lines ' || v_work_item.line_start || '-' || v_work_item.line_end || ')' || E'\n\n' ||
        '**Rule:** ' || v_work_item.rule_id || E'\n\n' ||
        '**Guidance:** ' || COALESCE(v_work_item.remediation_guidance, 'See example fix in audit rules'),
        'todo',
        p_assignee,
        CASE v_work_item.category 
            WHEN 'security' THEN 'critical'
            WHEN 'exception-handling' THEN 'high'
            ELSE 'medium'
        END,
        'code-audit-remediation',
        0,
        NOW(),
        NOW()
    )
    RETURNING id INTO v_task_id;
    
    -- Link task to work item
    UPDATE archon_audit_finding_tasks
    SET task_id = v_task_id,
        updated_at = NOW()
    WHERE id = p_work_item_id;
    
    RETURN v_task_id;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- TRIGGER: Update updated_at on changes
-- =============================================================================

CREATE OR REPLACE FUNCTION update_audit_finding_task_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_audit_finding_task_timestamp
    BEFORE UPDATE ON archon_audit_finding_tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_audit_finding_task_timestamp();

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON TABLE archon_audit_finding_tasks IS 
    'Links audit findings to tasks for remediation tracking. Findings start as pending_review and require human validation before creating tasks.';

COMMENT ON COLUMN archon_audit_finding_tasks.review_status IS 
    'pending_review=needs human review, confirmed_issue=valid problem to fix, intentional=valid code by design, false_positive=pattern matched incorrectly, fixed=completed, wont_fix=accepted tech debt';
