-- Add confidence scoring and detailed issue analysis columns
-- Migration 021: Enhanced triage data structure

ALTER TABLE archon_audit_finding_tasks
ADD COLUMN confidence_score FLOAT,
ADD COLUMN investigation_level INTEGER DEFAULT 1, -- 1=initial, 2=tool-assisted
ADD COLUMN issue_problem TEXT,           -- What specifically is wrong
ADD COLUMN issue_impact TEXT,            -- Why this matters
ADD COLUMN issue_evidence TEXT,          -- Supporting code patterns
ADD COLUMN investigation_path JSON;       -- Track which tools were used

-- Add index for filtering by confidence
CREATE INDEX idx_audit_finding_tasks_confidence ON archon_audit_finding_tasks(confidence_score) WHERE confidence_score IS NOT NULL;

-- Add index for investigation level
CREATE INDEX idx_audit_finding_tasks_investigation ON archon_audit_finding_tasks(investigation_level);
