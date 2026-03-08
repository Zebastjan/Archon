# Git Test Fixtures - Fixes Applied (March 7, 2026)

## Problem Summary

The Git Test Fixtures feature failed to initialize with error:
```
failed to initialize test fixture internal server error
message column archon sources.ID does not exist
```

## Root Cause Analysis

### Primary Issue: Wrong Column Name in Code

The code in `git_test_api.py` was using `.eq("id", ...)` instead of `.eq("source_id", ...)`:

```python
# WRONG - Lines 110, 125, 145, 163
supabase_client.table("archon_sources").delete().eq("id", source_id).execute()

# CORRECT
supabase_client.table("archon_sources").delete().eq("source_id", source_id).execute()
```

**Why this failed:**
- The `archon_sources` table uses `source_id` (TEXT) as primary key, NOT `id`
- PostgREST converts column names to uppercase in error messages, showing "ID" instead of "id"
- The error "column archon_sources.ID does not exist" meant we were querying a non-existent column

### Secondary Issue: Confusing Settings UI

The settings page had two sections that appeared to be Git test fixture controls:
1. **Features Section** - Working toggle that enables/disables fixtures ✅
2. **Bug Reporting Section** - Read-only fixture viewer (NOT a toggle) ❌

This caused user confusion about which control was actually functional.

### Database Schema Status

The database already had all required columns from migrations 013, 014, and 018:
- ✅ `source_type`
- ✅ `status`
- ✅ `embedding_model`, `embedding_dimensions`, `embedding_provider`
- ✅ `pipeline_status`, `pipeline_error`, `pipeline_completed_at`
- ✅ All 24 expected columns present

The schema was **not** the issue - only the code was wrong.

## Fixes Applied

### 1. Fixed Column References in `git_test_api.py`

**File:** `/home/zebastjan/dev/archon/python/src/server/api_routes/git_test_api.py`

Fixed 4 occurrences of incorrect column reference:

```python
# Line 110: Delete source entry
- supabase_client.table("archon_sources").delete().eq("id", existing_source_id).execute()
+ supabase_client.table("archon_sources").delete().eq("source_id", existing_source_id).execute()

# Line 125: Check if source exists
- existing_source_response = supabase_client.table("archon_sources").select("id").eq("id", source_id).execute()
+ existing_source_response = supabase_client.table("archon_sources").select("source_id").eq("source_id", source_id).execute()

# Line 145: Update existing source
- source_response = supabase_client.table("archon_sources").update(source_data).eq("id", source_id).execute()
+ source_response = supabase_client.table("archon_sources").update(source_data).eq("source_id", source_id).execute()

# Line 163: Cleanup on failure
- supabase_client.table("archon_sources").delete().eq("id", source_id).execute()
+ supabase_client.table("archon_sources").delete().eq("source_id", source_id).execute()
```

### 2. Removed Confusing Settings UI Section

**File:** `/home/zebastjan/dev/archon/archon-ui-main/src/pages/SettingsPage.tsx`

- Removed `GitTestFixturesSection` from Bug Reporting section (lines 260-271)
- Removed import for `GitTestFixturesSection` (line 37)
- Removed unused `GitBranch` icon import

The working Git Test Fixtures toggle remains in the Features section.

### 3. Added Comprehensive Testing Infrastructure

#### Created Real Database Schema Validation

**File:** `/home/zebastjan/dev/archon/python/tests/validate_schema.py`

- Standalone script that validates all 24 expected columns exist
- Uses Docker exec to query database directly (no Python dependencies needed)
- Exit code 0 = valid, 1 = invalid, 2 = cannot connect
- Clear error messages showing which columns are missing

```bash
# Run validation
cd /home/zebastjan/dev/archon/python
python tests/validate_schema.py
# Output: ✅ Schema validation passed - all 24 expected columns present
```

#### Added Pre-Startup Schema Validation

**File:** `/home/zebastjan/dev/archon/python/src/server/utils/schema_validator.py`

- New utility module for schema validation
- Validates all expected columns before server starts
- **Fails fast** with clear error messages if schema is incomplete

**File:** `/home/zebastjan/dev/archon/python/src/server/main.py` (lifespan function)

- Added schema validation step after migrations
- Server will refuse to start if schema validation fails
- Prevents runtime errors from missing columns

```python
# Validate database schema - fail fast if schema is incomplete
is_valid, message = validate_archon_sources_schema(supabase_client)
if not is_valid:
    raise RuntimeError(f"Database schema validation failed: {message}")
```

#### Created Integration Test Script

**File:** `/home/zebastjan/dev/archon/python/tests/test_fixtures_integration.py`

- Tests all three fixtures (simple-commits, multi-branch, file-structure)
- Validates end-to-end API initialization
- Automated cleanup after tests
- Clear pass/fail reporting

```bash
# Run integration tests (requires backend running)
cd /home/zebastjan/dev/archon/python
python tests/test_fixtures_integration.py
```

### 4. PostgREST Schema Cache Refresh

Restarted PostgREST to ensure schema cache is current:

```bash
docker restart supabase-rest
# Verified: Schema cache loaded in 0.4 milliseconds
```

## Testing

### How to Test Git Test Fixtures (Manual)

1. **Enable Feature in UI:**
   - Go to Settings → Features
   - Toggle "Git Test Fixtures" ON
   - Should see success message

2. **Initialize Fixtures:**
   - Go to Projects
   - Look for "Git Integration Test Project" card
   - Click "Initialize Test Fixtures" button
   - Try each fixture:
     - simple-commits (3 commits, 1 branch, 3 files)
     - multi-branch (4 commits, 3 branches, merge commit)
     - file-structure (13 files including binaries)

3. **Expected Result:**
   - ✅ Fixture initializes without errors
   - ✅ Commit history loads
   - ✅ File tree displays
   - ✅ No "column ID does not exist" errors

### Automated Testing

```bash
# 1. Validate database schema
cd /home/zebastjan/dev/archon/python
python tests/validate_schema.py

# 2. Run integration tests (requires backend running)
python tests/test_fixtures_integration.py

# 3. Run unit tests
python -m pytest tests/test_schema_validation.py -v
python -m pytest tests/api_routes/test_git_test_api.py -v
```

## Prevention & Best Practices

### Before Deploying Code Changes:

1. **Run schema validation:**
   ```bash
   python tests/validate_schema.py
   ```

2. **Check for invalid column references:**
   ```bash
   # Search for .eq("id", in archon_sources queries
   grep -rn '\.eq("id"' python/src/server/api_routes/
   ```

3. **Restart PostgREST after DDL changes:**
   ```bash
   docker restart supabase-rest
   ```

4. **Run integration tests:**
   ```bash
   python tests/test_fixtures_integration.py
   ```

### Schema Migration Workflow:

1. Write migration SQL in `migration/0.1.0/XXX_description.sql`
2. Apply migration to database
3. **Restart PostgREST** (critical!)
4. Run `python tests/validate_schema.py`
5. Update code to use new columns
6. Test thoroughly before committing

## Key Learnings

### ❌ What Went Wrong:

1. **Code had bugs despite documentation claiming fixes were applied**
   - Previous "fixes" in this document were documented but never actually applied to code
   - Always verify fixes are in the actual codebase, not just documented

2. **Tests used mocks instead of real database**
   - Mock-based tests passed even though real database queries would fail
   - Real database integration tests are essential

3. **No pre-deployment validation**
   - Schema issues only discovered at runtime via UI
   - Should catch schema problems before server starts

4. **Confusing UI design**
   - Two sections that looked like controls, but only one was functional
   - UI should be unambiguous about what actions are available

### ✅ What We Fixed:

1. **Fail-fast validation**
   - Server validates schema at startup
   - Clear error messages show exactly what's wrong
   - Prevents silent failures

2. **Real database tests**
   - `validate_schema.py` queries actual database
   - No reliance on mocks for critical validation
   - Docker exec approach works without Python dependencies

3. **Better testing infrastructure**
   - Standalone validation script
   - Integration tests for end-to-end validation
   - Clear pass/fail reporting

4. **Cleaner UI**
   - Removed confusing read-only section
   - Single, clear toggle for enabling/disabling fixtures
   - No ambiguity about functionality

## Current Status

✅ All 4 bugs in `git_test_api.py` fixed (lines 110, 125, 145, 163)
✅ Confusing settings UI section removed
✅ Database schema validation script created
✅ Pre-startup validation integrated
✅ Integration test script created
✅ PostgREST schema cache refreshed
✅ All 24 expected columns verified in database

**Git test fixtures should now work correctly!**

## Files Modified

- `python/src/server/api_routes/git_test_api.py` - Fixed column references
- `archon-ui-main/src/pages/SettingsPage.tsx` - Removed confusing UI section
- `python/src/server/main.py` - Added pre-startup validation
- `python/src/server/utils/schema_validator.py` - New validation utility
- `python/tests/validate_schema.py` - New standalone validation script
- `python/tests/test_fixtures_integration.py` - New integration test script
- `python/tests/test_schema_validation.py` - Enhanced with real DB tests
- `GIT_TEST_FIXTURES_FIXES.md` - Updated with actual fixes (this file)