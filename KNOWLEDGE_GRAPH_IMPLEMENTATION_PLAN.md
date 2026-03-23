# Knowledge Graph Architecture - IMPLEMENTATION PLAN

**Status**: PLANNING
**Created**: 2026-03-22
**Last Updated**: 2026-03-22
**Priority**: HIGH

---

## Executive Summary

Build a proper knowledge graph for Archon that enables:
1. **Semantic search** across code and documentation
2. **Cross-commit reasoning** (how code evolved)
3. **Branch awareness** (compare branches)
4. **AI summaries** for all content
5. **Relationship traversal** (callers, dependencies, etc.)

**Current State**: 3,893 code entities from 4 repos (no embeddings, no summaries)
**Target State**: Full knowledge graph with embeddings + AI summaries + cross-commit tracking

---

## Repositories

| Repo | Entities | Language | Status |
|------|----------|---------|--------|
| archon-python | 1,868 | Python | Extracted |
| syllablaze | 1,217 | Python | Extracted |
| octofriend | 600 | TypeScript | Extracted |
| Omnibus | 208 | Nim | Extracted |
| **Total** | **3,893** | | |

---

## Implementation Stages

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         IMPLEMENTATION PIPELINE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  STAGE 0: Environment Setup                                                  │
│  ├─ Add tree-sitter parsers: markdown, norg, nim                           │
│  └─ Verify all parsers work                                                │
│                                                                              │
│  STAGE 1: Fix Entity Extraction                                              │
│  ├─ Add Nim-specific entity types: proc, func, iterator, template, macro   │
│  ├─ Re-index all repos with new types                                       │
│  └─ Database migration for types                                            │
│                                                                              │
│  STAGE 2: Documentation Indexing                                            │
│  ├─ Add markdown parser (tree-sitter)                                        │
│  ├─ Add norg parser (tree-sitter)                                           │
│  ├─ Implement semantic chunking                                              │
│  ├─ Create archon_documents table                                          │
│  └─ Index .md, .norg, .rst files                                           │
│                                                                              │
│  STAGE 3: Schema Migration (BEFORE summaries!)                              │
│  ├─ Add entity_identity for cross-commit tracking                           │
│  ├─ Add summary column                                                     │
│  ├─ Add branch_name, parent_sha, change_type                               │
│  └─ Create indexes                                                          │
│                                                                              │
│  STAGE 4: BGE-M3 Embeddings                                                │
│  ├─ VRAM-safe single-worker mode                                            │
│  ├─ Checkpointing every 100 entities                                        │
│  ├─ Generate embeddings for all entities + documents                        │
│  └─ Use GPU (RTX 3060)                                                     │
│                                                                              │
│  STAGE 5: LFM2-8B Summaries                                                │
│  ├─ CPU mode (64GB RAM) to avoid GPU contention                             │
│  ├─ Dynamic summary length based on content size                            │
│  ├─ Semantic chunking (not arbitrary)                                       │
│  ├─ Skills-based summarization prompts                                       │
│  └─ Generate summaries for all entities + documents                          │
│                                                                              │
│  STAGE 6: Git Integration                                                   │
│  ├─ Track commits on indexing                                               │
│  ├─ Implement change detection (added/modified/deleted)                     │
│  └─ Enable cross-commit queries                                             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Stage 0: Environment Setup

### Install Tree-sitter Parsers

```bash
cd /home/zebastjan/dev/archon/python
source .venv/bin/activate

# Install tree-sitter parsers for additional languages
pip install tree-sitter-markdown
pip install tree-sitter-norg  # If available

# Check what's available
python3 -c "from tree_sitter_languages import languages; print(list(languages.keys()))"
```

### Available Tree-sitter Parsers

| Parser | File Types | Use Case |
|--------|-----------|----------|
| tree-sitter-python | .py | Code extraction ✅ |
| tree-sitter-javascript | .ts, .tsx, .js, .jsx | Code extraction ✅ |
| tree-sitter-nim | .nim, .nims | Code extraction ✅ |
| tree-sitter-markdown | .md | Document chunking |
| tree-sitter-norg | .norg | Document chunking (future) |

---

## Stage 1: Fix Nim Entity Types

### Current Problem

Database constraint only allows:
```
function, method, class, interface, module, variable, constant, import, decorator
```

But Nim has MORE types that matter:
- `proc` - procedure/function
- `func` - functional procedure (no side effects)
- `iterator` - iterator/generator
- `template` - compile-time macro
- `macro` - compile-time transformation
- `type` - type definition

### Solution: Add Nim-Specific Types

**Database Migration:**
```sql
-- Add new entity types for Nim
ALTER TABLE archon_code_entities 
DROP CONSTRAINT archon_code_entities_entity_type_check;

ALTER TABLE archon_code_entities 
ADD CONSTRAINT archon_code_entities_entity_type_check 
CHECK (entity_type IN (
    'function', 'method', 'class', 'interface', 'module',
    'variable', 'constant', 'import', 'decorator',
    -- Nim-specific types
    'proc', 'func', 'iterator', 'template', 'macro', 'type',
    -- Generic fallback
    'unknown'
));
```

**Update nim_support.py:**
```python
# Map Nim AST node types to entity types
ENTITY_TYPE_MAP = {
    "proc_declaration": "proc",
    "func_declaration": "func", 
    "method_declaration": "method",
    "iterator_declaration": "iterator",
    "template_declaration": "template",
    "macro_declaration": "macro",
    "type_declaration": "type",
    "const_declaration": "constant",
    "var_declaration": "variable",
    "import_statement": "import",
}
```

### Re-index

After fixing, re-run the indexer on Omnibus to get proper types.

---

## Stage 2: Documentation Indexing

### Semantic Chunking Strategy

**NOT arbitrary chunking** - use tree-sitter to understand document structure.

**Markdown Structure (via tree-sitter):**
```
document
├── frontmatter (YAML)
├── heading (H1) → Section boundary
├── heading (H2) → Subsection
├── paragraph → Content
├── code_block → Code example
├── list → Bullet points
└── block_quote → Quotation
```

**Chunking Rules:**
1. Split at H1 headings (major sections)
2. Split at H2 headings (subsections)
3. Max chunk size: ~2000 tokens (to fit in summary prompt)
4. Preserve context: include parent headings as metadata

### Document Schema

```sql
CREATE TABLE archon_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repo_id UUID REFERENCES archon_code_repos(id),
    
    -- Location
    file_path TEXT NOT NULL,
    chunk_index INT,  -- Position in file
    
    -- Content
    title TEXT,  -- Extracted from first H1
    content TEXT NOT NULL,  -- The chunk text
    content_type TEXT,  -- 'section', 'code_block', 'list'
    
    -- Classification
    doc_type TEXT,  -- 'readme', 'adr', 'design', 'api', 'guide', 'other'
    language TEXT,  -- For code blocks: 'python', 'nim', etc.
    
    -- Semantic metadata
    heading_path TEXT,  -- "Architecture > Components > Database"
    parent_headings JSONB,  -- [{level: 1, text: "..."}, {level: 2, text: "..."}]
    
    -- AI
    embedding_1024 VECTOR(1024),
    summary TEXT,
    
    -- Git
    commit_sha TEXT,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
);

CREATE INDEX idx_doc_repo ON archon_documents(repo_id);
CREATE INDEX idx_doc_type ON archon_documents(doc_type);
CREATE INDEX idx_doc_embedding ON archon_documents USING ivfflat(embedding_1024 vector_cosine_ops);
```

### Document Type Detection

```python
def detect_doc_type(file_path: str, title: str) -> str:
    """Classify document type from path and title."""
    path_lower = file_path.lower()
    title_lower = title.lower() if title else ""
    
    if "readme" in path_lower or title_lower.startswith("readme"):
        return "readme"
    if "adr" in path_lower or "/adr/" in path_lower:
        return "adr"  # Architecture Decision Record
    if "design" in path_lower or "architecture" in title_lower:
        return "design"
    if "api" in path_lower or "reference" in title_lower:
        return "api"
    if "guide" in path_lower or "tutorial" in path_lower:
        return "guide"
    if "changelog" in path_lower or "history" in title_lower:
        return "changelog"
    return "other"
```

### Indexing Extensions

```
.md  - Markdown (via tree-sitter-markdown)
.norg - Neorg (via tree-sitter-norg) [future]
.rst  - ReStructuredText (via regex or docutils)
.txt  - Plain text (simple split)
.org  - Org-mode (low priority)
```

---

## Stage 3: Schema Migration (BEFORE Summaries!)

This MUST happen before Stage 5 (LFM2-8B) because summaries need a place to go.

### Migration Script

```sql
-- 1. Add entity_identity for cross-commit tracking
ALTER TABLE archon_code_entities 
ADD COLUMN IF NOT EXISTS entity_identity TEXT;

ALTER TABLE archon_code_entities 
ADD COLUMN IF NOT EXISTS branch_name TEXT;

ALTER TABLE archon_code_entities 
ADD COLUMN IF NOT EXISTS parent_commit_sha TEXT;

ALTER TABLE archon_code_entities 
ADD COLUMN IF NOT EXISTS change_type TEXT CHECK (change_type IN ('added', 'modified', 'deleted'));

ALTER TABLE archon_code_entities 
ADD COLUMN IF NOT EXISTS summary TEXT;

-- 2. Backfill entity_identity (hash of unique key)
UPDATE archon_code_entities 
SET entity_identity = md5(
    repo_id::text || file_path || name || entity_type
)
WHERE entity_identity IS NULL;

-- 3. Set NOT NULL after backfill
ALTER TABLE archon_code_entities 
ALTER COLUMN entity_identity SET NOT NULL;

-- 4. Create indexes for cross-commit queries
CREATE INDEX IF NOT EXISTS idx_entity_identity 
ON archon_code_entities(entity_identity);

CREATE INDEX IF NOT EXISTS idx_entity_commit 
ON archon_code_entities(repo_id, commit_sha);

CREATE INDEX IF NOT EXISTS idx_entity_branch 
ON archon_code_entities(repo_id, branch_name);

CREATE INDEX IF NOT EXISTS idx_entity_file 
ON archon_code_entities(repo_id, file_path);
```

---

## Stage 4: BGE-M3 Embeddings

### VRAM Safety

- Reserve 3GB for Wayland/system
- Use only 8-9GB for BGE-M3
- Single-worker mode (one batch at a time)
- Monitor and pause if VRAM drops below 3GB free

### Configuration

```python
EMBEDDING_CONFIG = {
    "model": "bge-m3",
    "batch_size": 20,
    "dimension": 1024,
    "checkpoint_interval": 100,
    "ollama_url": "http://localhost:11434",
}
```

### Process

1. Load entities without embeddings
2. Batch in groups of 20
3. Generate embedding via Ollama API
4. Store in `embedding_1024` column
5. Checkpoint every 100
6. Log progress

---

## Stage 5: LFM2-8B Summaries

### Why CPU Mode?

| Resource | BGE-M3 | LFM2-8B |
|----------|--------|---------|
| **GPU VRAM** | 8GB | 0GB |
| **System RAM** | 0GB | 4.7GB |
| **Priority** | HIGH | LOW |

**Strategy**: GPU for BGE-M3 (higher throughput), CPU for LFM2-8B (avoids contention)

### Configuration

```bash
# Force CPU mode
OLLAMA_CUDA=0
OLLAMA_NUM_PARALLEL=1
OLLAMA_MAX_LOADED_MODELS=1
```

### Semantic Chunking for Summaries

**NOT fixed-size chunks** - use content structure.

**Dynamic Summary Length:**
| Content Size | Summary Length | Example |
|--------------|---------------|---------|
| < 100 tokens | 1 sentence | Simple function |
| 100-500 tokens | 1-2 sentences | Complex function |
| 500-1000 tokens | 2-3 sentences | Class/module |
| 1000-5000 tokens | 3-5 sentences | Large file section |
| > 5000 tokens | Multi-paragraph | Design doc, ADR |

### Skills-Based Summarization

Different prompts for different content types:

```python
SUMMARIZATION_SKILLS = {
    "nim_proc": """You are summarizing Nim code. Focus on:
- What the proc does (main purpose)
- Key parameters and return type
- Side effects (if func vs proc)
Example: "Parses CLI arguments and returns CliOptions object with category, mime_type, and modality fields."

""",
    
    "python_function": """You are summarizing Python code. Focus on:
- What the function accomplishes
- Parameters and return value
- Any exceptions or edge cases
Example: "Extracts code entities from source files using tree-sitter AST parsing and stores results in database."

""",
    
    "typescript_class": """You are summarizing TypeScript/TSX code. Focus on:
- Component purpose or class role
- Props/state if React component
- Key methods and their behavior
Example: "React component for rendering modals with customizable header, body, and footer slots."

""",
    
    "markdown_section": """You are summarizing documentation. Focus on:
- What this section explains
- Key concepts introduced
- Prerequisites or dependencies
Example: "Describes the database schema migration process including adding new tables, indexes, and backfilling existing data."

""",
    
    "adr": """You are summarizing an Architecture Decision Record. Focus on:
- The decision made
- Context/problem it solves
- Consequences (pros/cons)
Example: "Decision to use PostgreSQL with pgvector for knowledge graph - enables semantic search without separate vector DB while maintaining ACID compliance."

""",
    
    "design_doc": """You are summarizing a design document. Focus on:
- System/component being designed
- Key architectural decisions
- Integration points and interfaces
Example: "Architecture for service registry supporting lazy activation with D-Bus IPC for inter-service communication."

""",
}


def build_summary_prompt(content: str, content_type: str, skills: dict) -> str:
    """Build context-aware prompt for summarization."""
    skill = skills.get(content_type, skills.get("default", ""))
    
    return f"""{skill}

Content to summarize:
---
{content}
---

Provide a concise summary following the guidance above.
Summary:"""
```

### Batch Processing

```python
class SummarizationWorker:
    def __init__(self, model="kahnwong/lfm2:8b-a1b"):
        self.model = model
        self.client = httpx.AsyncClient(timeout=120.0)
        self.checkpoint_file = Path.home() / ".archon_summary_checkpoint.json"
    
    def get_summary_length(self, content: str) -> int:
        """Dynamic summary length based on content size."""
        tokens = len(content.split()) * 1.3  # Rough estimate
        
        if tokens < 100:
            return 20  # ~1 sentence
        elif tokens < 500:
            return 50  # 1-2 sentences
        elif tokens < 1000:
            return 100  # 2-3 sentences
        elif tokens < 5000:
            return 200  # 3-5 sentences
        else:
            return 400  # Multi-paragraph
    
    async def summarize(self, content: str, content_type: str) -> str:
        prompt = build_summary_prompt(content, content_type, SUMMARIZATION_SKILLS)
        max_tokens = self.get_summary_length(content)
        
        response = await self.client.post(
            "http://localhost:11434/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "options": {
                    "temperature": 0.3,
                    "num_predict": max_tokens,
                }
            }
        )
        return response.json()["response"].strip()
```

### Checkpointing

```python
CHECKPOINT_INTERVAL = 100  # Save every 100 summaries

# Checkpoint format
{
    "processed": 1234,
    "last_id": "uuid-of-last-entity",
    "timestamp": "2026-03-22T...",
    "model": "kahnwong/lfm2:8b-a1b",
}
```

---

## Stage 6: Git Integration

### On Re-Indexing

```python
async def get_git_context(repo_path: str) -> dict:
    """Get current git commit and branch info."""
    import subprocess
    
    # Current commit
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_path, capture_output=True, text=True
    ).stdout.strip()
    
    # Current branch
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=repo_path, capture_output=True, text=True
    ).stdout.strip() or "detached"
    
    # Parent commit
    parent = subprocess.run(
        ["git", "rev-parse", "HEAD~1"],
        cwd=repo_path, capture_output=True, text=True
    ).stdout.strip() or None
    
    return {
        "commit_sha": commit[:8],
        "branch_name": branch,
        "parent_commit_sha": parent[:8] if parent else None,
    }
```

### Change Detection

```python
def detect_change_type(
    current_entity: dict,
    previous_entity: dict | None
) -> str:
    """Detect if entity was added, modified, or deleted."""
    if previous_entity is None:
        return "added"
    
    if current_entity["source_code"] != previous_entity["source_code"]:
        return "modified"
    
    return "unchanged"  # Skip unchanged entities
```

---

## Testing Strategy

### 1. Test Semantic Chunking

```python
async def test_chunking():
    """Test markdown semantic chunking."""
    markdown = """
# Architecture

This document describes the system architecture.

## Components

The system has three main components:
- Database
- API Server
- Message Queue

## Database

PostgreSQL with pgvector extension for embeddings.
"""
    
    chunks = await semantic_chunk(markdown, "architecture.md")
    assert len(chunks) == 3  # H1 section + 2 H2 subsections
    assert chunks[0]["title"] == "Architecture"
    assert chunks[1]["title"] == "Components"
    assert chunks[2]["title"] == "Database"
```

### 2. Test Summary Quality

```python
async def test_summary_quality():
    """Test different summarization skills."""
    
    test_cases = [
        ("nim_proc", nim_code, "1-2 sentences"),
        ("python_function", python_code, "1-2 sentences"),
        ("markdown_section", markdown_content, "2-3 sentences"),
        ("adr", adr_content, "2-3 sentences"),
    ]
    
    for content_type, content, expected_length in test_cases:
        summary = await worker.summarize(content, content_type)
        tokens = len(summary.split())
        print(f"{content_type}: {tokens} tokens - {summary[:100]}...")
```

### 3. Test Context Window

```python
async def test_context_limits():
    """Test model with different context sizes."""
    
    sizes = [100, 500, 1000, 5000, 10000, 32000]
    
    for size in sizes:
        content = "word " * size
        summary = await worker.summarize(content, "test")
        print(f"{size} words -> {len(summary.split())} summary tokens")
```

---

## Estimated Timeline

| Stage | Complexity | Time |
|-------|-----------|------|
| Stage 0: Environment Setup | Low | 30 min |
| Stage 1: Nim Types | Medium | 1-2 hours |
| Stage 2: Documentation | High | 3-4 hours |
| Stage 3: Schema Migration | Medium | 1-2 hours |
| Stage 4: BGE-M3 | Medium | 2-4 hours |
| Stage 5: LFM2-8B | High | 4-6 hours |
| Stage 6: Git Integration | Medium | 2-3 hours |

**Total**: ~14-21 hours

---

## Files to Create/Modify

### New Files

```
python/src/server/services/
├── languages/
│   ├── markdown_support.py      # NEW: Markdown semantic chunking
│   └── norg_support.py          # NEW: Norg semantic chunking (future)
├── document_service.py           # NEW: Document indexing service
└── summarization_service.py      # NEW: LFM2-8B summarization

scripts/
├── stage1_fix_nim_types.py      # Database + code fixes
├── stage2_index_docs.py         # Document indexing
├── stage3_schema_migration.sql   # Schema changes
├── stage4_bge_m3_worker.py      # Embedding worker
└── stage5_lfm2_summaries.py    # Summarization worker
```

### Modify Files

```
python/src/server/services/languages/
├── nim_support.py              # Add Nim-specific types
└── language_registry.py         # Register markdown/norg

migration/
└── 013_add_documents_and_summaries.sql  # NEW: Full schema
```

---

## Open Questions

1. **Norg parser**: Should we prioritize implementing norg support now or later?

2. **Summary tone**: Should summaries be technical/objective or conversational?

3. **Incremental updates**: How should we handle new commits?
   - Option A: Re-index entire repo
   - Option B: Only process changed files (using entity_identity)

4. **Omnibus ADRs**: Should ADRs get special treatment (longer summaries, different format)?

---

## Verification Checklist

- [ ] tree-sitter-markdown installed and working
- [ ] tree-sitter-norg installed (for future)
- [ ] Nim entity types: proc, func, iterator, template, macro, type
- [ ] Documents indexed with semantic chunking
- [ ] archon_documents table created with embeddings
- [ ] Schema migration run (entity_identity, summary, etc.)
- [ ] BGE-M3 embeddings generated for all entities
- [ ] LFM2-8B summaries generated for all entities
- [ ] Git integration working (branch, commit tracking)
- [ ] Cross-commit queries working
