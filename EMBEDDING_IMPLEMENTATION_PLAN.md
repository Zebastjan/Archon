# Code Intelligence Implementation Plan

## Current State (BROKEN)
- 884k entities extracted but **ZERO embeddings**
- 855k relationships tracked but no semantic similarity
- Last sync: March 18 (3+ days stale)
- No automatic re-indexing on git commits

## Phase 1: Fix Embeddings (CRITICAL)

### 1.1 Verify Ollama Setup
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Pull embedding model if not present
ollama pull bge-large
```

### 1.2 Create Embedding Pipeline
- Process entities in batches (100-500 at a time)
- Generate 1024-dim embeddings using bge-large
- Store in `embedding_1024` column
- Handle rate limiting and retries

### 1.3 Backfill All Repositories
Priority order:
1. archon (358k entities) - Most important
2. syllablaze (279k entities)  
3. archon-ui (163k entities)
4. octofriend (84k entities)
5. Omnibus (111 entities)

Estimated time: 2-4 hours for all repos

## Phase 2: AI-Powered Summaries

### 2.1 Generate Code Summaries
For each function/class without docstring:
- Send source code to LLM (Ollama/local)
- Generate 1-2 sentence description
- Store in `docstring` column

### 2.2 High-Level Module Summaries
- Generate per-file summaries
- Generate per-directory summaries
- Build hierarchical understanding

## Phase 3: Git Integration

### 3.1 Git Hooks
Install in each repo:
- `post-commit`: Queue incremental sync
- `post-checkout`: Update worktree context
- `post-merge`: Full re-sync on merge

### 3.2 Watchdog Service
- Monitor file changes in tracked repos
- Debounce and batch updates
- Incremental indexing (only changed files)

### 3.3 Branch-Aware Indexing
- Each branch gets its own entity snapshot
- Commit SHA tracked per entity
- Diff-based updates

## Phase 4: Verification & Monitoring

### 4.1 Health Checks
- Daily embedding completeness check
- Relationship integrity validation
- Orphaned entity cleanup

### 4.2 Performance Optimization
- Query performance monitoring
- Index optimization
- Caching layer for common queries

## Implementation Status

| Component | Status | Priority |
|-----------|--------|----------|
| Tree-sitter extraction | ✅ Working | - |
| Relationship graph | ✅ Working | - |
| pgvector indexes | ✅ Ready | - |
| Embedding generation | ❌ Missing | P0 |
| AI summaries | ❌ Missing | P1 |
| Git hooks | ❌ Missing | P1 |
| Auto-sync | ❌ Missing | P2 |
| Monitoring | ❌ Missing | P3 |

## Next Steps

1. **IMMEDIATE**: Start Ollama and run embedding backfill
2. **TODAY**: Install git hooks in all repos
3. **THIS WEEK**: Implement AI summary generation
4. **ONGOING**: Set up monitoring and health checks

## Success Metrics

- [ ] 100% of entities have embeddings
- [ ] < 1 hour delay between commit and index update
- [ ] Semantic search returns relevant results
- [ ] Code similarity suggestions work
- [ ] Cross-reference navigation works
