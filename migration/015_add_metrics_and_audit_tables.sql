-- Migration 015: Add metrics tracking and audit rules tables
-- Part of Phase 2: Metrics Tracking and Audit Rules

-- =============================================================================
-- METRICS TRACKING TABLES
-- =============================================================================

-- Table for storing code metrics snapshots
CREATE TABLE IF NOT EXISTS archon_code_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repo_id UUID REFERENCES archon_code_repos(id) ON DELETE CASCADE,
    
    -- Snapshot identification
    snapshot_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    commit_sha TEXT,
    branch_name TEXT,
    
    -- Code size metrics
    total_files INTEGER DEFAULT 0,
    total_lines_of_code INTEGER DEFAULT 0,
    total_lines_of_comments INTEGER DEFAULT 0,
    total_blank_lines INTEGER DEFAULT 0,
    
    -- Entity counts
    total_functions INTEGER DEFAULT 0,
    total_classes INTEGER DEFAULT 0,
    total_modules INTEGER DEFAULT 0,
    total_interfaces INTEGER DEFAULT 0,
    total_enums INTEGER DEFAULT 0,
    total_variables INTEGER DEFAULT 0,
    total_imports INTEGER DEFAULT 0,
    
    -- Complexity metrics
    avg_cyclomatic_complexity DECIMAL(5,2),
    max_cyclomatic_complexity INTEGER,
    avg_function_length INTEGER,
    max_function_length INTEGER,
    
    -- Quality metrics
    code_to_comment_ratio DECIMAL(5,2),
    duplicate_lines INTEGER DEFAULT 0,
    todo_count INTEGER DEFAULT 0,
    fixme_count INTEGER DEFAULT 0,
    deprecated_count INTEGER DEFAULT 0,
    
    -- Health score (0-100)
    health_score INTEGER CHECK (health_score >= 0 AND health_score <= 100),
    
    -- Raw metrics JSON for extensibility
    raw_metrics JSONB DEFAULT '{}',
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for metrics table
CREATE INDEX IF NOT EXISTS idx_code_metrics_repo ON archon_code_metrics(repo_id);
CREATE INDEX IF NOT EXISTS idx_code_metrics_snapshot ON archon_code_metrics(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_code_metrics_branch ON archon_code_metrics(branch_name);
CREATE INDEX IF NOT EXISTS idx_code_metrics_health ON archon_code_metrics(health_score);

-- Table for file-level metrics
CREATE TABLE IF NOT EXISTS archon_file_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repo_id UUID REFERENCES archon_code_repos(id) ON DELETE CASCADE,
    entity_id UUID REFERENCES archon_code_entities(id) ON DELETE CASCADE,
    
    -- File identification
    file_path TEXT NOT NULL,
    language TEXT,
    
    -- Size metrics
    lines_of_code INTEGER DEFAULT 0,
    lines_of_comments INTEGER DEFAULT 0,
    blank_lines INTEGER DEFAULT 0,
    
    -- Entity counts
    function_count INTEGER DEFAULT 0,
    class_count INTEGER DEFAULT 0,
    import_count INTEGER DEFAULT 0,
    
    -- Complexity
    cyclomatic_complexity INTEGER DEFAULT 0,
    max_nesting_depth INTEGER DEFAULT 0,
    
    -- Quality indicators
    todo_count INTEGER DEFAULT 0,
    fixme_count INTEGER DEFAULT 0,
    deprecated_count INTEGER DEFAULT 0,
    
    -- Change tracking
    last_modified TIMESTAMP WITH TIME ZONE,
    change_frequency INTEGER DEFAULT 0, -- Number of changes in last 30 days
    
    -- Snapshot reference
    snapshot_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for file metrics
CREATE INDEX IF NOT EXISTS idx_file_metrics_repo ON archon_file_metrics(repo_id);
CREATE INDEX IF NOT EXISTS idx_file_metrics_entity ON archon_file_metrics(entity_id);
CREATE INDEX IF NOT EXISTS idx_file_metrics_path ON archon_file_metrics(file_path);
CREATE INDEX IF NOT EXISTS idx_file_metrics_complexity ON archon_file_metrics(cyclomatic_complexity);
CREATE INDEX IF NOT EXISTS idx_file_metrics_snapshot ON archon_file_metrics(snapshot_date);

-- =============================================================================
-- AUDIT RULES TABLES
-- =============================================================================

-- Table for audit rule definitions
CREATE TABLE IF NOT EXISTS archon_audit_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Rule identification
    rule_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT NOT NULL, -- 'complexity', 'style', 'security', 'performance', 'maintainability'
    severity TEXT NOT NULL DEFAULT 'warning', -- 'info', 'warning', 'error', 'critical'
    
    -- Rule configuration
    rule_type TEXT NOT NULL, -- 'threshold', 'pattern', 'custom'
    configuration JSONB DEFAULT '{}',
    
    -- Threshold values (for threshold rules)
    threshold_min DECIMAL(10,2),
    threshold_max DECIMAL(10,2),
    
    -- Pattern matching (for pattern rules)
    pattern TEXT,
    
    -- Target entities
    applies_to TEXT[] DEFAULT ARRAY['function', 'class', 'method'], -- entity types
    languages TEXT[], -- NULL means all languages
    file_patterns TEXT[], -- glob patterns like "*.py", "src/**/*.js"
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    is_builtin BOOLEAN DEFAULT FALSE, -- Built-in rules cannot be deleted
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by TEXT DEFAULT 'system',
    
    -- Versioning
    version INTEGER DEFAULT 1
);

-- Indexes for audit rules
CREATE INDEX IF NOT EXISTS idx_audit_rules_category ON archon_audit_rules(category);
CREATE INDEX IF NOT EXISTS idx_audit_rules_severity ON archon_audit_rules(severity);
CREATE INDEX IF NOT EXISTS idx_audit_rules_active ON archon_audit_rules(is_active);
CREATE INDEX IF NOT EXISTS idx_audit_rules_type ON archon_audit_rules(rule_type);

-- Table for audit findings
CREATE TABLE IF NOT EXISTS archon_audit_findings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- References
    rule_id UUID REFERENCES archon_audit_rules(id) ON DELETE CASCADE,
    entity_id UUID REFERENCES archon_code_entities(id) ON DELETE CASCADE,
    repo_id UUID REFERENCES archon_code_repos(id) ON DELETE CASCADE,
    
    -- Finding details
    finding_type TEXT NOT NULL, -- 'violation', 'suggestion', 'info'
    severity TEXT NOT NULL, -- 'info', 'warning', 'error', 'critical'
    message TEXT NOT NULL,
    description TEXT,
    
    -- Location
    file_path TEXT,
    line_start INTEGER,
    line_end INTEGER,
    column_start INTEGER,
    column_end INTEGER,
    
    -- Code snippet
    code_snippet TEXT,
    suggested_fix TEXT,
    
    -- Status
    status TEXT DEFAULT 'open', -- 'open', 'acknowledged', 'resolved', 'false_positive'
    acknowledged_by TEXT,
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    resolution_note TEXT,
    
    -- Resolution tracking
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolved_by TEXT,
    
    -- Audit run reference
    audit_run_id UUID,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for audit findings
CREATE INDEX IF NOT EXISTS idx_audit_findings_rule ON archon_audit_findings(rule_id);
CREATE INDEX IF NOT EXISTS idx_audit_findings_entity ON archon_audit_findings(entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_findings_repo ON archon_audit_findings(repo_id);
CREATE INDEX IF NOT EXISTS idx_audit_findings_severity ON archon_audit_findings(severity);
CREATE INDEX IF NOT EXISTS idx_audit_findings_status ON archon_audit_findings(status);
CREATE INDEX IF NOT EXISTS idx_audit_findings_type ON archon_audit_findings(finding_type);
CREATE INDEX IF NOT EXISTS idx_audit_findings_audit_run ON archon_audit_findings(audit_run_id);

-- Table for audit runs
CREATE TABLE IF NOT EXISTS archon_audit_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Run identification
    repo_id UUID REFERENCES archon_code_repos(id) ON DELETE CASCADE,
    name TEXT,
    description TEXT,
    
    -- Status
    status TEXT DEFAULT 'pending', -- 'pending', 'running', 'completed', 'failed', 'cancelled'
    
    -- Configuration
    ruleset TEXT[], -- List of rule_ids to run, NULL means all active rules
    entity_filter JSONB, -- Optional filter for entities
    
    -- Progress tracking
    total_entities INTEGER DEFAULT 0,
    processed_entities INTEGER DEFAULT 0,
    findings_count INTEGER DEFAULT 0,
    
    -- Timing
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,
    
    -- Results summary
    summary JSONB DEFAULT '{}',
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by TEXT DEFAULT 'system'
);

-- Indexes for audit runs
CREATE INDEX IF NOT EXISTS idx_audit_runs_repo ON archon_audit_runs(repo_id);
CREATE INDEX IF NOT EXISTS idx_audit_runs_status ON archon_audit_runs(status);
CREATE INDEX IF NOT EXISTS idx_audit_runs_created ON archon_audit_runs(created_at);

-- =============================================================================
-- AUDIT RULES FUNCTIONS
-- =============================================================================

-- Function to calculate cyclomatic complexity for an entity
CREATE OR REPLACE FUNCTION calculate_cyclomatic_complexity(
    p_entity_id UUID
) RETURNS INTEGER AS $$
DECLARE
    v_complexity INTEGER := 1; -- Base complexity
    v_entity_type TEXT;
    v_source_code TEXT;
BEGIN
    -- Get entity details
    SELECT entity_type, source_code INTO v_entity_type, v_source_code
    FROM archon_code_entities
    WHERE id = p_entity_id;
    
    IF v_source_code IS NULL THEN
        RETURN 1;
    END IF;
    
    -- Count decision points (simple heuristic)
    -- This is a basic implementation; more sophisticated analysis can be done in Python
    v_complexity := v_complexity + 
        (LENGTH(v_source_code) - LENGTH(REPLACE(v_source_code, 'if ', ''))) / 3 +
        (LENGTH(v_source_code) - LENGTH(REPLACE(v_source_code, 'elif ', ''))) / 5 +
        (LENGTH(v_source_code) - LENGTH(REPLACE(v_source_code, 'else:', ''))) / 5 +
        (LENGTH(v_source_code) - LENGTH(REPLACE(v_source_code, 'for ', ''))) / 4 +
        (LENGTH(v_source_code) - LENGTH(REPLACE(v_source_code, 'while ', ''))) / 6 +
        (LENGTH(v_source_code) - LENGTH(REPLACE(v_source_code, 'except', ''))) / 6;
    
    RETURN GREATEST(1, v_complexity);
END;
$$ LANGUAGE plpgsql;

-- Function to check if entity violates a threshold rule
CREATE OR REPLACE FUNCTION check_threshold_rule(
    p_entity_id UUID,
    p_rule_id UUID
) RETURNS TABLE(
    is_violation BOOLEAN,
    message TEXT,
    severity TEXT
) AS $$
DECLARE
    v_entity_type TEXT;
    v_metric_value DECIMAL(10,2);
    v_threshold_min DECIMAL(10,2);
    v_threshold_max DECIMAL(10,2);
    v_severity TEXT;
    v_rule_name TEXT;
    v_applies_to TEXT[];
    v_config JSONB;
BEGIN
    -- Get rule details
    SELECT 
        r.threshold_min,
        r.threshold_max,
        r.severity,
        r.name,
        r.applies_to,
        r.configuration
    INTO v_threshold_min, v_threshold_max, v_severity, v_rule_name, v_applies_to, v_config
    FROM archon_audit_rules r
    WHERE r.id = p_rule_id AND r.is_active = TRUE;
    
    IF v_threshold_min IS NULL AND v_threshold_max IS NULL THEN
        RETURN QUERY SELECT FALSE, 'No thresholds defined', 'info'::TEXT;
        RETURN;
    END IF;

    -- Get entity type
    SELECT entity_type INTO v_entity_type
    FROM archon_code_entities
    WHERE id = p_entity_id;
    
    -- Check if rule applies to this entity type
    IF NOT (v_entity_type = ANY(v_applies_to)) THEN
        RETURN QUERY SELECT FALSE, 'Rule does not apply to entity type', 'info'::TEXT;
        RETURN;
    END IF;

    -- Get metric value based on rule configuration
    -- For now, we use cyclomatic complexity as the primary metric
    IF v_config->>'metric' = 'cyclomatic_complexity' OR v_config IS NULL THEN
        SELECT calculate_cyclomatic_complexity(p_entity_id) INTO v_metric_value;
    ELSIF v_config->>'metric' = 'function_length' THEN
        SELECT COALESCE(LENGTH(source_code) - LENGTH(REPLACE(source_code, E'\n', '')), 0)
        INTO v_metric_value
        FROM archon_code_entities
        WHERE id = p_entity_id;
    ELSE
        -- Default to complexity
        SELECT calculate_cyclomatic_complexity(p_entity_id) INTO v_metric_value;
    END IF;
    
    -- Check thresholds
    IF v_threshold_max IS NOT NULL AND v_metric_value > v_threshold_max THEN
        RETURN QUERY SELECT 
            TRUE, 
            format('%s: value %s exceeds maximum threshold %s', v_rule_name, v_metric_value, v_threshold_max),
            v_severity;
        RETURN;
    END IF;
    
    IF v_threshold_min IS NOT NULL AND v_metric_value < v_threshold_min THEN
        RETURN QUERY SELECT 
            TRUE,
            format('%s: value %s below minimum threshold %s', v_rule_name, v_metric_value, v_threshold_min),
            v_severity;
        RETURN;
    END IF;
    
    RETURN QUERY SELECT FALSE, 'Within thresholds', 'info'::TEXT;
END;
$$ LANGUAGE plpgsql;

-- Function to run audit on a repository
CREATE OR REPLACE FUNCTION run_audit(
    p_repo_id UUID,
    p_ruleset TEXT[] DEFAULT NULL
) RETURNS TABLE(
    findings_count INTEGER,
    run_id UUID
) AS $$
DECLARE
    v_run_id UUID;
    v_entity RECORD;
    v_rule RECORD;
    v_check_result RECORD;
    v_findings_count INTEGER := 0;
BEGIN
    -- Create audit run record
    INSERT INTO archon_audit_runs (
        repo_id,
        name,
        status,
        ruleset,
        started_at,
        total_entities
    ) VALUES (
        p_repo_id,
        'Audit run for repo ' || p_repo_id::TEXT,
        'running',
        p_ruleset,
        NOW(),
        (SELECT COUNT(*) FROM archon_code_entities WHERE repo_id = p_repo_id)
    ) RETURNING id INTO v_run_id;
    
    -- Get rules to check
    FOR v_rule IN 
        SELECT id, rule_id, name, severity
        FROM archon_audit_rules
        WHERE is_active = TRUE
        AND (p_ruleset IS NULL OR rule_id = ANY(p_ruleset))
    LOOP
        -- Check each entity against this rule
        FOR v_entity IN 
            SELECT id, entity_type, name, file_path, line_start, line_end
            FROM archon_code_entities
            WHERE repo_id = p_repo_id
        LOOP
            -- Check threshold rules
            IF EXISTS (SELECT 1 FROM archon_audit_rules WHERE id = v_rule.id AND rule_type = 'threshold') THEN
                SELECT * INTO v_check_result
                FROM check_threshold_rule(v_entity.id, v_rule.id);
                
                IF v_check_result.is_violation THEN
                    INSERT INTO archon_audit_findings (
                        rule_id,
                        entity_id,
                        repo_id,
                        finding_type,
                        severity,
                        message,
                        file_path,
                        line_start,
                        line_end,
                        audit_run_id
                    ) VALUES (
                        v_rule.id,
                        v_entity.id,
                        p_repo_id,
                        'violation',
                        v_check_result.severity,
                        v_check_result.message,
                        v_entity.file_path,
                        v_entity.line_start,
                        v_entity.line_end,
                        v_run_id
                    );
                    
                    v_findings_count := v_findings_count + 1;
                END IF;
            END IF;
        END LOOP;
    END LOOP;
    
    -- Update audit run
    UPDATE archon_audit_runs
    SET 
        status = 'completed',
        completed_at = NOW(),
        duration_seconds = EXTRACT(EPOCH FROM (NOW() - started_at))::INTEGER,
        findings_count = v_findings_count,
        summary = jsonb_build_object(
            'total_findings', v_findings_count,
            'completed_at', NOW()
        )
    WHERE id = v_run_id;
    
    RETURN QUERY SELECT v_findings_count, v_run_id;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- VIEWS
-- =============================================================================

-- View for audit summary by repository
CREATE OR REPLACE VIEW archon_audit_summary AS
SELECT 
    r.id AS repo_id,
    r.name AS repo_name,
    COUNT(DISTINCT f.id) AS total_findings,
    COUNT(DISTINCT CASE WHEN f.severity = 'critical' THEN f.id END) AS critical_count,
    COUNT(DISTINCT CASE WHEN f.severity = 'error' THEN f.id END) AS error_count,
    COUNT(DISTINCT CASE WHEN f.severity = 'warning' THEN f.id END) AS warning_count,
    COUNT(DISTINCT CASE WHEN f.severity = 'info' THEN f.id END) AS info_count,
    COUNT(DISTINCT CASE WHEN f.status = 'open' THEN f.id END) AS open_count,
    COUNT(DISTINCT CASE WHEN f.status = 'resolved' THEN f.id END) AS resolved_count,
    MAX(f.created_at) AS last_finding_date,
    MAX(ar.completed_at) AS last_audit_date
FROM archon_code_repos r
LEFT JOIN archon_audit_findings f ON f.repo_id = r.id
LEFT JOIN archon_audit_runs ar ON ar.repo_id = r.id AND ar.status = 'completed'
GROUP BY r.id, r.name;

-- View for metrics trends
CREATE OR REPLACE VIEW archon_metrics_trends AS
SELECT 
    m.repo_id,
    r.name AS repo_name,
    m.snapshot_date,
    m.branch_name,
    m.health_score,
    m.total_files,
    m.total_lines_of_code,
    m.avg_cyclomatic_complexity,
    m.code_to_comment_ratio,
    LAG(m.health_score) OVER (PARTITION BY m.repo_id ORDER BY m.snapshot_date) AS prev_health_score,
    m.health_score - COALESCE(LAG(m.health_score) OVER (PARTITION BY m.repo_id ORDER BY m.snapshot_date), m.health_score) AS health_score_change
FROM archon_code_metrics m
JOIN archon_code_repos r ON r.id = m.repo_id;

-- =============================================================================
-- INSERT DEFAULT AUDIT RULES
-- =============================================================================

INSERT INTO archon_audit_rules (
    rule_id, name, description, category, severity, rule_type, 
    configuration, threshold_max, applies_to, is_builtin
) VALUES
-- Complexity rules
('complexity-high', 'High Cyclomatic Complexity', 
 'Functions with cyclomatic complexity greater than 10 should be refactored',
 'complexity', 'warning', 'threshold',
 '{"metric": "cyclomatic_complexity"}', 10, 
 ARRAY['function', 'method'], TRUE),

('complexity-critical', 'Critical Cyclomatic Complexity',
 'Functions with cyclomatic complexity greater than 20 must be refactored',
 'complexity', 'error', 'threshold',
 '{"metric": "cyclomatic_complexity"}', 20,
 ARRAY['function', 'method'], TRUE),

('function-too-long', 'Function Too Long',
 'Functions longer than 50 lines should be split',
 'maintainability', 'warning', 'threshold',
 '{"metric": "function_length"}', 50,
 ARRAY['function', 'method'], TRUE),

('function-critically-long', 'Function Critically Long',
 'Functions longer than 100 lines must be refactored',
 'maintainability', 'error', 'threshold',
 '{"metric": "function_length"}', 100,
 ARRAY['function', 'method'], TRUE),

-- Style rules
('missing-docstring', 'Missing Docstring',
 'Public functions should have docstrings',
 'style', 'info', 'pattern',
 '{"pattern": "no_docstring"}', NULL,
 ARRAY['function', 'class', 'method'], TRUE)

ON CONFLICT (rule_id) DO NOTHING;

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON TABLE archon_code_metrics IS 'Stores code quality metrics snapshots for repositories';
COMMENT ON TABLE archon_file_metrics IS 'Stores file-level code metrics';
COMMENT ON TABLE archon_audit_rules IS 'Defines audit rules for code quality checks';
COMMENT ON TABLE archon_audit_findings IS 'Stores audit rule violations and findings';
COMMENT ON TABLE archon_audit_runs IS 'Tracks audit execution runs';

COMMENT ON COLUMN archon_audit_rules.rule_id IS 'Unique identifier for the rule (e.g., complexity-high)';
COMMENT ON COLUMN archon_audit_rules.configuration IS 'JSON configuration specific to rule type';
COMMENT ON COLUMN archon_audit_findings.finding_type IS 'Type of finding: violation, suggestion, or info';
COMMENT ON COLUMN archon_audit_findings.suggested_fix IS 'AI-generated or manual suggested fix for the issue';

-- =============================================================================
-- MIGRATION TRACKING
-- =============================================================================

INSERT INTO archon_migrations (version, migration_name, applied_at)
VALUES ('015', 'Add metrics and audit tables', NOW())
ON CONFLICT (version) DO NOTHING;

COMMIT;
