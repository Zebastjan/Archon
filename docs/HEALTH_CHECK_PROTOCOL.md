# Archon Health Check Protocol

**Purpose:** Define the minimal set of checks required to verify that Archon/Omnibus infrastructure is "booted and healthy" after a cold start.

## The Three Required Checks

On a cold boot, you want one command to give you green across:

1. **Postgres (Archon DB)** — verified indirectly
2. **Archon server (API)** — `GET /health` returns 200
3. **Archon MCP server** — `health_check` tool passes with DB connectivity
4. **Background workers** (audit, code-intel) — verified via API health

### Check 1: Archon Server `/health`

```bash
curl -s http://localhost:8181/health | jq .
```

**Expected response:**
```json
{
  "status": "healthy",
  "service": "archon-backend",
  "ready": true,
  "credentials_loaded": true,
  "schema_valid": true
}
```

**Failure modes:**
- `503 initializing` — Server is still starting up
- `503 migration_required` — Database schema needs migration
- Connection refused — Server not running

### Check 2: MCP `health_check` Tool

The MCP health check now includes DB connectivity verification. The MCP server queries the archon-server `/health` endpoint and extracts the `database` status.

**What it verifies:**
- MCP server is running
- API service is reachable
- **Database is connected** (via archon-server health check)

**Health status fields:**
```json
{
  "success": true,
  "health": {
    "status": "healthy",
    "api_service": true,
    "agents_service": true|false,
    "database": true,
    "last_health_check": "2025-01-15T10:30:00Z"
  },
  "uptime_seconds": 123
}
```

### Check 3: MCP DB-Backed Tool

A simple tool that requires DB connectivity:

- `find_projects()` — Lists projects from the database

**Failure mode:**
- Returns connection error if DB is unreachable
- Returns empty list if no projects exist (this is OK)

## Automated Validation

Run the validation script after cold boot:

```bash
make health-check
# or
./scripts/validate_health.sh
```

**What it does:**
1. Waits for archon-server `/health` to return 200 with `ready: true`
2. Calls MCP `health_check` and verifies `database: true`
3. Calls `find_projects` and verifies it returns data (or empty list, not error)

## Startup Sequence

Expected startup behavior with retry logic:

1. Postgres starts first (healthcheck: `pg_isready`)
2. archon-server waits for Postgres healthy, then starts
   - Performs DB migrations on startup
   - `/health` returns 200 only when DB is verified
3. MCP server waits for archon-server healthy, then starts
   - Retries health check up to 10 times with exponential backoff
   - Fails loudly if DB connectivity never succeeds

## Troubleshooting

### "Database connectivity failed after 10 attempts"

**Check:**
```bash
# Is Postgres running?
docker compose ps postgres

# Is archon-server healthy?
curl http://localhost:8181/health

# Check archon-server logs
docker compose logs archon-server | tail -50

# Check MCP logs
docker compose logs archon-mcp | tail -50
```

### ".env file has localhost instead of postgres hostname"

**Fix:**
```bash
# Edit .env
ARCHON_DATABASE_URL=postgresql://archon:archon_local_dev@postgres:5432/archon
# NOT: @localhost:5432
```

Then restart:
```bash
docker compose down && docker compose up -d
```

## MCP-First Contract

Once health checks pass, all agents must:
- Use MCP tools for DB access (no `psql`, no shell queries)
- Query schema via MCP, not `grep`/`find`
- Stop and report if MCP call fails — no fallback to shell

See: `.windsurf/agents/archon-system-prompt.md`
