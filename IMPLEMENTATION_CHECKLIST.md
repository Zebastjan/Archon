# Semgrep Integration - Implementation Checklist

## ✅ Completed

### Database Layer
- [x] Migration `022_semgrep_integration.sql` created with:
  - `archon_semgrep_findings` - Store Semgrep results
  - `archon_audit_triage_memory` - Pattern → decision learning
  - `archon_audit_false_negatives` - Track missed bugs
  - `archon_audit_rule_quality` - Per-rule metrics
  - Semantic search functions for triage suggestions

### Service Layer  
- [x] `python/src/server/services/semgrep_service.py` - Core business logic:
  - Run Semgrep audits with configurable rulesets
  - Parse JSON output and store findings
  - Triage workflow with memory storage
  - Suggest decisions based on similar patterns
  - False negative tracking and analysis
  - Rule quality metrics

### API Layer
- [x] `python/src/server/api_routes/audit_api.py` - Server endpoints:
  - `POST /api/audit/run` - Execute audit
  - `GET /api/audit/findings` - List findings
  - `POST /api/audit/findings/{id}/triage` - Triage finding
  - `GET /api/audit/findings/{id}/suggest` - Get triage suggestion
  - `POST /api/audit/false-negatives` - Record missed bug
  - `GET /api/audit/rule-quality` - Rule quality metrics

---

## 🔧 Required Next Steps

### 1. Wire Migration (5 min)
**File:** `migration/complete_setup.sql`

Add to the end of the migrations list:
```sql
INSERT INTO archon_migrations (version, migration_name)
VALUES ('022', 'Semgrep integration and meta-audit system')
ON CONFLICT (version, migration_name) DO NOTHING;
```

### 2. Install Semgrep in Server Container (10 min)
**File:** `python/requirements.txt` or Dockerfile

Add:
```
semgrep>=1.60.0
```

Or in Dockerfile:
```dockerfile
RUN pip install semgrep
```

### 3. Register API Routes (5 min)
**File:** `python/src/server/main.py`

Add import and registration:
```python
from .api_routes import audit_api

# ... existing routes ...
app.include_router(audit_api.router)
```

### 4. Test End-to-End (30 min)

#### Test 1: Health Check
```bash
curl http://localhost:8000/api/audit/health
```
Expected: `{"status": "healthy", "semgrep_available": true}`

#### Test 2: Run Audit
```bash
curl -X POST http://localhost:8000/api/audit/run \
  -H "Content-Type: application/json" \
  -d '{
    "repo_id": "your-repo-uuid",
    "rulesets": ["p/ci"]
  }'
```
Expected: `{"status": "success", "findings_count": N}`

#### Test 3: List Findings
```bash
curl "http://localhost:8000/api/audit/findings?repo_id=your-repo-uuid&limit=10"
```

#### Test 4: Triage Finding
```bash
curl -X POST http://localhost:8000/api/audit/findings/{finding-id}/triage \
  -H "Content-Type: application/json" \
  -d '{
    "decision": "intentional",
    "rationale": "Broad except is used for top-level error routing",
    "reviewer": "zebastjan"
  }'
```

### 5. Add MCP Wrapper (After server tests pass)
**File:** Create `python/src/server/mcp_server/audit_tools.py`

MCP tools should call server endpoints via HTTP, not import service directly:
```python
async def code_audit_run_semgrep(repo_id: str, rulesets: list[str] | None = None):
    """MCP tool that calls server API."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://archon-server:8000/api/audit/run",
            json={"repo_id": repo_id, "rulesets": rulesets}
        )
        return response.json()
```

---

## 📋 Rollout Sequence

### Phase 1: Server-Only (This Week)
1. ✅ Migration created
2. ✅ Service created  
3. ✅ API routes created
4. ⬜ Wire migration
5. ⬜ Install Semgrep
6. ⬜ Register routes
7. ⬜ Test end-to-end
8. ⬜ Document ruleset policy (`p/ci` for PR gates)

**Success Criteria:**
- Health check returns healthy
- Can run audit on test repo
- Findings stored in database
- Can triage a finding

### Phase 2: MCP Integration (Next Week)
1. ⬜ Create MCP tools that call server endpoints
2. ⬜ Test MCP tools in isolation
3. ⬜ Update agent prompts to use audit tools
4. ⬜ Add audit workflow to agent capabilities

**Success Criteria:**
- MCP tool can trigger audit
- MCP tool can list findings
- MCP tool can triage findings

### Phase 3: Production Hardening (Week 3-4)
1. ⬜ Add async job queue for long audits
2. ⬜ Add caching for rule quality metrics
3. ⬜ Add webhook support for CI integration
4. ⬜ Create custom Semgrep rules for Archon patterns
5. ⬜ Document triage workflow for developers

**Success Criteria:**
- CI integration works (PR gates)
- Async audits don't block requests
- Custom rules catch Archon-specific issues

### Phase 4: Meta-Audit Maturity (Ongoing)
1. ⬜ First false negative recorded
2. ⬜ Triage memory has 50+ entries
3. ⬜ Suggestions are accurate >70% of time
4. ⬜ Rule quality report identifies 1+ rule to disable
5. ⬜ Custom rules written based on false negative analysis

**Success Criteria:**
- System learns from mistakes
- False positive rate <20% for active rules
- New bug types drive rule improvements

---

## 🐳 Container Strategy

**Semgrep installed in:**
- ✅ `archon-server` container (primary)
- ⬜ Optional: Dedicated `archon-audit-worker` container (for async processing)

**NOT installed in:**
- `archon-mcp` (lightweight wrapper only)
- `archon-ui` (calls APIs)
- `archon-agents` (calls APIs via MCP)

---

## 📊 Ruleset Policy

### PR Gates (Blocking CI)
- **Ruleset:** `p/ci`
- **Rationale:** High-confidence logic bugs and security issues
- **Threshold:** Zero tolerance for findings (or explicit suppressions)

### Scheduled/Manual Audits
- **Rulesets:** `p/security-audit`, `p/owasp-top-ten`, `p/cwe-top-25`
- **Rationale:** Broader security coverage, higher false positive rate acceptable
- **Workflow:** Findings → Triage → Task creation

### Custom Rules (Future)
- Archon-specific patterns
- Learned from false negatives
- Stored in `python/semgrep-rules/`

---

## 🎯 First Acceptance Test

**Test:** Python repo + TypeScript repo

**Steps:**
1. Index a Python repo (Archon itself?)
2. Index a TypeScript repo (archon-ui?)
3. Run audit with `p/ci` on both
4. Verify findings stored correctly
5. Triage 5 findings on each
6. Verify triage memory works (suggestions appear)
7. Record 1 false negative on each
8. Verify rule quality metrics calculated

**Pass Criteria:**
- Zero errors in logs
- Findings stored in database
- Triage decisions persisted
- Suggestions returned for similar patterns
- Rule quality report generated

---

## 🚫 What NOT to Do

1. **Don't** install Semgrep in MCP container
2. **Don't** import service directly in MCP (use HTTP calls)
3. **Don't** use old regex-based rules for new audits
4. **Don't** auto-triage with 8B model (use triage memory instead)
5. **Don't** enable noisy rules in CI (`p/security-audit`)
6. **Don't** skip the server-endpoints-first sequence

---

## ✅ Ready to Execute?

Next actions:
1. Run migration 022
2. Install Semgrep
3. Register API routes
4. Test health endpoint
5. Run first audit

Want me to do any of these now?
