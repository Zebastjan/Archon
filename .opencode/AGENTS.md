# OpenCode Agent Instructions for Archon

## Quick Reference: MCP Tools vs. Git Commands

**Use Git commands when:**
- Understanding what changed (`git diff`, `git status`)
- Viewing recent history (`git log`)
- Basic file operations (read, edit)

**Use MCP tools when:**
- Finding code by concept/meaning (semantic search)
- Exploring unfamiliar codebases
- Understanding code relationships
- Searching across different branches/commits

| Task | Best Tool |
|------|-----------|
| "What did I change?" | `git diff` |
| "Which files changed?" | `git status` |
| "Recent commits?" | `git log` |
| "Find auth code" | MCP semantic_search |
| "Where is X function?" | MCP find_entity |
| "What calls Y?" | MCP find_callers |
| "Search across branches" | MCP version-scoped |

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

### Skill 6: Working Tree Management
**When**: You need to manage your current working state
**Tools**: `reindex_file()`, `reindex_working_tree()`, `working_tree_stats()`

Example:
- "Index my current changes before searching"
- "Show me what's in the working tree"
- "Re-index this file after I edited it"

### Skill 7: Working Tree Search
**When**: You want to search your current working state
**Tools**: `search_working_tree()`, `search_all_states()`

Example:
- "Find my current auth implementation"
- "Search across both working tree and committed code"
- "Find what I just wrote in the working tree"

### Skill 8: Skills Management
**When**: You want to index or manage skill files
**Tools**: `skills_index()`, `skills_discover()`, `skills_delete()`

Example:
- "Index all skills in the skills/ directory"
- "What skills do we have available?"
- "Remove this old skill from the index"

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

### Pattern 4: Work with Working Tree
1. **reindex_working_tree**: Index all modified files
2. **search_working_tree**: Find what you're working on
3. **working_tree_stats**: See what's indexed
4. **reindex_file**: Index specific file after edit

### Pattern 5: Search Across States
1. **search_all_states**: Search both working_tree and committed
2. **compare results**: See differences between states
3. **working_tree_stats**: Understand working tree status

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

## Working Tree Tools

### Reindex Tools (ADR-016)
Use these tools when you've made changes and need to update the search index:

```
# Re-index a single file after editing
await reindex_file(repo_id="uuid", filepath="src/auth.py")

# Re-index all modified files in working tree
await reindex_working_tree(repo_id="uuid")

# Get statistics about working tree
await working_tree_stats(repo_id="uuid")
```

### Working Tree Search
Search across both working tree and committed code:

```
# Search only working tree (current state)
await search_working_tree(repo_id="uuid", query="authentication logic")

# Search both working tree and committed
await search_all_states(repo_id="uuid", query="database connection")

# Filter by file path
await search_working_tree(
    repo_id="uuid",
    query="auth",
    file_path_filter="src/auth/%"
)
```

## Skills Management

### Index Skills Directory
Make the skills/ directory searchable:

```
# Index all skills
await skills_index(repo_id="uuid")

# Discover what skills exist
await skills_discover()

# Remove a skill from index
await skills_delete(repo_id="uuid", skill_path="skills/prompts/old-skill.md")
```

## Content Type Filter

Filter search results by content type:

```
# Search only code entities
await codebase_search_by_semantics(
    repo_id="uuid",
    query="authentication",
    content_type="code"
)

# Search only documentation
await codebase_search_by_semantics(
    repo_id="uuid",
    query="setup guide",
    content_type="docs"
)

# Search all (default)
await codebase_search_by_semantics(
    repo_id="uuid",
    query="configuration",
    content_type="all"
)
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
