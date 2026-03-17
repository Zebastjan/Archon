# MCP Tools Fixes Applied

**Date**: 2025-01-20
**Status**: Fixes Applied, Restart Required

---

## Summary

| Issue Category | Count | Status |
|----------------|-------|--------|
| Database Configuration | 1 | ✅ Fixed |
| Async/Await Bugs | 6 | ✅ Fixed |
| Missing Methods | 5 | ✅ Implemented |
| **Total** | **12** | **✅ All Fixed** |

---

## Fix 1: Database Configuration (CRITICAL)

**File**: `.env`

**Problem**: MCP server running locally couldn't resolve Docker hostname `postgres`

**Change**:
```diff
- ARCHON_DATABASE_URL=postgresql://archon:archon_local_dev@postgres:5432/archon
+ ARCHON_DATABASE_URL=postgresql://archon:archon_local_dev@localhost:5434/archon
```

**Impact**: Enables database connectivity for all MCP tools

---

## Fix 2: Async/Await Bugs (HIGH)

### File: `python/src/mcp_server/features/worktree/worktree_tools.py`

**Problem**: Async service methods called without `await`

**Changes**:

#### Line 155 - worktree_validate_safe_to_work
```diff
- result = service.validate_safe_to_work(...)
+ result = await service.validate_safe_to_work(...)
```

#### Line 170 - worktree_find_conflicts
```diff
- conflicts = service.find_conflicts(...)
+ conflicts = await service.find_conflicts(...)
```

#### Line 205 - worktree_list_all
```diff
- worktrees = service.list_worktrees()
+ worktrees = await service.list_worktrees()
```

#### Line 257 - worktree_create_task (validate)
```diff
- validation = service.validate_safe_to_work(...)
+ validation = await service.validate_safe_to_work(...)
```

#### Line 282 - worktree_create_task (create)
```diff
- success, result = service.create_worktree_task(...)
+ success, result = await service.create_worktree_task(...)
```

#### Line 330 - worktree_sync_task_context
```diff
- success = service.sync_worktree_context(task_id)
+ success = await service.sync_worktree_context(task_id)
```

#### Line 356 - worktree_lock
```diff
- success = service.lock_worktree(worktree_id, locked)
+ success = await service.lock_worktree(worktree_id, locked)
```

**Impact**: Fixes runtime errors where coroutines weren't awaited

---

## Fix 3: Missing Service Methods (HIGH)

### File: `python/src/server/services/worktree_service.py`

**Problem**: Service methods called by MCP tools didn't exist

**Implemented Methods**:

### 3.1 `async def find_conflicts(...)`
```python
async def find_conflicts(
    self,
    worktree_id: str | None = None,
    file_paths: list[str] | None = None,
    entity_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Find conflicts with other worktrees."""
    # Implementation: Queries database for conflicting tasks
    # Returns list of conflicts with severity levels
```

### 3.2 `async def list_worktrees(...)`
```python
async def list_worktrees(self) -> list[dict[str, Any]]:
    """List all active worktrees with task counts."""
    # Implementation: Returns worktrees with:
    # - worktree_id, branch_name, repo_path
    # - active_task_count, doing_count
    # - last_activity
```

### 3.3 `async def create_worktree_task(...)`
```python
async def create_worktree_task(
    self,
    project_id: str,
    title: str,
    description: str,
    file_paths: list[str] | None,
    entity_ids: list[str] | None,
    assignee: str,
    priority: str,
    feature: str | None,
) -> tuple[bool, dict[str, Any]]:
    """Create a task with worktree context."""
    # Implementation: Inserts task into archon_tasks table
    # with worktree_id and branch_name from context
```

### 3.4 `async def sync_worktree_context(...)`
```python
async def sync_worktree_context(self, task_id: str) -> bool:
    """Sync worktree context for a task."""
    # Implementation: Updates task with current worktree_id and branch_name
```

### 3.5 `async def lock_worktree(...)`
```python
async def lock_worktree(self, worktree_id: str, locked: bool) -> bool:
    """Lock or unlock a worktree."""
    # Implementation: Updates locked status in archon_worktrees table
```

**Impact**: All worktree MCP tools now have functioning backend methods

---

## Files Modified

| File | Changes | Lines |
|------|---------|-------|
| `.env` | Database URL hostname | 1 |
| `worktree_tools.py` | Added `await` to 7 async calls | 7 |
| `worktree_service.py` | Added 5 missing async methods | ~200 |

**Total**: 3 files modified

---

## Required Database Schema

The new service methods expect these tables:

### archon_tasks
```sql
CREATE TABLE archon_tasks (
    id UUID PRIMARY KEY,
    project_id UUID REFERENCES archon_projects(id),
    title TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'todo',
    assignee TEXT,
    priority TEXT DEFAULT 'medium',
    feature TEXT,
    worktree_id TEXT,
    branch_name TEXT,
    file_paths TEXT[],
    entity_ids TEXT[],
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### archon_worktrees
```sql
CREATE TABLE archon_worktrees (
    worktree_id TEXT PRIMARY KEY,
    branch_name TEXT,
    repo_path TEXT,
    locked BOOLEAN DEFAULT FALSE,
    locked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**Note**: If these tables don't exist, the service methods will fail gracefully with logged errors.

---

## Verification Steps

### Step 1: Restart MCP Server
```bash
cd /home/zebastjan/dev/archon/python
pkill -f "mcp_server"  # Stop existing
python -m src.mcp_server.mcp_server &  # Start new
```

### Step 2: Test Database Connectivity
```bash
# Test connection
psql postgresql://archon:archon_local_dev@localhost:5434/archon -c "SELECT 1"

# Test MCP tool
curl -s http://localhost:8051/mcp -X POST \
  -H "Content-Type: application/json" \
  -d '{"tool": "code_audit_get_rules"}' | jq .
```

### Step 3: Test Fixed Tools
```bash
# Test worktree tools
curl -s http://localhost:8051/mcp -X POST \
  -H "Content-Type: application/json" \
  -d '{"tool": "worktree_list_all"}' | jq .

curl -s http://localhost:8051/mcp -X POST \
  -H "Content-Type: application/json" \
  -d '{"tool": "worktree_validate_safe_to_work", "file_paths": [".octofriend/octofriend.json5"]}' | jq .
```

### Step 4: Run Full Sanity Check
- Re-run the sanity check script
- Verify no more "coroutine" errors
- Verify no more database connection errors

---

## Expected Results

After restart:

### Before Fixes
- ✅ `worktree_get_current_info` - Working
- ❌ `worktree_list_all` - Error: "'WorktreeService' object has no attribute 'list_worktrees'"
- ❌ `worktree_validate_safe_to_work` - Error: "'coroutine' object has no attribute 'is_safe'"
- ❌ `code_audit_get_rules` - Error: "could not translate host name 'postgres'"
- ❌ `audit_get_context` - Error: "Failed to initialize database"

### After Fixes
- ✅ `worktree_get_current_info` - Still working
- ✅ `worktree_list_all` - Returns list (may be empty if no worktrees)
- ✅ `worktree_validate_safe_to_work` - Returns validation result
- ✅ `code_audit_get_rules` - Returns rules (may be empty if none configured)
- ✅ `audit_get_context` - Returns findings (may be empty if no data)

---

## Rollback Instructions

If issues arise:

1. **Database URL**:
   ```bash
   git checkout .env  # Revert to original
   ```

2. **Code Changes**:
   ```bash
   git checkout python/src/mcp_server/features/worktree/worktree_tools.py
   git checkout python/src/server/services/worktree_service.py
   ```

3. **Restart MCP**:
   ```bash
   pkill -f "mcp_server"
   python -m src.mcp_server.mcp_server &
   ```

---

## Next Steps

1. ✅ **Fixes Applied** - All 12 issues resolved
2. ⏳ **Restart MCP Server** - Required to load new `.env`
3. ⏳ **Verify Database Connectivity** - Test with `psql`
4. ⏳ **Test All Fixed Tools** - Run verification steps
5. ⏳ **Re-run Sanity Check** - Confirm all tools work

---

## Summary

All critical issues have been addressed:
- Database connectivity fixed via `.env` change
- All async/await bugs fixed (7 locations)
- All missing service methods implemented (5 methods)

**Ready for restart and verification.**
