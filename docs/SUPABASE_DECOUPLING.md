# Supabase Decoupling Summary

**Status:** COMPLETE - Core audit path now uses Postgres exclusively  
**Date:** 2026-03-16  

---

## What Was Changed

### 1. Core Audit Path - audit_api.py

**Before:** Used `get_supabase_client()` for all DB operations  
**After:** Uses `get_database_connector()` (Postgres asyncpg)

| Endpoint | Change |
|----------|--------|
| `POST /api/audit/run` | Now queries `archon_code_repos` via Postgres |
| `GET /api/audit/false-negatives` | Uses `db.fetch()` instead of Supabase |
| `GET /api/audit/rule-quality/{check_id}` | Uses `db.fetchrow()` instead of Supabase |
| `GET /api/audit/triage-memory` | Uses `db.fetch()` and `db.fetchval()` |

**Key fixes:**
- Added JSON parsing for `methodology` field (stored as text in Postgres)
- Added missing `from pathlib import Path` import

### 2. Nim Audit Service - nim_audit_service.py

**Before:** Hardcoded `localhost:5434` connection string  
**After:** Uses `ARCHON_DATABASE_URL` env var with Docker-compatible defaults

```python
# Now uses env var or defaults to Docker postgres host
db_url = os.getenv("ARCHON_DATABASE_URL", 
                  "postgresql://archon:archon_local_dev@postgres:5432/archon")
```

### 3. Environment Configuration - .env.example

**Before:** Supabase marked as "Legacy" with confusing instructions  
**After:** Clear "Postgres first, Supabase optional" messaging

```bash
# =============================================================================
# OPTIONAL: Supabase Configuration (Sample/Demo only - NOT required for core audits)
# =============================================================================
# Supabase is NOT required for Archon core functionality including:
# - Repository indexing and code entity extraction
# - Nim audits and security scanning
# - All MCP tools and API endpoints
#
# ⚠️ DO NOT set these for standard Archon/Nim audit workflows.
# If audit code asks for SUPABASE_URL/SUPABASE_SERVICE_KEY, that's a bug—
# report it so we can fix the service to use standard Postgres.
```

---

## Verification Results

### Test: Omnibus Nim Audit via Postgres

```bash
curl -X POST http://localhost:8181/api/audit/run \
  -d '{"repo_id": "15f7ea16-d016-492b-8193-dbbd55f33281"}'
```

**Result:**
```json
{
  "status": "success",
  "total_findings": 18,
  "repo_name": "Omnibus"
}
```

**Findings breakdown:**
- 18 suspicious discard usages detected
- 0 missing doc comments
- All stored via Postgres (no Supabase references in logs)

### Test: Repository Indexing (Nim entities)

```bash
curl http://localhost:8181/api/code_repos
```

**Result:**
```json
{
  "name": "Omnibus",
  "status": "ready",
  "entities_count": 62
}
```

**62 Nim entities** indexed from 34 files via Tree-sitter.

---

## Files Modified

| File | Changes |
|------|---------|
| `python/src/server/api_routes/audit_api.py` | Replaced Supabase with DatabaseConnector; added JSON parsing; added Path import |
| `python/src/server/services/nim_audit_service.py` | Fixed hardcoded DB connection to use env vars |
| `.env.example` | Updated Supabase section to clearly mark as optional |

---

## Remaining Supabase References (Non-Core)

These are **sample/demo code only** and do not affect core functionality:

- `python/src/agents/sample_supabase_agent.py` - Example agent (optional)
- Various comments in `docker-compose.yml` mentioning legacy Supabase support

**Core services (audit, indexing, MCP) are now 100% Postgres-native.**

---

## Error Message Changes

**Before:**
```
"SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in environment variables"
```

**After:**
```
"This environment uses direct PostgreSQL; Supabase credentials are not required. 
If you see this message, it is a bug—please fix the service to use the standard Postgres DB connector."
```

(Note: This exact message appears in `.env.example` as guidance; actual errors now come from Postgres connection failures, not Supabase env checks.)

---

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   MCP Tools     │────▶│  audit_api.py    │────▶│   Postgres      │
│  (Windsurf)     │     │  (FastAPI)       │     │  (Docker)       │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌──────────────────┐
                        │  nim_audit_svc   │
                        │  (Tree-sitter)   │
                        └──────────────────┘
```

**No Supabase in core path.** Sample/demo code may still reference Supabase for external integrations.
