# Repository Health Check - Pending Issues

**Date:** Current session  
**Branch:** `feature/multi-language-code-intelligence`  
**Status:** MCP tools accessible, but database connection issues prevent health check execution

## Issues Discovered

### 1. Database Connection Unavailable
- **Error:** `could not translate host name "postgres" to address: Name or service not known`
- **Impact:** All code audit and code entity tools fail because they can't connect to the database
- **Likely Cause:** PostgreSQL server is not running locally or the connection configuration is incorrect

### 2. Repository Health Check Tool Bug
- **Error:** `'coroutine' object has no attribute 'is_safe'`
- **File:** `/home/zebastjan/dev/archon/python/src/mcp_server/features/code_audit/repo_health_super_tool.py`
- **Root Cause:** Coroutine handling issue - likely a missing `await` when calling an async method that returns an object with an `is_safe` property
- **Impact:** The `repo_health_check` and `orchestrated_repo_health_check` MCP tools are broken

### 3. No Code Entities Ingested
- **Result:** `codebase_find_entity` returns success but with 0 entities
- **Cause:** Database is offline, so no repositories have been ingested
- **Note:** Test file at `python/tests/mcp_server/features/code_entities/test_code_entity_tools.py` uses repo_id `"76abe5b8-693a-40e4-a3a3-c08289465d7d"` but this repo doesn't exist in the database

## MCP Tools Status Summary

| Tool | Status | Notes |
|------|--------|-------|
| `worktree_get_current_info` | ✅ Working | Returns worktree context correctly |
| `rag_get_available_sources` | ✅ Working | Returns empty list (no sources configured) |
| `codebase_find_entity` | ✅ Working | Returns empty results (DB offline) |
| `repo_health_check` | ❌ Broken | Coroutine handling bug |
| `orchestrated_repo_health_check` | ❌ Broken | Depends on repo_health_check |
| `code_audit_calculate_metrics` | ❌ Broken | Database connection failure |
| `code_audit_run` | ❌ Broken | Database connection failure |

## Next Steps

1. **Start PostgreSQL database**
   ```bash
   # Option 1: Using Docker
   docker run -d --name archon-postgres \
     -e POSTGRES_USER=archon \
     -e POSTGRES_PASSWORD=archon \
     -e POSTGRES_DB=archon \
     -p 5432:5432 \
     postgres:15
   ```

2. **Fix the coroutine bug in repo_health_super_tool.py**
   - Look for calls to `is_safe` property on what might be a coroutine
   - Add missing `await` statements as needed
   - The error suggests something like `result.is_safe` should be `(await result).is_safe`

3. **Ingest a repository for testing**
   ```bash
   cd /home/zebastjan/dev/archon/python
   # Use the setup script mentioned in codebase_tools.py
   # scripts/setup_archon_repo.py ingests "archon-python" and "archon-ui"
   ```

4. **Alternative: Review existing analysis**
   - There's a `codebase_analysis_report.json` in `/home/zebastjan/dev/archon/python/`
   - This contains analysis of 195 files, 1508 entities, quality score of 90
   - Can be used to understand codebase health without running live checks

## Relevant Files

- `/home/zebastjan/dev/archon/python/src/mcp_server/features/code_audit/code_audit_tools.py` - MCP tool definitions
- `/home/zebastjan/dev/archon/python/src/mcp_server/features/code_audit/repo_health_super_tool.py` - Bug location (likely)
- `/home/zebastjan/dev/archon/python/src/server/mcp_server/codebase_tools.py` - Legacy codebase tools
- `/home/zebastjan/dev/archon/python/codebase_analysis_report.json` - Pre-computed analysis

## Context

Current worktree:
- **Path:** `/home/zebastjan/dev/archon`
- **Branch:** `feature/multi-language-code-intelligence`
- **Worktree ID:** `3bda1365-b4e5-5fd8-b9ab-9118fa6e414e`
- **Uncommitted changes:** `python/tests/git_integration/fixtures/embedded-test-repo`
