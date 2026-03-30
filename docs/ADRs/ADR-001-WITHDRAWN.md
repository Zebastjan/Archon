# ADR-001: Restartable RAG Ingestion Pipeline

## Status: ~~Proposed~~ → **WITHDRAWN**

## Original Date: 2026-02-22
## Withdrawal Date: 2026-03-25

---

## Withdrawal Notice

ADR-001 is formally withdrawn. It is retained here for historical reference only
and should not be treated as a project goal or backlog item.

### Why It Was Written

At Archon's inception, the project was conceived partly as a RAG pipeline manager —
a system that could ingest web documentation, crawl external sources, and build
queryable knowledge stores that AI agents could use as context.

The ADR proposed a state-machine pipeline with checkpointing, multiple embedding
model support, and independent stage retries.

### Why It Is Withdrawn

The landscape of AI coding tools changed faster than anticipated:

1. **Modern AI IDEs have native web search**: OpenCode, OctoFriend, Claude Code,
   Cursor, and Windsurf all include built-in web retrieval and RAG over external
   content. Building a competing pipeline would duplicate already-solved
   infrastructure with no meaningful advantage.

2. **Archon's unique value is elsewhere**: What these tools *do not* provide is
   Git-native, commit-scoped, version-aware search over a *local* codebase and
   its documentation. That is Archon's actual differentiator.

3. **Web ingestion is not where the problems are**: The real pain points in AI-
   assisted development are stale context, mixed-branch confusion, undocumented
   code changes, and broken doc-code synchronization — all local, Git-native
   problems.

### What Replaces It

The knowledge pipeline Archon *does* need is entirely Git-native:

| Original ADR-001 Concept | Replaced By |
|--------------------------|-------------|
| State-machine pipeline for web crawl | ADR-003: Git-Aware Knowledge Base |
| Checkpointing for restartability | ADR-003: Blob SHA incremental re-index |
| Multiple embedding models | ADR-005: BGE-M3 as primary (local, open source) |
| Doc chunking pipeline | ADR-015: Documentation as First-Class Knowledge |
| Retry failed stages | ADR-016: File-Save Triggered Re-indexing |

### Future Consideration

If a web ingestion capability is needed in the future, it should be implemented
as a **separate, standalone project** that complements Archon rather than as a
module within it. The Archon codebase and architecture should not be burdened with
web crawling concerns.

---

## Original Summary (for reference)

> The original ADR proposed a state-machine RAG pipeline with stages:
> Download → Chunk → Embed → Summarize, with explicit status transitions
> (`pending → in_progress → done | failed`), new tables
> (`archon_document_blobs`, `archon_chunks`, `archon_embedding_sets`,
> `archon_embeddings`, `archon_summaries`), and support for multiple
> embedders per source.

---

## Related Decisions

- ADR-003: Git-Aware Knowledge Base Architecture *(replaces this)*
- ADR-015: Documentation as First-Class Knowledge *(replaces doc ingestion aspect)*
