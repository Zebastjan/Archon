# Archon Documentation

## Architecture Decision Records (ADRs)

All architectural decisions must be documented as ADRs. See [CLAUDE.md](../CLAUDE.md) for the ADR process.

### Current ADRs

- [ADR-001: Restartable RAG Ingestion Pipeline](./ADRs/001-restartable-rag-pipeline.md) (Proposed)
- [ADR-002: Crawl Reliability, Ingestion Quality Control & DB Validation](./ADRs/002-crawl-reliability.md) (Proposed)
- [ADR-003: MCP Server Consolidation to STDIO Transport](./ADRs/003-mcp-server-consolidation.md) (Accepted)
- [ADR-004: Single-Container Architecture](./ADRs/004-single-container-architecture.md) (Accepted)
- [ADR-005: Code Intelligence with BGE-M3 Embeddings](./ADRs/005-code-intelligence-bge-m3.md) (Accepted)
- [ADR-006: Documentation Cleanup and Archive Strategy](./ADRs/006-documentation-cleanup.md) (Accepted)

## Documentation Standards

- Keep root docs focused (`README.md`, `CLAUDE.md`, `CONTRIBUTING.md`)
- Detailed docs in `docs/`
- Use ADRs for architectural decisions
- No port 8051 references (MCP is stdio only)
- Single-container architecture (not microservices)

## Roadmap

See [GitHub Issues](https://github.com/anomalyco/archon/issues) for current features and bug fixes.
