# Working Tree Re-indexing Guide

## Overview

When you make changes to files, the search index becomes stale. The reindex tools
let you update the index immediately, without waiting for a commit.

## Problem It Solves

Previously, search results reflected the last committed state. If you edited a file
but hadn't committed, searches would return the old implementation. Now:
- `reindex_file()` updates the index for a single file
- `reindex_working_tree()` updates all modified files
- `search_working_tree()` searches your current working state

## Tools

### Reindex Tools

#### `reindex_file(repo_id, filepath)`
Manually trigger re-indexing of a specific file.

**When to use:**
- After editing a file and before searching for its contents
- When file watcher is not running
- To force re-index after bulk edits

**Example:**
```python
await reindex_file(
    repo_id="uuid",
    filepath="src/auth.py"
)
```

**Returns:**
```json
{
    "success": true,
    "status": "reindexed",
    "chunks_updated": 5,
    "embedding_ms": 120
}
```

#### `reindex_working_tree(repo_id, paths=None)`
Re-index all modified files in the working tree.

**When to use:**
- After pulling changes from remote
- After multiple file edits
- Before starting a search session

**Example:**
```python
# Re-index all modified files
await reindex_working_tree(repo_id="uuid")

# Re-index specific files only
await reindex_working_tree(
    repo_id="uuid",
    paths=["src/auth.py", "src/config.py"]
)
```

#### `working_tree_stats(repo_id)`
Get statistics about working tree chunks.

**When to use:**
- Check what's indexed in the working tree
- Verify embedding status
- Debug search issues

**Example:**
```python
await working_tree_stats(repo_id="uuid")
```

**Returns:**
```json
{
    "success": true,
    "chunks_by_source": {
        "working_tree": 150,
        "committed": 500
    },
    "working_tree_embeddings": 145
}
```

### Search Tools

#### `search_working_tree(repo_id, query, top_k=10, file_path_filter=None)`
Search only working tree chunks.

**When to use:**
- Find code you just wrote but haven't committed
- Search your current working state
- Isolate working changes from committed code

**Example:**
```python
await search_working_tree(
    repo_id="uuid",
    query="authentication logic",
    file_path_filter="src/auth/%"
)
```

#### `search_all_states(repo_id, query, top_k=10, include_working_tree=True, include_committed=True, file_path_filter=None)`
Search both working tree and committed chunks.

**When to use:**
- See both states in one query
- Compare current vs committed implementations
- Get comprehensive search results

**Example:**
```python
# Search both states
await search_all_states(
    repo_id="uuid",
    query="database connection",
    include_working_tree=True,
    include_committed=True
)

# Only search committed code
await search_all_states(
    repo_id="uuid",
    query="api routes",
    include_working_tree=False,
    include_committed=True
)
```

## Workflow

### After Editing Files
1. Edit file(s)
2. `reindex_file()` or `reindex_working_tree()`
3. `search_working_tree()` to find your changes

### Before Committing
1. `working_tree_stats()` to verify index
2. `search_all_states()` to see full picture
3. `commit_with_review()` to commit

### After Pulling Changes
1. `git pull`
2. `reindex_working_tree()` to update index
3. Continue searching

## Status States

| Status | Meaning |
|--------|---------|
| `reindexed` | File was re-indexed successfully |
| `unchanged` | File unchanged since last index |
| `skipped` | File not watched or too large |

## Configuration

Reindex settings in `.archon/config.toml`:

```toml
[watcher]
enabled = true
debounce_ms = 500
max_file_size_kb = 512
```

## Troubleshooting

- **No results from search_working_tree()**: Run `reindex_working_tree()` first
- **Status is "skipped"**: File may be too large or not in watched extensions
- **Embeddings missing**: Check embedding service is running (Ollama)
