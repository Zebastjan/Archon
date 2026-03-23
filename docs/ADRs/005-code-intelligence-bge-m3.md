# ADR-005: Code Intelligence with BGE-M3 Embeddings

## Status: Accepted

## Date: 2026-03-23

## Context

Archon's primary goal is **code intelligence** - enabling AI agents to deeply understand and reason about codebases. This requires:
- Rich code embeddings for semantic search
- Knowledge graph over code entities (functions, classes, files)
- Understanding of commits and branches
- Multi-language support

We evaluated several embedding models for code understanding:
- OpenAI text-embedding-3-large
- BGE-M3 (BAAI)
- CodeBERT
- Various Ollama models

## Decision

We will use **BGE-M3** as the primary embedding model for code intelligence:

### Why BGE-M3?
1. **Multi-language Support**: 100+ languages supported
2. **Dense + Sparse**: Combines dense vectors with lexical matching
3. **Native Reranking**: Built-in reranking capability
4. **Open Source**: No API dependencies
5. **Quality**: Competitive with OpenAI on code tasks
6. **Local**: Can run via Ollama (no external API)

### Architecture for Code Intelligence

```
Codebase → Indexing → Code Entities → Knowledge Graph
                              ↓
                      BGE-M3 Embeddings
                              ↓
                    Semantic Search + RAG
                              ↓
                    MCP Tools for AI Agents
```

### MCP Tools for Code Intelligence
- `codebase_search_by_semantics` - Semantic code search
- `codebase_find_entity` - Find functions/classes by name
- `codebase_get_entity_context` - Get relationships
- `codebase_commits` - Track commit history
- `codebase_entity_evolution` - Track entity changes
- `codebase_compare_branches` - Compare branches

### Knowledge Graph
Code entities are stored with relationships:
- **File → Contains → Function/Class**
- **Function → Calls → Function**
- **Class → Inherits → Class**
- **Commit → Modifies → Entity**

## Consequences

### Positive
- Rich code understanding for AI agents
- Multi-language support out of the box
- Local deployment possible (Ollama)
- Knowledge graph enables reasoning over code history

### Negative
- Requires indexing to populate code entities
- Embedding quality depends on code parsing
- Larger storage for knowledge graph

## Related Decisions

- ADR-003: MCP Server Consolidation to STDIO Transport
- ADR-004: Single-Container Architecture
