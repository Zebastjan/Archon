# Security Audit Skill

Comprehensive security-focused code audit combining orchestrated analysis with DB security checks.

## When to Use

Use this skill when:
- Performing a security review
- Looking for vulnerabilities
- Pre-deployment security check
- Responding to security concerns
- Regular security maintenance

## When NOT to Use

Do NOT use when:
- You need general code quality audit (use quick-health-check with focus="full")
- You're investigating a specific known vulnerability (use audit-context)
- You only need DB security (use db_security_audit directly)

## Tool Selection

**Primary**: `orchestrated_repo_health_check` with `focus="security"`
- LLM-powered security analysis
- Human-friendly recommendations
- Comprehensive coverage

**Secondary**: `db_security_audit`
- SQL injection detection
- DB credential scanning
- Python/TypeScript specific

**Context**: `audit_get_context`
- Cross-reference with existing findings
- Batched findings review

## Workflow

### Step 1: Comprehensive Security Audit

```
orchestrated_repo_health_check(repo_id, focus="security")
```

### Step 2: DB Security Audit (Parallel)

If codebase uses databases:

```
db_security_audit(repo_id, include_tests=False)
```

**Note**: These two calls are independent and can be batched.

### Step 3: Cross-Reference (Optional)

```
audit_get_context(repo_name)
```

**Only if** you want to see historical findings or correlate with existing issues.

### Step 4: Analysis & Presentation

Structure your response:

```markdown
# Security Audit: [Project Name]

**Overall Security Score**: [X]/100

## Executive Summary
[From orchestrated output]

## Critical Findings
[List CRITICAL severity items]

## High Priority Issues

### General Security
[From orchestrated_repo_health_check]

### Database Security
[From db_security_audit]
- SQL Injection: [count] findings
- Unsafe queries: [count]
- Credential issues: [count]

## Recommendations by Priority

### Immediate (Fix Today)
1. [Critical finding with location]

### This Sprint
1. [High priority items]

### Next Sprint
1. [Medium priority improvements]

## Detailed Findings

### [Category 1]
[Detailed breakdown]

### [Category 2]
[Detailed breakdown]
```

## Batching Rules

**Step 1 & 2 MUST be batched** - independent security checks:
- `orchestrated_repo_health_check(focus="security")` + `db_security_audit`

**Step 3** (Optional): 1 additional call
- `audit_get_context` (only if historical context needed)

**Maximum**: 1-2 calls (1 batch + optional follow-up)

## Severity Classification

| Severity | Action Required | Timeline |
|----------|----------------|----------|
| CRITICAL | Immediate fix | Today |
| ERROR | High priority | This sprint |
| WARNING | Address soon | Next 2 sprints |
| INFO | Consider | Backlog |

## Example Invocation

User: "Run a security audit on archon"

Claude: [Batch: orchestrated_repo_health_check(focus="security") + db_security_audit]

Claude: "# Security Audit: Archon

**Overall Security Score**: 72/100

## Executive Summary
Repository has acceptable security posture with 2 critical issues requiring immediate attention. SQL injection vulnerabilities found in legacy query code. Authentication implementation is solid but lacks rate limiting.

## Critical Findings ⚠️

1. **Hardcoded API Key** (config.py:42)
   - Severity: CRITICAL
   - Risk: Credential exposure

2. **SQL Injection** (legacy.py:88)
   - Severity: CRITICAL
   - Risk: Data breach, unauthorized access

## Database Security Scan

**Findings**: 5 total
- SQL Injection patterns: 2
- Unsafe query building: 2
- Hardcoded credentials: 1

**Files Affected**:
- legacy.py (2 issues)
- config.py (1 issue)
- migrations/001_initial.py (2 issues)

## Recommendations

### Immediate (Fix Today)
1. Remove hardcoded API key from config.py - use environment variable
2. Replace raw SQL concatenation with parameterized queries in legacy.py

### This Sprint
1. Add rate limiting to authentication endpoints
2. Implement input validation middleware
3. Review all database query patterns

### Next Sprint
1. Set up security scanning in CI/CD
2. Implement security headers (CSP, HSTS)
3. Add dependency vulnerability scanning

## Detailed Findings

### SQL Injection (2 occurrences)
```python
# legacy.py:88 - VULNERABLE
cursor.execute("SELECT * FROM users WHERE id = " + user_id)

# FIX: Use parameterized queries
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
```

### Hardcoded Secrets (1 occurrence)
```python
# config.py:42 - VULNERABLE
API_KEY = 'sk-live-abc123...'

# FIX: Use environment variable
API_KEY = os.environ.get('API_KEY')
if not API_KEY:
    raise ValueError("API_KEY environment variable required")
```"
