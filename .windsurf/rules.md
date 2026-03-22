# Archon Windsurf Rules

## Project Overview
Archon is an AI agent framework built on Pydantic AI with PostgreSQL backends.

## Architecture
- **Unified Server**: Runs on `http://localhost:8181` (FastAPI + MCP combined)
- **Database**: Local PostgreSQL on port 5433 with pgvector
- **Embeddings**: Ollama + BGE-Large (1024 dimensions)
- **Configuration**: Strict YAML config at `python/config.yaml`

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
