# TODO - Feature: Improved Chunking

**Branch:** `feature/improved-chunking`
**Last Updated:** 2026-02-25

---

## In Progress

### Fix Torch/Torchvision Compatibility (Blocking Issue)

- [ ] Diagnose and fix torch/torchvision version incompatibility
- [ ] Verify docling can import successfully
- [ ] Run test_docling_chunkers.py to verify implementation
- [ ] Commit fix

**Issue:** torch 2.8.0+cpu and torchvision 0.23.0 are incompatible with docling.
Error: `RuntimeError: operator torchvision::nms does not exist`

---

### Docling Integration (Phase 2 of Chunking Roadmap) ✅ COMPLETED

- [x] Install docling package
- [x] Create DoclingDocumentProcessor for PDF/DOCX processing
- [x] Implement DoclingHierarchicalChunker
- [x] Implement DoclingHybridChunker  
- [x] Map Docling metadata (headings, page numbers, tables, figures) to ChunkResult
- [x] Create test fixtures with sample PDFs/DOCX
- [x] Create test_docling_chunkers.py
- [x] Committed to branch (pending: environment fix to run tests)

---

## Up Next

1. **Fix Torch Compatibility** (BLOCKING)
   - [ ] Diagnose torch/torchvision version issue
   - [ ] Find compatible versions for docling
   - [ ] Update pyproject.toml with pins if needed
   - [ ] Test docling imports work
   - [ ] Run test_docling_chunkers.py

2. **Schema Migration**
   - [ ] Run migration 016_add_chunking_metadata.sql
   - [ ] Verify new columns: section_path, section_title, page_number, element_type, order_index, metadata
   - [ ] Verify chunking_runs table created

---

## Completed

### Phase 1 Chunking ✅

- [x] BasicChunker - wraps existing smart_chunk_text
- [x] TokenAwareChunker - token-based splitting with overlap
- [x] MarkdownAwareChunker - respects Markdown heading structure
- [x] CodeAwareChunker - keeps code blocks as complete units
- [x] All 56 chunking tests passing

### Hybrid Schema ✅

- [x] Migration 016_add_chunking_metadata.sql created
- [x] New columns on archon_chunks: section_path, section_title, page_number, element_type, order_index, metadata
- [x] New table archon_chunking_runs for versioned chunking/A-B testing

### Integration ✅

- [x] Updated ChunkResult with new metadata fields
- [x] Updated all Phase 1 chunkers to populate new fields
- [x] Created docling_chunkers.py stubs (raises DoclingNotInstalledError)
- [x] Updated factory with docling strategies
- [x] Updated pipeline_orchestrator.py to use new chunking API
- [x] Updated document_storage_operations.py to pass chunking_strategy

---

## Notes

### Future: TreeSitter Integration (Phase 4)

TreeSitter will be added in a future phase for:
- Code intelligence for MCP agents
- Accurate function/class boundary detection
- Refactor code_extraction_service.py when TreeSitter is added

See: `docs/roadmap/001-chunking-roadmap.md` (Phase 4)

### Chunking Strategies Currently Available

| Strategy | Description |
|----------|-------------|
| `basic` | Simple size-based chunking |
| `token_aware` | Token-based with overlap |
| `markdown_aware` | Respects Markdown headings |
| `code_aware` | Keeps code blocks intact |
| `docling_hierarchical` | Docling structure-aware (PDF/DOCX) |
| `docling_hybrid` | Docling with token limits (PDF/DOCX) |

---

## Related Files

### Chunking Module
- `python/src/server/services/chunking/__init__.py`
- `python/src/server/services/chunking/chunker_base.py` - ChunkResult dataclass
- `python/src/server/services/chunking/factory.py` - get_chunker()
- `python/src/server/services/chunking/chunkers/basic.py`
- `python/src/server/services/chunking/chunkers/token_aware.py`
- `python/src/server/services/chunking/chunkers/markdown_aware.py`
- `python/src/server/services/chunking/chunkers/code_aware.py`
- `python/src/server/services/chunking/chunkers/docling_chunkers.py`

### Integration Points
- `python/src/server/services/ingestion/pipeline_orchestrator.py`
- `python/src/server/services/ingestion/ingestion_state_service.py`
- `python/src/server/services/crawling/document_storage_operations.py`

### Tests
- `python/tests/chunking/` - 56 passing tests

### Database
- `migration/0.1.0/016_add_chunking_metadata.sql`

---

## How to Resume Work

1. Read this TODO file to understand current state
2. Check `git status` for any uncommitted changes
3. Run `uv run pytest tests/chunking/ -v` to verify tests pass
4. Check the roadmap at `docs/roadmap/001-chunking-roadmap.md`
