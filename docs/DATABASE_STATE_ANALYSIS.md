# Database State - Root Cause Analysis & Permanent Solution

## Why This Keeps Happening

After investigation, here are the **root causes** of the recurring database issues:

### 1. **Supabase vs Plain PostgreSQL Mismatch**
The database schema was designed for **Supabase** (hosted PostgreSQL with extensions) but runs on **plain PostgreSQL** in Docker. Key differences:
- RLS policies reference `auth` schema and `authenticated` role (Supabase-specific)
- `auth.role()` and `auth.uid()` functions don't exist in plain PostgreSQL
- These cause migration failures even though tables are created

**Evidence:** Every migration with RLS policies fails with:
```
ERROR: role "service_role" does not exist
ERROR: current transaction is aborted
ROLLBACK
```

### 2. **Multiple Migration Sources**
Schema is split across **three different locations**:
- `/migration/complete_setup.sql` - Master schema (1,393 lines)
- `/migration/0.1.0/*.sql` - 21 incremental migration files
- `/migration/01[2-9]_*.sql` and `/migration/02[0-3]_*.sql` - 12 numbered migrations

**Problem:** No single command applies all migrations. Easy to miss some.

### 3. **Git Tables Migration Failure**
The migration `017_add_git_tables.sql` was **partially failing** due to Supabase RLS policies at the end, causing a ROLLBACK. The tables (`archon_git_repositories`, `archon_git_commits`, `archon_git_files`) were never actually created despite the migration claiming to run.

**Evidence:** `db_verify.sh` showed 36 tables but `archon_git_commits` was MISSING.

### 4. **No Automated Verification**
There's no automatic check that runs when the application starts to ensure the database is in the correct state.

---

## Current Database State (VERIFIED)

**Last Verified:** March 28, 2026  
**Status:** ✅ FULLY OPERATIONAL

### Extensions Installed
| Extension | Version | Status |
|-----------|---------|--------|
| vector | 0.8.2 | ✅ |
| pgcrypto | 1.3 | ✅ |
| pg_trgm | 1.6 | ✅ |

### Tables Created: 39 total

**Core Tables:**
- ✅ `archon_projects`
- ✅ `archon_tasks`
- ✅ `archon_sources`
- ✅ `archon_settings` (45 settings loaded)
- ✅ `archon_prompts`

**Git Tables (NEWLY FIXED):**
- ✅ `archon_git_repositories`
- ✅ `archon_git_commits`
- ✅ `archon_git_files`

**Code Intelligence:**
- ✅ `archon_code_entities`
- ✅ `archon_code_relationships`
- ✅ `archon_code_examples`
- ✅ `archon_code_repos`
- ✅ `archon_code_metrics`
- ✅ `archon_file_metrics`

**Audit System:**
- ✅ `archon_audit_findings`
- ✅ `archon_audit_rules`
- ✅ `archon_audit_runs`
- ✅ `archon_audit_config`
- ✅ `archon_audit_triage_memory`
- ✅ `archon_audit_false_negatives`
- ✅ `archon_audit_finding_tasks`
- ✅ `archon_audit_rule_quality`

**Embeddings & Search:**
- ✅ `archon_embeddings`
- ✅ `archon_embedding_models`
- ✅ `archon_embedding_sets`
- ✅ `archon_chunks`
- ✅ `archon_knowledge_items`

**Documents:**
- ✅ `archon_documents`
- ✅ `archon_document_blobs`
- ✅ `archon_document_versions`
- ✅ `archon_pages`
- ✅ `archon_crawled_pages`
- ✅ `archon_crawl_url_state`
- ✅ `archon_page_metadata`
- ✅ `archon_summaries`

**Other:**
- ✅ `archon_migrations`
- ✅ `archon_operation_progress`
- ✅ `archon_project_sources`
- ✅ `archon_semgrep_config`
- ✅ `archon_semgrep_findings`

---

## Permanent Solution Created

### 1. **Verification Script** ✅
**File:** `/home/zebastjan/dev/archon/scripts/db_verify.sh`

**Purpose:** Quick health check of database state
**Usage:**
```bash
./scripts/db_verify.sh
```

**Output:**
- Green checkmarks for working components
- Red X for missing components
- Exit code: 0 = healthy, 1 = warnings, 2 = critical errors

### 2. **Automated Setup Script** ✅
**File:** `/home/zebastjan/dev/archon/scripts/db_setup.sh`

**Purpose:** One-command database repair/setup
**Usage:**
```bash
./scripts/db_setup.sh
```

**What it does:**
1. Installs pgvector extension
2. Applies `complete_setup.sql` (master schema)
3. Applies all `0.1.0/` migrations
4. Applies all numbered migrations (012-023)
5. Verifies table count (expects 36+)

### 3. **Startup Check Script** ✅
**File:** `/home/zebastjan/dev/archon/scripts/db_startup_check.sh`

**Purpose:** Run before starting Archon services to ensure DB is ready
**Usage:**
```bash
./scripts/db_startup_check.sh
```

**What it does:**
- Waits for database to be ready (with timeout)
- Checks table count
- If incomplete, automatically runs `db_setup.sh`
- Verifies pgvector and settings

**Integration:** Add to docker-compose `depends_on` or systemd service.

---

## How to Prevent Future Issues

### **Immediate Actions:**

1. **Verify current state:**
   ```bash
   ./scripts/db_verify.sh
   ```

2. **If issues found, repair:**
   ```bash
   ./scripts/db_setup.sh
   ```

3. **Verify repair worked:**
   ```bash
   ./scripts/db_verify.sh
   ```

### **Ongoing Prevention:**

1. **Before each development session:**
   ```bash
   ./scripts/db_startup_check.sh
   ```

2. **Add to your workflow:**
   - Put `./scripts/db_startup_check.sh` in your shell startup
   - Or add to docker-compose as a healthcheck

3. **After any Docker restart:**
   - Container restarts don't reset data (volume persists)
   - But verify with `db_verify.sh` to be sure

### **If Database Gets Reset:**

The PostgreSQL data is stored in a Docker volume at:
```
/var/lib/docker/volumes/[volume_id]/_data
```

**Data persists across container restarts.** If data is missing, either:
1. Volume was manually deleted (`docker volume rm`)
2. Database was manually reset
3. `docker-compose down -v` was used (removes volumes)

**Recovery:**
```bash
./scripts/db_setup.sh  # Reapplies all migrations
```

---

## Single Source of Truth

**The correct database state is:**

1. **39 archon_* tables** (not 36, not 10)
2. **pgvector v0.8.2** installed and active
3. **45 settings** in `archon_settings`
4. **All migrations applied** (complete_setup.sql + 0.1.0/ + 012-023)

**Verification command:**
```bash
docker exec -e PGPASSWORD=archon archon-postgres psql -U archon -d archon -c "SELECT COUNT(*) FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'archon_%';"
# Should return: 39
```

**If count is less than 39, run:**
```bash
./scripts/db_setup.sh
```

---

## Summary

**Problem:** Database state kept reverting or being incomplete due to:
- Supabase/PostgreSQL incompatibilities
- Multiple migration sources
- Git tables migration silently failing
- No automated verification

**Solution Created:**
- ✅ `db_verify.sh` - Quick health check
- ✅ `db_setup.sh` - Automated repair
- ✅ `db_startup_check.sh` - Pre-flight check
- ✅ This documentation - Single source of truth

**Current Status:** Database is fully operational with all 39 tables, pgvector installed, and all settings loaded.

**Next time you check:** Run `./scripts/db_verify.sh` to see the actual state in seconds.
