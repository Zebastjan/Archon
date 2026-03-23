# OpenCode Agent Instructions for Archon

## Skills: When to Use Which Tool

### Skill 1: Find Code by Name
**When**: You know (approximately) what something is called
**Tool**: `codebase_find_entity`

Example:
- "Find the extract_entities function"
- "Where is the CodeEntityService class?"
- "Show me all methods named initialize"

### Skill 2: Find Code by Concept
**When**: You know WHAT you want but not the name
**Tool**: `codebase_semantic_search`

Example:
- "Find code that handles git commits"
- "Show me database connection pooling"
- "Find error handling patterns"

### Skill 3: Understand Code Context
**When**: You found code and want to understand it fully
**Tool**: `codebase_get_entity_context`

Example:
- "What calls this function?"
- "What does this class inherit from?"
- "Show me the full implementation"

### Skill 4: Find Usage/Impact
**When**: You need to know "who uses this?"
**Tool**: `codebase_find_callers`

Example:
- "Who calls the embedding service?"
- "What depends on this function?"
- "Find all usages of this class"

### Skill 5: Explore Repository
**When**: You need a high-level view
**Tool**: `codebase_repo_stats` and `codebase_list_repos`

Example:
- "What repos do we have indexed?"
- "How many functions are in this codebase?"
- "Show me the file structure"

## Workflow Patterns

### Pattern 1: Understand a Feature
1. **semantic_search**: "Find code that handles X"
2. **find_entity**: Look for specific function names
3. **get_entity_context**: Deep dive into key functions
4. **find_callers**: Understand how it's used

### Pattern 2: Find Impact of Changes
1. **find_entity**: Locate the function/class to change
2. **find_callers**: See all places that call it
3. **get_entity_context**: Understand the relationships

### Pattern 3: Explore New Codebase
1. **repo_stats**: Get high-level view
2. **find_by_file**: Look at key files
3. **semantic_search**: Find relevant features
4. **get_entity_context**: Deep dive

## Repository IDs

Use these IDs when querying:

### ✅ Fully Ingested (with BGE-M3 1024-dim embeddings)
| Repository | ID | Entities | Embeddings | Language |
|------------|-----|----------|------------|----------|
| **archon-python** | `76abe5b8-693a-40e4-a3a3-c08289465d7d` | ~5,000 | ✅ 100% | Python |
| **syllablaze** | `c8b210fa-8d64-4cb2-9c17-446bc314191f` | ~3,000 | ✅ 100% | Python |
| **octofriend** | `358e1fae-5794-4be8-a160-d32df0e97d0f` | ~600 | ✅ 100% | TypeScript |

**Total**: ~8,600 entities with BGE-M3 1024-dim embeddings

### Semantic Search
✅ **All repositories support semantic search** via `codebase_search_by_semantics`

## Prompt Patterns

### For Finding Code
```
Use codebase_find_entity in repo "archon-python" to find "extract_entities"
```

### For Semantic Search
```
Use codebase_semantic_search in repo "archon-python" with query "database connection pooling"
```

### For Understanding Context
```
Use codebase_get_entity_context with entity_id "uuid-from-previous-search"
```

### For Finding Callers
```
Use codebase_find_callers in repo "archon-python" for function "generate_embeddings"
```

## Automatic Repository Detection

When working with files, automatically detect the repo:
- `.py` files in `python/src/` → archon-python
- `.py` files in `octofriend/` → octofriend
- `.ts/.tsx` files in `syllablaze/` → syllablaze

## Best Practices

1. **Start broad, then narrow**: Use semantic search first, then find exact entities
2. **Check relationships**: Always look at callers and callees
3. **Use embeddings**: BGE-M3 1024-dim embeddings understand code semantics
4. **Link to GitHub**: When showing results, generate GitHub URLs for reference
5. **Incremental updates**: Repos auto-update on commit via git hooks

## Troubleshooting

If tools aren't working:
1. Check if archon-mcp is running: `curl http://localhost:8051/health`
2. Verify repo_id is correct
3. Try simpler queries first
4. Check logs: `docker logs archon`
