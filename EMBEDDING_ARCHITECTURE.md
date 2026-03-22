# Embedding Service Architecture

## The Problem

We need embeddings for:
1. **Documents** (crawled docs, knowledge base)
2. **Code entities** (functions, classes, etc.)
3. **Queries** (for RAG search)

But we have conflicting requirements:
- **pgvector** = fast similarity search, indexes (IVFFlat, HNSW)
- **No pgvector** = JSONB arrays work but are SLOW for large datasets
- **Ollama** = local embeddings (BGE-Large = 1024 dims)
- **OpenAI** = cloud embeddings (optional fallback)

## The Solution: Pluggable Embedding Service

```
┌────────────────────────────────────────────────────────────┐
│                    Embedding Service                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │
│  │   Ollama    │  │   OpenAI    │  │  Local Model    │   │
│  │  (BGE-Large)│  │  (Optional) │  │  (Fallback)     │   │
│  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘   │
│         │                 │                  │            │
│         └─────────────────┴──────────────────┘            │
│                           │                               │
│                    ┌────────┴────────┐                     │
│                    │  Generate Embed │                     │
│                    └────────┬────────┘                     │
│                             │                              │
│         ┌───────────────────┼───────────────────┐           │
│         ▼                   ▼                   ▼           │
│  ┌────────────┐    ┌─────────────┐    ┌──────────┐      │
│  │  pgvector  │    │ JSONB Store │    │ In-Mem   │      │
│  │  (fast)    │    │  (fallback) │    │  Cache   │      │
│  └────────────┘    └─────────────┘    └──────────┘      │
└────────────────────────────────────────────────────────────┘
```

## Storage Backends

### 1. pgvector (Primary)
```sql
CREATE TABLE archon_embeddings (
    embedding VECTOR(1024),  -- Fast similarity search
    ...
);
CREATE INDEX ON archon_embeddings USING ivfflat (embedding vector_cosine_ops);
```
**Pros:** Fast ANN search, proper indexes
**Cons:** Requires pgvector extension

### 2. JSONB Store (Fallback)
```sql
CREATE TABLE archon_embeddings (
    embedding JSONB,  -- Array: [0.1, 0.2, ...]
    ...
);
-- Search in Python (slow)
```
**Pros:** Works everywhere
**Cons:** O(n) search, no indexes, slow at scale

### 3. In-Memory Cache (Speed Layer)
```python
embedding_cache: dict[str, np.ndarray] = {}
# Cache frequently accessed embeddings in RAM
```
**Pros:** Sub-millisecond access
**Cons:** Lost on restart, memory limited

## Why This Matters

### Without pgvector (JSONB only):
- 10k embeddings × 1024 dims = 10MB
- Search: 10k cosine calculations = **~100ms**

### With pgvector (IVFFlat index):
- Same data
- Search: **~1-5ms** (100x faster)

### With in-memory cache:
- Frequently accessed embeddings: **~0.1ms**

## Architecture Decision

**Primary:** pgvector + Ollama (BGE-Large, 1024 dims)
**Fallback:** JSONB arrays (if pgvector unavailable)
**Accelerator:** In-memory LRU cache for hot embeddings

This gives us:
1. **Fast** search with pgvector
2. **Works** without pgvector (just slower)
3. **Blazing fast** cache for repeated queries
