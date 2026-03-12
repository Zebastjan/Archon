# Code Entity Usage Guide

**Feature:** Multi-language code intelligence via Tree-sitter  
**Branch:** `feature/multi-language-code-intelligence`

---

## Quick Start

### 1. Apply Database Migration

```bash
# Apply the migration to your Supabase/PostgreSQL instance
psql $DATABASE_URL < migration/012_add_code_entities_and_relationships.sql
```

### 2. Install Dependencies

```bash
cd python
uv pip install -e ".[server]"
```

### 3. Extract Code Entities from a Repository

#### Via API

```bash
# Sync commits and extract entities in one call
curl -X POST "http://localhost:8000/api/projects/{project_id}/repository/sync-with-entities" \
  -H "Content-Type: application/json" \
  -d '{
    "branch_name": "main",
    "extract_entities": true,
    "entity_batch_size": 50
  }'

# Or extract entities separately for a specific commit
curl -X POST "http://localhost:8000/api/projects/{project_id}/repository/extract-entities" \
  -H "Content-Type: application/json" \
  -d '{
    "commit_sha": "abc123",
    "batch_size": 50
  }'
```

#### Via Python

```python
from src.server.services.git.git_repository_service import GitRepositoryService

service = GitRepositoryService()

# Extract from all supported files at HEAD
results = await service.extract_code_entities(
    repo_id="your-repo-uuid",
    commit_sha="HEAD",
    batch_size=50
)

print(f"Processed: {results['processed']} files")
print(f"Entities: {results['entities_created']}")
print(f"Relationships: {results['relationships_created']}")
```

---

## MCP Tools Usage

### Find Entities by Name

```python
# In Claude Code or other MCP client
await codebase_find_entity(
    repo_id="uuid",
    name="get_user",
    entity_type="function"
)

# Returns:
{
  "success": True,
  "count": 3,
  "entities": [
    {
      "id": "uuid",
      "name": "get_user_by_id",
      "entity_type": "function",
      "language": "python",
      "file_path": "src/services/user.py",
      "line_start": 45,
      "line_end": 62,
      "signature": "def get_user_by_id(user_id: int) -> User:",
      "docstring": "Retrieve user by ID from database."
    }
  ]
}
```

### Get Entity Context (Relationships)

```python
# Find what a function calls and what calls it
await codebase_get_entity_context(
    entity_id="entity-uuid",
    include_callees=True,
    include_callers=True
)

# Returns:
{
  "success": True,
  "entity_id": "uuid",
  "relationship_count": 5,
  "relationships": [
    {
      "relationship_type": "CALLS",
      "entity_name": "db.query",
      "entity_type": "function"
    },
    {
      "relationship_type": "CALLS",
      "entity_name": "validate_user",
      "entity_type": "function"
    }
  ]
}
```

---

## Querying Entities via SQL

### Find All Functions in a File

```sql
SELECT name, signature, line_start, line_end
FROM archon_code_entities
WHERE repo_id = 'uuid'
  AND file_path = 'src/services/user.py'
  AND entity_type = 'function'
ORDER BY line_start;
```

### Find Callers of a Function

```sql
-- Find all functions that call 'get_user'
SELECT ce.name, ce.file_path, ce.line_start
FROM archon_code_entities ce
JOIN archon_code_relationships cr ON ce.id = cr.source_entity_id
JOIN archon_code_entities target ON cr.target_entity_id = target.id
WHERE target.name = 'get_user'
  AND cr.relationship_type = 'CALLS';
```

### Find Dead Code (Functions Never Called)

```sql
-- Find functions with no incoming CALLS relationships
SELECT ce.name, ce.file_path
FROM archon_code_entities ce
LEFT JOIN archon_code_relationships cr 
  ON ce.id = cr.target_entity_id 
  AND cr.relationship_type = 'CALLS'
WHERE ce.entity_type = 'function'
  AND ce.repo_id = 'uuid'
  AND cr.id IS NULL;
```

### Class Hierarchy

```sql
-- Find all classes and their inheritance
SELECT 
  ce.name as class_name,
  ce.signature,
  cr.target_name as parent_class
FROM archon_code_entities ce
LEFT JOIN archon_code_relationships cr 
  ON ce.id = cr.source_entity_id 
  AND cr.relationship_type = 'INHERITS'
WHERE ce.entity_type = 'class'
  AND ce.repo_id = 'uuid';
```

### Semantic Search

```sql
-- Search by embedding (requires embeddings to be generated)
SELECT * FROM match_archon_code_entities_multi(
  query_embedding := ARRAY[0.1, 0.2, ...]::vector,  -- Your embedding
  embedding_dimension := 1536,
  match_count := 10,
  filter := '{}',
  repo_filter := 'uuid'
);
```

---

## Dogfooding: Query Archon Itself

### Example Queries

```python
# 1. Find all places using Supabase client
await codebase_find_entity(
    repo_id="archon-repo-uuid",
    name="get_supabase_client",
    entity_type="function"
)

# 2. Find MCP tool registrations
await codebase_find_entity(
    repo_id="archon-repo-uuid",
    name="register_",
    entity_type="function"
)

# 3. Get context around a service
entities = await codebase_find_entity(
    repo_id="archon-repo-uuid",
    name="GitRepositoryService",
    entity_type="class"
)

if entities["entities"]:
    await codebase_get_entity_context(
        entity_id=entities["entities"][0]["id"],
        include_callees=True,
        include_callers=False
    )
```

---

## Supported Languages

| Language | File Extensions | Entity Types |
|----------|----------------|--------------|
| Python | .py, .pyw, .pyi | function, method, class, import |
| TypeScript | .ts, .tsx | function, method, class, interface, type_alias |
| JavaScript | .js, .jsx, .mjs, .cjs | function, method, class |

### Adding a New Language

1. Install tree-sitter grammar:
```bash
uv pip install tree-sitter-nim
```

2. Create language support:
```python
# src/server/services/languages/nim_support.py
from .language_support import LanguageSupportBase

class NimLanguageSupport(LanguageSupportBase):
    language_id = "nim"
    file_extensions = [".nim", ".nims"]
    
    def extract_entities_and_relationships(self, content, file_path):
        # Parse with tree-sitter-nim
        # Extract procs, types, etc.
        pass
```

3. Register in `language_registry.py`:
```python
from .nim_support import NimLanguageSupport
registry.register(NimLanguageSupport())
```

---

## Architecture Overview

```
User Request
    │
    ▼
┌─────────────────┐
│  MCP Tool / API │
└────────┬────────┘
         │
    ┌────▼────┐
    │  Route  │
    └────┬────┘
         │
    ┌────▼─────────────┐
    │ GitRepositoryService│
    │  - extract_code_entities()
    └────┬─────────────┘
         │
    ┌────▼─────────────┐
    │ CodeEntityService   │
    │  - extract_and_store()
    └────┬─────────────┘
         │
    ┌────▼─────────────┐
    │ LanguageSupport     │
    │  (Tree-sitter)      │
    └────┬─────────────┘
         │
    ┌────▼─────────────┐
    │ PostgreSQL          │
    │  archon_code_entities
    │  archon_code_relationships
    └────────────────────┘
```

---

## Troubleshooting

### "No language support for file"
- Check file extension is in supported list
- Verify tree-sitter grammar is installed

### "Parse error"
- File may have syntax errors
- Tree-sitter grammar version mismatch

### "No entities found"
- File may be empty or only contain imports
- Try a different file with more code

### Database errors
- Ensure migration 012 was applied
- Check RLS policies allow inserts

---

## Next Steps

1. **Generate Embeddings**
   - Integrate with existing EmbeddingService
   - Generate embeddings for extracted entities
   - Enable semantic search

2. **Incremental Updates**
   - Detect changed files on new commits
   - Update only modified entities
   - Track entity history across commits

3. **Cross-File Resolution**
   - Resolve imports across files
   - Build module-level dependency graph
   - Enable "find all references"

4. **More Languages**
   - Add Rust, Go, Java support
   - Test with OpenClaw codebase

---

**Questions?** Check `IMPLEMENTATION_SUMMARY_MULTI_LANGUAGE.md` for technical details.
