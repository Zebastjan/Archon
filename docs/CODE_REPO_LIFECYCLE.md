# Code Repository Lifecycle in Archon

**Version:** 1.0.0  
**Applies to:** Archon code intelligence system

---

## Lifecycle States

A repository in Archon progresses through these states:

```
┌─────────────┐    ┌──────────┐    ┌───────────┐    ┌────────┐
│  Not Known  │───▶│ Created  │───▶│ Indexing  │───▶│ Ready  │
└─────────────┘    └──────────┘    └───────────┘    └────────┘
     │                   │                │               │
     │                   │                ▼               │
     │                   │           ┌──────────┐         │
     │                   │           │  Error   │         │
     │                   │           └──────────┘         │
     │                   │                │               │
     │                   │                └───────────────┘
     │                   │                     (retry)
     │                   │
     │                   ▼
     │            ┌────────────┐
     └───────────▶│ Existing   │ (idempotent)
                  └────────────┘
```

### State Definitions

| State | Description | Database Indicators |
|-------|-------------|---------------------|
| **Not Known** | Repo has never been registered | No row in `archon_code_repos` |
| **Created** | Repo row exists, but no entities ingested | Row exists, `last_synced` is NULL |
| **Indexing** | Ingestion in progress | `indexing_status = 'indexing'` or `last_synced` stale + recent `indexing_started_at` |
| **Ready** | Fully indexed and available for queries | `last_synced` recent, entities exist in `archon_code_entities` |
| **Error** | Indexing failed | `indexing_status = 'error'`, `error_message` set |

---

## State Transitions

### Not Known → Created

**Trigger:** Call `code_repos_create_and_index` or HTTP `POST /api/code_repos/create-and-index`

**What happens:**
1. Validate `local_path` exists and is a git repository
2. Check if repo already exists by `local_path` (idempotent)
3. Create row in `archon_code_repos`:
   ```sql
   INSERT INTO archon_code_repos (name, local_path, github_url, branch, ...)
   VALUES (...)
   ```
4. Set `indexing_status = 'queued'`

### Created → Indexing

**Trigger:** Background task starts ingestion

**What happens:**
1. Update `indexing_status = 'indexing'`, `indexing_started_at = NOW()`
2. Call ingestion pipeline (`quick_ingest_repo.py` or `CodeEntityService`)
3. Extract entities from all supported files
4. Store in `archon_code_entities`

### Indexing → Ready

**Trigger:** Ingestion completes successfully

**What happens:**
1. Update `indexing_status = 'ready'`
2. Set `last_synced = NOW()`
3. Update `last_commit_sha` to current HEAD
4. Update `entities_count` (or query `archon_code_entities`)

### Indexing → Error

**Trigger:** Ingestion fails

**What happens:**
1. Update `indexing_status = 'error'`
2. Set `error_message` with failure details
3. Allow retry via `reindex: true` parameter

### Ready → Indexing (Reindex)

**Trigger:** Call with `reindex: true` or incremental update (git hook)

**What happens:**
- Full re-ingestion: Clear entities, re-extract all files
- Incremental: Only update changed files (post-commit hook)

---

## Current Manual Steps (Before Automation)

Before the unified `create_and_index` operation, adding a repo required:

```bash
# Step 1: Create repo row (via direct DB or git_repo_manager)
cd /home/zebastjan/dev/archon/python
uv run python -c "
import asyncio
from src.server.services.git_repo_manager import get_repo_manager

async def main():
    manager = get_repo_manager()
    config = await manager.register_local_repo(
        '/home/zebastjan/dev/Omnibus',
        name='Omnibus'
    )
    print(f'Repo ID: {config.repo_id}')

asyncio.run(main())
"

# Step 2: Trigger indexing (separate step)
uv run python scripts/quick_ingest_repo.py /home/zebastjan/dev/Omnibus

# Step 3: Verify in database
psql -c "SELECT * FROM archon_code_entities WHERE repo_id = (SELECT id FROM archon_code_repos WHERE name = 'Omnibus') LIMIT 5;"
```

**Problems with manual approach:**
- Requires shell access to Archon server
- Multiple discrete steps
- No unified status tracking
- Not accessible via MCP

---

## Automated Flow (With Create + Index)

### Via HTTP API

```bash
# Create and index in one call
curl -X POST http://localhost:8181/api/code_repos/create-and-index \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Omnibus",
    "local_path": "/home/zebastjan/dev/Omnibus",
    "github_url": "https://github.com/zebastjan/Omnibus"
  }'

# Response:
# {
#   "success": true,
#   "repo_id": "550e8400-e29b-41d4-a716-446655440000",
#   "name": "Omnibus",
#   "status": "queued",
#   "entities_count": 0,
#   "existing": false
# }

# Poll status until ready
curl http://localhost:8181/api/code_repos/550e8400-e29b-41d4-a716-446655440000/status

# Response when ready:
# {
#   "repo_id": "550e8400-e29b-41d4-a716-446655440000",
#   "status": "ready",
#   "entities_count": 1234,
#   "last_synced": "2025-01-15T10:30:00Z"
# }
```

### Via MCP Tool

```python
# Create and index
result = await code_repos_create_and_index(
    name="Omnibus",
    local_path="/home/zebastjan/dev/Omnibus",
    github_url="https://github.com/zebastjan/Omnibus",
    wait_for_ready=True,  # Optional: block until ready
    timeout_seconds=300
)

# Response:
# {
#   "success": True,
#   "repo_id": "550e8400-e29b-41d4-a716-446655440000",
#   "status": "ready",
#   "entities_count": 1234,
#   "existing": False
# }

# Now use for audit
context = await audit_get_context(repo_name="Omnibus")
```

### Via CLI

```bash
# Add repo
archon code-repos add \
  --name Omnibus \
  --root-path /home/zebastjan/dev/Omnibus \
  --github-url https://github.com/zebastjan/Omnibus

# Output:
# Created repo Omnibus (550e8400-e29b-41d4-a716-446655440000)
# Status: indexing...
# 
# Polling status... ready!
# Entities indexed: 1234
```

---

## Idempotency and Safety

### Idempotency

The `create_and_index` operation is idempotent:

| Scenario | Behavior |
|----------|----------|
| Repo doesn't exist | Create row, start indexing, return `existing: false` |
| Repo exists, status=ready | Return existing repo_id, `existing: true`, `status: ready` |
| Repo exists, status=indexing | Return existing repo_id, continue monitoring |
| Repo exists, status=error | Return error, suggest `reindex: true` to retry |

### Safety

| Check | Error Response |
|-------|---------------|
| Path doesn't exist | `status: "error"`, `error_message: "Path not found: /path"` |
| Path not a git repo | `status: "error"`, `error_message: "Not a git repository: /path"` |
| Indexing fails | `status: "error"`, `error_message` includes exception details |
| Timeout (if waiting) | Return current status, note that indexing continues |

---

## Database Schema

### archon_code_repos (Existing)

```sql
CREATE TABLE archon_code_repos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    local_path TEXT UNIQUE NOT NULL,
    github_owner TEXT,
    github_repo TEXT,
    github_url TEXT,
    branch TEXT DEFAULT 'main',
    last_commit_sha TEXT,
    last_synced TIMESTAMPTZ,
    auto_sync BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Proposed Additions

```sql
-- Add status tracking columns
ALTER TABLE archon_code_repos ADD COLUMN IF NOT EXISTS indexing_status TEXT DEFAULT 'created';
ALTER TABLE archon_code_repos ADD COLUMN IF NOT EXISTS indexing_started_at TIMESTAMPTZ;
ALTER TABLE archon_code_repos ADD COLUMN IF NOT EXISTS indexing_completed_at TIMESTAMPTZ;
ALTER TABLE archon_code_repos ADD COLUMN IF NOT EXISTS error_message TEXT;
ALTER TABLE archon_code_repos ADD COLUMN IF NOT EXISTS entities_count INTEGER DEFAULT 0;
```

**Status enum:** `created`, `queued`, `indexing`, `ready`, `error`

---

## Integration with Recipes

When a recipe (e.g., `omnibus-nim-audit-triage`) calls `audit_get_context` and gets "Repository not found":

```python
# 1. Call create_and_index (single sanctioned path)
result = await code_repos_create_and_index(
    name="Omnibus",
    local_path="/home/zebastjan/dev/Omnibus"
)

# 2. Handle response
if result["status"] == "ready":
    # Proceed with audit
    context = await audit_get_context(repo_name="Omnibus")
elif result["status"] in ["queued", "indexing"]:
    # Poll or ask user to wait
    await poll_until_ready(result["repo_id"])
    context = await audit_get_context(repo_name="Omnibus")
elif result["status"] == "error":
    # Report error, no shell fallback
    raise RuntimeError(f"Failed to index repo: {result['error_message']}")
```

**Forbidden:**
- ❌ Using `psql` to manually insert rows
- ❌ Running ingestion scripts via shell
- ❌ Using `grep`/`find` to locate the repo

---

## Change Log

- **v1.0.0** (2025-01-15): Documented current lifecycle and proposed unified create+index flow
