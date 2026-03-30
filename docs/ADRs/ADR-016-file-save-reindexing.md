# ADR-016: File-Save Triggered Re-indexing

## Status: Proposed

## Date: 2026-03-25

## Authors: zebastjan

---

## Context

The current knowledge base is updated **on commit**. This creates a significant
mid-session staleness problem:

- Agent modifies `services/git_service.py` and `docs/ADRs/015-...md`
- No commit has been made yet
- Agent searches `codebase_search_by_semantics("git repository registration")` —
  returns results from the **previous commit**, missing the in-progress changes
- Agent builds on stale context, producing incorrect or redundant work

This is especially painful in Archon's own development workflow, where:
- Sessions may span hours without a formal commit
- `commit_with_review()` is a deliberate, heavyweight gate (as intended)
- The gap between "file saved" and "commit" can be large

### Why Commit-Only Indexing Made Sense Originally

Commits are a natural, clean synchronization point. Indexing on every save would
historically have been too expensive. However:

1. BGE-M3 (ADR-005) supports incremental re-embedding of individual files
2. Blob SHA comparison (ADR-003) makes it cheap to detect what actually changed
3. Modern NVMe I/O makes file-watching practical at low overhead
4. The alternative (agents working from stale context) has real cost in wasted work

---

## Decision

Implement a **file-save watcher** that triggers lightweight re-indexing of
individual files when they are modified in the working tree, without requiring
a commit.

### Architecture

```
File modified (editor save)
        ↓
FileWatcherService (inotify / watchdog)
        ↓
Blob SHA comparison — same as last index? → skip
        ↓
Re-chunk + Re-embed (single file only)
        ↓
archon_chunks / archon_embeddings updated
        ↓
Record tagged: source = "working_tree", commit_sha = null
```

### Working Tree vs Committed State

Chunks have a `source` field to distinguish indexing origin:

| source | commit_sha | Meaning |
|--------|-----------|---------|
| `committed` | abc1234 | Indexed from a commit |
| `working_tree` | null | Indexed from current unsaved/uncommitted state |

On commit, all `working_tree` chunks for the committed files are **replaced** by
`committed` chunks. The working tree entries are ephemeral.

Search tools include working-tree chunks by default (they represent the most
current state). Historical search (`codebase_search_at_commit`) ignores them.

### FileWatcherService

```python
class FileWatcherService:
    """
    Watches working tree for file changes and triggers incremental re-indexing.
    Runs as a background async task within the MCP server process.
    """

    WATCH_EXTENSIONS = {
        ".py", ".ts", ".go", ".rs",         # code
        ".md", ".rst", ".org", ".norg",     # docs
        ".sql", ".yaml", ".toml", ".json",  # config
    }

    IGNORE_PATTERNS = [
        ".git/", "__pycache__/", "node_modules/",
        ".archon/", "dist/", "build/", "*.pyc"
    ]

    async def on_file_changed(self, filepath: str) -> IndexResult:
        """
        Called when a watched file is saved.
        1. Compare blob SHA with last indexed SHA
        2. If changed: re-chunk, re-embed, update DB
        3. If unchanged: no-op
        """
```

### MCP Tool: `reindex_file`

For cases where the watcher is unavailable or an explicit re-index is preferred:

```python
@mcp.tool()
async def reindex_file(
    repo_id: str,
    filepath: str
) -> dict:
    """
    Manually trigger re-indexing of a specific file.

    Use when:
    - File watcher is not running
    - You want to force re-index after bulk edits
    - You need to confirm current state is indexed before a search

    Args:
        repo_id: Repository UUID
        filepath: Path relative to repo root

    Returns:
        {
          "status": "reindexed" | "unchanged" | "skipped",
          "chunks_updated": int,
          "embedding_ms": int
        }
    """
```

### MCP Tool: `reindex_working_tree`

For broader re-sync without committing:

```python
@mcp.tool()
async def reindex_working_tree(
    repo_id: str,
    paths: list[str] = None  # None = all modified files
) -> dict:
    """
    Re-index all modified files in the working tree.

    Compares current file state against last indexed SHA.
    Only re-embeds files that have actually changed.

    Returns summary of what was updated.
    """
```

### Watcher Lifecycle

- Watcher starts automatically when MCP server starts
- Watcher scope: current worktree only (respects ADR-014 worktree isolation)
- Watcher pauses during `commit_with_review()` execution (avoid race conditions)
- Watcher writes activity to `.archon/hooks/watcher.log` (rolling, max 1MB)

### Configuration

```toml
# .archon/config.toml
[watcher]
enabled = true           # default: true
debounce_ms = 500        # wait 500ms after last save before re-indexing
max_file_size_kb = 512   # skip files larger than 512KB
watch_extensions = []    # empty = use defaults; override to add/remove
```

---

## Implementation Checklist

- [ ] Add `source` and nullable `commit_sha` fields to `archon_chunks` table
- [ ] Implement `FileWatcherService` using `watchdog` library
- [ ] Add watcher startup to MCP server initialization
- [ ] Implement `reindex_file()` MCP tool
- [ ] Implement `reindex_working_tree()` MCP tool
- [ ] Update search query to include working_tree chunks by default
- [ ] Ensure `codebase_search_at_commit()` excludes working_tree chunks
- [ ] On commit: replace working_tree chunks with committed chunks for affected files
- [ ] Add `.archon/config.toml` watcher configuration support
- [ ] Add watcher pause/resume around `commit_with_review()`
- [ ] Write tests: file save → chunk updated in DB
- [ ] Write tests: unchanged file save → no-op
- [ ] Write tests: commit → working_tree chunks replaced by committed chunks
- [ ] Write tests: `reindex_working_tree()` detects all modified files

---

## Consequences

### Positive

- Agent searches reflect current working state, not last commit
- Eliminates a significant class of "working from stale context" errors
- `reindex_file()` tool gives agent explicit control when needed
- Working-tree indexing is clearly tagged — no confusion about committed state

### Negative

- Background watcher adds a persistent process and I/O overhead
- Race conditions possible between watcher and agent edits (mitigated by debounce)
- Working-tree chunks are not permanent — must not be relied on for history
- Watcher may miss saves from tools that write atomically (mitigated by polling fallback)

---

## Alternatives Considered

1. **Index on every file write** (no debounce) — Too expensive; rapid successive saves
   would flood the embedding queue
2. **Periodic polling only** (no inotify) — Higher latency, less responsive; file
   changes may be missed for minutes
3. **Manual `reindex_file()` only** (no watcher) — Requires agent discipline;
   easy to forget; doesn't solve the problem automatically
4. **Commit more frequently** — Fights against `commit_with_review()` as a
   deliberate gate; commits should be meaningful

**Selected**: Automatic watcher with debounce + manual MCP tool fallback

---

## Related Decisions

- ADR-003: Git-Aware Knowledge Base (blob SHA comparison reused here)
- ADR-005: Code Intelligence with BGE-M3 (embedding model used for re-indexing)
- ADR-009: Commit Automation Pipeline (watcher pauses during commit review)
- ADR-014: Worktree Branch Discipline (watcher scope = current worktree only)
- ADR-015: Documentation as First-Class Knowledge (docs re-indexed on save too)
