# Version-Scoped Search Guide

## Default Behavior

All code search tools automatically scope to **HEAD of the current branch**.
Deleted functions will NOT appear in results. This prevents agents from receiving
stale code context.

## Problem It Solves

Previously, searching for "how does foo work" would return the old implementation
even if `foo()` was deleted in the current commit. Now:
- Default search returns only code that exists at HEAD
- Deleted functions don't appear in results
- Agents get accurate, non-stale context

## Tools

### Default Search (HEAD only)
- `codebase_search_by_semantics(repo_id, query)` - Semantic search at HEAD
- `codebase_search_by_semantics(repo_id, query, content_type="code")` - Filter by content type
- `codebase_find_entity(repo_id, name)` - Find entity at HEAD
- `codebase_list_entities_in_file(repo_id, file_path)` - List entities at HEAD

### Historical Search (explicit opt-in)
- `codebase_search_at_commit(repo_id, commit_sha, query)` - Search at specific commit
- `codebase_search_on_branch(repo_id, branch_name, query)` - Search on specific branch
- `codebase_entity_evolution(repo_id, entity_name)` - Track entity changes over time

### Working Tree Search (current uncommitted state)
- `search_working_tree(repo_id, query)` - Search only working tree chunks
- `search_all_states(repo_id, query)` - Search both working_tree and committed
- `reindex_file(repo_id, filepath)` - Update index for single file
- `reindex_working_tree(repo_id)` - Update index for all modified files

## Examples

### Find current implementation
```python
# Returns only code at HEAD of current branch
result = await codebase_find_entity(
    repo_id="76abe5b8-693a-40e4-a3a3-c08289465d7d",
    name="extract_entities"
)
```

### Find historical implementation
```python
# Returns code at specific commit (time travel)
result = await codebase_search_at_commit(
    repo_id="76abe5b8-693a-40e4-a3a3-c08289465d7d",
    commit_sha="abc1234",
    query="extract_entities"
)
```

### Search on a specific branch
```python
# Returns code on the specified branch
result = await codebase_search_on_branch(
    repo_id="76abe5b8-693a-40e4-a3a3-c08289465d7d",
    branch_name="feature/new-auth",
    query="user authentication"
)
```

### Search working tree (uncommitted changes)
```python
# First re-index modified files
await reindex_working_tree(repo_id="uuid")

# Then search your current working state
result = await search_working_tree(
    repo_id="uuid",
    query="authentication logic"
)
```

### Search across both states
```python
# See both working tree and committed code in one query
result = await search_all_states(
    repo_id="uuid",
    query="database connection",
    include_working_tree=True,
    include_committed=True
)
```

### Filter by content type
```python
# Search only code entities
result = await codebase_search_by_semantics(
    repo_id="uuid",
    query="authentication",
    content_type="code"
)

# Search only documentation
result = await codebase_search_by_semantics(
    repo_id="uuid",
    query="setup guide",
    content_type="docs"
)
```

## Current Branch Detection

The MCP server automatically detects the current branch from:
1. Environment variable `ARCHON_BRANCH` (set by `archon-mcp` wrapper)
2. Git worktree context (when using `scripts/archon-mcp`)

## Verification

To check current search scope:
```python
result = await worktree_get_current_info()
# Returns: {branch_name, commit_sha, is_clean, ...}
```

To check working tree index status:
```python
stats = await working_tree_stats(repo_id="uuid")
# Returns: {chunks_by_source, working_tree_embeddings, ...}
```

## Search Results Include Branch Info

Each search result now includes:
```json
{
  "name": "extract_entities",
  "file_path": "src/services/code_entity_service.py",
  "branch": "feature/multi-language-code-intelligence",
  "commit": "abc123def"
}
```

This lets you verify the result is from the expected branch.

## See Also

- [Working Tree Re-indexing](./working-tree-reindex.md) - Tools for updating the index
- [Skills Indexing](./skills-indexing.md) - Making skills searchable