# Semantic Search Setup Guide

## Overview

Archon now supports semantic search over code entities using Ollama embeddings with branch/commit scoping.

## Current Status

✅ **Working:**
- Ollama integration with bge-m3 model (1024 dimensions)
- Semantic search API endpoint: `POST /api/code/search`
- Branch-scoped searching
- Commit-scoped searching
- Automatic worktree context detection via MCP tools

## Configuration

### Database Settings

The following settings must be configured in `archon_settings` table:

```sql
-- Required for semantic search
INSERT INTO archon_settings (id, key, value, is_encrypted, category, description)
VALUES (
    gen_random_uuid(), 
    'EMBEDDING_PROVIDER', 
    'ollama', 
    false, 
    'rag_strategy', 
    'Embedding provider: ollama, openai'
);

INSERT INTO archon_settings (id, key, value, is_encrypted, category, description)
VALUES (
    gen_random_uuid(), 
    'EMBEDDING_MODEL', 
    'bge-m3', 
    false, 
    'rag_strategy', 
    'Embedding model name'
);

INSERT INTO archon_settings (id, key, value, is_encrypted, category, description)
VALUES (
    gen_random_uuid(), 
    'LLM_BASE_URL', 
    'http://172.17.0.1:11434', 
    false, 
    'rag_strategy', 
    'Ollama server URL'
);
```

### Environment Variables (docker-compose.yml)

```yaml
environment:
  - OLLAMA_URL=http://172.17.0.1:11434
  - EMBEDDING_PROVIDER=ollama
  - OLLAMA_EMBEDDING_MODEL=bge-m3
```

### Ollama Setup

Ensure Ollama is running on the host with bge-m3 model:

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Pull bge-m3 if not already present
ollama pull bge-m3
```

## API Usage

### Basic Semantic Search

```bash
curl -X POST http://localhost:8181/api/code/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "database connection pooling",
    "match_count": 5
  }'
```

### Branch-Scoped Search

```bash
curl -X POST http://localhost:8181/api/code/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "database connection pooling",
    "match_count": 5,
    "branch_name": "feature/multi-backend-stt"
  }'
```

### Commit-Scoped Search

```bash
curl -X POST http://localhost:8181/api/code/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "database connection pooling",
    "match_count": 5,
    "commit_sha": "dafd78a3"
  }'
```

### Combined Filters

```bash
curl -X POST http://localhost:8181/api/code/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "database connection pooling",
    "match_count": 5,
    "repo_id": "6a783e2e-6887-4c04-bd11-35fc22d775ea",
    "entity_type": "function",
    "branch_name": "feature/multi-backend-stt"
  }'
```

## Response Format

```json
{
  "success": true,
  "results": [
    {
      "id": "15c8eead-7979-4649-8219-923e98db398c",
      "repo_id": "6a783e2e-6887-4c04-bd11-35fc22d775ea",
      "file_path": "blaze/orchestration.py",
      "entity_type": "method",
      "name": "Orchestrator.__init__",
      "signature": "def __init__(self, ...)",
      "docstring": null,
      "source_code": "def __init__(self): ...",
      "language": "python",
      "similarity": 0.4367724976348958,
      "branch_name": "feature/multi-backend-stt",
      "commit_sha": "dafd78a3"
    }
  ],
  "query": "database connection pooling",
  "match_count": 5,
  "total_found": 3,
  "repo_filter": "6a783e2e-6887-4c04-bd11-35fc22d775ea",
  "entity_type_filter": "function",
  "branch_filter": "feature/multi-backend-stt",
  "commit_filter": null,
  "version_scoped": true
}
```

## MCP Tools Integration

The MCP tools automatically use worktree context for branch-scoped searches:

- `codebase_find_entity` - Searches current branch by default
- `codebase_get_entity_context` - Returns entities from current branch
- `codebase_find_callers` - Shows callers from current branch

### Worktree Context

MCP server detects branch/commit from environment:
```python
from src.mcp_server.worktree_context import get_current_branch, get_current_commit

branch = get_current_branch()  # Current git branch
commit = get_current_commit()    # Current commit SHA
```

## Knowledge Graph Features

### Cross-Commit/Branch Reasoning

To search across all branches/commits (for regression analysis):

```bash
# Don't specify branch_name or commit_sha to search all versions
curl -X POST http://localhost:8181/api/code/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "auth logic",
    "match_count": 10
  }'
```

### Entity Relationships

Entities are linked by:
- `repo_id` - Repository membership
- `branch_name` - Branch context
- `commit_sha` - Version context
- `entity_identity` - Same entity across versions

## Troubleshooting

### "Connection error" when creating embeddings

1. Check Ollama is running: `curl http://localhost:11434/api/tags`
2. Verify bge-m3 is pulled: `ollama list | grep bge-m3`
3. Check container can reach Ollama: `docker exec archon curl http://172.17.0.1:11434/api/tags`

### "column metadata does not exist"

The PostgreSQL functions were updated. If this error occurs:
```bash
# Recreate the functions
docker exec archon psql -U archon -d archon -c "
DROP FUNCTION IF EXISTS match_archon_code_entities_multi(vector,integer,integer,jsonb,uuid);
DROP FUNCTION IF EXISTS match_archon_code_entities(vector,integer,jsonb,uuid);
-- Then recreate as shown in migration files
"
```

### No results for branch

Check that entities exist for the branch:
```sql
SELECT COUNT(*) FROM archon_code_entities WHERE branch_name = 'your-branch-name';
```

## Future Enhancements

- [ ] Cross-repo semantic search
- [ ] Knowledge graph visualization
- [ ] Change impact analysis across branches
- [ ] Automatic regression detection
- [ ] TLA+ specification linking
