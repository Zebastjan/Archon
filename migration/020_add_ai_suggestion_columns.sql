-- Migration 020: Add AI Suggestion Columns to Audit Finding Tasks
-- Adds columns to store Liquid 8B triage suggestions

-- =============================================================================
-- ADD COLUMNS: Store AI-suggested labels and rationales
-- =============================================================================

ALTER TABLE archon_audit_finding_tasks 
    ADD COLUMN IF NOT EXISTS suggested_label TEXT,
    ADD COLUMN IF NOT EXISTS suggested_rationale TEXT;

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON COLUMN archon_audit_finding_tasks.suggested_label IS 
    'AI suggested decision: y=confirmed_issue, n=false_positive, i=intentional, w=wont_fix, s=skip';

COMMENT ON COLUMN archon_audit_finding_tasks.suggested_rationale IS 
    'AI explanation for the suggested decision (10-20 words)';

-- =============================================================================
-- VERIFY
-- =============================================================================

-- Check columns were added
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'archon_audit_finding_tasks' 
AND column_name IN ('suggested_label', 'suggested_rationale');
