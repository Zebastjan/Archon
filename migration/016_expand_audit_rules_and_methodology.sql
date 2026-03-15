-- Migration 016: Expand Audit Rules and Add Methodology Support
-- Part of Phase 2: Enhanced Rule Catalog and Methodology-Aware Audits

-- =============================================================================
-- EXTEND ARCHON_AUDIT_RULES SCHEMA
-- =============================================================================

-- Add new columns for rule metadata
ALTER TABLE archon_audit_rules
ADD COLUMN IF NOT EXISTS implementation_type TEXT DEFAULT 'threshold',
ADD COLUMN IF NOT EXISTS rationale TEXT,
ADD COLUMN IF NOT EXISTS remediation_guidance TEXT,
ADD COLUMN IF NOT EXISTS example_violation TEXT,
ADD COLUMN IF NOT EXISTS example_fix TEXT,
ADD COLUMN IF NOT EXISTS "references" TEXT[],
ADD COLUMN IF NOT EXISTS methodology_tags JSONB DEFAULT '[]',
ADD COLUMN IF NOT EXISTS applies_to_tdd BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS applies_to_doc_driven BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS applies_to_security_first BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS owasp_category TEXT,
ADD COLUMN IF NOT EXISTS cwe_id TEXT,
ADD COLUMN IF NOT EXISTS estimated_fix_time_minutes INTEGER;

-- Add indexes for new columns
CREATE INDEX IF NOT EXISTS idx_audit_rules_methodology ON archon_audit_rules USING GIN(methodology_tags);
CREATE INDEX IF NOT EXISTS idx_audit_rules_tdd ON archon_audit_rules(applies_to_tdd) WHERE applies_to_tdd = TRUE;
CREATE INDEX IF NOT EXISTS idx_audit_rules_doc_driven ON archon_audit_rules(applies_to_doc_driven) WHERE applies_to_doc_driven = TRUE;
CREATE INDEX IF NOT EXISTS idx_audit_rules_security ON archon_audit_rules(applies_to_security_first) WHERE applies_to_security_first = TRUE;
CREATE INDEX IF NOT EXISTS idx_audit_rules_owasp ON archon_audit_rules(owasp_category);

-- =============================================================================
-- EXTEND ARCHON_AUDIT_FINDINGS SCHEMA
-- =============================================================================

-- Add methodology context to findings
ALTER TABLE archon_audit_findings
ADD COLUMN IF NOT EXISTS methodology_tag TEXT,
ADD COLUMN IF NOT EXISTS fix_complexity TEXT,
ADD COLUMN IF NOT EXISTS auto_fixable BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS ai_suggested_fix TEXT,
ADD COLUMN IF NOT EXISTS similar_findings_count INTEGER DEFAULT 0;

-- =============================================================================
-- EXPANDED AUDIT RULES
-- =============================================================================

-- Security Rules
INSERT INTO archon_audit_rules (
    rule_id, name, description, category, severity, rule_type,
    configuration, pattern, applies_to, is_builtin, is_active,
    implementation_type, rationale, remediation_guidance,
    example_violation, example_fix, "references",
    applies_to_security_first, owasp_category, cwe_id, estimated_fix_time_minutes
) VALUES
(
    'hardcoded-secrets',
    'Hardcoded Secrets Detected',
    'Detects hardcoded API keys, passwords, tokens, and secrets in source code',
    'security', 'critical', 'pattern',
    '{"patterns": ["api_key", "password", "secret", "token", "apikey"]}',
    '(password|secret|token|api_key)\s*=\s*["''][^"'']+["'']',
    ARRAY['function', 'method', 'variable'],
    TRUE, TRUE,
    'pattern-static',
    'Hardcoded secrets pose severe security risks. They may be exposed in version control and compromise systems.',
    'Move secrets to environment variables or secure vaults. Use configuration management tools.',
    'API_KEY = "sk-1234567890abcdef"',
    'API_KEY = os.getenv("API_KEY")',
    ARRAY['https://owasp.org/Top10/A07_2021-Identification_and_Authentication_Failures/', 'https://cwe.mitre.org/data/definitions/798.html'],
    TRUE, 'A07:2021', 'CWE-798', 5
),
(
    'sql-injection',
    'Potential SQL Injection',
    'Detects potentially unsafe SQL query construction',
    'security', 'critical', 'pattern',
    '{"patterns": ["execute", "cursor", "query"]}',
    '(execute|query)\s*\([^)]*[+%].*\)',
    ARRAY['function', 'method'],
    TRUE, TRUE,
    'pattern-static',
    'String concatenation in SQL queries enables SQL injection attacks, allowing attackers to execute arbitrary database commands.',
    'Use parameterized queries/prepared statements. Never concatenate user input into SQL.',
    'cursor.execute("SELECT * FROM users WHERE id = " + user_id)',
    'cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))',
    ARRAY['https://owasp.org/Top10/A03_2021-Injection/', 'https://cwe.mitre.org/data/definitions/89.html'],
    TRUE, 'A03:2021', 'CWE-89', 15
),
(
    'unsafe-eval',
    'Unsafe Code Evaluation',
    'Detects dangerous use of eval(), exec(), or similar dynamic code execution',
    'security', 'critical', 'pattern',
    '{"functions": ["eval", "exec", "compile"]}',
    '\b(eval|exec)\s*\(',
    ARRAY['function', 'method'],
    TRUE, TRUE,
    'pattern-static',
    'Dynamic code execution with eval/exec allows arbitrary code execution and is extremely dangerous.',
    'Use safer alternatives like ast.literal_eval() for parsing, or proper serialization.',
    'result = eval(user_input)',
    'result = json.loads(user_input)',
    ARRAY['https://owasp.org/Top10/A03_2021-Injection/', 'https://cwe.mitre.org/data/definitions/95.html'],
    TRUE, 'A03:2021', 'CWE-95', 30
),
(
    'insecure-deserialization',
    'Insecure Deserialization',
    'Detects unsafe use of pickle, yaml.load, or other deserialization',
    'security', 'error', 'pattern',
    '{"functions": ["pickle", "yaml.load"]}',
    '\b(pickle\.loads?|yaml\.load)\s*\(',
    ARRAY['function', 'method'],
    TRUE, TRUE,
    'pattern-static',
    'Deserializing untrusted data can lead to remote code execution.',
    'Use yaml.safe_load(), json.loads(), or other safe deserialization methods.',
    'data = pickle.loads(untrusted_data)',
    'data = json.loads(untrusted_data)',
    ARRAY['https://owasp.org/Top10/A08_2021-Software_and_Data_Integrity_Failures/', 'https://cwe.mitre.org/data/definitions/502.html'],
    TRUE, 'A08:2021', 'CWE-502', 20
),
(
    'weak-crypto',
    'Weak Cryptography',
    'Detects use of weak cryptographic algorithms',
    'security', 'error', 'pattern',
    '{"algorithms": ["md5", "sha1", "des"]}',
    '\b(md5|sha1|DES)\b',
    ARRAY['function', 'method'],
    TRUE, TRUE,
    'pattern-static',
    'Weak cryptographic algorithms are vulnerable to attacks and should not be used for security-sensitive operations.',
    'Use strong algorithms: SHA-256 or SHA-3 for hashing, AES for encryption.',
    'hash = hashlib.md5(data).hexdigest()',
    'hash = hashlib.sha256(data).hexdigest()',
    ARRAY['https://owasp.org/Top10/A02_2021-Cryptographic_Failures/', 'https://cwe.mitre.org/data/definitions/327.html'],
    TRUE, 'A02:2021', 'CWE-327', 15
),
(
    'subprocess-shell-true',
    'Shell=True in Subprocess',
    'Detects subprocess calls with shell=True that could allow command injection',
    'security', 'error', 'pattern',
    '{"function": "subprocess"}',
    'subprocess\.[\w]+\s*\([^)]*shell\s*=\s*True',
    ARRAY['function', 'method'],
    TRUE, TRUE,
    'pattern-static',
    'Using shell=True with user input allows shell injection attacks.',
    'Use shell=False and pass command as list. Sanitize all inputs.',
    'subprocess.call(command, shell=True)',
    'subprocess.call(shlex.split(command), shell=False)',
    ARRAY['https://owasp.org/Top10/A03_2021-Injection/', 'https://cwe.mitre.org/data/definitions/78.html'],
    TRUE, 'A03:2021', 'CWE-78', 20
)

ON CONFLICT (rule_id) DO UPDATE SET
    description = EXCLUDED.description,
    severity = EXCLUDED.severity,
    configuration = EXCLUDED.configuration,
    pattern = EXCLUDED.pattern,
    implementation_type = EXCLUDED.implementation_type,
    rationale = EXCLUDED.rationale,
    remediation_guidance = EXCLUDED.remediation_guidance,
    example_violation = EXCLUDED.example_violation,
    example_fix = EXCLUDED.example_fix,
    "references" = EXCLUDED."references",
    applies_to_security_first = EXCLUDED.applies_to_security_first,
    owasp_category = EXCLUDED.owasp_category,
    cwe_id = EXCLUDED.cwe_id,
    estimated_fix_time_minutes = EXCLUDED.estimated_fix_time_minutes,
    updated_at = NOW();

-- Maintainability Rules
INSERT INTO archon_audit_rules (
    rule_id, name, description, category, severity, rule_type,
    configuration, threshold_max, applies_to, is_builtin, is_active,
    implementation_type, rationale, remediation_guidance,
    example_violation, example_fix, "references",
    estimated_fix_time_minutes
) VALUES
(
    'too-many-params',
    'Too Many Parameters',
    'Functions with more than 7 parameters are hard to understand and maintain',
    'maintainability', 'warning', 'threshold',
    '{"metric": "parameter_count"}',
    7,
    ARRAY['function', 'method'],
    TRUE, TRUE,
    'mechanical-static',
    'High parameter count indicates tight coupling and makes functions difficult to understand, test, and refactor.',
    'Refactor using a configuration object/data class, or split into multiple functions.',
    'def process_data(name, age, email, phone, address, city, country, zip_code):',
    'def process_data(user_info: UserInfo):',
    ARRAY['https://refactoring.guru/introduce-parameter-object'],
    30
),
(
    'deeply-nested',
    'Deeply Nested Code',
    'Code with nesting depth greater than 4 is difficult to follow',
    'maintainability', 'warning', 'threshold',
    '{"metric": "nesting_depth"}',
    4,
    ARRAY['function', 'method'],
    TRUE, TRUE,
    'mechanical-static',
    'Deep nesting makes code hard to understand and increases cognitive load.',
    'Extract nested blocks into separate functions, or use early returns.',
    'if x:\n    if y:\n        if z:\n            if w:\n                do_something()',
    'if not x or not y:\n    return\nif z and w:\n    do_something()',
    ARRAY['https://refactoring.guru/replace-nested-conditional-with-guard-clauses'],
    20
),
(
    'cognitive-complexity',
    'High Cognitive Complexity',
    'Code is difficult to understand due to complex control flow',
    'maintainability', 'warning', 'threshold',
    '{"metric": "cognitive_complexity"}',
    15,
    ARRAY['function', 'method'],
    TRUE, TRUE,
    'mechanical-static',
    'Cognitive complexity measures how difficult code is to understand, considering nesting and logical operators.',
    'Break complex functions into smaller, single-purpose functions. Use descriptive names.',
    NULL,
    NULL,
    ARRAY['https://www.sonarsource.com/docs/CognitiveComplexity.pdf'],
    45
),
(
    'duplicate-code',
    'Duplicate Code Detected',
    'Similar code blocks detected, violates DRY principle',
    'maintainability', 'warning', 'pattern',
    '{"min_lines": 6, "min_similarity": 0.8}',
    NULL,
    ARRAY['function', 'method', 'class'],
    TRUE, TRUE,
    'heuristic-static',
    'Duplicate code makes maintenance harder - changes must be made in multiple places.',
    'Extract common code into shared functions or base classes.',
    NULL,
    NULL,
    ARRAY['https://refactoring.guru/extract-method'],
    30
),
(
    'inconsistent-naming',
    'Inconsistent Naming Convention',
    'Mixing snake_case, camelCase, or other naming styles',
    'maintainability', 'info', 'pattern',
    '{"convention": "snake_case"}',
    NULL,
    ARRAY['function', 'method', 'class', 'variable'],
    TRUE, TRUE,
    'heuristic-static',
    'Consistent naming conventions improve code readability and reduce cognitive load.',
    'Follow language conventions (snake_case in Python, camelCase in JS).',
    'def myFunction(): pass',
    'def my_function(): pass',
    ARRAY['https://pep8.org/#naming-conventions'],
    10
)

ON CONFLICT (rule_id) DO UPDATE SET
    description = EXCLUDED.description,
    threshold_max = EXCLUDED.threshold_max,
    implementation_type = EXCLUDED.implementation_type,
    rationale = EXCLUDED.rationale,
    remediation_guidance = EXCLUDED.remediation_guidance,
    example_violation = EXCLUDED.example_violation,
    example_fix = EXCLUDED.example_fix,
    "references" = EXCLUDED."references",
    estimated_fix_time_minutes = EXCLUDED.estimated_fix_time_minutes,
    updated_at = NOW();

-- Documentation/Test Hygiene Rules
INSERT INTO archon_audit_rules (
    rule_id, name, description, category, severity, rule_type,
    configuration, applies_to, is_builtin, is_active,
    implementation_type, rationale, remediation_guidance,
    example_violation, example_fix, "references",
    methodology_tags, applies_to_doc_driven,
    estimated_fix_time_minutes
) VALUES
(
    'public-api-missing-docs',
    'Public API Missing Documentation',
    'Public functions and classes should have docstrings',
    'documentation', 'warning', 'pattern',
    '{"check": "docstring_exists"}',
    ARRAY['function', 'class', 'method'],
    TRUE, TRUE,
    'mechanical-static',
    'Documentation helps other developers understand how to use your code correctly.',
    'Add docstrings describing purpose, parameters, return values, and exceptions.',
    'def calculate_total(items):\n    return sum(items)',
    'def calculate_total(items):\n    """Calculate total price of items.\n    \n    Args:\n        items: List of Item objects\n    Returns:\n        float: Total price\n    """\n    return sum(items)',
    ARRAY['https://peps.python.org/pep-0257/'],
    '["doc-driven"]', TRUE,
    5
),
(
    'missing-type-hints',
    'Missing Type Hints',
    'Function parameters and return values should be typed',
    'documentation', 'info', 'pattern',
    '{"check": "type_hints"}',
    ARRAY['function', 'method'],
    TRUE, TRUE,
    'mechanical-static',
    'Type hints improve code clarity and enable better IDE support and static analysis.',
    'Add type hints to function signatures.',
    'def process(data):\n    return data.items',
    'def process(data: dict) -> list:\n    return data.items',
    ARRAY['https://docs.python.org/3/library/typing.html'],
    '["doc-driven"]', TRUE,
    5
),
(
    'complex-lambda',
    'Complex Lambda Expression',
    'Lambdas should be simple; use named functions for complex logic',
    'maintainability', 'info', 'threshold',
    '{"metric": "lambda_complexity"}',
    ARRAY['function'],
    TRUE, TRUE,
    'heuristic-static',
    'Complex lambdas are hard to read and debug. Named functions are clearer.',
    'Convert to a named function with a descriptive name.',
    'sorted(data, key=lambda x: complex_calculation(x[0], x[1], x[2]))',
    'def get_sort_key(item):\n    return complex_calculation(item[0], item[1], item[2])\n\nsorted(data, key=get_sort_key)',
    ARRAY['https://refactoring.guru/replace-method-with-method-object'],
    '["readability"]', FALSE,
    10
),
(
    'broad-except',
    'Broad Exception Handling',
    'Catching generic exceptions hides bugs and makes debugging difficult',
    'maintainability', 'warning', 'pattern',
    '{"pattern": "except:"}',
    ARRAY['function', 'method'],
    TRUE, TRUE,
    'pattern-static',
    'Catching generic exceptions can mask real errors and make debugging difficult.',
    'Catch specific exceptions only, or at minimum log the exception details.',
    'try:\n    do_work()\nexcept:\n    pass',
    'try:\n    do_work()\nexcept ValueError as e:\n    logger.error(f"Invalid value: {e}")',
    ARRAY['https://peps.python.org/pep-0008/#programming-recommendations'],
    '["maintainability", "debugging"]', FALSE,
    10
)

ON CONFLICT (rule_id) DO UPDATE SET
    description = EXCLUDED.description,
    implementation_type = EXCLUDED.implementation_type,
    rationale = EXCLUDED.rationale,
    remediation_guidance = EXCLUDED.remediation_guidance,
    example_violation = EXCLUDED.example_violation,
    example_fix = EXCLUDED.example_fix,
    "references" = EXCLUDED."references",
    methodology_tags = EXCLUDED.methodology_tags,
    applies_to_doc_driven = EXCLUDED.applies_to_doc_driven,
    estimated_fix_time_minutes = EXCLUDED.estimated_fix_time_minutes,
    updated_at = NOW();

-- Methodology-Aware Rules (TDD, Doc-Driven)
INSERT INTO archon_audit_rules (
    rule_id, name, description, category, severity, rule_type,
    configuration, applies_to, is_builtin, is_active,
    implementation_type, rationale, remediation_guidance,
    example_violation, example_fix, "references",
    methodology_tags, applies_to_tdd, applies_to_doc_driven,
    estimated_fix_time_minutes
) VALUES
(
    'untested-production-code',
    'Untested Production Code',
    'Production files without corresponding test files',
    'methodology', 'warning', 'custom',
    '{"check": "has_test_file"}',
    ARRAY['function', 'class', 'module'],
    TRUE, TRUE,
    'custom-query',
    'Tests provide confidence in changes and serve as documentation. Untested code is risky.',
    'Create corresponding test files following your testing conventions.',
    NULL,
    NULL,
    NULL,
    '["tdd", "testing", "quality"]', TRUE, FALSE,
    60
),
(
    'missing-tests-for-public-api',
    'Public API Missing Tests',
    'Public functions and classes should have unit tests',
    'methodology', 'warning', 'pattern',
    '{"visibility": "public", "has_tests": false}',
    ARRAY['function', 'method', 'class'],
    TRUE, TRUE,
    'heuristic-static',
    'Public APIs are contracts with users and must be tested to ensure reliability.',
    'Write unit tests covering normal cases, edge cases, and error conditions.',
    NULL,
    NULL,
    NULL,
    '["tdd", "testing"]', TRUE, FALSE,
    30
),
(
    'test-assert-quality',
    'Low Quality Test Assertions',
    'Tests with weak or missing assertions',
    'methodology', 'warning', 'pattern',
    '{"check": "assertion_quality"}',
    ARRAY['function', 'method'],
    TRUE, TRUE,
    'heuristic-static',
    'Tests without proper assertions may give false confidence - they pass but do not verify behavior.',
    'Add specific assertions that verify expected behavior, not just that no exception is raised.',
    NULL,
    NULL,
    NULL,
    '["tdd", "testing", "quality"]', TRUE, FALSE,
    15
)

ON CONFLICT (rule_id) DO UPDATE SET
    description = EXCLUDED.description,
    implementation_type = EXCLUDED.implementation_type,
    rationale = EXCLUDED.rationale,
    remediation_guidance = EXCLUDED.remediation_guidance,
    methodology_tags = EXCLUDED.methodology_tags,
    applies_to_tdd = EXCLUDED.applies_to_tdd,
    applies_to_doc_driven = EXCLUDED.applies_to_doc_driven,
    estimated_fix_time_minutes = EXCLUDED.estimated_fix_time_minutes,
    updated_at = NOW();

-- =============================================================================
-- UPDATE EXISTING RULES WITH ENHANCED METADATA
-- =============================================================================

-- Update existing complexity rules
UPDATE archon_audit_rules SET
    implementation_type = 'threshold-static',
    rationale = CASE
        WHEN rule_id = 'complexity-high' THEN 'Functions with cyclomatic complexity > 10 are harder to test and maintain, increasing bug risk.'
        WHEN rule_id = 'complexity-critical' THEN 'Functions with cyclomatic complexity > 20 are very difficult to understand and should be refactored immediately.'
        ELSE rationale
    END,
    remediation_guidance = CASE
        WHEN rule_id LIKE 'complexity%' THEN 'Extract nested conditionals into helper functions. Consider using polymorphism or strategy pattern.'
        ELSE remediation_guidance
    END,
    example_violation = CASE
        WHEN rule_id = 'complexity-high' THEN 'def process(): if a: if b: if c: if d: return True'
        ELSE example_violation
    END,
    example_fix = CASE
        WHEN rule_id = 'complexity-high' THEN 'def process(): if not a or not b: return False return helper(c, d)'
        ELSE example_fix
    END,
    "references" = ARRAY['https://en.wikipedia.org/wiki/Cyclomatic_complexity', 'https://martinfowler.com/bliki/FunctionLength.html']
WHERE rule_id IN ('complexity-high', 'complexity-critical', 'function-too-long', 'function-critically-long');

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON COLUMN archon_audit_rules.implementation_type IS 'Type of rule implementation: threshold-static, pattern-static, heuristic-static, custom-query';
COMMENT ON COLUMN archon_audit_rules.rationale IS 'Explanation of why this rule matters';
COMMENT ON COLUMN archon_audit_rules.remediation_guidance IS 'How to fix violations of this rule';
COMMENT ON COLUMN archon_audit_rules.example_violation IS 'Example code that violates the rule';
COMMENT ON COLUMN archon_audit_rules.example_fix IS 'Example of corrected code';
COMMENT ON COLUMN archon_audit_rules."references" IS 'URLs to relevant documentation';
COMMENT ON COLUMN archon_audit_rules.methodology_tags IS 'JSON array of methodology tags';
COMMENT ON COLUMN archon_audit_rules.applies_to_tdd IS 'Whether this rule applies to TDD methodology';
COMMENT ON COLUMN archon_audit_rules.applies_to_doc_driven IS 'Whether this rule applies to documentation-first development';
COMMENT ON COLUMN archon_audit_rules.applies_to_security_first IS 'Whether this rule applies to security-first development';
COMMENT ON COLUMN archon_audit_rules.owasp_category IS 'OWASP Top 10 category';
COMMENT ON COLUMN archon_audit_rules.cwe_id IS 'CWE identifier';
COMMENT ON COLUMN archon_audit_rules.estimated_fix_time_minutes IS 'Estimated time to fix violations';

COMMENT ON COLUMN archon_audit_findings.methodology_tag IS 'Which methodology this finding relates to';
COMMENT ON COLUMN archon_audit_findings.fix_complexity IS 'Estimated complexity of fix: simple, moderate, complex';
COMMENT ON COLUMN archon_audit_findings.auto_fixable IS 'Whether this can be auto-fixed';
COMMENT ON COLUMN archon_audit_findings.ai_suggested_fix IS 'AI-generated fix suggestion';

-- =============================================================================
-- MIGRATION TRACKING
-- =============================================================================

INSERT INTO archon_migrations (version, migration_name, applied_at)
VALUES ('016', 'Expand audit rules and add methodology support', NOW())
ON CONFLICT (version, migration_name) DO NOTHING;

COMMIT;
