# DB Audit Triage Notes

> **Date**: March 2026  
> **Scope**: SQL injection and unsafe database patterns in Archon server code  
> **Policy**: `python/src/server/semgrep_rules/db/`

---

## Ruleset Overview

### Custom Rules Created

1. **python-sql-injection.yaml**
   - `db-python-sql-injection-psycopg2`: Detects string formatting in psycopg2.execute()
   - `db-python-sql-injection-string-format`: Detects f-string/query construction
   - `db-python-sql-injection-execute-many`: Flags executemany with dynamic queries
   - `db-python-unsafe-raw-sql`: Warns on asyncpg raw execution
   - `db-python-hardcoded-sql-credentials`: Detects hardcoded connection strings

2. **js-sql-injection.yaml**
   - `db-js-sql-injection-string-concat`: Detects string concat in queries
   - `db-js-sql-injection-template-literal`: Detects template literals in queries
   - `db-js-sql-injection-pg-format`: Notes pg-format usage (safe for identifiers)
   - `db-js-unsafe-dynamic-query`: Flags dynamic query construction
   - `db-js-hardcoded-connection-string`: Detects hardcoded postgres URLs

### Official Rulesets Used

- `p/python`: Python security patterns
- `p/javascript`: JavaScript security patterns  
- `p/typescript`: TypeScript security patterns
- `p/security-audit`: General security audit patterns

### Exclusions (Test Files)

By default, we exclude:
- `**/test/**`, `**/tests/**`
- `**/*_test.py`, `**/*.test.ts`, `**/*.test.js`
- `**/fixtures/**`, `**/mocks/**`
- `**/conftest.py`

---

## Triage Decision Framework

### Decision: `needs_fix` (Critical)

Apply when:
- SQL injection via string formatting/concatenation
- Hardcoded database credentials
- User input directly interpolated into queries

Examples:
```python
# BAD - needs_fix
cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")  # SQLi

# BAD - needs_fix  
conn = psycopg2.connect("postgresql://user:secret@localhost/db")  # Hardcoded
```

### Decision: `intentional` (Safe by Design)

Apply when:
- pg-format used for identifiers (not values)
- Migration files with DDL only
- Schema definition queries with no user input

Examples:
```python
# OK - intentional (DDL only, no user data)
cursor.execute("CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY)")

# OK - intentional (pg-format for identifiers only)
query = format("ALTER TABLE %I ADD COLUMN %I TEXT", table_name, col_name)
```

### Decision: `wont_fix` (Low Risk)

Apply when:
- Pattern is technically a finding but risk is negligible
- Code is in test/migration paths already excluded
- False positive rate is high for this pattern

Examples:
- Complex ORM-generated queries flagged as "raw SQL"
- Internal admin scripts with hardcoded read-only queries

### Decision: `needs_review` (Manual Verification)

Apply when:
- execute_many with bound parameters (might be safe)
- Dynamic query construction with sanitization
- Raw SQL that uses parameterization but flagged

Examples:
```python
# REVIEW - might be safe
cursor.executemany("INSERT INTO logs VALUES (%s, %s)", data_list)  # Check if data_list is trusted
```

---

## Configuration

### Machine-Readable Config
- File: `python/src/server/config/db_audit_triage.yaml`
- Contains default decisions per check_id
- Supports path-based overrides
- Records confidence levels

### Running DB Audit

```python
# Via MCP tool
await repo_health_check(
    repo_id="...",
    focus="security",
    ruleset="python/src/server/semgrep_rules/db/python-sql-injection.yaml,python/src/server/semgrep_rules/db/js-sql-injection.yaml"
)

# Via API
POST /api/audit/run
{
    "repo_id": "...",
    "rulesets": ["p/python", "p/javascript", "python/src/server/semgrep_rules/db"],
    "exclude_patterns": ["**/test/**", "**/migrations/**"]
}
```

---

## Known Patterns

### Safe: Parameterized Queries
```python
# These are SAFE and should not be flagged
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))

# asyncpg - uses $1, $2 style
cursor.execute("SELECT * FROM users WHERE id = $1", user_id)
```

### Unsafe: String Interpolation
```python
# These are UNSAFE and will be flagged
cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
cursor.execute("SELECT * FROM users WHERE id = " + user_id)
cursor.execute("SELECT * FROM users WHERE id = %s" % user_id)
```

### Gray Area: Dynamic Queries with Safeguards
```python
# These need review - might be safe with proper validation
allowed_columns = {"name", "email", "id"}
if column in allowed_columns:
    cursor.execute(f"SELECT {column} FROM users")  # Safe if column is validated
```

---

## Integration with Audit Workflow

1. **Run Audit**: Trigger DB ruleset via `POST /api/audit/run`
2. **Fetch Results**: Use `audit_get_context(repo_name)` for batched results
3. **Auto-Triage**: Apply defaults from `db_audit_triage.yaml`
4. **Review**: Only `needs_review` findings surface for human attention
5. **Record**: Store decisions in `archon_audit_triage_memory`
6. **Learn**: Future similar findings get auto-triaged based on history

---

## Maintenance

### When to Update

- New database library added (e.g., SQLAlchemy, Prisma)
- New finding patterns observed
- Rule false positive rate exceeds 50%

### How to Update

1. Edit `python/src/server/semgrep_rules/db/*.yaml` for rule changes
2. Edit `python/src/server/config/db_audit_triage.yaml` for triage changes
3. Test on Archon server code first
4. Update this document with rationale

---

## References

- OWASP SQL Injection: https://owasp.org/www-community/attacks/SQL_Injection
- psycopg2 Best Practices: https://www.psycopg.org/docs/usage.html#sql-injection-attacks
- Semgrep SQL Rules: https://semgrep.dev/r?q=sql
- Trail of Bits Rules: https://github.com/trailofbits/semgrep-rules
