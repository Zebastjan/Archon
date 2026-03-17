# Quick Health Check Skill

Rapid assessment of codebase health using the orchestrated super-tool with LLM-powered insights.

## When to Use

Use this skill when:
- Starting a code audit
- Evaluating code quality before significant changes
- Comparing multiple repositories
- Preparing for code review
- Getting a quick "state of the codebase" assessment

## When NOT to Use

Do NOT use when:
- You need specific finding details (use audit_get_context)
- You're investigating a single function (use function-deep-dive)
- You need DB security audit specifically (use db_security_audit)
- The orchestrator service is unavailable (use repo_health_check as fallback)

## Tool Selection Priority

**PREFERRED**: `orchestrated_repo_health_check`
- Provides LLM-generated executive summary
- Human-friendly detailed analysis
- Better recommendations

**FALLBACK**: `repo_health_check`
- Same underlying audit data
- No LLM insights
- Use when orchestrator unavailable

## Workflow

### Step 1: Determine Focus
Based on user request, select focus area:

| User Request | Focus Parameter |
|--------------|-----------------|
| "Health check" / "Audit" | `focus="full"` |
| "Security audit" / "Vulnerabilities" | `focus="security"` |
| "Test coverage" / "Testing" | `focus="tdd"` |
| "Documentation" / "Docs" | `focus="docs"` |
| "Code quality" / "Maintainability" | `focus="maintainability"` |
| "Database security" / "SQL injection" | `focus="db"` |

### Step 2: Execute Audit

```
orchestrated_repo_health_check(repo_id, focus="<selected_focus>")
```

This is a **single tool call** - no batching needed for the primary audit.

### Step 3: Cross-Reference (Optional)

If findings are detected, optionally get more context:

```
audit_get_context(repo_name)  # For detailed findings breakdown
```

**Note**: Only make this call if user wants to dive deeper into specific findings.

### Step 4: Presentation

Structure response based on orchestrated output:

```markdown
# Health Check: [Project Name]
**Focus**: [Security/TDD/Docs/Maintainability/Full]
**Score**: [X]/100

## Executive Summary
[Copy from orchestrated output's executive_summary]

## Detailed Analysis
[Copy from orchestrated output's detailed_analysis]

## Category Scores
- Overall: [X]
- Security: [X]
- Complexity: [X]
- Documentation: [X]
[etc.]

## Top Findings
[List from highlights, if any]

## Recommendations
[List from recommendations]
```

## Response Handling

### Success (orchestrated=True)
Present the LLM-generated insights directly. The orchestrator has already:
- Analyzed raw metrics
- Generated human-friendly summaries
- Prioritized recommendations

### Success (orchestrated=False / Fallback)
The orchestrator was unavailable. Present standard output:
- Health score
- Category scores
- Raw highlights
- Generate your own summary

### Failure
Report the error and suggest:
- Checking if repo_id is correct
- Trying repo_health_check as fallback
- Verifying database connectivity

## Tool Call Limits

**Maximum calls for this skill**:
- Primary audit: 1 call (`orchestrated_repo_health_check`)
- Optional follow-up: +1 call (`audit_get_context`) if findings exist

**Target**: 1-2 calls total

## Example Invocation

User: "Run a security audit on the archon repo"

Claude: [calls orchestrated_repo_health_check(repo_id="abc-123", focus="security")]

Claude: "# Health Check: Archon
**Focus**: Security
**Score**: 78/100

## Executive Summary
Repository has good overall security hygiene with 2 critical findings requiring immediate attention. SQL injection vulnerabilities detected in 3 legacy query builders. Authentication flow is properly implemented but lacks rate limiting.

## Detailed Analysis
• Address hardcoded secrets in config.py (lines 42-45)
• Refactor raw SQL in legacy_queries.py to use parameterized queries
• Add rate limiting to authentication endpoints
• Review CORS configuration for overly permissive settings
• Enable security headers middleware

## Category Scores
- Security: 72/100
- Complexity: 85/100
- Documentation: 78/100

## Top Findings
1. **CRITICAL**: Hardcoded API key (config.py:42)
2. **CRITICAL**: SQL injection vulnerability (legacy.py:88)
3. **WARNING**: Missing rate limiting (auth.py:156)"
