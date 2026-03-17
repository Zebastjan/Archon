-- Migration 022: Semgrep Integration and Meta-Audit System
-- Replaces regex-based audit with Semgrep AST-aware analysis
-- Adds triage memory and false negative tracking for continuous improvement

-- =============================================================================
-- SEMGREP FINDINGS TABLE
-- Fresh start for Semgrep-based audits (separate from old archon_audit_findings)
-- =============================================================================

CREATE TABLE IF NOT EXISTS archon_semgrep_findings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Repository reference
    repo_id UUID REFERENCES archon_code_repos(id) ON DELETE CASCADE,
    
    -- Semgrep-specific fields
    semgrep_check_id TEXT NOT NULL,      -- e.g., "python.lang.security.audit.eval-detected"
    semgrep_rule_url TEXT,                -- Link to rule documentation
    
    -- Finding details
    message TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('INFO', 'WARNING', 'ERROR')),
    confidence TEXT DEFAULT 'medium',     -- Semgrep confidence level
    
    -- Location
    file_path TEXT NOT NULL,
    line_start INTEGER,
    line_end INTEGER,
    column_start INTEGER,
    column_end INTEGER,
    
    -- Code context
    code_snippet TEXT,
    
    -- Metavariables (captured pattern variables)
    metavariables JSONB DEFAULT '{}',
    
    -- Data flow info (for taint rules)
    data_flow JSONB DEFAULT '{}',
    
    -- Audit tracking
    status TEXT DEFAULT 'open' CHECK (status IN ('open', 'triaged', 'suppressed')),
    
    -- Run reference
    audit_run_id UUID REFERENCES archon_audit_runs(id) ON DELETE SET NULL,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_semgrep_findings_repo ON archon_semgrep_findings(repo_id);
CREATE INDEX idx_semgrep_findings_check_id ON archon_semgrep_findings(semgrep_check_id);
CREATE INDEX idx_semgrep_findings_status ON archon_semgrep_findings(status);
CREATE INDEX idx_semgrep_findings_file ON archon_semgrep_findings(file_path);
CREATE INDEX idx_semgrep_findings_run ON archon_semgrep_findings(audit_run_id);

-- =============================================================================
-- TRIAGE MEMORY: Store pattern -> decision mappings
-- This is the core of the "meta-audit" system
-- =============================================================================

CREATE TABLE IF NOT EXISTS archon_audit_triage_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- What triggered this triage
    check_id TEXT NOT NULL,              -- Semgrep check_id or rule_id
    repo_id UUID REFERENCES archon_code_repos(id) ON DELETE CASCADE,
    
    -- The pattern that was identified
    -- Store multiple ways to match:
    pattern_type TEXT NOT NULL CHECK (pattern_type IN (
        'exact_code',        -- Exact code match (rarely used)
        'ast_pattern',       -- Abstract syntax tree pattern
        'semantic_hash',     -- Embedding-based similarity
        'call_chain',        -- Function call pattern
        'file_pattern',      -- File path pattern
        'context_aware'      -- Complex context-dependent pattern
    )),
    
    pattern_value TEXT NOT NULL,         -- The actual pattern
    pattern_embedding VECTOR(1024),      -- For semantic similarity
    
    -- The decision made
    decision TEXT NOT NULL CHECK (decision IN (
        'confirmed_issue',   -- Real bug, needs fix
        'intentional',       -- Valid by design
        'false_positive',    -- Tool misfired
        'wont_fix'          -- Valid but accepted tech debt
    )),
    
    -- Why this decision was made
    decision_rationale TEXT NOT NULL,
    
    -- Context that informed the decision
    surrounding_code TEXT,               -- Code around the finding
    call_context TEXT,                   -- Who calls this code
    
    -- Confidence metrics
    confidence_score DECIMAL(3,2),       -- 0.0 to 1.0
    reviewer_experience TEXT,            -- Who reviewed it
    
    -- Link to the specific finding
    original_finding_id UUID,
    
    -- Hit tracking
    times_applied INTEGER DEFAULT 1,     -- How many times this pattern was matched
    last_applied_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Validation tracking (for meta-audit)
    was_validated BOOLEAN DEFAULT FALSE, -- Did we verify this was correct?
    validation_result TEXT CHECK (validation_result IN ('correct', 'incorrect', 'uncertain')),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_triage_memory_check_id ON archon_audit_triage_memory(check_id);
CREATE INDEX idx_triage_memory_pattern ON archon_audit_triage_memory(pattern_type, pattern_value);
CREATE INDEX idx_triage_memory_decision ON archon_audit_triage_memory(decision);
CREATE INDEX idx_triage_memory_embedding ON archon_audit_triage_memory 
    USING hnsw (pattern_embedding vector_cosine_ops);

-- =============================================================================
-- FALSE NEGATIVE LOG
-- Track bugs that slipped past the audit (meta-audit)
-- =============================================================================

CREATE TABLE IF NOT EXISTS archon_audit_false_negatives (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    repo_id UUID REFERENCES archon_code_repos(id) ON DELETE CASCADE,
    
    -- The bug that was missed
    bug_type TEXT NOT NULL,              -- e.g., "race_condition", "null_deref"
    bug_description TEXT NOT NULL,
    
    -- Where it occurred
    file_path TEXT NOT NULL,
    line_start INTEGER,
    line_end INTEGER,
    code_snippet TEXT,
    
    -- When it was discovered
    discovered_at TIMESTAMPTZ DEFAULT NOW(),
    discovered_by TEXT,                  -- Who found it
    discovery_method TEXT,               -- e.g., "production_bug", "manual_review", "other_tool"
    
    -- Link to fix
    fix_commit_sha TEXT,
    fix_pr_number INTEGER,
    
    -- Analysis: Why was this missed?
    root_cause TEXT,                     -- Human analysis of why audit missed it
    
    -- Could we have caught it?
    would_semgrep_catch BOOLEAN,         -- If we re-run semgrep now, does it flag?
    semgrep_rules_that_would_catch TEXT[], -- Which rules would have caught it?
    
    -- Action items
    action_taken TEXT,                   -- What we did about it
    new_rule_created BOOLEAN DEFAULT FALSE,
    new_rule_id TEXT,
    
    -- Tracking
    audit_run_at TIMESTAMPTZ,            -- When we last audited before the bug
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_false_negatives_repo ON archon_audit_false_negatives(repo_id);
CREATE INDEX idx_false_negatives_type ON archon_audit_false_negatives(bug_type);
CREATE INDEX idx_false_negatives_discovered ON archon_audit_false_negatives(discovered_at);

-- =============================================================================
-- RULE QUALITY METRICS
-- Track how well each rule/check is performing
-- =============================================================================

CREATE TABLE IF NOT EXISTS archon_audit_rule_quality (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    check_id TEXT NOT NULL UNIQUE,       -- Semgrep check_id
    
    -- Stats
    total_findings INTEGER DEFAULT 0,
    confirmed_issues INTEGER DEFAULT 0,
    false_positives INTEGER DEFAULT 0,
    intentional_count INTEGER DEFAULT 0,
    wont_fix_count INTEGER DEFAULT 0,
    
    -- Calculated metrics
    precision DECIMAL(5,4),              -- confirmed / total
    false_positive_rate DECIMAL(5,4),    -- fp / total
    
    -- Trending
    last_audit_at TIMESTAMPTZ,
    trend_direction TEXT CHECK (trend_direction IN ('improving', 'degrading', 'stable')),
    
    -- Recommendations
    should_disable BOOLEAN DEFAULT FALSE,
    disable_reason TEXT,
    
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- SEMGREP CONFIGURATION
-- Track which rulesets we use per repo
-- =============================================================================

CREATE TABLE IF NOT EXISTS archon_semgrep_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    repo_id UUID REFERENCES archon_code_repos(id) ON DELETE CASCADE,
    
    -- Configuration
    rulesets TEXT[] DEFAULT ARRAY['p/security-audit', 'p/owasp-top-ten', 'p/cwe-top-25'],
    custom_rules_path TEXT,              -- Path to custom semgrep rules
    exclude_patterns TEXT[] DEFAULT ARRAY['tests/', 'test/', '*_test.py', '*.test.ts'],
    
    -- Suppression settings
    nosemgrep_ignored_rules TEXT[],      -- Rules we ignore via nosemgrep
    file_path_ignores TEXT[],            -- Files/paths to exclude
    
    -- Runtime settings
    max_file_size_kb INTEGER DEFAULT 1024,
    timeout_seconds INTEGER DEFAULT 300,
    
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(repo_id)
);

-- =============================================================================
-- FUNCTIONS
-- =============================================================================

-- Function: Find similar triage decisions using semantic search
CREATE OR REPLACE FUNCTION find_similar_triage_decisions(
    p_check_id TEXT,
    p_code_embedding VECTOR(1024),
    p_similarity_threshold DECIMAL(3,2) DEFAULT 0.85
)
RETURNS TABLE (
    decision TEXT,
    decision_rationale TEXT,
    confidence_score DECIMAL(3,2),
    similarity DECIMAL(5,4)
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        tm.decision,
        tm.decision_rationale,
        tm.confidence_score,
        (1 - (tm.pattern_embedding <=> p_code_embedding))::DECIMAL(5,4) as similarity
    FROM archon_audit_triage_memory tm
    WHERE tm.check_id = p_check_id
    AND (1 - (tm.pattern_embedding <=> p_code_embedding)) >= p_similarity_threshold
    ORDER BY similarity DESC
    LIMIT 5;
END;
$$ LANGUAGE plpgsql;

-- Function: Record a false negative (bug that slipped past audit)
CREATE OR REPLACE FUNCTION record_false_negative(
    p_repo_id UUID,
    p_bug_type TEXT,
    p_bug_description TEXT,
    p_file_path TEXT,
    p_discovered_by TEXT DEFAULT 'manual',
    p_root_cause TEXT DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    v_id UUID;
BEGIN
    INSERT INTO archon_audit_false_negatives (
        repo_id,
        bug_type,
        bug_description,
        file_path,
        discovered_by,
        discovery_method,
        root_cause
    ) VALUES (
        p_repo_id,
        p_bug_type,
        p_bug_description,
        p_file_path,
        p_discovered_by,
        'manual_review',
        p_root_cause
    )
    RETURNING id INTO v_id;
    
    RETURN v_id;
END;
$$ LANGUAGE plpgsql;

-- Function: Update rule quality metrics
CREATE OR REPLACE FUNCTION update_rule_quality_metrics(
    p_check_id TEXT
)
RETURNS VOID AS $$
DECLARE
    v_total INTEGER;
    v_confirmed INTEGER;
    v_fp INTEGER;
    v_precision DECIMAL(5,4);
    v_fp_rate DECIMAL(5,4);
BEGIN
    -- Count findings from semgrep_findings joined with triage
    SELECT 
        COUNT(*),
        COUNT(*) FILTER (WHERE tm.decision = 'confirmed_issue'),
        COUNT(*) FILTER (WHERE tm.decision = 'false_positive')
    INTO v_total, v_confirmed, v_fp
    FROM archon_semgrep_findings sf
    LEFT JOIN archon_audit_triage_memory tm 
        ON sf.semgrep_check_id = tm.check_id
        AND sf.file_path = split_part(tm.surrounding_code, ':', 1)
    WHERE sf.semgrep_check_id = p_check_id;
    
    -- Calculate metrics
    IF v_total > 0 THEN
        v_precision := v_confirmed::DECIMAL / v_total;
        v_fp_rate := v_fp::DECIMAL / v_total;
    ELSE
        v_precision := 0;
        v_fp_rate := 0;
    END IF;
    
    -- Update or insert
    INSERT INTO archon_audit_rule_quality (
        check_id,
        total_findings,
        confirmed_issues,
        false_positives,
        precision,
        false_positive_rate,
        last_audit_at
    ) VALUES (
        p_check_id,
        v_total,
        v_confirmed,
        v_fp,
        v_precision,
        v_fp_rate,
        NOW()
    )
    ON CONFLICT (check_id) DO UPDATE SET
        total_findings = EXCLUDED.total_findings,
        confirmed_issues = EXCLUDED.confirmed_issues,
        false_positives = EXCLUDED.false_positives,
        precision = EXCLUDED.precision,
        false_positive_rate = EXCLUDED.false_positive_rate,
        last_audit_at = EXCLUDED.last_audit_at,
        updated_at = NOW();
END;
$$ LANGUAGE plpgsql;

-- Function: Get triage suggestion for a finding
CREATE OR REPLACE FUNCTION get_triage_suggestion(
    p_finding_id UUID
)
RETURNS TABLE (
    suggested_decision TEXT,
    confidence DECIMAL(5,4),
    similar_cases INTEGER,
    rationale TEXT
) AS $$
DECLARE
    v_check_id TEXT;
    v_embedding VECTOR(1024);
BEGIN
    -- Get finding details
    SELECT semgrep_check_id INTO v_check_id
    FROM archon_semgrep_findings
    WHERE id = p_finding_id;
    
    IF v_check_id IS NULL THEN
        RETURN;
    END IF;
    
    -- Note: This function assumes the embedding is passed or computed elsewhere
    -- For now, return a placeholder that can be enhanced
    RETURN QUERY
    SELECT 
        mode() WITHIN GROUP (ORDER BY tm.decision) as suggested_decision,
        AVG(tm.confidence_score)::DECIMAL(5,4) as confidence,
        COUNT(*)::INTEGER as similar_cases,
        'Based on ' || COUNT(*) || ' similar previously triaged patterns' as rationale
    FROM archon_audit_triage_memory tm
    WHERE tm.check_id = v_check_id
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- TRIGGERS
-- =============================================================================

CREATE OR REPLACE FUNCTION update_semgrep_finding_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_semgrep_finding_timestamp
    BEFORE UPDATE ON archon_semgrep_findings
    FOR EACH ROW
    EXECUTE FUNCTION update_semgrep_finding_timestamp();

CREATE OR REPLACE FUNCTION update_triage_memory_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    NEW.last_applied_at = NOW();
    NEW.times_applied = NEW.times_applied + 1;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_triage_memory_timestamp
    BEFORE UPDATE ON archon_audit_triage_memory
    FOR EACH ROW
    EXECUTE FUNCTION update_triage_memory_timestamp();

-- =============================================================================
-- VIEWS
-- =============================================================================

-- View: Findings ready for review with triage suggestions
CREATE OR REPLACE VIEW archon_semgrep_findings_for_review AS
SELECT 
    sf.*,
    repo.name as repo_name,
    (SELECT suggested_decision FROM get_triage_suggestion(sf.id)) as suggested_decision,
    (SELECT confidence FROM get_triage_suggestion(sf.id)) as suggestion_confidence
FROM archon_semgrep_findings sf
JOIN archon_code_repos repo ON sf.repo_id = repo.id
WHERE sf.status = 'open'
ORDER BY sf.severity DESC, sf.created_at;

-- View: Rule quality summary
CREATE OR REPLACE VIEW archon_rule_quality_summary AS
SELECT 
    check_id,
    total_findings,
    confirmed_issues,
    false_positives,
    ROUND(precision * 100, 2) as precision_pct,
    ROUND(false_positive_rate * 100, 2) as fp_rate_pct,
    CASE 
        WHEN should_disable THEN 'DISABLE'
        WHEN false_positive_rate > 0.5 THEN 'REVIEW'
        WHEN precision > 0.7 THEN 'GOOD'
        ELSE 'MONITOR'
    END as recommendation,
    last_audit_at
FROM archon_audit_rule_quality
ORDER BY false_positive_rate DESC;

-- View: False negative analysis
CREATE OR REPLACE VIEW archon_false_negative_analysis AS
SELECT 
    fn.*,
    repo.name as repo_name,
    CASE
        WHEN would_semgrep_catch IS NULL THEN 'not_analyzed'
        WHEN would_semgrep_catch THEN 'would_catch_now'
        ELSE 'still_missing'
    END as current_status
FROM archon_audit_false_negatives fn
JOIN archon_code_repos repo ON fn.repo_id = repo.id
ORDER BY fn.discovered_at DESC;

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON TABLE archon_semgrep_findings IS 
    'Semgrep audit findings - AST-aware pattern matching results. Separate from legacy archon_audit_findings table.';

COMMENT ON TABLE archon_audit_triage_memory IS 
    'Stores pattern -> decision mappings for intelligent triage suggestions. Core of the meta-audit system.';

COMMENT ON TABLE archon_audit_false_negatives IS 
    'Tracks bugs that slipped past audits. Critical for identifying blind spots and improving rules.';

COMMENT ON TABLE archon_audit_rule_quality IS 
    'Tracks precision and false positive rates per rule to guide rule selection and tuning.';

-- =============================================================================
-- MIGRATION TRACKING
-- =============================================================================

INSERT INTO archon_migrations (version, migration_name, applied_at)
VALUES ('022', 'Semgrep integration and meta-audit system', NOW())
ON CONFLICT (version) DO NOTHING;
