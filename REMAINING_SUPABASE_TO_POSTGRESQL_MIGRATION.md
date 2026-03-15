# Remaining Supabase to PostgreSQL Migration Tasks

**Status:** Production code migration is 100% complete ✅
**Remaining:** Test infrastructure, dev utilities, and agent work orders subsystem
**Date:** 2026-03-14

---

## 📋 Table of Contents

1. [Migration Overview](#migration-overview)
2. [What's Already Complete](#whats-already-complete)
3. [Remaining Work Breakdown](#remaining-work-breakdown)
4. [Migration Pattern & Examples](#migration-pattern--examples)
5. [Testing Strategy](#testing-strategy)
6. [Commit History](#commit-history)

---

## Migration Overview

### Goal
Migrate all remaining Supabase client usage to PostgreSQL using `get_database_connector()` from the DatabaseConnector class (asyncpg-based connection pooling).

### Why This Matters
- **Consistency**: All code should use the same database access pattern
- **Performance**: PostgreSQL connection pooling is more efficient
- **Maintainability**: Single database abstraction layer
- **Future-proofing**: Removes dependency on Supabase client library

---

## What's Already Complete

### ✅ Production Code (100% Complete)

**Services (36 files):**
- Tier 1-6: Core services (crawling, storage, embeddings, RAG, credentials, git)
- Tier 7: Project services (6 files)
- Tier 8: Knowledge services (3 files)
- Tier 9: Base services (2 files)

**API Routes (3 files):**
- `git_api.py` - 18 database operations
- `pages_api.py` - 3 database operations
- `settings_api.py` - 4 database operations

**Agents (1 file):**
- `document_agent.py` - 2 database operations

**Utilities (2 files):**
- `progress_tracker.py` - 11+ database operations
- `main.py` - 3 database operations (migrations, schema validation)

**Total:** 41+ files, 200+ database operations migrated

### 📝 Commits Created
- `e552379` - Tier 7 & 8 services (9 services)
- `1107d35` - Final services (2 services)
- `aa4297b` - Progress tracker utility
- `4a16c0f` - API routes (git, pages, settings)
- `332e3b6` - Document agent and main.py

---

## Remaining Work Breakdown

### 1. Test Files (Priority: Medium)

Test files use Supabase for fixtures, mocking, and database setup. These need to be migrated to use PostgreSQL.

#### Files to Migrate:

**Conftest Files (Shared Test Fixtures):**
```
tests/conftest.py
tests/agent_work_orders/conftest.py
tests/git_integration/conftest.py
```

**Test Files Using Supabase Client:**
```
tests/api_routes/test_git_test_api.py
tests/services/git_service/test_git_repository_service.py
tests/test_task_counts.py
tests/test_token_optimization.py
tests/test_llms_txt_link_following.py
tests/test_pause_resume_cancel_api.py
tests/test_knowledge_api_integration.py
tests/test_knowledge_api_pagination.py
tests/test_crawl_checkpoint_resume.py
tests/test_crawl_url_state_service.py
tests/test_crawling_service_subdomain.py
tests/test_rag_strategies.py
tests/test_settings_api.py
tests/test_async_credential_service.py
tests/test_crawl_orchestration_isolated.py
tests/test_rag_simple.py
tests/test_api_essentials.py
tests/server/services/test_migration_service.py
tests/git_integration/test_merge_scenarios.py
tests/git_integration/test_commit_classification.py
tests/git_integration/test_diff.py
tests/git_integration/test_divergent_files.py
tests/git_integration/test_edge_cases.py
tests/git_integration/test_file_deletions.py
tests/git_integration/test_git_repository_integration.py
tests/progress_tracking/integration/test_document_storage_progress.py
tests/progress_tracking/integration/test_pause_resume_flow.py
tests/progress_tracking/integration/test_crawl_orchestration_progress.py
tests/agent_work_orders/test_repository_config_repository.py
```

#### Key Changes Needed:

1. **Fixture Setup**
   - Replace `@pytest.fixture` that create Supabase clients
   - Use `get_database_connector()` instead
   - Update database cleanup to use PostgreSQL `TRUNCATE` or `DELETE`

2. **Mock Updates**
   - Replace `mock.patch('...get_supabase_client')` with `mock.patch('...get_database_connector')`
   - Update mock return values to match asyncpg format (list of dicts, not `.data` attribute)

3. **Assertions**
   - Change `response.data` to `response` (asyncpg returns list directly)
   - Update any Supabase-specific error handling

---

### 2. Development/Debugging Utilities (Priority: Low)

These are utility scripts used for development and debugging. They can be migrated opportunistically.

#### Files:

```
python/inspect_db.py
python/create_table.py
scripts/register_all_repos.py
scripts/register_repos.py
scripts/auto_triage_audit_findings.py
scripts/auto_triage_audit_findings.py.bak
scripts/generate_embeddings.py
scripts/review_audit_findings.py
scripts/test_triage_diverse.py
scripts/test_triage_sample.py
```

#### Key Changes:

- Replace `get_supabase_client()` with `get_database_connector()`
- Add `async`/`await` if scripts become async
- Handle direct PostgreSQL queries instead of Supabase table API

---

### 3. Agent Work Orders Subsystem (Priority: Low)

This is a separate subsystem for managing agent work orders. Can be migrated independently.

#### Files:

```
src/agent_work_orders/database/client.py
src/agent_work_orders/state_manager/repository_config_repository.py
src/agent_work_orders/state_manager/supabase_repository.py
src/agent_work_orders/state_manager/repository_factory.py
src/agent_work_orders/utils/state_reconciliation.py
src/agent_work_orders/server.py
```

#### Key Changes:

- Update `database/client.py` to use PostgreSQL connector
- Migrate repository classes to use async PostgreSQL queries
- Update factory methods to create PostgreSQL-based repositories
- Test work order creation, retrieval, and state management

---

### 4. README Files & Documentation (Priority: Low)

Some README files reference Supabase setup. These should be updated.

#### Files:

```
tests/git_integration/README.md
tests/progress_tracking/README.md
```

#### Changes:

- Update setup instructions to reference PostgreSQL
- Remove Supabase-specific configuration details
- Add PostgreSQL connection string examples

---

## Migration Pattern & Examples

### Standard Migration Pattern

#### Before (Supabase):
```python
from ..utils import get_supabase_client

def my_function():
    supabase = get_supabase_client()
    response = supabase.table("my_table").select("*").eq("id", item_id).execute()

    if not response.data:
        return None

    return response.data[0]
```

#### After (PostgreSQL):
```python
from ..services.database import get_database_connector

async def my_function():
    db = get_database_connector()
    response = await db.fetch(
        "SELECT * FROM my_table WHERE id = $1",
        item_id
    )

    if not response:
        return None

    return response[0]
```

### Key Differences

| Aspect | Supabase | PostgreSQL |
|--------|----------|------------|
| **Import** | `from ..utils import get_supabase_client` | `from ..services.database import get_database_connector` |
| **Client** | `supabase = get_supabase_client()` | `db = get_database_connector()` |
| **Query** | `supabase.table("table").select("*").eq("col", val).execute()` | `await db.fetch("SELECT * FROM table WHERE col = $1", val)` |
| **Result** | `response.data` (attribute access) | `response` (list directly) |
| **Insert** | `supabase.table("t").insert(data).execute()` | `await db.execute("INSERT INTO t (...) VALUES ($1, $2)", val1, val2)` |
| **Update** | `supabase.table("t").update(data).eq("id", id).execute()` | `await db.execute("UPDATE t SET col = $1 WHERE id = $2", val, id)` |
| **Delete** | `supabase.table("t").delete().eq("id", id).execute()` | `await db.execute("DELETE FROM t WHERE id = $1", id)` |
| **Async** | Synchronous | `async`/`await` required |
| **Parameters** | Chained methods | Positional `$1, $2, $3...` |

### Common Patterns

#### 1. SELECT Queries

**Supabase:**
```python
response = supabase.table("users").select("name, email").eq("id", user_id).execute()
users = response.data
```

**PostgreSQL:**
```python
users = await db.fetch(
    "SELECT name, email FROM users WHERE id = $1",
    user_id
)
```

#### 2. INSERT with RETURNING

**Supabase:**
```python
response = supabase.table("users").insert({
    "name": "John",
    "email": "john@example.com"
}).execute()
new_user = response.data[0]
```

**PostgreSQL:**
```python
result = await db.fetch(
    """
    INSERT INTO users (name, email)
    VALUES ($1, $2)
    RETURNING *
    """,
    "John",
    "john@example.com"
)
new_user = result[0]
```

#### 3. UPDATE Operations

**Supabase:**
```python
response = supabase.table("users").update({
    "email": "newemail@example.com"
}).eq("id", user_id).execute()
```

**PostgreSQL:**
```python
await db.execute(
    "UPDATE users SET email = $1 WHERE id = $2",
    "newemail@example.com",
    user_id
)
```

#### 4. JSONB Operations

**Supabase (contains):**
```python
response = supabase.table("commits").select("*").contains("branches", ["main"]).execute()
```

**PostgreSQL:**
```python
import json
response = await db.fetch(
    "SELECT * FROM commits WHERE branches @> $1",
    json.dumps(["main"])
)
```

#### 5. Pagination

**Supabase:**
```python
response = supabase.table("items").select("*").range(offset, offset + limit - 1).execute()
```

**PostgreSQL:**
```python
response = await db.fetch(
    "SELECT * FROM items LIMIT $1 OFFSET $2",
    limit,
    offset
)
```

#### 6. Count Queries

**Supabase:**
```python
response = supabase.table("users").select("id", count="exact").execute()
total = response.count
```

**PostgreSQL:**
```python
result = await db.fetch("SELECT COUNT(*) as count FROM users")
total = result[0]["count"]
```

---

## Testing Strategy

### 1. Test File Migration Approach

**Step 1: Update Fixtures**
```python
# Before
@pytest.fixture
def supabase_client():
    return get_supabase_client()

# After
@pytest.fixture
async def db():
    return get_database_connector()
```

**Step 2: Update Setup/Teardown**
```python
# Before
@pytest.fixture(autouse=True)
def cleanup_db(supabase_client):
    yield
    supabase_client.table("test_table").delete().neq("id", "").execute()

# After
@pytest.fixture(autouse=True)
async def cleanup_db(db):
    yield
    await db.execute("DELETE FROM test_table")
```

**Step 3: Update Test Functions**
```python
# Before
def test_something(supabase_client):
    response = supabase_client.table("users").select("*").execute()
    assert len(response.data) > 0

# After
async def test_something(db):
    response = await db.fetch("SELECT * FROM users")
    assert len(response) > 0
```

### 2. Mock Updates for Unit Tests

**Before:**
```python
@mock.patch('module.get_supabase_client')
def test_function(mock_supabase):
    mock_client = MagicMock()
    mock_client.table().select().eq().execute.return_value = MagicMock(
        data=[{"id": "1", "name": "Test"}]
    )
    mock_supabase.return_value = mock_client
```

**After:**
```python
@mock.patch('module.get_database_connector')
async def test_function(mock_db):
    mock_db.return_value.fetch = AsyncMock(
        return_value=[{"id": "1", "name": "Test"}]
    )
```

### 3. Running Tests After Migration

```bash
# Run specific test file
pytest tests/test_knowledge_api_integration.py -v

# Run all tests in a directory
pytest tests/git_integration/ -v

# Run tests with coverage
pytest --cov=src --cov-report=html
```

---

## Special Considerations

### 1. JSONB Fields

PostgreSQL uses JSONB for JSON data. You must serialize with `json.dumps()`:

```python
import json

# Inserting JSONB
await db.execute(
    "INSERT INTO table (data) VALUES ($1)",
    json.dumps({"key": "value"})
)

# Querying JSONB with @> (contains)
await db.fetch(
    "SELECT * FROM table WHERE data @> $1",
    json.dumps({"key": "value"})
)
```

### 2. UPSERT Operations

**Supabase:**
```python
supabase.table("table").upsert(data).execute()
```

**PostgreSQL:**
```python
await db.execute(
    """
    INSERT INTO table (id, name)
    VALUES ($1, $2)
    ON CONFLICT (id) DO UPDATE SET
        name = EXCLUDED.name
    """,
    id_val,
    name_val
)
```

### 3. Array Operations

**Checking array containment:**
```python
# PostgreSQL uses @> for containment
await db.fetch(
    "SELECT * FROM table WHERE tags @> $1",
    json.dumps(["tag1"])
)
```

### 4. Async Context

All database operations MUST be awaited and functions MUST be async:

```python
# ❌ Wrong
def my_function():
    db = get_database_connector()
    result = db.fetch("SELECT * FROM table")  # Missing await!

# ✅ Correct
async def my_function():
    db = get_database_connector()
    result = await db.fetch("SELECT * FROM table")
```

---

## Verification Checklist

After migrating each file, verify:

- [ ] All `get_supabase_client()` imports replaced with `get_database_connector()`
- [ ] All `supabase.table()` operations converted to SQL queries
- [ ] All database calls use `await` (and function is `async`)
- [ ] All `.data` attribute accesses removed (asyncpg returns list directly)
- [ ] All JSONB fields use `json.dumps()` for serialization
- [ ] All parameterized queries use `$1, $2, $3...` placeholders
- [ ] No SQL injection vulnerabilities (always use parameterized queries)
- [ ] Tests pass (if migrating test files)

---

## File Search Commands

To find remaining Supabase usage:

```bash
# Find all files with get_supabase_client
grep -r "get_supabase_client" --include="*.py" .

# Find all Supabase imports
grep -r "from.*supabase.*import\|import.*supabase" --include="*.py" .

# Find Supabase table operations
grep -r "supabase_client\|\.table(" --include="*.py" .

# Count remaining references
grep -r "get_supabase_client" --include="*.py" . | wc -l
```

---

## Commit Message Template

When committing migrations, use this format:

```
chore: migrate [area] from Supabase to PostgreSQL

Migrated [number] files in [area] to use PostgreSQL via get_database_connector():

- file1.py: [number] database operations ([description])
- file2.py: [number] database operations ([description])

Changes:
- Replaced get_supabase_client() with get_database_connector()
- Converted Supabase table operations to PostgreSQL queries
- Added async/await for all database operations
- Updated [specific patterns, e.g., JSONB handling, pagination, etc.]

All operations now use parameterized PostgreSQL queries.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

Example:
```
chore: migrate test fixtures from Supabase to PostgreSQL

Migrated 3 conftest files to use PostgreSQL via get_database_connector():

- tests/conftest.py: 5 fixtures
- tests/agent_work_orders/conftest.py: 3 fixtures
- tests/git_integration/conftest.py: 4 fixtures

Changes:
- Replaced supabase_client fixtures with db connector fixtures
- Updated database cleanup to use PostgreSQL TRUNCATE
- Made all fixture functions async where needed
- Updated mock patches to use get_database_connector

All test fixtures now use PostgreSQL for consistency.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

---

## Questions or Issues?

If you encounter issues during migration:

1. **Check existing migrations** - Review commits `e552379`, `1107d35`, `aa4297b`, `4a16c0f`, `332e3b6` for examples
2. **Review DatabaseConnector** - Located at `src/server/services/database/db_connector.py`
3. **Test incrementally** - Migrate one file at a time and run tests
4. **Check PostgreSQL docs** - For JSONB, array operations, or advanced features

---

## Summary

**Total Remaining Files:** ~60+ files
- Test files: ~30 files
- Dev utilities: ~10 files
- Agent work orders: ~6 files
- Documentation: ~2 files

**Estimated Effort:**
- Test files: 4-6 hours (requires careful mock/fixture updates)
- Dev utilities: 1-2 hours (straightforward migrations)
- Agent work orders: 2-3 hours (subsystem migration)
- Documentation: 30 minutes (text updates)

**Priority Order:**
1. Test files (enables proper testing of migrated code)
2. Dev utilities (used for debugging and development)
3. Agent work orders (separate subsystem, lower priority)
4. Documentation (informational only)

Good luck with the migration! 🚀
