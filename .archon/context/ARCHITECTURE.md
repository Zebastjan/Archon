# Architecture Overview


## Active ADRs

- **001-restartable-rag-pipeline**: ADR-001: Restartable RAG Ingestion Pipeline (Proposed)

- **003-mcp-server-consolidation**: ADR-003: MCP Server Consolidation to STDIO Transport (Accepted)

- **004-single-container-architecture**: ADR-004: Single-Container Architecture (Accepted)

- **005-code-intelligence-bge-m3**: ADR-005: Code Intelligence with BGE-M3 Embeddings (Accepted)

- **006-documentation-cleanup**: ADR-006: Documentation Cleanup and Archive Strategy (Accepted)

- **007-version-scoped-search**: ADR-007: Version-Scoped Search as Default Behavior (**Implemented** (2026-03-24))

- **008-worktree-context-binding**: ADR-008: Worktree-Per-Context Model with CLI Wrapper (**Implemented** (2026-03-24))

- **009-commit-automation-pipeline**: ADR-009: Commit Automation with Staged Review (**Implemented** (2026-03-24))

- **010-intelligent-auditing-system**: ADR-010: Intelligent Code Auditing System (**Implemented** (2026-03-24))

- **011-audit-feedback-loop**: ADR-011: Audit Feedback Loop and Learning Mechanism (**Implemented** (2026-03-24))

- **012-per-commit-context-bundle**: ADR-012: Per-Commit Context Bundle (**Implemented** (2026-03-25))

- **013-skills-prompts-documentation**: ADR-013: Skills & Prompts as First-Class Documentation (Proposed)

- **014-worktree-branch-discipline**: ADR-014: Worktree and Branch Discipline (**Implemented** (2026-03-24))

- **015-agent-recovery-interruption**: ADR-015: Agent Recovery and Interruption Handling (**Proposed** (2026-03-26))

- **ADR-001-WITHDRAWN**: ADR-001: Restartable RAG Ingestion Pipeline (~~Proposed~~ → **WITHDRAWN**)

- **ADR-003-Git-Aware-Knowledge-Base**: ADR-003: Git-Aware Knowledge Base Architecture (Unknown)

- **ADR-004-Git-Test-Suite-Integration**: ADR-004: Git Test Suite Integration (Unknown)

- **ADR-015-documentation-first-class**: ADR-015: Documentation as First-Class Knowledge (Proposed)

- **ADR-016-file-save-reindexing**: ADR-016: File-Save Triggered Re-indexing (Proposed)



## Core Components

### Single Container Architecture
All services run in a single container:
- API Server (port 8181)
- MCP Server (stdio transport)
- PostgreSQL with pgvector (embedded)
- Agents service

### MCP Transport
- **stdio**: Primary transport for IDE integration
- Accessed via `docker exec -i archon python -m src.mcp_server.mcp_server_stdio`

### Database
- PostgreSQL with pgvector extension
- 1024-dim embeddings (BGE-M3 model)
- Async connection via asyncpg

### Code Intelligence
- Entity extraction and indexing
- Semantic search via embeddings
- Knowledge graph for relationships