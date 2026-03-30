# Archon Windsurf Rules

## Project Overview
Archon is an AI agent framework built on Pydantic AI with PostgreSQL backends.

## Architecture
- **Unified Server**: Runs on `http://localhost:8181` (FastAPI + MCP combined)
- **Database**: Local PostgreSQL on port 5433 with pgvector
- **Embeddings**: Ollama + BGE-Large (1024 dimensions)
- **Configuration**: Strict YAML config at `python/config.yaml`

## 🚨 AUTOMATIC SESSION STARTUP (CRITICAL)

### On Every Session Start, You MUST:

1. **Load Context Bundle** - Read `.archon/context/STATUS.md` immediately
2. **Display Health Status** - Show top 5 audit findings from `repo_health_check`
3. **List Active Tasks** - Call `find_tasks` to show what's in progress
4. **Verify Skills** - Confirm `skills_discover` returns 15+ skills

### Startup Tool Sequence (Execute in Order):

```
mcp0_worktree_get_current_info → Display branch/context
mcp0_find_projects → Show active projects
mcp0_repo_health_check → Show health score + top issues
mcp0_skills_discover → Verify skills indexed
```

### Context Display Format:

```
# Session Startup Summary
- **Branch**: {current_branch}
- **Project**: {project_name}
- **Health Score**: {score}/100
- **Active Tasks**: {count}
- **Audit Issues**: {critical} critical, {warning} warnings
- **Skills**: {count} indexed
```

## Critical Rules

### 1. Use MCP Tools First
- **Projects**: `find_projects`, `manage_project`
- **Tasks**: `find_tasks`, `manage_task`
- **RAG**: `rag_search_knowledge_base`, `rag_search_code_examples`
- **Code Audit**: `repo_health_check`, `db_security_audit`
- **Code Intelligence**: `codebase_find_entity`, `codebase_search_by_semantics`

### 2. No Direct DB Access
❌ **Forbidden**: psql, direct SQL queries
✅ **Required**: Use MCP tools or service layer

### 3. Configuration
- Config: `python/config.yaml` (validated with Pydantic)
- Server port: 8181
- PostgreSQL port: 5433

## Quick Commands

```bash
# Start everything
python start.py

# Check status
python start.py --status

# Stop everything
python start.py --stop
```

## MCP Endpoints
- **SSE**: `http://localhost:8181/mcp`
- **Health**: `http://localhost:8181/health`
- **API**: `http://localhost:8181/api/*`

## Key Documentation
- `CLAUDE.md` - Project philosophy and constraints
- `python/config.yaml` - Server configuration
- `ROADMAP.md` - Development roadmap
