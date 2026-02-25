# ADR-003: Git-Aware Knowledge Base Architecture

**Status**: Accepted
**Date**: 2025-02-25
**Authors**: Claude Code, zebastjan

## Context

Archon is transitioning to a local-first, Git-centric architecture where Git becomes the primary source of truth for projects and code. The current knowledge base system indexes documents and web pages but lacks awareness of Git repositories, commits, and branches.

### Problems with Current Approach

1. **No Version Awareness**: Knowledge base doesn't track which version of code documentation belongs to
2. **Branch Blindness**: Can't search for content specific to a branch or commit
3. **No History**: Unable to query "what did the docs say at commit X?"
4. **Monorepo Challenges**: Can't filter by path patterns within large repositories
5. **Git as External**: Git is treated as just another file source rather than the canonical source of truth

### Requirements

1. Git must be the canonical source of truth for code, not the database
2. Database should be a queryable mirror of Git history
3. Agents must be able to query knowledge base consistent with current branch/commit
4. Support for walking Git history and reasoning across branches
5. Maintain separate embeddings/chunks for different commits/branches
6. Efficient incremental re-indexing (skip unchanged files)

## Decision

We will implement a Git-Aware Knowledge Base that treats Git as the primary source of truth and creates a database mirror keyed to Git commits.

### Architecture Overview

**Three-Layer Design**:
1. **Git Layer**: GitRepositoryService for repository operations
2. **Database Mirror**: Git metadata tables linked to existing pipeline
3. **Query Layer**: Git-aware search with commit/branch filtering

### Core Tables

**`archon_git_repositories`**:
- Stores repository metadata (path, URL, default branch)
- Tracks crawl status and configuration
- JSONB config for path filters and indexing policy

**`archon_git_commits`**:
- Append-only commit history
- Links to parent commits for graph traversal
- Tracks branches and tags

**`archon_git_files`**:
- File-level tracking per commit
- Uses git blob SHA for content-addressing
- Detects language and tracks deletion

**Integration with Existing Pipeline**:
- `archon_document_blobs` gains git_file_id, git_commit_id references
- `archon_sources` gains repo_id reference
- Existing chunking/embedding pipeline reused

### Phase 1 Implementation (Completed)

**Database Schema**:
- Migration 017: Core git tables with indexes and RLS
- Migration 018: Link git tables to existing pipeline

**GitRepositoryService**:
- Repository registration and validation
- Commit syncing from git log
- File tree navigation at specific commits
- File content retrieval via git
- Language detection (40+ languages)
- Binary file filtering (60+ text extensions, 40+ binary extensions)

**Testing**:
- 16 unit tests covering all core functionality
- Language detection and binary filtering
- Repository validation and error handling

### Phase 2 Roadmap (Next Steps)

1. **Git-Aware Crawling**: Index repositories through pipeline orchestrator
2. **File Chunking API**: Route to appropriate chunker based on language
3. **Git-Aware Search**: Extend RAG service with GitSearchContext
4. **API Endpoints**: REST API for git operations
5. **Frontend Integration**: UI for repository management

### Key Design Decisions

#### 1. Indexing Scope: Full History Schema, Selective Implementation

**Decision**: Schema designed for full history, implementation starts conservative

**Rationale**:
- Phase 1: Index only branch heads (main, develop, etc.)
- Schema supports full history without shortcuts
- Phase 2: Add selective history indexing (last N commits, time windows, marked ranges)
- Configurable policies: heads_only, recent_only, full_history

**Why Full History Matters**:
- Time-travel RAG: "What did the docs say at commit X?"
- Impact analysis: "Show chunks changed between commit A and B"
- Knowledge graph over time
- Regression analysis

#### 2. Monorepo Handling: Fine-Grained Path Control

**Three-Level Filtering**:

**Level 1**: Repo on/off toggle (`enabled` flag)

**Level 2**: Path filters (primary control)
```json
{
  "include_globs": ["src/backend/**/*.py", "docs/**/*.md"],
  "exclude_globs": ["**/node_modules/**", "**/dist/**", "**/__pycache__/**"]
}
```

**Level 3**: Language filters (optional)
```json
{
  "languages": ["python", "typescript", "markdown"]
}
```

**Rationale**:
- Glob patterns provide precise control
- Default exclude patterns for common junk
- Early filtering in file tree walk (before loading content)
- Stored in JSONB config column for flexibility

#### 3. Chunking Strategy: Profile-Based API

**Decision**: Git layer calls generic `chunk_file()` API, doesn't know which chunker is used

**Interface**:
```python
async def chunk_file(
    repo_id: UUID,
    file_path: str,
    content: str,
    language: str | None,
    commit_sha: str
) -> list[ChunkResult]
```

**Routing Logic**:
- Code files → CodeAwareChunker
- Markdown/docs → MarkdownAwareChunker
- Other text → BasicChunker fallback

**Rationale**:
- No hardcoded chunking strategies in git layer
- Future-proof: swap in better chunkers (Docling, AST-based)
- Integrates with improved chunking work

#### 4. Binary Files: Skip in Git Layer

**Decision**: Skip binary files by extension detection, delegate complex docs to separate pipeline

**Git Layer Behavior**:
- Extension-based filtering (BINARY_EXTENSIONS, TEXT_EXTENSIONS)
- Heuristic for unknown extensions (check for null bytes)
- Only text-like files sent to chunking

**Separate Pipeline for Complex Docs**:
- PDFs, Word docs, images → Docling pipeline
- OCR for images → Separate doc ingestion
- Same `archon_chunks` table, different path

**Rationale**:
- Keep git integration simple
- Delegate complex document processing
- Binary detection is fast and reliable

## Consequences

### Positive

1. **Git as Source of Truth**: Database becomes a queryable mirror, not the authority
2. **Version Awareness**: Search results can be filtered by commit/branch
3. **Time Travel**: Query historical state of documentation
4. **Incremental Updates**: Only re-index changed files
5. **Monorepo Support**: Fine-grained path filtering
6. **Language Awareness**: Automatic detection and appropriate chunking
7. **Extensible**: Schema supports full history without refactoring

### Negative

1. **Storage Growth**: Full history indexing multiplies storage needs
2. **Complexity**: More tables and relationships to maintain
3. **Initial Indexing**: Branch heads still require full scan
4. **Git Dependency**: System requires git binary and GitPython

### Mitigations

1. **Selective Indexing**: Start with heads_only, add history on-demand
2. **Incremental Re-indexing**: Skip unchanged files via blob SHA comparison
3. **JSONB Config**: Flexible path filtering reduces junk indexing
4. **Binary Filtering**: Early rejection of non-indexable files

## Implementation Status

### Completed (Phase 1)

- [x] Database migrations (017, 018)
- [x] GitRepositoryService core methods
- [x] Language detection (40+ languages)
- [x] Binary file filtering
- [x] Unit tests (16 tests, all passing)
- [x] Exception handling and error serialization
- [x] Code quality (Ruff, MyPy, type hints)

### Next Steps (Phase 2)

- [ ] Git-aware crawling service
- [ ] File chunker routing API
- [ ] Integration with pipeline orchestrator
- [ ] Git-aware search (GitSearchContext)
- [ ] REST API endpoints
- [ ] Frontend UI for repository management

### Future Enhancements (Phase 3+)

- [ ] Incremental re-indexing (compare blob SHAs)
- [ ] IPFS integration for large artifacts
- [ ] Multi-repository search
- [ ] AST-aware chunking (tree-sitter)
- [ ] Git submodule support
- [ ] Background git watcher service

## Related Documents

- Implementation Plan: `/home/zebastjan/.claude/projects/-home-zebastjan-dev-archon/d29e78f3-939c-4f20-bb3d-a62fad3aa343.jsonl`
- Migration 017: `migration/0.1.0/017_add_git_tables.sql`
- Migration 018: `migration/0.1.0/018_link_git_to_blobs.sql`
- Git Service: `python/src/server/services/git/git_repository_service.py`
- Tests: `python/tests/services/git_service/test_git_repository_service.py`

## References

- SovereignPath Architecture Direction (user requirements)
- Existing chunking API: `python/src/server/services/chunking/`
- Pipeline tables: `migration/0.1.0/014_add_pipeline_tables.sql`
