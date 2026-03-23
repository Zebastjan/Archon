# Knowledge Graph Architecture - TODO

**Status**: PLANNING
**Created**: 2026-03-22
**Priority**: HIGH

---

## The Problem

We want to build a knowledge graph that enables:
1. **Semantic search** - Find code by meaning, not just name
2. **Cross-commit reasoning** - Understand how code evolved
3. **Branch awareness** - Compare differences between branches
4. **Code summarization** - AI-generated descriptions
5. **Relationship traversal** - Find callers, callees, dependencies

**Current State**:
- ✅ 3,893 code entities extracted (Python, TypeScript, Nim)
- ✅ Relationships tracked (DEFINES, CALLS, INHERITS)
- ❌ No vector embeddings yet
- ❌ No summaries
- ❌ Schema not designed for cross-commit reasoning
- ❌ Documentation not indexed

---

## Decision 1: PostgreSQL vs Graph Database

### Current: PostgreSQL with pgvector

**Pros:**
- Already in use (no new infrastructure)
- pgvector for semantic search
- ACID transactions
- SQL flexibility
- Good for hybrid queries (vectors + structured data)

**Cons:**
- Relationship traversal is slow (JOINs across multiple tables)
- No native graph algorithms (PageRank, shortest path, etc.)
- Complex queries for "find all functions that call X, which calls Y"

### Alternative: Neo4j

**Pros:**
- Native graph storage and traversal
- Cypher query language (expressive for relationships)
- Built-in graph algorithms
- Excellent for "find paths between entities"
- AuraDB free tier available

**Cons:**
- Separate infrastructure
- No vector search natively (need to combine with vector DB)
- Learning curve for Cypher
- Synchronization complexity

### Recommendation: **Hybrid Approach**

Keep PostgreSQL + pgvector for:
- Semantic search (embeddings)
- Entity storage
- Full-text search
- Structured queries

Use PostgreSQL's built-in graph capabilities via:
- Recursive CTEs for traversal
- Materialized paths for hierarchy
- Adjacency lists with indexes

**Verdict**: PostgreSQL is sufficient. Neo4j adds complexity without enough benefit for our use case.

---

## Decision 2: Summarization Model

### Actual Model: LFM2-8B (Liquid Foundation Model 2)

**Ollama Model Name**: `kahnwong/lfm2:8b-a1b`

**Specifications**:
| Property | Value |
|----------|-------|
| Parameters | 8.3B total, 1.5B active (MoE) |
| Context Length | **128K tokens** |
| Architecture | LFM2 MoE (mixture-of-experts) |
| Quantization | Q4_0 |
| Size | 4.7 GB |
| Speed | ~2300 tokens/s prompt, ~170 tokens/s generation |

**Why LFM2-8B**:
- ✅ MoE architecture: Only activates 1.5B params per token
- ✅ 128K context (massive, not the 32K mentioned earlier)
- ✅ CPU optimized (2x faster than standard transformers on CPU)
- ✅ Fits in 64GB RAM on CPU
- ✅ Works well on GPU (RTX 3060 tested)

**Context Window Issue Investigation**:
- User mentioned 600 token limit issues
- Model supports 128K context - likely a configuration issue with previous model
- Tested successfully with 2000+ tokens, no issues
- The 1.2B Liquid models may have had different limits

### Implementation Plan

```python
# summarizer.py
class CodeSummarizer:
    def __init__(self, model="kahnwong/lfm2:8b-a1b"):
        self.model = model
        self.client = httpx.AsyncClient(timeout=120.0)
    
    async def summarize_function(self, source_code: str) -> str:
        prompt = f"Summarize this function in one sentence:\n\n{source_code[:2000]}"
        # Call Ollama API
        response = await self.client.post(
            "http://localhost:11434/api/generate",
            json={"model": self.model, "prompt": prompt}
        )
        return response.json()["response"].strip()
    
    async def summarize_batch(self, entities: list) -> list[str]:
        # Process with checkpointing
        pass
```

### Ollama API Usage

```python
import httpx

async def summarize(code: str) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "kahnwong/lfm2:8b-a1b",
                "prompt": f"Summarize in one sentence:\n{code[:2000]}",
                "options": {
                    "temperature": 0.3,  # Low temp for consistent summaries
                    "num_predict": 100,  # Short response
                }
            },
            timeout=60.0
        )
        return response.json()["response"]
```

---

## Schema Migration: Cross-Commit Knowledge Graph

### Current Schema (Insufficient)

```sql
archon_code_entities (
    id UUID,
    repo_id UUID,
    file_path TEXT,
    line_start INT,
    line_end INT,
    entity_type TEXT,
    name TEXT,
    signature TEXT,
    docstring TEXT,  -- Only if exists in source
    source_code TEXT,
    -- embeddings...
    commit_sha TEXT,
    -- MISSING: branch, parent_commit, entity_identity
)
```

### Target Schema

```sql
-- Main entities table
archon_code_entities (
    id UUID PRIMARY KEY,
    repo_id UUID REFERENCES archon_code_repos(id),
    
    -- Identity (for cross-commit tracking)
    entity_identity TEXT NOT NULL,  -- hash(repo_id:file_path:name:type)
    
    -- Location
    file_path TEXT NOT NULL,
    line_start INT NOT NULL,
    line_end INT NOT NULL,
    
    -- Classification
    entity_type TEXT NOT NULL,  -- function, method, class, interface, type, const, var
    language TEXT NOT NULL,
    
    -- Content
    name TEXT NOT NULL,
    signature TEXT,
    docstring TEXT,            -- Original docstring (if any)
    summary TEXT,              -- AI-generated summary (NEW)
    source_code TEXT NOT NULL,
    
    -- Git metadata (NEW)
    commit_sha TEXT NOT NULL,
    branch_name TEXT,           -- Which branch
    parent_commit_sha TEXT,     -- For history traversal
    change_type TEXT,          -- 'added', 'modified', 'deleted'
    
    -- Embeddings
    embedding_1024 VECTOR(1024),
    embedding_model TEXT,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT entity_identity_idx UNIQUE (repo_id, commit_sha, file_path, name, entity_type)
)

-- Index for cross-commit queries
CREATE INDEX idx_entity_identity ON archon_code_entities(entity_identity);
CREATE INDEX idx_commit ON archon_code_entities(repo_id, commit_sha);
CREATE INDEX idx_branch ON archon_code_entities(repo_id, branch_name);
CREATE INDEX idx_file ON archon_code_entities(repo_id, file_path);
```

### Migration Script

```sql
-- Add new columns
ALTER TABLE archon_code_entities 
    ADD COLUMN IF NOT EXISTS entity_identity TEXT,
    ADD COLUMN IF NOT EXISTS branch_name TEXT,
    ADD COLUMN IF NOT EXISTS parent_commit_sha TEXT,
    ADD COLUMN IF NOT EXISTS change_type TEXT,
    ADD COLUMN IF NOT EXISTS summary TEXT;

-- Backfill entity_identity
UPDATE archon_code_entities 
SET entity_identity = md5(repo_id::text || file_path || name || entity_type)
WHERE entity_identity IS NULL;

-- Set entity_identity as NOT NULL (after backfill)
ALTER TABLE archon_code_entities 
ALTER COLUMN entity_identity SET NOT NULL;
```

---

## Relationship Types (Expanded)

### Current (3 types)
- DEFINES
- CALLS
- INHERITS

### Target (10 types)
- DEFINES (entity provides this name)
- CALLS (function calls another)
- INHERITS (class inherits from class)
- IMPLEMENTS (class implements interface)
- USES (imports/requires/depends on)
- ANNOTATES (decorator/macro applied)
- RETURNS (returns type)
- ACCEPTS (parameter types)
- DECORATES (decorator on function)
- CONTAINS (file contains entity)

---

## Processing Pipeline

### Stage 1: Extraction
```
Git Commit → Tree-sitter → Code Entities → Database
```

### Stage 2: Embedding (BGE-M3)
```
Entities → Batch → Ollama BGE-M3 → 1024-dim vectors → Database
```

### Stage 3: Summarization (Liquid 8B)
```
Entities → Batch → Ollama Liquid 8B → Summaries → Database
```

### Stage 4: Relationships
```
Source Code → AST Analysis → Relationship Extraction → Database
```

---

## VRAM Management Strategy

**Problem**: Like BGE-M3, Liquid 8B will crash Wayland if not managed.

**Solution**: Unified VRAM Manager

```python
class VRAMManager:
    """Shared VRAM manager for all GPU tasks."""
    
    RESERVED_VRAM_GB = 3.0  # Always keep 3GB for system
    
    def __init__(self):
        self.tasks = []  # Queued tasks
        self.active_task = None
        
    def can_run(self, required_vram_gb: float) -> bool:
        """Check if we have enough VRAM."""
        free = self.get_free_vram()
        return free >= required_vram_gb + self.RESERVED_VRAM_GB
    
    def acquire(self, task_name: str, required_vram_gb: float):
        """Acquire VRAM for a task."""
        while not self.can_run(required_vram_gb):
            time.sleep(10)  # Wait, check periodically
            self.check_wayland()  # Graceful degradation
            
    def release(self):
        """Release VRAM after task."""
        # Clear GPU cache
        # Reset model state
```

---

## TODO List

### P0: Critical (Must Have)

- [ ] **BGE-M3 Embedding Worker**
  - VRAM-safe single-worker mode
  - Checkpointing every 100 entities
  - Resume on interrupt
  - Run on existing 3,893 entities

- [ ] **Schema Migration**
  - Add entity_identity column
  - Add branch_name, parent_sha, change_type
  - Add summary column
  - Create indexes

- [ ] **LFM2-8B Summarization Worker**
  - Model: `kahnwong/lfm2:8b-a1b` (4.7GB)
  - 128K context window (no 600 token limit!)
  - Batch processing with checkpoints
  - Generate summaries for all 3,893 entities
  - Can run on CPU (64GB RAM) or GPU (RTX 3060)

### P1: Important (Should Have)

- [ ] **Documentation Indexing**
  - Index .md, .rst, .txt files
  - Treat as "documents" not "entities"
  - Separate embedding space

- [ ] **Relationship Expansion**
  - Add IMPLEMENTS, USES, ANNOTATES
  - Fill in missing relationship types

- [ ] **Branch Tracking**
  - Extract branch from git context
  - Track which branch each entity came from

### P2: Nice to Have

- [ ] **Commit History**
  - Store parent_commit_sha
  - Enable "how did this change" queries

- [ ] **Change Type Tracking**
  - Detect added/modified/deleted
  - Visual diff highlighting

- [ ] **AI-Powered Code Review**
  - Use summaries for PR descriptions
  - Detect breaking changes

---

## Open Questions (ANSWERED)

1. ~~**Liquid 8B exact model name**: What Ollama model name for Liquid 8B?~~
   - ✅ **Answer**: `kahnwong/lfm2:8b-a1b` (LFM2-8B-A1B by Liquid AI)
   - 8.3B total params, 1.5B active (MoE)
   - 128K context window!

2. **Summary length**: 1 sentence? 2 sentences? Paragraph?
   - Recommendation: 1-2 sentences for functions, 2-3 for classes/modules

3. **Summary language**: Same as code? Always English?
   - Recommendation: English summaries for all code

4. **Incremental updates**: How to handle new commits without re-indexing everything?
   - Use entity_identity to detect changed/new entities
   - Only process changed files

---

## Estimated Work

| Task | Complexity | Time |
|------|-----------|------|
| BGE-M3 Worker | Medium | 2-4 hours |
| Schema Migration | Medium | 2-3 hours |
| LFM2-8B Worker | Medium | 2-3 hours |
| Documentation Indexing | Low | 1-2 hours |
| Relationship Expansion | Medium | 3-4 hours |

**Total**: ~10-16 hours

---

## Next Steps

1. ⏳ Get BGE-M3 embeddings working (blocking everything else)
2. ⏳ Run schema migration on existing data
3. ⏳ Test LFM2-8B summarization (works great!)
4. ⏳ Add documentation indexing
5. ⏳ Expand relationships

---

## Testing Results (2026-03-22)

### LFM2-8B Tests
- ✅ 128K context window verified
- ✅ Code summarization works (tested with Python function)
- ✅ ~2300 tokens/s prompt processing
- ✅ ~170 tokens/s generation
- ✅ 4.7GB model size (Q4_0)
- ✅ Works on GPU (RTX 3060)
- ✅ Works on CPU (tested with OLLAMA_CUDA=0)

