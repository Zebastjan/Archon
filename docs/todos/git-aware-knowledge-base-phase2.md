# Git-Aware Knowledge Base - Phase 2 TODO

**Status**: Ready to Start
**Priority**: High
**Owner**: TBD
**Started**: Not started
**Estimated Effort**: 3-5 days

## Overview

Complete Phase 2 of Git-Aware Knowledge Base implementation, which adds git repository crawling, indexing, and search capabilities to Archon.

## Context

Phase 1 (✅ Completed) created the foundation:
- Database schema with git tables
- GitRepositoryService for repository operations
- Language detection and binary filtering
- 16 passing unit tests

Phase 2 will integrate git repositories into the knowledge base pipeline and enable git-aware search.

## Tasks

### 1. Create Git-Aware Crawling Service

**File**: `python/src/server/services/crawling/git_crawling_service.py`

**Responsibilities**:
- Index git repositories at specific commits
- Walk file tree using GitRepositoryService
- Filter files by patterns and language
- Create archon_git_files records
- Create archon_document_blobs with source_type='git'
- Queue files for chunking and embedding

**Key Methods**:
```python
async def crawl_repository(
    repo_id: UUID,
    commit_sha: str,
    file_patterns: list[str] = ["*.py", "*.js", "*.md"],
    chunking_strategy: str = "code_aware",
) -> dict
```

**Integration Points**:
- Use GitRepositoryService.get_file_tree()
- Use GitRepositoryService.get_file_content()
- Create document_blobs with git metadata
- Call file_chunker.chunk_file()

**Testing**:
- Unit tests with mock git repository
- Integration test with real test repo
- Test path filtering
- Test language detection integration

**Estimated Effort**: 1 day

---

### 2. Create File Chunker Routing API

**File**: `python/src/server/services/chunking/file_chunker.py`

**Responsibilities**:
- Route to appropriate chunker based on language/extension
- Enrich chunks with git metadata
- Return ChunkResult with standardized format

**Strategy Selection**:
- `.py`, `.js`, `.ts`, `.java`, `.go` → CodeAwareChunker
- `.md`, `.rst`, `.txt` → MarkdownAwareChunker
- `.json`, `.yaml` → BasicChunker (preserve structure)
- Default → TokenAwareChunker

**Key Method**:
```python
async def chunk_file(
    file_path: str,
    content: str,
    language: str | None = None,
    repo_id: UUID | None = None,
    commit_sha: str | None = None,
    **options
) -> list[ChunkResult]
```

**Git Metadata Enrichment**:
```python
for chunk in chunks:
    if chunk.metadata is None:
        chunk.metadata = {}
    chunk.metadata["repo_id"] = str(repo_id) if repo_id else None
    chunk.metadata["commit_sha"] = commit_sha
    chunk.metadata["file_path"] = file_path
    chunk.metadata["language"] = language
```

**Testing**:
- Test routing for each file type
- Test metadata enrichment
- Test chunker integration

**Estimated Effort**: 0.5 days

---

### 3. Extend Pipeline Orchestrator for Git

**File**: `python/src/server/services/ingestion/pipeline_orchestrator.py`

**Changes**:
- Add `source_type='git'` handling in run_pipeline()
- Pass git metadata through to blob creation
- Support git_file_id, commit_id in blobs
- Reuse existing chunking/embedding pipeline

**New Flow**:
```
1. Detect source_type='git'
2. Call GitCrawlingService.crawl_repository()
3. For each file:
   a. Create archon_git_files record
   b. Create archon_document_blobs (source_type='git')
   c. Call file_chunker.chunk_file()
   d. Store chunks with git metadata
   e. Queue embedding jobs
```

**Testing**:
- Integration test: index test repository
- Verify git metadata propagates to chunks
- Test error handling
- Test status updates

**Estimated Effort**: 1 day

---

### 4. Add Git-Aware Search

**File**: `python/src/server/services/search/rag_service.py`

**Create GitSearchContext**:
```python
@dataclass
class GitSearchContext:
    repo_id: UUID | None = None
    commit_sha: str | None = None
    branch_name: str | None = None
    file_path_filter: str | None = None  # e.g., "src/server/**/*.py"
    language_filter: str | None = None
```

**Extend search_knowledge_base()**:
```python
async def search_knowledge_base(
    query: str,
    git_context: GitSearchContext | None = None,
    ...
) -> list[SearchResult]
```

**Query Changes**:
- Join with archon_git_files when git_context provided
- Filter by commit_sha if specified
- Filter by branch_name if specified
- Apply path patterns using file_path LIKE
- Filter by language if specified

**Testing**:
- Test search with git context
- Test search without git context (backward compat)
- Test path filtering
- Test language filtering

**Estimated Effort**: 1 day

---

### 5. Create Git API Endpoints

**File**: `python/src/server/api_routes/git_api.py`

**Endpoints to Create**:

**Repository Management**:
- `POST /api/git/repositories` - Register repository
- `GET /api/git/repositories` - List repositories
- `GET /api/git/repositories/{id}` - Get repository details
- `DELETE /api/git/repositories/{id}` - Remove repository

**Commit History**:
- `GET /api/git/repositories/{id}/commits` - List commits
- `GET /api/git/repositories/{id}/branches/{branch}/commits` - Branch-specific
- `POST /api/git/repositories/{id}/sync` - Sync git commits to DB

**File Browsing**:
- `GET /api/git/repositories/{id}/commits/{sha}/files` - File tree at commit
- `GET /api/git/repositories/{id}/commits/{sha}/files/{path}` - File content

**Indexing**:
- `POST /api/git/repositories/{id}/index` - Index repository at current HEAD
- `POST /api/git/repositories/{id}/commits/{sha}/index` - Index specific commit

**Git-Aware Search**:
- Extend `POST /api/knowledge/search` with query params:
  - `?repo_id={id}`
  - `&commit_sha={sha}`
  - `&branch_name={branch}`
  - `&file_path_filter={pattern}`
  - `&language_filter={lang}`

**Testing**:
- Integration tests for each endpoint
- Test authentication
- Test error responses

**Estimated Effort**: 1 day

---

### 6. Create Frontend Git Feature

**Directory**: `archon-ui-main/src/features/git/`

**Components to Create**:
- `GitRepositoryList.tsx` - Show registered repos
- `GitBranchSelector.tsx` - Choose branch for search context
- `GitCommitHistory.tsx` - Browse commit history
- `GitFileTree.tsx` - Browse files at specific commit
- `GitSearchContext.tsx` - Display git context in search results

**Services**:
- `gitService.ts` - API calls to git endpoints
- `useGitQueries.ts` - TanStack Query hooks

**Extend Knowledge Search**:
- Add git context selector to search UI
- Show file path, branch, commit SHA in results
- Link to git file viewer (GitHub URL or local path)

**Testing**:
- Component tests with React Testing Library
- Integration tests with MSW mocks
- Test git context filtering

**Estimated Effort**: 2 days

---

## Success Criteria

### Must Have

- [ ] Register git repositories via API
- [ ] Sync git commits to archon_git_commits table
- [ ] Index files at branch HEAD
- [ ] Link chunks to git files via foreign keys
- [ ] Search with git context filtering (repo_id, commit_sha)
- [ ] Path/language filters working for monorepos
- [ ] UI to register and browse repositories
- [ ] All integration tests passing

### Can Defer to Phase 3

- Historical commit indexing (beyond HEAD)
- Incremental re-indexing (skip unchanged files)
- Git submodule support
- AST-based chunking
- IPFS integration
- Background git watcher service

## Dependencies

- ✅ Phase 1 completed (migrations, GitRepositoryService)
- ✅ Existing chunking API in place
- ✅ Pipeline orchestrator extensible
- ✅ RAG service extensible

## Risks & Mitigations

**Risk**: Large repositories take too long to index
**Mitigation**: Implement path filtering early, skip node_modules by default

**Risk**: Binary files accidentally indexed
**Mitigation**: Binary detection already implemented in GitRepositoryService

**Risk**: Git operations block async pipeline
**Mitigation**: Use ThreadPoolExecutor for git operations if needed

**Risk**: Full history indexing multiplies storage
**Mitigation**: Phase 2 only indexes branch heads, full history deferred

## Testing Strategy

### Unit Tests
- Test each new service method
- Mock git operations
- Test git metadata propagation

### Integration Tests
- Create test git repository
- Index via API
- Search with git context
- Verify end-to-end flow

### Manual Testing
- Register real git repository (Archon itself)
- Index multiple branches
- Search across commits
- Browse file tree

## Documentation Updates

- [ ] Update API documentation with git endpoints
- [ ] Add git usage guide to user docs
- [ ] Update MCP tools to expose git operations
- [ ] Create video demo of git-aware search

## Related ADRs

- ADR-003: Git-Aware Knowledge Base Architecture

## References

- GitRepositoryService: `python/src/server/services/git/git_repository_service.py`
- Existing chunkers: `python/src/server/services/chunking/chunkers/`
- Pipeline orchestrator: `python/src/server/services/ingestion/pipeline_orchestrator.py`
- RAG service: `python/src/server/services/search/rag_service.py`
