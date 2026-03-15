-- Migration 017: Add P0 Exception Handling Audit Rules
-- Implements security-focused exception handling rules

-- =============================================================================
-- EXCEPTION HANDLING RULES (P0)
-- =============================================================================

INSERT INTO archon_audit_rules (
    rule_id,
    name,
    description,
    category,
    severity,
    rule_type,
    configuration,
    pattern,
    applies_to,
    is_builtin,
    is_active,
    implementation_type,
    rationale,
    remediation_guidance,
    example_violation,
    example_fix,
    "references",
    methodology_tags,
    applies_to_security_first,
    estimated_fix_time_minutes
) VALUES
-- Rule 1: broad-except (Enhanced)
(
    'broad-except',
    'Broad Exception Handler',
    'Detects overly broad exception handling that may hide errors',
    'security',
    'error',
    'pattern',
    '{"pattern": "except\\s*:", "exclude": "except\\s+\\w+\\s*:"}',
    'except\\s*:\s*$',
    ARRAY['function', 'method'],
    TRUE,
    TRUE,
    'pattern-static',
    'Bare "except:" catches all exceptions including KeyboardInterrupt and SystemExit, hiding critical errors and making debugging impossible.',
    'Catch specific exceptions only. Use "except Exception:" as minimum, or better, catch specific exception types like ValueError, KeyError, etc.',
    'try:\n    process_data()\nexcept:\n    pass',
    'try:\n    process_data()\nexcept ValueError as e:\n    logger.error(f"Invalid data: {e}")\n    raise',
    ARRAY['https://docs.python.org/3/library/exceptions.html', 'https://cwe.mitre.org/data/definitions/396.html'],
    '["security", "reliability", "debugging"]',
    TRUE,
    10
),

-- Rule 2: exception-not-logged
(
    'exception-not-logged',
    'Exception Not Logged',
    'Exceptions caught but not logged make debugging impossible',
    'security',
    'warning',
    'pattern',
    '{"pattern": "except.*\\n.*(?<!log)(?<!print)", "check_logging": true}',
    'except\\s+(\\w+)\\s*:\\s*\\n\\s*(?!.*(?:log|print|raise))',
    ARRAY['function', 'method'],
    TRUE,
    TRUE,
    'pattern-static',
    'Without logs, production errors are invisible and impossible to debug. Exceptions should always be logged or re-raised.',
    'Add logging to exception handlers. Even simple logging like logger.error(f"Processing failed: {e}") helps with debugging.',
    'try:\n    result = api_call()\nexcept APIError as e:\n    result = None',
    'try:\n    result = api_call()\nexcept APIError as e:\n    logger.error(f"API call failed: {e}")\n    result = None',
    ARRAY['https://docs.python.org/3/library/logging.html', 'https://cwe.mitre.org/data/definitions/778.html'],
    '["reliability", "debugging", "security"]',
    TRUE,
    5
),

-- Rule 3: async-exception-swallowed
(
    'async-exception-swallowed',
    'Async Exception Swallowed',
    'Async function calls with swallowed exceptions hide errors',
    'security',
    'error',
    'pattern',
    '{"pattern": "async.*try.*except.*pass", "async_context": true}',
    'async\\s+def\\s+\\w+.*try[^}]*except[^}]*pass',
    ARRAY['function'],
    TRUE,
    TRUE,
    'pattern-static',
    'Async errors need special handling. Swallowing async exceptions can cause silent failures in concurrent operations, leading to data corruption or hangs.',
    'Re-raise exceptions after logging, or use proper error handling with asyncio.gather(return_exceptions=True). Never silently pass on async errors.',
    'async def process():\n    try:\n        await risky_operation()\n    except:\n        pass',
    'async def process():\n    try:\n        await risky_operation()\n    except OperationFailed as e:\n        logger.error(f"Operation failed: {e}")\n        raise ProcessingError("Could not complete") from e',
    ARRAY['https://docs.python.org/3/library/asyncio.html', 'https://cwe.mitre.org/data/definitions/391.html'],
    '["security", "async", "reliability"]',
    TRUE,
    15
);

-- Update the broad-except rule to be more specific
UPDATE archon_audit_rules 
SET 
    name = 'Broad Exception Handler (Security Risk)',
    severity = 'error',
    applies_to_security_first = TRUE
WHERE rule_id = 'broad-except';

-- =============================================================================
-- CREATE INDEXES FOR PERFORMANCE
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_audit_findings_category_exception
ON archon_audit_findings(repo_id, severity) 
WHERE severity IN ('critical', 'error');

-- =============================================================================
-- ADD HELPER FUNCTION FOR EXCEPTION RULE CHECKING
-- =============================================================================

CREATE OR REPLACE FUNCTION check_exception_handling(
    p_source_code TEXT,
    p_language TEXT DEFAULT 'python'
) RETURNS TABLE(
    rule_id TEXT,
    severity TEXT,
    message TEXT,
    line_number INTEGER
) AS $$
DECLARE
    v_lines TEXT[];
    v_line TEXT;
    v_line_num INTEGER := 0;
    v_in_try_block BOOLEAN := FALSE;
    v_try_start INTEGER := 0;
    v_has_specific_except BOOLEAN := FALSE;
    v_has_logging BOOLEAN := FALSE;
    v_is_async BOOLEAN := FALSE;
BEGIN
    -- Split source into lines
    v_lines := string_to_array(p_source_code, E'\\n');
    
    -- Check if this is an async function
    FOR v_line IN SELECT unnest(v_lines) LOOP
        v_line_num := v_line_num + 1;
        IF v_line ~ '^\\s*async\\s+def\\s+' THEN
            v_is_async := TRUE;
            EXIT;
        END IF;
    END LOOP;
    
    -- Reset for main analysis
    v_line_num := 0;
    
    FOR v_line IN SELECT unnest(v_lines) LOOP
        v_line_num := v_line_num + 1;
        
        -- Detect try block
        IF v_line ~ '^\\s*try\\s*:' THEN
            v_in_try_block := TRUE;
            v_try_start := v_line_num;
            v_has_specific_except := FALSE;
            v_has_logging := FALSE;
        
        -- Detect except block
        ELSIF v_in_try_block AND v_line ~ '^\\s*except\\s*:' THEN
            -- Check for specific exception
            IF v_line ~ 'except\\s+\\w+\\s*:' THEN
                v_has_specific_except := TRUE;
            END IF;
            
            -- Check if broad except
            IF v_line ~ '^\\s*except\\s*:' AND NOT v_has_specific_except THEN
                rule_id := 'broad-except';
                severity := 'error';
                message := 'Broad exception handler at line ' || v_line_num || ': use specific exceptions';
                line_number := v_line_num;
                RETURN NEXT;
            END IF;
            
        -- Check for logging in except block
        ELSIF v_in_try_block AND v_line ~ '^\\s*except' THEN
            -- Look ahead for logging in the next few lines
            DECLARE
                v_lookahead INTEGER;
                v_check_line TEXT;
            BEGIN
                FOR v_lookahead IN 1..5 LOOP
                    IF v_line_num + v_lookahead <= array_length(v_lines, 1) THEN
                        v_check_line := v_lines[v_line_num + v_lookahead];
                        IF v_check_line ~ '(log|print|logger)' THEN
                            v_has_logging := TRUE;
                            EXIT;
                        END IF;
                        -- Exit if we hit another except or end of block
                        IF v_check_line ~ '^\\s*(except|finally|class|def)\\s*' THEN
                            EXIT;
                        END IF;
                    END IF;
                END LOOP;
            END;
            
            IF NOT v_has_logging THEN
                rule_id := 'exception-not-logged';
                severity := 'warning';
                message := 'Exception handler at line ' || v_line_num || ' does not log the error';
                line_number := v_line_num;
                RETURN NEXT;
            END IF;
            
            -- Check for async exception swallowing
            IF v_is_async AND v_line ~ 'except' AND v_line ~ 'pass' THEN
                rule_id := 'async-exception-swallowed';
                severity := 'error';
                message := 'Async function at line ' || v_try_start || ' swallows exceptions - security risk';
                line_number := v_try_start;
                RETURN NEXT;
            END IF;
            
        -- Detect end of try/except block
        ELSIF v_in_try_block AND (v_line ~ '^\\s*(class|def)\\s+' OR v_line ~ '^[^\\s]') THEN
            v_in_try_block := FALSE;
        END IF;
    END LOOP;
    
    RETURN;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- UPDATE AUDIT_SUMMARY VIEW TO INCLUDE EXCEPTION FINDINGS
-- =============================================================================

CREATE OR REPLACE VIEW archon_audit_summary_exception_focus AS
SELECT 
    r.id AS repo_id,
    r.name AS repo_name,
    COUNT(DISTINCT f.id) AS total_exception_findings,
    COUNT(DISTINCT CASE WHEN f.severity = 'critical' AND f2.category = 'security' THEN f.id END) AS critical_security_exceptions,
    COUNT(DISTINCT CASE WHEN f2.rule_id = 'broad-except' THEN f.id END) AS broad_except_count,
    COUNT(DISTINCT CASE WHEN f2.rule_id = 'exception-not-logged' THEN f.id END) AS not_logged_count,
    COUNT(DISTINCT CASE WHEN f2.rule_id = 'async-exception-swallowed' THEN f.id END) AS async_swallowed_count,
    COUNT(DISTINCT f.file_path) AS files_with_exceptions,
    ARRAY_AGG(DISTINCT f.file_path) FILTER (WHERE f.severity IN ('critical', 'error')) AS exception_hotspots
FROM archon_code_repos r
LEFT JOIN archon_audit_findings f ON f.repo_id = r.id AND f.status = 'open'
LEFT JOIN archon_audit_rules f2 ON f2.id = f.rule_id
WHERE f2.category = 'security' OR f2.rule_id IN ('broad-except', 'exception-not-logged', 'async-exception-swallowed')
GROUP BY r.id, r.name;

-- =============================================================================
-- ADD COMMENTS
-- =============================================================================

COMMENT ON FUNCTION check_exception_handling IS 'Analyzes source code for exception handling anti-patterns';
COMMENT ON VIEW archon_audit_summary_exception_focus IS 'Summary of exception handling violations per repository';

-- =============================================================================
-- MIGRATION TRACKING
-- =============================================================================

INSERT INTO archon_migrations (version, migration_name, applied_at)
VALUES ('017', 'Add exception handling rules (P0)', NOW())
ON CONFLICT (version, migration_name) DO NOTHING;

COMMIT;
