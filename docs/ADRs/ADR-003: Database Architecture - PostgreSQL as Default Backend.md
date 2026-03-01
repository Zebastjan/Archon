# ADR-003: Database Architecture - PostgreSQL as Default Backend

**Status:** In Progress  
**Date:** 2026-02-25  
**Authors:** Zebastjan Johanzen

---

## Context

We have spent considerable time exploring database options for Archon, including Supabase, Neon, Weaviate, Qdrant, Neo4j, and SQLite. The goal of this ADR is to document the decisions made about Archon's database architecture and provide a foundation for future extensibility.

Key requirements:
- Sovereign, long-term project brain (not SaaS-bound)
- Easy to run locally or self-host (Docker, bare metal, VPS)
- Centered on Git + Postgres for repo history, chunks/embeddings, and metadata
- Support for future alternative backends without entangling core logic

---

## Decision

### 1. Git as the Canonical Source of Truth

Git repositories hold:
- Actual code
- Commit history
- Branches and tags

Postgres stores **indexed views** over Git:
- `repos`, `commits`, `files`, `chunks`
- Later: `relations` (graph edges), `tasks`, `docs`, etc.

Archon never "owns" the code; it mirrors and indexes it.

### 2. PostgreSQL (with pgvector) as Default Backend

PostgreSQL with pgvector will be the default and canonical backend for:
- Indexed views over Git (chunks, embeddings)
- Project/task/knowledge graph metadata
- Long-term, structured memory

Reasons for this choice:

| Factor | Rationale |
|--------|-----------|
| **Maturity & ubiquity** | Battle-tested, widely available, excellent tooling, easy local/dev setup |
| **One system for relational + vector** | With pgvector, embeddings stored alongside metadata in a single DB |
| **Sovereignty / self-hosting** | Users can run Postgres anywhere without tying to a specific cloud vendor |
| **Strong relational modeling** | Better fit than vector-only stores for Git history, knowledge graphs, projects/tasks |

### 3. Lightweight Database Abstraction Layer

We will introduce a `db_connector` / repository layer that:
- Defines clear interfaces for core operations:
  - Inserting/searching chunks
  - Managing repos/commits/files
  - Managing relations/graph edges
  - Managing projects/tasks/docs
- Has a Postgres implementation as the default
- Can gain additional implementations later:
  - Supabase (still Postgres under the hood)
  - Neon Postgres
  - Weaviate/Qdrant adapters for embeddings
  - Other stores without changing core logic

Core code (agents, MCP tools, chunking pipeline) must talk to this connector, not directly to database-specific APIs.

---

## Rejected (Non-Default) Options

These are not "bad" tools—they're just not our default foundation.

### Supabase

- **Pros:** Hosted Postgres + pgvector, auth, storage, real-time
- **Cons:** Adds SaaS dependency and implicit lock-in for core data; schema harder to evolve programmatically
- **Decision:** Treat as optional deployment target via abstraction layer, not required

### Neon

- **Pros:** Serverless Postgres, branching, modern features
- **Cons:** Cloud-only, vendor-specific; branching features redundant with Git
- **Decision:** Possible future integration, but not default

### Weaviate, Qdrant, Pinecone (Vector Databases)

- **Pros:** Powerful vector search, hybrid search, scalable
- **Cons:** Another moving piece and subscription just for embeddings; overkill for early stages
- **Decision:** Keep architecture vector-store agnostic via abstraction

### Neo4j / Dedicated Graph DBs

- **Pros:** Natural for knowledge graphs
- **Cons:** Extra infra, licensing/operational complexity
- **Decision:** Start with relational tables for relations (e.g., `relations(from_id, to_id, type)`), consider dedicated graph DB only if truly needed

### SQLite

- **Pros:** Simple, embedded, zero-config
- **Cons:** Weak for multi-user, multi-service architecture; concurrency/scaling limits
- **Decision:** May be useful for tiny single-user experiments, but not canonical backend

---

## Implementation Notes

### Schema Assumptions

All schema designs in this ADR assume vanilla PostgreSQL with the following extensions:
- `vector` (pgvector)
- `pgcrypto`
- `pg_trgm`

### Abstraction Layer Structure

```
src/
  db/
    interfaces/
      chunk_repository.py      # Insert/search chunks
      repo_repository.py       # Manage repos/commits/files
      relation_repository.py   # Manage graph edges
      project_repository.py    # Manage projects/tasks/docs
    implementations/
      postgres/
        postgres_chunk_repo.py
        postgres_repo_repo.py
        ...
      supabase/               # Future
      neon/                   # Future
      weaviate/               # Future (embeddings only)
    connector.py              # Factory/context provider
```

### Migration Path

1. **Immediate:** Refactor existing database access through new repository interfaces
2. **Short-term:** Implement Postgres connector as default
3. **Medium-term:** Add alternative backends (Supabase, Neon) via adapter pattern
4. **Long-term:** Evaluate dedicated vector stores if pgvector proves insufficient

---

## Why This Aligns with "It's All About Git + Knowledge"

- **Git** is our truth for code and history
- **Postgres** is our truth for:
  - Indexing (chunks, embeddings)
  - Project/knowledge graph metadata
  - Long-term, structured memory
- Everything else (Supabase, Neon, vector DBs) is an **optional implementation detail**, not the shape of Archon's core

This gives us:
- Sovereignty and portability
- A clean, understandable stack
- A strong foundation for project-centric knowledge graph and MCP agents

---

## Future Work

- Git integration (indexing commits, files, branches)
- Knowledge graph relations stored in Postgres
- Alternative backend implementations via abstraction layer

---

## Related ADRs

- ADR-001: Crawl & Ingestion Pipeline Improvements (superseded)
- ADR-002: Crawl Reliability, Provenance Tracking & Validation
