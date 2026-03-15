-- Migration 018: Add P1 Assertion Quality Audit Rules
-- Implements TDD-focused testing quality rules

-- =============================================================================
-- ASSERTION QUALITY RULES (P1)
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
    file_patterns,
    is_builtin,
    is_active,
    implementation_type,
    rationale,
    remediation_guidance,
    example_violation,
    example_fix,
    "references",
    methodology_tags,
    applies_to_tdd,
    estimated_fix_time_minutes
) VALUES
-- Rule 1: assert-missing-in-test
(
    'assert-missing-in-test',
    'Missing Assertions in Test',
    'Test functions without assertions verify nothing',
    'testing',
    'warning',
    'heuristic',
    '{"check": "has_assertions", "min_assertions": 1}',
    NULL,
    ARRAY['function', 'method'],
    ARRAY['%test%', '%spec%', 'test_*.py', '*_test.py', 'tests/**/*.py'],
    TRUE,
    TRUE,
    'heuristic-static',
    'Tests without assertions provide false confidence. They run and pass but verify no behavior. Every test should have at least one assertion that validates expected output.',
    'Add meaningful assertions. Use assertEqual, assertTrue, assertRaises, or framework-specific assertions to verify behavior.',
    'def test_process_data():\n    result = process_data(input)\n    # No assertion!',
    'def test_process_data():\n    result = process_data(input)\n    assertEqual(expected, result)\n    assertTrue(result.is_valid)',
    ARRAY['https://docs.pytest.org/en/stable/assert.html', 'https://testing.googleblog.com/2015/04/just-say-no-to-more-end-to-end-tests.html'],
    '["tdd", "testing", "quality"]',
    TRUE,
    5
),

-- Rule 2: assert-weak-boolean
(
    'assert-weak-boolean',
    'Weak Boolean Assertion',
    'Boolean assertions without context are weak and hard to debug',
    'testing',
    'info',
    'pattern',
    '{"pattern": "assertTrue\\(\\w+\\)", "require_context": true}',
    'assert(True|assertTrue)\\s*\\(\\s*\\w+\\s*\\)\\s*$',
    ARRAY['function', 'method'],
    ARRAY['%test%', '%spec%', 'test_*.py', '*_test.py'],
    TRUE,
    TRUE,
    'pattern-static',
    'Boolean assertions like assertTrue(result) fail with unhelpful messages. When they fail, you don''t know what the expected vs actual values were.',
    'Replace assertTrue(result) with assertEqual(expected, result) or add a descriptive message: assertTrue(result, f"Expected valid, got {result}").',
    'assertTrue(result)',
    'assertEqual(True, result)\n# or\nassertTrue(result, "Processing should return valid result")',
    ARRAY['https://docs.pytest.org/en/stable/how-to/assert.html'],
    '["tdd", "testing", "quality", "debugging"]',
    TRUE,
    3
),

-- Rule 3: assert-exception-not-tested
(
    'assert-exception-not-tested',
    'Exception Path Not Tested',
    'Functions that may throw exceptions should test error cases',
    'testing',
    'warning',
    'heuristic',
    '{"check": "exception_paths", "min_exception_tests": 1}',
    NULL,
    ARRAY['function'],
    ARRAY['%test%', '%spec%', 'test_*.py', '*_test.py'],
    TRUE,
    TRUE,
    'heuristic-static',
    'Exception paths are part of the API contract. If a function can raise ValueError, NotFoundError, etc., those paths should be tested to ensure error handling works correctly.',
    'Add test cases for error conditions using assertRaises or try/except in tests. Test both happy path and error paths.',
    'def test_process_valid_data():\n    result = process(valid_data)\n    assertEqual(expected, result)\n    # No test for invalid data!',
    'def test_process_valid_data():\n    result = process(valid_data)\n    assertEqual(expected, result)\n\ndef test_process_invalid_data_raises():\n    with assertRaises(ValueError):\n        process(invalid_data)',
    ARRAY['https://docs.python.org/3/library/unittest.html#unittest.TestCase.assertRaises'],
    '["tdd", "testing", "quality", "reliability"]',
    TRUE,
    10
),

-- Rule 4: assert-mock-not-verified (bonus)
(
    'assert-mock-not-verified',
    'Mock Not Verified',
    'Mock objects should verify they were called as expected',
    'testing',
    'warning',
    'pattern',
    '{"pattern": "Mock.*assert", "check_verification": true}',
    'Mock\\([^)]+\\)(?!.*assert_called)',
    ARRAY['function', 'method'],
    ARRAY['%test%', 'test_*.py', '*_test.py'],
    TRUE,
    TRUE,
    'heuristic-static',
    'Creating mocks without verifying they were called defeats the purpose of mocking. Mocks should assert that expected interactions occurred.',
    'Add mock verification: mock_obj.assert_called_once() or mock_obj.assert_called_with(expected_args).',
    'mock_api = Mock()\nprocess_data(mock_api)\n# No verification that api was called!',
    'mock_api = Mock()\nprocess_data(mock_api)\nmock_api.fetch.assert_called_once_with(expected_params)',
    ARRAY['https://docs.python.org/3/library/unittest.mock.html'],
    '["tdd", "testing", "quality"]',
    TRUE,
    5
),

-- Rule 5: assert-equality-on-floats (bonus)
(
    'assert-equality-on-floats',
    'Float Equality Assertion',
    'Direct float comparison is unreliable due to precision',
    'testing',
    'warning',
    'pattern',
    '{"pattern": "assertEqual.*float", "require_delta": true}',
    'assertEqual\\s*\\(.*[^a-zA-Z]float[^)]*\\)',
    ARRAY['function', 'method'],
    ARRAY['%test%', 'test_*.py', '*_test.py'],
    TRUE,
    TRUE,
    'pattern-static',
    'Floating point equality comparisons are unreliable due to IEEE 754 representation. 0.1 + 0.2 != 0.3 due to precision limits.',
    'Use assertAlmostEqual or assertEqual with a delta/rel_tol parameter for float comparisons.',
    'assertEqual(0.3, result)  # May fail!',
    'assertAlmostEqual(0.3, result, places=7)\n# or\nassertEqual(0.3, result, delta=0.0001)',
    ARRAY['https://docs.python.org/3/library/unittest.html#unittest.TestCase.assertAlmostEqual'],
    '["tdd", "testing", "quality"]',
    FALSE,
    3
);

-- =============================================================================
-- CREATE INDEX FOR TEST FILE PATTERN MATCHING
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_code_entities_test_files 
ON archon_code_entities(repo_id, file_path) 
WHERE file_path LIKE '%test%' OR file_path LIKE '%spec%';

-- =============================================================================
-- CREATE VIEW FOR TEST QUALITY SUMMARY
-- =============================================================================

CREATE OR REPLACE VIEW archon_test_quality_summary AS
SELECT 
    r.id AS repo_id,
    r.name AS repo_name,
    COUNT(DISTINCT e.id) AS total_test_entities,
    COUNT(DISTINCT CASE WHEN e.file_path LIKE '%test%' THEN e.id END) AS test_file_entities,
    COUNT(DISTINCT f.id) AS total_assertion_findings,
    COUNT(DISTINCT CASE WHEN f2.rule_id = 'assert-missing-in-test' THEN f.id END) AS missing_assertions,
    COUNT(DISTINCT CASE WHEN f2.rule_id = 'assert-weak-boolean' THEN f.id END) AS weak_assertions,
    COUNT(DISTINCT CASE WHEN f2.rule_id = 'assert-exception-not-tested' THEN f.id END) AS missing_exception_tests,
    COUNT(DISTINCT CASE WHEN f2.rule_id = 'assert-mock-not-verified' THEN f.id END) AS unverified_mocks,
    CASE 
        WHEN COUNT(DISTINCT e.id) = 0 THEN 'no_tests'
        WHEN COUNT(DISTINCT f.id) = 0 THEN 'good'
        WHEN COUNT(DISTINCT f.id)::float / COUNT(DISTINCT e.id) < 0.1 THEN 'fair'
        ELSE 'poor'
    END AS test_quality_rating
FROM archon_code_repos r
LEFT JOIN archon_code_entities e ON e.repo_id = r.id 
    AND (e.file_path LIKE '%test%' OR e.file_path LIKE '%spec%')
LEFT JOIN archon_audit_findings f ON f.repo_id = r.id AND f.status = 'open'
LEFT JOIN archon_audit_rules f2 ON f2.id = f.rule_id 
    AND f2.rule_id IN ('assert-missing-in-test', 'assert-weak-boolean', 
                       'assert-exception-not-tested', 'assert-mock-not-verified',
                       'assert-equality-on-floats')
GROUP BY r.id, r.name;

-- =============================================================================
-- CREATE HELPER FUNCTION FOR ASSERTION DETECTION
-- =============================================================================

CREATE OR REPLACE FUNCTION check_assertion_quality(
    p_source_code TEXT,
    p_file_path TEXT,
    p_is_test_file BOOLEAN DEFAULT FALSE
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
    v_in_test_function BOOLEAN := FALSE;
    v_function_start INTEGER := 0;
    v_assertion_count INTEGER := 0;
    v_has_exception_test BOOLEAN := FALSE;
    v_function_name TEXT := '';
BEGIN
    -- Only check test files
    IF NOT p_is_test_file AND NOT (p_file_path LIKE '%test%' OR p_file_path LIKE '%spec%') THEN
        RETURN;
    END IF;
    
    v_lines := string_to_array(p_source_code, E'\\n');
    
    FOR v_line IN SELECT unnest(v_lines) LOOP
        v_line_num := v_line_num + 1;
        
        -- Detect test function start
        IF v_line ~* '^\\s*def\\s+test_' OR v_line ~* '^\\s*def\\s+spec' THEN
            -- Check previous function for assertions
            IF v_in_test_function AND v_assertion_count = 0 AND v_function_start > 0 THEN
                rule_id := 'assert-missing-in-test';
                severity := 'warning';
                message := 'Test function "' || v_function_name || '" has no assertions';
                line_number := v_function_start;
                RETURN NEXT;
            END IF;
            
            v_in_test_function := TRUE;
            v_function_start := v_line_num;
            v_assertion_count := 0;
            v_has_exception_test := FALSE;
            
            -- Extract function name
            v_function_name := substring(v_line from 'def\\s+(\\w+)');
        
        -- Count assertions
        ELSIF v_in_test_function AND (
            v_line ~* 'assert|expect|should|verify'
        ) THEN
            v_assertion_count := v_assertion_count + 1;
            
            -- Check for weak boolean assertion
            IF v_line ~* 'assert(true|asserttrue)\\s*\\(\\s*\\w+\\s*\\)' THEN
                rule_id := 'assert-weak-boolean';
                severity := 'info';
                message := 'Weak boolean assertion at line ' || v_line_num || ': use assertEqual with expected value';
                line_number := v_line_num;
                RETURN NEXT;
            END IF;
            
            -- Check for float equality
            IF v_line ~* 'assert.*float' OR v_line ~* 'assertequal.*\\d+\\.\\d+' THEN
                rule_id := 'assert-equality-on-floats';
                severity := 'warning';
                message := 'Float equality assertion at line ' || v_line_num || ': use assertAlmostEqual';
                line_number := v_line_num;
                RETURN NEXT;
            END IF;
        
        -- Check for exception testing
        ELSIF v_in_test_function AND (
            v_line ~* 'assertraises|pytest\\.raises|expect.*throw'
        ) THEN
            v_has_exception_test := TRUE;
        
        -- Detect function end
        ELSIF v_in_test_function AND v_line ~* '^\\s*def\\s+' AND v_line !~* 'test_|spec' THEN
            v_in_test_function := FALSE;
        END IF;
    END LOOP;
    
    -- Check last function
    IF v_in_test_function AND v_assertion_count = 0 AND v_function_start > 0 THEN
        rule_id := 'assert-missing-in-test';
        severity := 'warning';
        message := 'Test function "' || v_function_name || '" has no assertions';
        line_number := v_function_start;
        RETURN NEXT;
    END IF;
    
    RETURN;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON VIEW archon_test_quality_summary IS 'Summary of test quality metrics per repository';
COMMENT ON FUNCTION check_assertion_quality IS 'Analyzes test code for assertion quality issues';

-- =============================================================================
-- MIGRATION TRACKING
-- =============================================================================

INSERT INTO archon_migrations (version, migration_name, applied_at)
VALUES ('018', 'Add assertion quality rules (P1)', NOW())
ON CONFLICT (version, migration_name) DO NOTHING;

COMMIT;
