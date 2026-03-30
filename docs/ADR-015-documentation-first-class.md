# ADR-015: Documentation as First-Class Knowledge

## Status: Proposed

## Date: 2026-03-25

## Authors: zebastjan

---

## Context

Archon's original framing positioned it as a **code intelligence** platform, with
documentation treated as a secondary concern in the chunking pipeline. In practice,
the most valuable knowledge in a project lives equally in its documentation:

- Architecture Decision Records (ADRs)
- README files and setup guides
- API reference docs (Markdown, reStructuredText)
- Skills and workflow guides (`skills/`)
- Inline design notes (`.norg`, `.org`)
- Rich format documents (PDFs, Word docs via Docling)

Modern AI coding tools (OpenCode, OctoFriend, Claude Code, Cursor) provide their own
web search and general knowledge retrieval. **Archon's unique value is Git-native,
version-scoped, commit-aware search over everything in your repository** — not just
`.py` files, but every text artifact that describes, specifies, or guides the project.

The current ADR-003 Git-Aware Knowledge Base partially addresses this — a
`MarkdownAwareChunker` and Docling pipeline are referenced — but they are treated as
edge-case routing logic rather than a stated first-class requirement. This ADR
formalizes the principle.

### Specific Gaps

1. ADR-003 routes docs to `MarkdownAwareChunker` but does not define chunking
   strategy, metadata, or embedding priorities for doc files
2. No RST, NORG, or Org-mode chunker is defined
3. PDF/rich format handling (Docling) is described as "a separate pipeline" with no
   integration spec
4. The `skills/` directory is version-controlled but not indexed — agents cannot
   semantically search skills
5. ADRs themselves are not queryable through the MCP search tools
6. Doc-to-code relationships are not represented in the knowledge graph

---

## Decision

**All text artifacts committed to the Git repository are indexed, chunked, embedded,
and queryable with the same commit-scoped semantic search as source code.**

Documentation is not a secondary pipeline. It is an equal participant in the
knowledge graph.

### Supported File Types

| Format | Extensions | Chunker |
|--------|-----------|---------|
| Markdown | `.md`, `.mdx` | `MarkdownAwareChunker` (header-aware splitting) |
| reStructuredText | `.rst` | `ReSTChunker` (section-aware splitting) |
| Org-mode / Norg | `.org`, `.norg` | `OrgChunker` (heading-aware splitting) |
| Plain text | `.txt`, `.text` | `BasicChunker` |
| PDF | `.pdf` | `DoclingChunker` (via Docling pipeline) |
| Word | `.docx`, `.doc` | `DoclingChunker` (via Docling pipeline) |
| Code | `.py`, `.ts`, `.go`, etc. | `CodeAwareChunker` (language-specific) |

> **Note on Docling**: PDF and Word documents require the Docling service. This runs
> as an optional sidecar within the single-container architecture (ADR-004). If
> Docling is unavailable, rich format files are skipped with a warning, not failed.

### Chunking Principles for Documentation

1. **Structure-preserving**: Headers, sections, and hierarchy are preserved as
   metadata on chunks — not stripped out
2. **Cross-reference extraction**: Links to other docs, code references (e.g.,
   `` `MyClass` ``), and ADR references (e.g., `ADR-007`) are extracted as edges
   in the knowledge graph
3. **Summary generation**: Each document gets a one-paragraph LLM-generated summary
   stored alongside its chunks for fast high-level retrieval
4. **Version-scoped**: Doc chunks are tagged with `git_commit_id` and `git_file_id`
   exactly like code chunks — historical state is queryable

### Knowledge Graph Extensions

In addition to the code entity relationships defined in ADR-005, documentation
introduces the following edge types:

```
Doc → Describes → Feature
Doc → References → CodeEntity (function, class, module)
Doc → Supersedes → Doc  (e.g., ADR-015 supersedes ADR-001 rationale)
Doc → RelatesTo → Doc
ADR → Implements → Feature
Skill → Guides → Workflow
```

These edges are populated during the indexing pass using lightweight heuristic
extraction (regex + LLM assist for ambiguous cases).

### Skills Directory Indexing

The `skills/` directory is a first-class documentation source:

- All files under `skills/` are indexed on every commit that touches them
- Agents can search skills semantically: `codebase_search_by_semantics(query="how to switch worktrees")`
  will surface `skills/workflows/zig-zag-workflow.md`
- Skill drift detection (ADR-013) is enhanced: when a tool signature changes, the
  index is updated AND the related skill chunk is flagged as potentially stale

### MCP Tool Behavior

No new tools are required. Existing tools gain doc awareness:

- `codebase_search_by_semantics()` — already searches all indexed content; docs now
  included by default
- `codebase_find_entity()` — extended to match doc sections and ADR titles, not
  just code entities
- `codebase_entity_evolution()` — can track how a doc section changed across commits

New optional filter parameter added to search tools:

```python
await codebase_search_by_semantics(
    repo_id="...",
    query="how to set up worktrees",
    content_type="docs"   # "code" | "docs" | "all" (default: "all")
)
```

### Docling Integration

Docker Compose adds optional Docling sidecar:

```yaml
services:
  archon:
    # existing single container
  docling:
    image: ds4sd/docling-serve:latest
    ports:
      - "5001:5001"
    profiles: ["rich-docs"]   # opt-in only
```

The chunking router calls `http://localhost:5001/convert` for PDF/Word files when
available. If unavailable, file is logged to `archon_skipped_files` table for
later retry.

---

## Implementation Checklist

- [ ] Implement `ReSTChunker` for `.rst` files
- [ ] Implement `OrgChunker` for `.org` / `.norg` files
- [ ] Define `MarkdownAwareChunker` chunking strategy (header depth, max chunk size)
- [ ] Add Docling sidecar to Docker Compose with `rich-docs` profile
- [ ] Implement `DoclingChunker` that calls Docling service
- [ ] Add `archon_skipped_files` table for retry tracking
- [ ] Add doc edge types to knowledge graph schema
- [ ] Implement cross-reference extraction during doc indexing pass
- [ ] Add `content_type` filter parameter to MCP search tools
- [ ] Index `skills/` directory on commit
- [ ] Add doc summary generation to indexing pipeline
- [ ] Update ADR-003 to reference this ADR as the doc-indexing spec
- [ ] Write tests: markdown chunking preserves headers
- [ ] Write tests: RST section splitting
- [ ] Write tests: cross-reference extraction from docs
- [ ] Write tests: Docling fallback on unavailable service

---

## Consequences

### Positive

- Agents can search architecture decisions, workflows, and guides semantically
- ADRs are discoverable by topic, not just by number
- `skills/` becomes a searchable, commit-versioned knowledge base
- Doc-to-code cross-references make impact analysis richer
- No new MCP tools required — existing tools gain capability

### Negative

- Indexing time increases proportional to doc volume
- Docling dependency adds operational complexity (mitigated by opt-in profile)
- Cross-reference extraction quality depends on heuristic accuracy
- OrgChunker / NOrgChunker need custom implementation (no mature library)

---

## Related Decisions

- ADR-003: Git-Aware Knowledge Base (doc chunking routing defined there; this ADR
  specifies the full implementation)
- ADR-005: Code Intelligence with BGE-M3 (embedding model; docs use same model)
- ADR-009: Commit Automation Pipeline (doc drift detection runs at commit time)
- ADR-013: Skills & Prompts as First-Class Documentation (skills/ structure)
- ADR-001: Restartable RAG Pipeline (**Withdrawn** — see withdrawal notice)
