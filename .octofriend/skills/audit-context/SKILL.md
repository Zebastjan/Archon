# Audit Context Skill

Get comprehensive audit findings in a single batched call - the preferred entry point for all audit analysis.

## When to Use

Use this skill when:
- Starting ANY audit-related work
- Triage of existing findings
- Getting a comprehensive view of codebase issues
- Cross-referencing findings with code entities
- Preparing for remediation work

## When NOT to Use

Do NOT use when:
- You only need audit rules definitions (use code_audit_get_rules)
- You need to update finding status (use code_audit_acknowledge_finding)
- You're running a new audit (use quick-health-check or repo_health_check)

## Why This Skill is Critical

**`audit_get_context`** is a SUPER-TOOL that replaces multiple separate calls:

| Instead Of | Use |
|------------|-----|
| code_audit_get_findings() + code_audit_get_summary() + code_audit_get_rules() | audit_get_context() |
| Multiple calls to get repo_id and findings | Single batched call |
| Sequential discovery | Parallel grouped results |

**Benefits**:
- Reduces tool calls from 4-5 to 1
- Returns findings grouped by source (semgrep, audit_rules, etc.)
- Includes sample snippets for immediate analysis
- Provides repo_id for follow-up operations

## Workflow

### Step 1: Get Context

```
audit_get_context(repo_name="<repository_name>")
```

**Note**: Use repo **name**, not repo_id. This tool looks up the ID internally.

### Step 2: Analyze Results

The response includes:

```json
{
  "success": true,
  "repo_id": "uuid",           // Use for follow-up operations
  "findings_by_source": {      // Grouped by detection source
    "semgrep": [...],
    "audit_rules": [...]
  },
  "summary": {
    "total_open": 17,
    "critical": 5,
    "error": 0,
    "warning": 12
  }
}
```

### Step 3: Presentation

Structure your response:

```markdown
# Audit Context: [repo_name]

**Repository ID**: [repo_id]
**Total Open Findings**: [total_open]

## Severity Breakdown
- Critical: [X]
- Error: [Y]
- Warning: [Z]
- Info: [W]

## Findings by Source

### [Source 1]: [count] findings
| Check ID | Count | Severity | Sample |
|----------|-------|----------|--------|
| [id] | [N] | [sev] | [file]:[line] |

### [Source 2]: [count] findings
...

## Top Issues to Address
1. **[Severity]**: [Check ID] ([count] occurrences)
   - Sample: [file]:[line] - [snippet preview]

2. ...

## Recommended Actions
- [Specific next steps based on findings]
```

## Integration with Other Tools

**Got repo_id? Use it for**:
- codebase_find_entity(repo_id, ...)
- codebase_get_repository_stats(repo_id)
- repo_health_check(repo_id)

**Got finding location? Deep dive with**:
- codebase_find_entity(repo_id, name from finding)
- function-deep-dive skill

## Example Invocation

User: "Show me the audit findings for archon"

Claude: [calls audit_get_context(repo_name="archon")]

Claude: "# Audit Context: archon

**Repository ID**: abc-123-uuid
**Total Open Findings**: 17

## Severity Breakdown
- Critical: 0 ✅
- Error: 3 ⚠️
- Warning: 12
- Info: 2

## Findings by Source

### semgrep: 10 findings
| Check ID | Count | Severity | Sample |
|----------|-------|----------|--------|
| hardcoded-secrets | 2 | ERROR | config.py:42 |
| sql-injection | 1 | ERROR | legacy.py:88 |
| unused-import | 5 | WARNING | various |
| weak-crypto | 2 | WARNING | auth.py:156 |

### audit_rules: 7 findings
| Check ID | Count | Severity | Sample |
|----------|-------|----------|--------|
| complexity-high | 3 | WARNING | mcp_server.py:145 |
| missing-docstring | 4 | INFO | services.py:23 |

## Top Issues to Address

1. **ERROR**: hardcoded-secrets (2 occurrences)
   - Sample: config.py:42 - `API_KEY = 'sk-...'`
   - Sample: config.py:45 - `DB_PASSWORD = 'admin123'`

2. **ERROR**: sql-injection (1 occurrence)
   - Sample: legacy.py:88 - `cursor.execute("SELECT * FROM users WHERE id = " + user_id)`

3. **WARNING**: complexity-high (3 occurrences)
   - Sample: mcp_server.py:145 - function complexity score: 12

## Recommended Actions
1. **Immediate**: Remove hardcoded secrets, use environment variables
2. **This sprint**: Replace raw SQL with parameterized queries
3. **Next sprint**: Refactor high-complexity functions in mcp_server.py"

## Batching Rules

**This skill uses exactly 1 tool call** - no batching needed.

Follow-up operations can be batched with the returned repo_id.
