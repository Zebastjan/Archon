# Code Audit Workflows Documentation

## Overview

The Archon Code Audit system provides comprehensive code quality and security analysis. This document explains how to run audits via CLI and how to use the Security & Quality Audit skill in agents.

## Running Repository Audits

### Via CLI

The `archon-audit` CLI command provides an easy way to run audits from the command line.

#### Installation

The CLI is available at `python/src/cli/audit_cli.py`. To make it easily accessible:

```bash
# Add alias to your shell
alias archon-audit="python /path/to/archon/python/src/cli/audit_cli.py"

# Or create a symlink
ln -s /path/to/archon/python/src/cli/audit_cli.py /usr/local/bin/archon-audit
```

#### Commands

##### 1. Run Full Audit

```bash
archon-audit audit-repo --repo-id=<REPO_UUID>
```

Example output:
```
🔍 Running audit on repository: abc-123-def

📊 Calculating code metrics...
   ✓ Health Score: 78/100
   ✓ Files: 156
   ✓ LOC: 42,350

🔎 Running audit rules...
   ✓ Findings: 23
   ✓ Audit Run ID: run-xyz-789

📋 Retrieving findings...
   ✓ Retrieved 23 findings

📝 Generating report...

============================================================
AUDIT COMPLETE
============================================================

Health Score: 78/100
Total Findings: 23

  CRITICAL: 0
  ERROR: 3
  WARNING: 15
  INFO: 5

Full report written to: None
Use --output to save report to file
```

##### 2. Save Report to File

```bash
archon-audit audit-repo --repo-id=<REPO_UUID> --output=audit-report.md
```

This generates a comprehensive Markdown report with:
- Health score visualization
- High-level metrics summary
- Detailed complexity analysis
- Quality indicators
- Top 10 findings with suggested fixes
- Recommendations for improvement

##### 3. Run Specific Ruleset

```bash
archon-audit audit-repo --repo-id=<REPO_UUID> --ruleset=security-only
```

Available rulesets:
- `default` - All active rules (default)
- `security-only` - Security rules only
- `complexity-only` - Complexity rules only
- `custom` - Comma-separated list of rule IDs:

```bash
archon-audit audit-repo --repo-id=<REPO_UUID> --ruleset=complexity-high,hardcoded-secrets,missing-docstring
```

##### 4. List Available Rules

```bash
# List all active rules
archon-audit list-rules

# Filter by category
archon-audit list-rules --category=security
archon-audit list-rules --category=complexity
archon-audit list-rules --category=maintainability

# Include inactive rules
archon-audit list-rules --include-inactive
```

### Via MCP Tools

For programmatic access, use the MCP tools directly:

```python
# Calculate metrics
metrics = await code_audit_calculate_metrics(repo_id="abc-123")

# Run audit
result = await code_audit_run(
    repo_id="abc-123",
    ruleset=["hardcoded-secrets", "sql-injection"]
)

# Get findings
findings = await code_audit_get_findings(
    repo_id="abc-123",
    status="open",
    severity="critical"
)

# Get summary
summary = await code_audit_get_summary(repo_id="abc-123")

# Get available rules
rules = await code_audit_get_rules(category="security")
```

## Using the Security & Quality Audit Skill

### When to Use the Skill

**New Repository Setup:**
- Always run an audit when starting work on a new codebase
- Identifies security risks before deployment
- Establishes baseline health score

**Pre-Deployment Checks:**
- Run security-focused audit before releases
- Check for hardcoded secrets
- Verify no critical vulnerabilities

**Sprint Planning:**
- Identify high-risk areas for refactoring
- Quantify technical debt
- Prioritize work based on health score impact

**Code Reviews:**
- Automated findings support human review
- Catch issues reviewers might miss
- Ensure consistent standards

**Periodic Maintenance:**
- Weekly audits track score trends
- Catch regressions early
- Monitor improvement progress

### How to Use the Skill

#### 1. Initial Assessment

The agent should start by calculating metrics:

```
1. Call code_audit_calculate_metrics(repo_id)
2. Review the health_score (0-100)
3. Note key metrics: total_files, avg_cyclomatic_complexity, code_to_comment_ratio
```

**Health Score Interpretation:**

| Score | Status | Action |
|-------|--------|--------|
| 90-100 | 🟢 Excellent | Minor improvements only |
| 70-89 | 🟡 Good | Some areas need attention |
| 50-69 | 🟠 Fair | Significant refactoring recommended |
| 0-49 | 🔴 Poor | Major overhaul required |

#### 2. Run Full Audit

```
1. Call code_audit_run(repo_id, ruleset)
   - Use ruleset=null for all rules
   - Or specify ["category-security"] for security-only
2. Note findings_count
3. If > 50 findings, focus on critical first
```

#### 3. Analyze Findings

```
1. Call code_audit_get_findings(repo_id, status="open")
2. Filter by severity: critical → error → warning → info
3. Group by category: security → complexity → maintainability
4. Prioritize by impact × effort
```

#### 4. Generate Report

Create a summary with:
- Health score and trend
- Top 10 critical issues
- Quick wins (low effort, high impact)
- Security vulnerabilities (if any)
- Recommended next steps

### Sample Agent Interactions

#### Scenario: New Repository Audit

**User:** "Audit this codebase"

**Agent Response:**
```
1. "I'll run a comprehensive audit of this repository."
2. Call code_audit_calculate_metrics(repo_id)
3. "The health score is 67 (Fair). Let me run a detailed audit..."
4. Call code_audit_run(repo_id)
5. "Found 23 issues. Here are the critical ones:"
6. Call code_audit_get_findings(repo_id, severity="critical")
7. Present findings:
   - 🔴 hardcoded-secrets: API key in config.py
   - 🟠 complexity-high: process_data() has complexity 18
   - 🟠 sql-injection: Unparameterized query in users.py
```

#### Scenario: Security-Focused Audit

**User:** "Check for security issues"

**Agent Response:**
```
1. "Running security-focused audit..."
2. Call code_audit_run(repo_id, ruleset=["hardcoded-secrets", "sql-injection", "unsafe-eval", "insecure-deserialization", "weak-crypto"])
3. "Security scan complete. Found 2 critical issues:"
   - hardcoded-secrets: Database password in settings.py
   - sql-injection: String concatenation in query() function
4. Provide remediation guidance for each
```

#### Scenario: Pre-Refactoring Assessment

**User:** "What should I refactor first?"

**Agent Response:**
```
1. "Analyzing codebase for refactoring candidates..."
2. Call code_audit_calculate_metrics(repo_id)
3. Call code_audit_get_findings(repo_id, category="complexity")
4. "Here are the top refactoring opportunities:"
   1. process_data() - complexity 24, 150 lines
   2. authenticate_user() - complexity 19, 89 lines
   3. generate_report() - complexity 17, 120 lines
5. Suggest starting with highest complexity/impact ratio
```

## Rule Categories

### Security Rules (Highest Priority)

Always address security findings first.

| Rule | Severity | Description |
|------|----------|-------------|
| hardcoded-secrets | 🔴 Critical | API keys, passwords in code |
| sql-injection | 🔴 Critical | Unparameterized queries |
| unsafe-eval | 🔴 Critical | eval(), exec(), dynamic code |
| insecure-deserialization | 🟠 Error | Unsafe pickle, yaml.load |
| weak-crypto | 🟠 Error | MD5, SHA1, DES usage |
| subprocess-shell-true | 🟠 Error | Command injection risk |

**References:**
- OWASP Top 10: https://owasp.org/Top10/
- CWE Database: https://cwe.mitre.org/

### Complexity Rules (High Priority)

| Rule | Severity | Threshold | Description |
|------|----------|-----------|-------------|
| complexity-critical | 🟠 Error | > 20 | Very complex functions |
| complexity-high | 🟡 Warning | > 10 | Complex functions |
| function-critically-long | 🟠 Error | > 100 lines | Very long functions |
| function-too-long | 🟡 Warning | > 50 lines | Long functions |
| deeply-nested | 🟡 Warning | > 4 levels | Deep nesting |
| cognitive-complexity | 🟡 Warning | > 15 | High cognitive load |

### Maintainability Rules (Medium Priority)

| Rule | Severity | Description |
|------|----------|-------------|
| too-many-params | 🟡 Warning | > 7 parameters |
| duplicate-code | 🟡 Warning | Copy-pasted blocks |
| inconsistent-naming | 🔵 Info | Mixed naming conventions |
| broad-except | 🟡 Warning | Generic exception handling |
| complex-lambda | 🔵 Info | Complex lambda expressions |

### Documentation/Test Rules (Medium Priority)

| Rule | Severity | Description |
|------|----------|-------------|
| public-api-missing-docs | 🟡 Warning | Undocumented public APIs |
| missing-type-hints | 🔵 Info | Untyped parameters |
| missing-docstring | 🔵 Info | No docstrings |

### Methodology Rules (TDD/Doc-Driven)

| Rule | Severity | Description |
|------|----------|-------------|
| untested-production-code | 🟡 Warning | No corresponding test file |
| missing-tests-for-public-api | 🟡 Warning | Public APIs without tests |
| test-assert-quality | 🟡 Warning | Weak test assertions |

## Interpreting Metrics

### Health Score Components

The health score (0-100) considers:

1. **Complexity Penalty** (-3 points per unit over 10)
2. **Length Penalty** (-1 point per 5 lines over 50)
3. **Documentation Penalty** (-10 if ratio > 20:1)
4. **TODO Penalty** (-2 per TODO, max -20)
5. **Max Complexity Penalty** (-1 per 2 units over 20)

### Key Metrics

| Metric | Good | Fair | Poor |
|--------|------|------|------|
| Health Score | 70-100 | 50-69 | < 50 |
| Avg Complexity | < 8 | 8-15 | > 15 |
| Max Complexity | < 15 | 15-25 | > 25 |
| Code:Comment | 4-10:1 | 10-20:1 | > 20:1 |
| Avg Function Length | < 25 | 25-50 | > 50 |

### Complexity Calculation

Cyclomatic complexity counts:
- if, elif, else statements (+1 each)
- for, while loops (+1 each)
- except blocks (+1 each)
- Logical operators (+1 for and/or chains)

Base complexity = 1

Example:
```python
def example(x, y):  # Base: 1
    if x:           # +1
        if y:       # +1
            return 1
        return 0    # Total: 3
```

## Best Practices

### Security Issues

1. **Never** commit secrets - use environment variables
2. **Always** use parameterized queries
3. **Validate** all user inputs
4. **Sanitize** data before logging/display

### Complexity Issues

1. Extract nested conditionals into functions
2. Replace switch/if chains with polymorphism
3. Split long functions (aim for < 30 lines)
4. Reduce parameter count with config objects

### Documentation Issues

1. Add docstrings to all public functions/classes
2. Include parameter types and return values
3. Document exceptions raised
4. Add usage examples for complex APIs

## Configuration

### Custom Rules

You can add custom rules to `archon_audit_rules`:

```sql
INSERT INTO archon_audit_rules (
    rule_id, name, description, category, severity, rule_type,
    configuration, pattern, applies_to, is_active, is_builtin,
    implementation_type, rationale, remediation_guidance
) VALUES (
    'custom-rule',
    'Custom Rule Name',
    'Description of what this rule checks',
    'maintainability',
    'warning',
    'pattern',
    '{"pattern": "specific-regex"}',
    'your-regex-pattern-here',
    ARRAY['function', 'method'],
    TRUE,
    FALSE,
    'pattern-static',
    'Why this rule matters',
    'How to fix violations'
);
```

### Rule Types

- **threshold**: Compares metric against min/max values
- **pattern**: Uses regex to match code patterns
- **custom**: Uses database functions for complex logic

### Implementation Types

- **threshold-static**: Static threshold comparison
- **pattern-static**: Regex pattern matching
- **heuristic-static**: Algorithm-based detection
- **mechanical-static**: Simple mechanical checks
- **custom-query**: Database function-based

## Troubleshooting

### No Entities Found

If `code_audit_calculate_metrics` returns empty:
- Ensure repository has been indexed
- Check that `archon_code_entities` has data for repo_id
- Verify file paths are being parsed correctly

### False Positives

Some rules may produce false positives:
- Review the finding context
- Use `code_audit_acknowledge_finding` to mark as acknowledged
- Consider adjusting rule thresholds

### Performance Issues

For large repositories:
- Run audits during off-peak hours
- Use specific rulesets instead of all rules
- Process findings in batches

## Additional Resources

- [OWASP Top 10](https://owasp.org/Top10/)
- [CWE Database](https://cwe.mitre.org/)
- [Cyclomatic Complexity](https://en.wikipedia.org/wiki/Cyclomatic_complexity)
- [Refactoring Guru](https://refactoring.guru/)

## Migration History

- **Migration 015**: Initial metrics and audit tables
- **Migration 016**: Expanded rule catalog with 23 rules, methodology support
