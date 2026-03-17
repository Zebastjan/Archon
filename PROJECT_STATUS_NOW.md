# Archon Project Status - March 2026

> **Source of Truth**: This document reflects the actual running system.  
> **Last Updated**: March 2026  
> **Status**: Live code is authoritative - docs follow code.

---

## What's Solid and Working Now

### 1. MCP Server (Port 8051)

**Architecture**: HTTP-based microservices approach - MCP server calls other services via HTTP, not direct imports. Reduces container size from 1.66GB to ~150MB.

**Registered Tool Modules** (from `python/src/mcp_server/mcp_server.py`):
- ✅ RAG Module - Knowledge base queries via HTTP
- ✅ Project Tools - Project management
- ✅ Task Tools - Task lifecycle (todo → doing → review → done)
- ✅ Document Tools - Document management with versioning
- ✅ Feature Tools - Feature flag management
- ✅ Code Entity Tools - Structural code understanding (6 tools)
- ✅ Worktree Safety Tools - Branch isolation and conflict prevention (7 tools)
- ✅ Code Audit Tools - Metrics and quality analysis (8+ tools)
- ✅ Code Repos Tools - Repository indexing and management (3 tools)

**Total**: ~35+ MCP tools available

### 2. Core API Server (Port 8181)

**Active Routers** (from `python/src/server/main.py`):
- `/api/settings` - Settings and credentials
- `/api/knowledge` - Knowledge base, crawling, RAG
- `/api/pages` - Page management
- `/api/ollama` - Ollama integration
- `/api/openrouter` - OpenRouter integration
- `/api/projects` - Project and task management
- `/api/git*` - Git operations (multiple routers)
- `/api/progress` - Operation progress tracking
- `/api/agent*` - Agent chat and work orders
- `/api/internal` - Internal operations
- `/api/bug_report` - Bug reporting
- `/api/providers` - Provider management
- `/api/version` - Version management
- `/api/migration` - Database migrations
- `/api/ingestion` - Document ingestion pipeline
- `/api/audit` - **Semgrep-based code audits** (NEW)
- `/api/code_repos` - **Code repository management** (NEW)
- `/health`, `/api/health` - Health checks with schema validation

### 3. Code Intelligence System

**Multi-Language Support**:
- ✅ Python (tree-sitter)
- ✅ TypeScript/JavaScript (tree-sitter)
- ✅ **NIM** (tree-sitter via tree-sitter-language-pack)

**Code Entity Tools** (6 MCP tools):
1. `codebase_find_entity` - Search by name (partial match)
2. `codebase_get_entity_details` - Full entity details + source code
3. `codebase_get_entity_context` - Relationships (callers, callees)
4. `codebase_search_by_semantics` - Vector similarity search
5. `codebase_list_entities_in_file` - File contents
6. `codebase_get_repository_stats` - Repository statistics

**Entity Types Extracted**:
- Functions, Classes, Methods
- NIM-specific: Procedures, Templates, Macros, Iterators, Types

**Relationship Types**:
- CALLS, INHERITS, IMPORTS, DEFINES

### 4. Code Repository Lifecycle

**MCP Tools**:
- `code_repos_create_and_index(name, local_path, github_url)` - Creates repo entry, triggers background indexing
- `code_repos_get_status(repo_id)` - Returns: created, indexing, ready, error
- `code_repos_list()` - All registered repos with entity counts

**Indexing Status Flow**:
```
created → indexing → ready
   ↓         ↓         ↓
(no work) (background) (searchable)
```

**Repository Record** (`archon_code_repos`):
- id, name, local_path, github_url
- methodology (JSON - configurable audit layers)
- last_synced, last_commit_sha, created_at
- status determined by presence of entities + last_synced

### 5. Worktree Safety System (COMPLETE)

**7 MCP Tools**:
1. `worktree_get_current_info` - Auto-detect git context
2. `worktree_validate_safe_to_work` - Check before operations
3. `worktree_find_conflicts` - Predict conflicts
4. `worktree_list_all` - All active worktrees
5. `worktree_create_task` - Create task with context
6. `worktree_sync_task_context` - Sync after branch switch
7. `worktree_lock` - Lock for maintenance

**Automatic Validation**:
- Happens BEFORE task creation/updates
- Checks: file conflicts, entity conflicts, worktree locks, branch mismatches
- Database-level RPC functions for conflict detection

**Database** (`migration/014_add_worktree_safety_to_tasks.sql`):
- 10 new columns on tasks table
- PostgreSQL functions: `detect_worktree_conflicts()`, `validate_worktree_safe()`
- View: `archon_worktree_summary`

### 6. Audit System (Multi-Layer)

**Architecture**: Semgrep-based (replaces legacy regex rules)

**MCP Tools**:
- `repo_health_check` - Super-tool (metrics + audit + safety)
- `orchestrated_repo_health_check` - LLM-enhanced summaries (RECOMMENDED)
- `audit_get_context` - Batched findings with samples
- `code_audit_calculate_metrics` - Code metrics only
- `code_audit_run` - Run audits
- `code_audit_get_findings` - Query findings
- `code_audit_get_summary` - Statistics
- `code_audit_get_rules` - Rule definitions
- `code_audit_acknowledge_finding` - Triage workflow

**API Endpoints** (`audit_api.py`):
- `POST /api/audit/run` - Multi-layer audit
- `GET /api/audit/findings` - List with filters
- `GET /api/audit/findings/{id}` - Detail view
- `POST /api/audit/findings/{id}/triage` - Triage decision
- `GET /api/audit/findings/{id}/suggest` - AI triage suggestion
- `POST /api/audit/false-negatives` - Record missed bugs
- `GET /api/audit/rule-quality` - Rule quality metrics

**Audit Layers** (configurable via methodology JSON):
1. Semgrep security/static analysis (default: `p/ci` ruleset)
2. Coverage checks (pytest-cov/c8) - if enabled
3. Test companion checks - if enabled
4. **DB Security Audit** (NEW) - if Python/JS files present
5. NIM audit (3 layers) - if NIM files detected or enabled

**DB Security Audit** (COMPLETE - March 2026):
- **Custom Rules**: `python/src/server/semgrep_rules/db/`
  - `python-sql-injection.yaml` - Psycopg2/AsyncPG patterns (5 rules)
  - `js-sql-injection.yaml` - Node.js/pg patterns (5 rules)
  - `db_policy.yaml` - Policy configuration
- **Coverage**: SQL injection, unsafe raw SQL, hardcoded credentials
- **Exclusions**: Test files excluded by default
- **Triage Config**: `python/src/server/config/db_audit_triage.yaml`
- **Documentation**: `DB_AUDIT_NOTES.md`
- **MCP Tool**: `db_security_audit(repo_id, include_tests=False)`
- **Results**: Archon server audited - 0 SQL injection findings, 5 hardcoded dev credentials (acceptable)
- **Report**: `DB_AUDIT_RESULTS_ARCHON.md`

**NIM Audit Layers** (when enabled):
- Nimalyzer pragma checks
- Semgrep generic NIM rules
- Tree-sitter NIM audit

**Triage System**:
- Decisions: confirmed_issue, intentional, false_positive, wont_fix
- Triage memory with semantic similarity
- False negative tracking for meta-audit

### 7. Orchestrator Service (Port 8080)

**Status**: Phase 2 Complete

**Features**:
- Local LLM integration (Ollama-compatible)
- Models: llama3.2 (8B), qwen2.5:7b, mistral:7b, codellama:7b
- Hardware: RTX 3060 12GB, 4-bit quantization (~4-5GB VRAM)

**Endpoints**:
- `GET /health` - Health check
- `POST /orchestrator/repo_health_check` - LLM-enhanced audit
- `POST /orchestrator/plan_refactors` - Refactoring planner (stub)

**Fallback Behavior**: If orchestrator unavailable, `orchestrated_repo_health_check` falls back to standard `repo_health_check`

### 8. Ingestion Pipeline

**Restartable Pipeline** (ADR-001/002):
- Worker-based architecture
- Checkpoint/resume capability
- Health validation at each stage

**API Endpoints** (`ingestion_api.py`):
- `POST /api/ingestion/process-embeddings` - Trigger embedding worker
- `POST /api/ingestion/process-summaries` - Trigger summary worker
- `GET /api/ingestion/health/{source_id}` - Pipeline health
- `GET /api/ingestion/health` - Aggregate health
- `POST /api/ingestion/retry-failed-*` - Retry failed jobs

**Crawl Integration**: `use_new_pipeline=true` flag in crawl requests

---

## What's Not Used / Disabled / Deprecated

### Supabase for Audits
- **Status**: NOT USED
- Audit system uses **PostgreSQL directly** via `archon_audit_*` tables
- No Supabase dependency for audit functionality

### Legacy Regex-Based Audit Rules
- **Status**: DEPRECATED / REPLACED
- Original regex-based rules replaced by Semgrep
- Rule quality metrics now track Semgrep rule performance

### Old Monolithic Pipeline
- **Status**: STILL AVAILABLE but not default
- New pipeline is opt-in via `use_new_pipeline=true`
- Old pipeline remains for backward compatibility

### Direct MCP Imports
- **Status**: ARCHITECTURE CHANGED
- MCP server no longer imports services directly
- All communication via HTTP to other services
- Reduces container size significantly

---

## Database Schema Overview

### Core Tables
- `archon_sources` - Knowledge sources
- `archon_crawled_pages` - Crawled content
- `archon_chunks` - Document chunks
- `archon_embeddings` - Vector embeddings
- `archon_code_repos` - Code repositories
- `archon_code_entities` - Extracted code entities
- `archon_code_relationships` - Entity relationships
- `archon_audit_findings` - Audit findings
- `archon_audit_triage_memory` - Triage decisions
- `archon_audit_false_negatives` - Missed bugs
- `archon_audit_rule_quality` - Rule metrics
- `archon_tasks` - Project tasks (with worktree columns)
- `archon_worktree_summary` - Worktree analytics (view)

---

## Next Steps (Actually Relevant)

### Immediate (Blocking)

1. **Complete NIM Triage Configuration**
   - Current: NIM audit layers exist, basic rules in place
   - Need: Finish any remaining `needs_review` triage entries
   - File: `OMNIBUS_NIM_TRIAGE_REPORT.md` (if exists) or audit rule config

2. **Verify Omnibus Indexing Status**
   - Use `code_repos_get_status(repo_id="...")` to check
   - If not indexed: `code_repos_create_and_index(name="Omnibus", local_path="/path/to/Omnibus")`

### Short-Term (Workflow Improvements)

3. **Agent Skills / Prompt Separation**
   - Extract prompts from hardcoded Python to external `SKILL.md` files
   - Enables prompt management without code changes
   - Location: `python/src/mcp_server/skills/` exists, needs population

4. **Batch Processing Pre-Flight**
   - Estimated data volume before crawl
   - Token cost estimation
   - Risk assessment (time/cost warnings)

### Not Currently Relevant (Defer)

- ❌ RAG pipeline refactors (current pipeline working)
- ❌ Additional audit rules beyond what's configured
- ❌ IDE extensions (not started)
- ❌ IPFS integration (not started)
- ❌ Database abstraction (PostgreSQL working)
- ❌ Knowledge graph (not started)

---

## Key Files for OctoFriend

### When Answering "What's Working?"
1. **This file** (`PROJECT_STATUS_NOW.md`)
2. **MCP Server**: `python/src/mcp_server/mcp_server.py` - see registered modules
3. **API Routes**: `python/src/server/main.py` - see included routers
4. **Live Health**: Check `/health` endpoint

### When Answering "What's Next?"
1. Check `archon_code_repos` table for indexing status
2. Check `archon_tasks` for active work
3. Check `archon_audit_findings` for triage backlog
4. Only then consult legacy roadmaps (marked as historical)

### When Code Conflicts with Docs
- **Code wins**
- Update docs to match code
- Not the other way around

---

## Tool Usage Hierarchy

**For Code Audits** (in priority order):
1. `orchestrated_repo_health_check(repo_id, focus)` - LLM-enhanced, single call
2. `repo_health_check(repo_id, focus)` - Standard, no LLM
3. Individual tools only for specific needs

**For Repository Management**:
1. `code_repos_create_and_index(...)` - Create + index
2. `code_repos_get_status(repo_id)` - Check status
3. `code_repos_list()` - All repos

**For Code Understanding**:
1. `codebase_find_entity(repo_id, name)` - Find by name
2. `codebase_search_by_semantics(repo_id, query)` - Natural language search
3. `codebase_get_entity_context(entity_id)` - Relationships

**For Safety**:
1. Worktree validation happens **automatically** on task operations
2. Explicit: `worktree_validate_safe_to_work(file_paths=[...])`
3. Proactive: `worktree_find_conflicts(file_paths=[...])`

---

## Legacy Roadmap Documents (Historical Only)

The following documents are **out of date** as of March 2026:
- `ROADMAP.md`
- `ROADMAP_NEXT_PHASE.md`
- `IMPLEMENTATION_SUMMARY.md`

See banner notes at top of each file. This document (`PROJECT_STATUS_NOW.md`) is the current source of truth.

---

## How to Verify Current State

```python
# 1. Check MCP health
await health_check()  # MCP tool

# 2. Check API health
curl http://localhost:8181/health

# 3. List registered repos
await code_repos_list()

# 4. Check audit context
await audit_get_context("archon")

# 5. Check current worktree
await worktree_get_current_info()
```

---

**Rule**: If this document conflicts with live code, the live code is correct. Update this document.
