# Multi-Language Code Intelligence Implementation Summary

**Branch:** `feature/multi-language-code-intelligence`
**Status:** Phase 1 Complete - Core Infrastructure Ready

---

## Overview

This implementation adds Tree-sitter-based code entity extraction and relationship tracking to Archon. It enables Archon to:

1. **Parse source code** using Tree-sitter grammars (Python, TypeScript/JavaScript)
2. **Extract entities** (functions, classes, methods, interfaces, etc.)
3. **Track relationships** (CALLS, INHERITS, IMPORTS, DEFINES, etc.)
4. **Store with multi-dimensional embeddings** (384, 768, 1024, 1536, 3072)
5. **Query via SQL** including graph traversal and semantic search

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Language Support Layer                    │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐    │
│  │ Python Support  │  │ TypeScript/JS   │  │ Future: Nim/Zig │    │
│  │ (tree-sitter)   │  │ (tree-sitter)   │  │ (tree-sitter)   │    │
│  └────────┬────────┘  └────────┬────────┘  └─────────────────┘    │
│           │                    │                                    │
│           └────────────────────┘                                    │
│                    │                                                │
│           ┌────────▼────────┐                                       │
│           │ LanguageSupport │ ← Protocol/Abstract Base              │
│           │   Protocol      │   (extract_entities_and_relationships)│
│           └────────┬────────┘                                       │
│                    │                                                │
│  ┌─────────────────▼─────────────────┐                               │
│  │     LanguageSupportRegistry       │                               │
│  │  (file extension → language map)  │                               │
│  └─────────────────┬─────────────────┘                               │
└────────────────────┼───────────────────────────────────────────────┘
                     │
┌────────────────────▼───────────────────────────────────────────────┐
│                      Extraction Layer                                 │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  CodeEntityService                                           │    │
│  │  ├─ extract_and_store_entities(repo_id, files)               │    │
│  │  ├─ generate_embeddings(repo_id, model)                      │    │
│  │  ├─ find_entity_by_name(repo_id, name)                       │    │
│  │  ├─ get_entity_relationships(entity_id)                    │    │
│  │  └─ search_entities(query_embedding)                       │    │
│  └──────────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────────────┘
                     │
┌────────────────────▼───────────────────────────────────────────────┐
│                      Database Layer                                   │
│  ┌─────────────────────────┐    ┌─────────────────────────────┐     │
│  │  archon_code_entities   │───▶│  archon_code_relationships  │     │
│  │  - id (UUID)            │    │  - id (UUID)                │     │
│  │  - repo_id (FK)         │    │  - source_entity_id (FK)    │     │
│  │  - file_path            │    │  - target_entity_id (FK)    │     │
│  │  - entity_type          │    │  - relationship_type        │     │
│  │  - name                 │    │  - metadata (JSONB)         │     │
│  │  - signature            │    └─────────────────────────────┘     │
│  │  - source_code          │                                       │
│  │  - embedding_* (5 dims) │                                       │
│  │  - language             │                                       │
│  │  - commit_sha           │                                       │
│  └─────────────────────────┘                                       │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Files Created

### Database Migration
- `migration/012_add_code_entities_and_relationships.sql` (507 lines)
  - Creates `archon_code_entities` table with 5 embedding dimensions
  - Creates `archon_code_relationships` table for graph edges
  - Indexes for efficient querying
  - RLS policies for security
  - PostgreSQL functions:
    - `match_archon_code_entities_multi()` - semantic search
    - `get_entity_relationships()` - graph traversal
    - `find_entity_path()` - 2-hop path finding

### Language Support Module
- `python/src/server/services/languages/__init__.py` (20 lines)
- `python/src/server/services/languages/language_support.py` (138 lines)
  - `CodeEntity` dataclass
  - `CodeRelationship` dataclass  
  - `LanguageSupport` protocol
  - `LanguageSupportBase` abstract class
  - `ParseError` exception

- `python/src/server/services/languages/language_registry.py` (140 lines)
  - `LanguageSupportRegistry` class
  - Global registry instance
  - Lazy loading of language modules

- `python/src/server/services/languages/python_support.py` (513 lines)
  - `PythonLanguageSupport` class
  - Extracts: functions, classes, methods, imports, decorators
  - Relationships: CALLS, INHERITS, IMPORTS, DEFINES, DECORATES
  - Handles async, nested functions, docstrings

- `python/src/server/services/languages/typescript_support.py` (703 lines)
  - `TypeScriptLanguageSupport` class
  - Handles both TypeScript and JavaScript
  - Extracts: functions, classes, interfaces, type aliases, methods
  - Relationships: CALLS, INHERITS, IMPORTS, DEFINES, IMPLEMENTS, DECORATES
  - Supports generics, async/await, decorators

### Service Layer
- `python/src/server/services/code_entity_service.py` (458 lines)
  - `CodeEntityService` class
  - `extract_and_store_entities()` - main extraction pipeline
  - `generate_embeddings()` - placeholder for embedding generation
  - `find_entity_by_name()` - name-based search
  - `get_entity_relationships()` - relationship traversal
  - `search_entities()` - semantic search via embeddings

### Tests
- `python/tests/languages/test_language_support.py` (267 lines)
  - Tests for language registry
  - Tests for Python extraction
  - Tests for TypeScript extraction
  - Integration test placeholders

### Dependencies
- Updated `python/pyproject.toml`
  - `tree-sitter>=0.22.0`
  - `tree-sitter-python>=0.21.0`
  - `tree-sitter-typescript>=0.21.0`
  - `tree-sitter-javascript>=0.21.0`

---

## Usage Examples

### Extract from Python Files

```python
from src.server.services.languages import get_language_for_file

support = get_language_for_file("src/main.py")
entities, relationships = support.extract_entities_and_relationships(
    content="def greet(): pass",
    file_path="src/main.py"
)

# entities[0] -> CodeEntity(
#     entity_type="function",
#     name="greet",
#     signature="def greet()",
#     line_start=1,
#     line_end=1
# )
```

### Store Entities and Relationships

```python
from src.server.services.code_entity_service import CodeEntityService

service = CodeEntityService()

# Assuming async file_content_getter function
results = await service.extract_and_store_entities(
    repo_id="uuid",
    commit_sha="abc123",
    file_paths=["src/main.py", "src/utils.py"],
    file_content_getter=async_get_content
)

# results = {
#     "processed": 2,
#     "entities_created": 15,
#     "relationships_created": 23,
#     "errors": []
# }
```

### Query by Name

```python
entities = await service.find_entity_by_name(
    repo_id="uuid",
    name="get_user",
    entity_type="function"
)
```

### Get Relationships

```python
relationships = await service.get_entity_relationships(
    entity_id="entity-uuid",
    relationship_types=["CALLS"],
    direction="outgoing"
)

# Returns functions called by this entity
```

### Semantic Search

```python
from src.server.services.embeddings.embedding_service import EmbeddingService

# Generate embedding
embedding_service = EmbeddingService()
embedding = await embedding_service.get_embedding("user authentication")

# Search code entities
results = await service.search_entities(
    query_embedding=embedding,
    embedding_dimension=1536,
    match_count=10,
    repo_filter="repo-uuid"
)
```

---

## Database Schema Details

### archon_code_entities

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| repo_id | UUID | FK to archon_git_repositories |
| file_path | TEXT | Relative path in repo |
| line_start | INT | Starting line (1-indexed) |
| line_end | INT | Ending line (1-indexed) |
| entity_type | TEXT | function/class/method/interface/etc |
| name | TEXT | Fully qualified name |
| signature | TEXT | Function signature or class def |
| docstring | TEXT | Documentation |
| source_code | TEXT | Full source of entity |
| embedding_* | VECTOR | 5 columns for different dims |
| embedding_model | TEXT | Which model was used |
| embedding_dimension | INT | Dimension of used embedding |
| language | TEXT | python/typescript/javascript |
| commit_sha | TEXT | Git commit SHA |
| metadata | JSONB | Additional metadata |

### archon_code_relationships

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| source_entity_id | UUID | FK to source entity |
| target_entity_id | UUID | FK to target entity |
| relationship_type | TEXT | CALLS/INHERITS/IMPORTS/etc |
| metadata | JSONB | Line number, confidence, etc |

### Relationship Types

- `CALLS` - Function calls another function
- `INHERITS` - Class inherits from another
- `IMPORTS` - Module imports another
- `DEFINES` - Container defines contained entity
- `USES` - Entity uses another (variables, etc)
- `DECORATES` - Decorator applied to entity
- `IMPLEMENTS` - Class implements interface
- `RETURNS` - Function returns type
- `ACCEPTS` - Function accepts parameter type
- `RAISES` - Function raises exception

---

## Next Steps

### Immediate (Before Merge)

1. **Install Dependencies**
   ```bash
   cd python
   uv pip install -e ".[server]"
   ```

2. **Run Migration**
   ```bash
   # Apply 012_add_code_entities_and_relationships.sql to database
   ```

3. **Run Tests**
   ```bash
   cd python
   uv run pytest tests/languages/test_language_support.py -v
   ```

4. **Test Extraction**
   ```python
   # Test with Archon repo files
   from src.server.services.languages import get_language_for_file
   
   support = get_language_for_file("src/server/services/client_manager.py")
   with open("src/server/services/client_manager.py") as f:
       entities, rels = support.extract_entities_and_relationships(
           f.read(), "client_manager.py"
       )
   print(f"Found {len(entities)} entities")
   ```

### Phase 2 (Post-Merge)

1. **Integration with GitRepositoryService**
   - Add `extract_code_entities()` method
   - Call after `sync_commits()`
   - Batch process files

2. **Embedding Generation**
   - Integrate with existing `EmbeddingService`
   - Generate embeddings for extracted entities
   - Support multiple dimensions

3. **MCP Tools**
   - Add `codebase_find_function` tool
   - Add `codebase_get_function_context` tool
   - Add `codebase_search_entities` tool

4. **Dogfooding**
   - Ingest Archon repo itself
   - Query: "Find all places using Supabase client"
   - Query: "Show class hierarchy"

### Phase 3 (Future Languages)

Adding a new language (e.g., Nim, Zig, ZAMO):

1. Install tree-sitter grammar: `uv pip install tree-sitter-nim`
2. Create `nim_support.py` implementing `LanguageSupport`
3. Register in `language_registry.py`
4. Add tests

Example:
```python
# src/server/services/languages/nim_support.py
class NimLanguageSupport(LanguageSupportBase):
    language_id = "nim"
    file_extensions = [".nim", ".nims"]
    
    def extract_entities_and_relationships(self, content, file_path):
        # Parse with tree-sitter-nim
        # Extract procs, types, etc.
        pass
```

---

## Design Decisions

### Multi-Dimensional Embeddings

Following Archon's existing pattern, we support 5 embedding dimensions:
- 384: Small models (all-MiniLM-L6-v2)
- 768: BGE-small, efficient
- 1024: BGE-base, Ollama models
- 1536: OpenAI default (text-embedding-3-small)
- 3072: OpenAI large (text-embedding-3-large)

This allows:
- A/B testing different models
- Using different models for different use cases
- Migrating without re-indexing everything

### Normalized Relationship Table

Relationships are stored in a separate table (not JSONB arrays) to enable:
- Efficient graph queries ("find all callers")
- Foreign key constraints
- Indexing for performance
- SQL-based graph traversal

### Protocol-Based Design

Using `typing.Protocol` for `LanguageSupport` allows:
- Duck typing - any class with right methods works
- Runtime checking with `isinstance()`
- Easy testing with mocks
- No forced inheritance

### Lazy Language Loading

Languages are loaded on first registry access:
- Faster startup when only using some languages
- Graceful degradation if parser not installed
- Easy to add optional language dependencies

---

## Testing Strategy

### Unit Tests
- `test_language_registry.py` - Registry behavior
- `test_python_support.py` - Python extraction
- `test_typescript_support.py` - TypeScript extraction

### Integration Tests
- Test with real git repository
- Test with Archon's own code
- Test database operations

### Manual Testing
```bash
# Test Python extraction
python -c "
from src.server.services.languages import get_language_for_file
support = get_language_for_file('test.py')
print(f'Language: {support.language_id}')
"

# Test TypeScript extraction
python -c "
from src.server.services.languages import get_language_for_file
support = get_language_for_file('test.ts')
print(f'Language: {support.language_id}')
"
```

---

## Performance Considerations

### Parsing
- Tree-sitter is fast (incremental parsing)
- Large files parse in milliseconds
- Memory usage proportional to file size

### Storage
- One row per entity
- Relationships stored once
- Embeddings stored in appropriate column
- Indexes on frequently queried columns

### Querying
- `match_archon_code_entities_multi()` uses ivfflat indexes
- Relationship queries use B-tree indexes
- Foreign keys ensure referential integrity

---

## Open Questions

1. **Embedding Generation Timing**
   - Generate immediately after extraction?
   - Queue for background processing?
   - Configurable per repository?

2. **Incremental Updates**
   - How to update when file changes?
   - Compare AST or re-extract everything?
   - Track which entities changed?

3. **Cross-File Relationships**
   - Currently only within-file
   - Need symbol resolution for imports
   - Build module index?

4. **Embedding Model Selection**
   - Code-specific models (CodeBERT, etc)?
   - Different models for different languages?
   - User-configurable?

---

## References

- [Tree-sitter Documentation](https://tree-sitter.github.io/tree-sitter/)
- [Python Grammar](https://github.com/tree-sitter/tree-sitter-python)
- [TypeScript Grammar](https://github.com/tree-sitter/tree-sitter-typescript)
- [Archon ADR-002](https://github.com/coleam00/Archon/blob/main/ADR-002-IMPLEMENTATION-STATUS.md)
- [OpenClaw VISION.md](https://github.com/openclaw/openclaw/blob/main/VISION.md)

---

**Summary:** This implementation provides a solid foundation for multi-language code intelligence in Archon. It follows existing patterns, supports extensibility, and enables powerful code understanding queries. Ready for testing and integration.
