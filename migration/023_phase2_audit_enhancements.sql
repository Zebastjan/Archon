-- Migration 023: Phase 2 Audit Enhancements
-- Coverage integration, methodology config, and multi-source findings

-- =============================================================================
-- ADD SOURCE COLUMN TO FINDINGS TABLE
-- =============================================================================

ALTER TABLE archon_semgrep_findings 
ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'semgrep';

-- Create index for source filtering
CREATE INDEX IF NOT EXISTS idx_semgrep_findings_source 
ON archon_semgrep_findings(source);

-- Update existing records
UPDATE archon_semgrep_findings 
SET source = 'semgrep' 
WHERE source IS NULL;

-- =============================================================================
-- ADD METHODOLOGY CONFIG TO REPOS
-- =============================================================================

ALTER TABLE archon_code_repos 
ADD COLUMN IF NOT EXISTS methodology JSONB DEFAULT '{}'::jsonb;

-- Add index for methodology queries
CREATE INDEX IF NOT EXISTS idx_code_repos_methodology 
ON archon_code_repos USING GIN(methodology);

-- =============================================================================
-- ADD COVERAGE THRESHOLD CONFIG
-- =============================================================================

ALTER TABLE archon_code_repos 
ADD COLUMN IF NOT EXISTS coverage_threshold INTEGER DEFAULT 80;

-- =============================================================================
-- CREATE AUDIT SOURCES ENUM/VALIDATION
-- =============================================================================

-- Add constraint to validate source values
-- Note: Using check constraint instead of enum for flexibility
ALTER TABLE archon_semgrep_findings 
ADD CONSTRAINT valid_source_values 
CHECK (source IN (
    'semgrep',           -- Original Semgrep findings
    'pytest-cov',        -- Python coverage
    'c8',                -- TypeScript/JavaScript coverage
    'companion-check',   -- Test companion file checks
    'nim-tree-sitter-audit', -- Nim audit adapter
    'semantic-drift'     -- Future: knowledge graph drift detection
));

-- =============================================================================
-- ADD AUDIT CONFIG TABLE (for repo-specific settings)
-- =============================================================================

CREATE TABLE IF NOT EXISTS archon_audit_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repo_id UUID REFERENCES archon_code_repos(id) ON DELETE CASCADE,
    
    -- Coverage settings
    coverage_enabled BOOLEAN DEFAULT true,
    coverage_threshold INTEGER DEFAULT 80,
    coverage_source TEXT DEFAULT 'auto', -- 'pytest-cov', 'c8', or 'auto'
    
    -- Methodology enforcement
    enforce_docstrings BOOLEAN DEFAULT true,
    enforce_test_companions BOOLEAN DEFAULT true,
    enforce_coverage BOOLEAN DEFAULT true,
    
    -- Custom rules
    custom_rules_path TEXT,
    disabled_rules TEXT[] DEFAULT '{}',
    
    -- Per-language settings
    python_enabled BOOLEAN DEFAULT true,
    typescript_enabled BOOLEAN DEFAULT true,
    javascript_enabled BOOLEAN DEFAULT true,
    nim_enabled BOOLEAN DEFAULT false, -- Opt-in for now
    
    -- Methodology config (JSONB for flexibility)
    methodology JSONB DEFAULT '{}'::jsonb,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(repo_id)
);

CREATE INDEX idx_audit_config_repo ON archon_audit_config(repo_id);

-- Trigger to update timestamp
CREATE OR REPLACE FUNCTION update_audit_config_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_audit_config_timestamp
    BEFORE UPDATE ON archon_audit_config
    FOR EACH ROW
    EXECUTE FUNCTION update_audit_config_timestamp();

-- =============================================================================
-- FUNCTION: Get audit config for repo (creates default if missing)
-- =============================================================================

CREATE OR REPLACE FUNCTION get_audit_config(p_repo_id UUID)
RETURNS JSONB AS $$
DECLARE
    v_config JSONB;
BEGIN
    -- Get or create config
    INSERT INTO archon_audit_config (repo_id)
    VALUES (p_repo_id)
    ON CONFLICT (repo_id) DO NOTHING;
    
    SELECT jsonb_build_object(
        'coverage_enabled', coverage_enabled,
        'coverage_threshold', coverage_threshold,
        'coverage_source', coverage_source,
        'enforce_docstrings', enforce_docstrings,
        'enforce_test_companions', enforce_test_companions,
        'enforce_coverage', enforce_coverage,
        'custom_rules_path', custom_rules_path,
        'disabled_rules', disabled_rules,
        'python_enabled', python_enabled,
        'typescript_enabled', typescript_enabled,
        'javascript_enabled', javascript_enabled,
        'nim_enabled', nim_enabled,
        'methodology', COALESCE(methodology, '{}'::jsonb)
    ) INTO v_config
    FROM archon_audit_config
    WHERE repo_id = p_repo_id;
    
    RETURN v_config;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- UPDATE EXISTING REPOS WITH DEFAULT METHODOLOGY
-- =============================================================================

UPDATE archon_code_repos 
SET methodology = jsonb_build_object(
    'primary', 'tdd',
    'enforce', jsonb_build_array('coverage', 'docstrings'),
    'coverage_threshold', 80,
    'docstring_required', jsonb_build_array('public', 'exported'),
    'test_companion_pattern', 'test_{module}.py'
)
WHERE methodology = '{}'::jsonb OR methodology IS NULL;

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON COLUMN archon_semgrep_findings.source IS 
    'Source of the finding: semgrep, pytest-cov, c8, companion-check, nim-tree-sitter-audit, etc.';

COMMENT ON COLUMN archon_code_repos.methodology IS 
    'JSONB configuration for audit methodology (tdd, ddd, etc.)';

COMMENT ON COLUMN archon_code_repos.coverage_threshold IS 
    'Minimum code coverage percentage required (default 80%)';

COMMENT ON TABLE archon_audit_config IS 
    'Per-repository audit configuration and rule enablement';

-- =============================================================================
-- MIGRATION TRACKING
-- =============================================================================

INSERT INTO archon_migrations (version, migration_name, applied_at)
VALUES ('023', 'Phase 2 audit enhancements - coverage and methodology', NOW())
ON CONFLICT (version) DO NOTHING;
