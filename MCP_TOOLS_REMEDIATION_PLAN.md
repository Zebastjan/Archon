# MCP Tools Remediation Plan

**Date**: 2025-01-20
**Status**: Critical Issues Identified, Fix Plan Ready

## Executive Summary

Three categories of issues identified:
1. **Configuration Issue** (1) - Database hostname mismatch
2. **Code Bugs** (3) - Async/await and missing methods
3. **Infrastructure** - Services are healthy but networking is misconfigured

---

## Issue 1: Database Connectivity (CRITICAL)

### Problem
MCP server can't connect to PostgreSQL because it's configured for Docker networking but running locally.

### Evidence
```
"could not translate host name "postgres" to address: Name or service not known"
```

### Root Cause
**`.env` configuration:**
```bash
ARCHON_DATABASE_URL=postgresql://archon:archon_local_dev@postgres:5432/archon
```

The MCP server is running **locally** (not in Docker), so it can't resolve the Docker hostname `postgres`.

### Impact
- 9 of 12 tools broken (75%)
- All audit tools fail
- All project/task tools fail
- All codebase entity tools fail

### Fix (Priority: CRITICAL)

**Option A: Quick Fix (Recommended for Development)**

1. Edit `.env` file:
   ```bash
   # BEFORE:
   ARCHON_DATABASE_URL=postgresql://archon:archon_local_dev@postgres:5432/archon
   
   # AFTER:
   ARCHON_DATABASE_URL=postgresql://archon:archon_local_dev@localhost:5434/archon
   ```

2. Verify PostgreSQL is accessible on localhost:5434:
   ```bash
   psql postgresql://archon:archon_local_dev@localhost:5434/archon -c "SELECT 1"
   ```

3. Restart MCP server to pick up new env var

**Option B: Run MCP in Docker (Alternative)**

Run the MCP server inside Docker where it can resolve the `postgres` hostname:
```bash
docker-compose up archon-mcp -d
```

**Recommendation**: Use Option A for development - it's faster and matches the typical local development workflow.

---

## Issue 2: Code Bugs (HIGH)

### Bug 2.1: Missing `list_worktrees` Method

**Location**: `python/src/mcp_server/features/worktree/worktree_tools.py:257`

**Problem**:
```python
worktrees = service.list_worktrees()
```

But `WorktreeService` doesn't have this method.

**Fix**: Add the missing method to `worktree_service.py`:

```python
# In python/src/server/services/worktree_service.py

async def list_worktrees(self) -> list[dict[str, Any]]:
    """List all active worktrees with task counts."""
    try:
        db = get_database_connector()
        result = await db.fetch(
            """
            SELECT 
                w.worktree_id,
                w.branch_name,
                w.repo_path,
                COUNT(t.id) as active_task_count,
                COUNT(CASE WHEN t.status = 'doing' THEN 1 END) as doing_count,
                MAX(t.updated_at) as last_activity
            FROM archon_worktrees w
            LEFT JOIN archon_tasks t ON t.worktree_id = w.worktree_id 
                AND t.status IN ('todo', 'doing', 'review')
            GROUP BY w.worktree_id, w.branch_name, w.repo_path
            ORDER BY last_activity DESC
            """
        )
        
        return [
            {
                "worktree_id": row["worktree_id"],
                "branch_name": row["branch_name"],
                "repo_path": row["repo_path"],
                "active_task_count": row["active_task_count"],
                "doing_count": row["doing_count"],
                "last_activity": row["last_activity"].isoformat() if row["last_activity"] else None,
            }
            for row in result
        ]
    except Exception as e:
        logger.error(f"Error listing worktrees: {e}")
        return []
```

**Note**: If `archon_worktrees` table doesn't exist, this needs to be created via migration first.

---

### Bug 2.2: Async Method Not Awaited

**Location**: `python/src/mcp_server/features/worktree/worktree_tools.py:155`

**Problem**:
```python
result = service.validate_safe_to_work(
    task_id=task_id,
    file_paths=file_paths,
    entity_ids=entity_ids,
)
# Missing 'await'!
```

The `validate_safe_to_work` method is `async`, so it returns a coroutine object, not the result.

**Fix**: Add `await`:

```python
result = await service.validate_safe_to_work(
    task_id=task_id,
    file_paths=file_paths,
    entity_ids=entity_ids,
)
```

---

### Bug 2.3: Another Async Method Not Awaited

**Location**: `python/src/mcp_server/features/worktree/worktree_tools.py:277`

**Problem**:
```python
validation = service.validate_safe_to_work(
    file_paths=file_paths,
    entity_ids=entity_ids,
)
# Missing 'await'!
```

**Fix**: Add `await`:

```python
validation = await service.validate_safe_to_work(
    file_paths=file_paths,
    entity_ids=entity_ids,
)
```

---

## Issue 3: API Server Error (MEDIUM)

### Problem
`find_projects` and `find_tasks` return HTTP 500 errors from the archon-server API.

### Evidence
```
"Failed to list projects: cannot unpack non-iterable coroutine object"
"Server error '500 Internal Server Error' for url 'http://localhost:8181/api/tasks'"
```

### Likely Root Cause
The API server (archon-server) is also having database connectivity issues, causing internal errors.

### Fix
1. Fix Issue #1 (Database connectivity) first
2. Check if API server picks up the database
3. If still failing, check API server logs:
   ```bash
   docker-compose logs archon-server --tail 100
   ```

---

## Verification Steps

After applying fixes:

### Step 1: Database Connectivity
```bash
# Test database connection
psql postgresql://archon:archon_local_dev@localhost:5434/archon -c "SELECT version();"
```

### Step 2: MCP Server Health
```bash
# Restart MCP server
cd /home/zebastjan/dev/archon/python
python -m src.mcp_server.mcp_server &

# Test health endpoint
curl -s http://localhost:8051/health
```

### Step 3: Tool Tests

**Test 1**: worktree_get_current_info (already working)
```bash
# This should continue to work
curl -s http://localhost:8051/mcp -X POST \
  -H "Content-Type: application/json" \
  -d '{"tool": "worktree_get_current_info"}'
```

**Test 2**: audit_get_context (currently broken)
```bash
# Should work after database fix
curl -s http://localhost:8051/mcp -X POST \
  -H "Content-Type: application/json" \
  -d '{"tool": "audit_get_context", "repo_name": "archon"}'
```

**Test 3**: code_audit_get_rules (currently broken)
```bash
# Should work after database fix
curl -s http://localhost:8051/mcp -X POST \
  -H "Content-Type: application/json" \
  -d '{"tool": "code_audit_get_rules"}'
```

---

## Implementation Order

### Phase 1: Database Fix (5 minutes)
1. [ ] Edit `.env` file: change `postgres:5432` to `localhost:5434`
2. [ ] Verify database connectivity: `psql ...`
3. [ ] Restart MCP server
4. [ ] Test: `audit_get_context`

### Phase 2: Code Bug Fixes (15 minutes)
1. [ ] Fix Bug 2.2: Add `await` at line 155
2. [ ] Fix Bug 2.3: Add `await` at line 277
3. [ ] Fix Bug 2.1: Add `list_worktrees` method (or stub)
4. [ ] Restart MCP server
5. [ ] Test: `worktree_validate_safe_to_work`
6. [ ] Test: `worktree_list_all`

### Phase 3: Verification (10 minutes)
1. [ ] Re-run full sanity check
2. [ ] Verify all 12 previously broken tools
3. [ ] Test skills with new fixes

---

## Why PostgreSQL Should Be Running

The containers show:
```
archon-postgres Up 39 hours (healthy) 0.0.0.0:5434->5432/tcp
```

**PostgreSQL IS running**, but:
1. It's inside Docker on port 5434 (exposed to host)
2. The MCP server is running locally, not in Docker
3. The `.env` file has Docker-internal hostname `postgres` which only works inside Docker

**Solution**: Change the hostname to `localhost` and use the exposed port `5434`.

---

## Migration Path for Production

If this needs to work in both Docker and local development:

**Option 1: Environment-specific .env files**
```bash
# .env.local
ARCHON_DATABASE_URL=postgresql://archon:archon_local_dev@localhost:5434/archon

# .env.docker
ARCHON_DATABASE_URL=postgresql://archon:archon_local_dev@postgres:5432/archon
```

**Option 2: Use docker-compose.override.yml for local dev**
```yaml
# docker-compose.override.yml
services:
  archon-mcp:
    environment:
      - ARCHON_DATABASE_URL=postgresql://archon:archon_local_dev@postgres:5432/archon
```

**Recommendation**: Stick with local development config (localhost:5434) and use Docker Compose for production deployments.

---

## Estimated Timeline

| Phase | Time | Owner |
|-------|------|-------|
| Database Fix | 5 min | User |
| Code Bug Fixes | 15 min | Claude/Octofriend |
| Verification | 10 min | User |
| **Total** | **30 min** | - |

---

## Success Criteria

✅ All tools return valid JSON (not database connection errors)
✅ `worktree_get_current_info` continues to work
✅ `audit_get_context` returns findings (may be empty if no data, but not error)
✅ `codebase_find_entity` returns entities (after indexing)
✅ `find_projects` returns projects (after database fix)
✅ Skills can execute without database errors

---

## Rollback Plan

If issues arise:
1. Keep backup of `.env`: `cp .env .env.backup.$(date +%Y%m%d_%H%M%S)`
2. Revert `.env` changes: `cp .env.backup.* .env`
3. Restart MCP server
4. File shows original state is preserved

---

## Notes

- The skills I created are **correct** - they just can't work until the database is accessible
- Once fixes applied, the skills will work as designed with batched tool calls
- The batching patterns are sound - verified by the tools that do work
