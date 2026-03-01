## Chunking Roadmap for Archon

This document outlines a proposed roadmap for improving Archon’s chunking strategy in the ingestion and RAG pipeline. It builds on existing community discussions and upstream work (e.g., Docling’s advanced chunking for RAG) that we can pull from.  [github](https://github.com/coleam00/Archon/issues/756)

### 1. Motivation

Current chunking is mostly size‑driven, with limited awareness of document structure or semantics. This leads to two common failure modes:

- Chunks that are **too big**, wasting context window and mixing unrelated ideas.  [github](https://github.com/microsoftdocs/architecture-center/blob/main/docs/ai-ml/guide/rag/rag-chunking-phase.md)  
- Chunks that are **too small**, forcing the retriever to pull multiple fragments just to reconstruct a single coherent thought.  [github](https://github.com/microsoftdocs/architecture-center/blob/main/docs/ai-ml/guide/rag/rag-chunking-phase.md)

The roadmap goal is to move toward **structure‑aware, semantic‑friendly chunking** that:

- Preserves coherent units of meaning (sections, paragraphs, functions).  [docs.databricks](https://docs.databricks.com/aws/en/generative-ai/tutorials/ai-cookbook/quality-data-pipeline-rag)  
- Respects model token limits.  
- Plays nicely with downstream summarization, tagging, and RAG.

There are already discussions and prototypes in the wild we can leverage, especially around Docling’s HierarchicalChunker/HybridChunker and Archon’s existing RAG/crawling work.  [github](https://github.com/coleam00/Archon/issues/756)

***

### 2. Phase 1 – Formalize “Basic but Sensible” Chunking

**Goal:** Get to a solid baseline that’s clearly better than fixed‑size character slicing, without major architectural changes.

**Key ideas:**

1. **Paragraph and sentence‑aware chunking for prose**

   - Split text into paragraphs (or short runs of sentences) as base units.  [github](https://github.com/zahaby/intro-llm-rag/blob/main/main-aspects/chunking.md)  
   - Merge adjacent units until a target token size is reached (e.g., 400–800 tokens), with optional small overlap (10–20%).  [docs.databricks](https://docs.databricks.com/aws/en/generative-ai/tutorials/ai-cookbook/quality-data-pipeline-rag)

2. **Structure‑respecting chunking for obvious markup**

   - For Markdown/HTML, respect headings and sections: never create chunks that span unrelated top‑level sections.  [docs.databricks](https://docs.databricks.com/aws/en/generative-ai/tutorials/ai-cookbook/quality-data-pipeline-rag)  
   - Store a simple `section_path` (e.g., `Guide > Installation > Linux`) for each chunk to help retrieval and UI.

3. **Code‑aware chunking**

   - Use function/class/module boundaries as primary units when indexing code, where possible.  [docs.databricks](https://docs.databricks.com/aws/en/generative-ai/tutorials/ai-cookbook/quality-data-pipeline-rag)  
   - Include docstrings/comments adjacent to the code in the same chunk to keep semantics with implementation.

4. **Implementation details**

   - Treat chunking as a **post‑processing step** in the ingestion pipeline:  
     - Document version is ingested and stored.  
     - Chunking worker reads that version, emits chunks, and can be retried safely.  [docs.databricks](https://docs.databricks.com/aws/en/generative-ai/tutorials/ai-cookbook/quality-data-pipeline-rag)  
   - Store metadata like `document_version_id`, `chunk_index`, `section_path`, and `token_estimate` for each chunk.

This phase can be implemented with existing parsers and simple heuristics, and it aligns with multiple external best‑practice guides.  [docs.databricks](https://docs.databricks.com/aws/en/generative-ai/tutorials/ai-cookbook/quality-data-pipeline-rag)

***

### 3. Phase 2 – Integrate Docling for Advanced Document Chunking

**Goal:** Leverage Docling’s advanced RAG‑oriented chunking to handle PDFs/Office/complex docs in a structure‑aware way.  [github](https://github.com/coleam00/Archon/issues/756)

**Key ideas:**

1. **Use Docling’s document hierarchy**

   - Parse documents into a rich tree: sections, headings, paragraphs, tables, figures, etc.  [github](https://github.com/DS4SD/docling/discussions/191)  
   - This provides the “semantic skeleton” that text‑only chunkers lack.

2. **Adopt HierarchicalChunker / HybridChunker patterns**

   - **HierarchicalChunker**: create chunks that align strictly with structural blocks (sections/subsections).  [github](https://github.com/DS4SD/docling/discussions/191)  
   - **HybridChunker**: start with the hierarchy but enforce target chunk sizes by splitting big sections and merging small ones within the same path, tuned for embeddings and context window.  [github](https://github.com/DS4SD/docling/discussions/191)  
   - Configure target token sizes and overlap to match our embedding/generation models.  [docs.databricks](https://docs.databricks.com/aws/en/generative-ai/tutorials/ai-cookbook/quality-data-pipeline-rag)

3. **Pluggable chunker abstraction**

   - Introduce a simple interface like `chunk_document(document_version, strategy=...)` where strategies include:  
     - `basic_markdown`, `basic_plaintext` (from Phase 1),  
     - `docling_hierarchical`, `docling_hybrid` (Phase 2),  
     - potentially later: `semantic_embedding_based`.  
   - This keeps ingestion and storage decoupled from the specific chunking implementation.

4. **Reuse existing discussion work**

   - There is already a Docling community discussion specifically about “Advanced chunking for RAG” that outlines motivations and examples; we should mirror those concepts where appropriate.  [github](https://github.com/DS4SD/docling/discussions/191)  
   - Archon’s existing `mcp-crawl4ai-rag` work can be updated to call into the same chunker abstraction so that crawling and local ingestion behave consistently.  [github](https://github.com/coleam00/mcp-crawl4ai-rag)

***

### 4. Phase 3 – Semantic / Adaptive Chunking (Optional but Valuable)

**Goal:** Improve chunk boundaries using semantics, not just structure or length.

**Possible approaches:**

1. **Embedding‑driven boundary detection**

   - Split text into smaller units (sentences or short spans), compute embeddings, and group adjacent units until:  
     - Token limit is approached, or  
     - Semantic similarity with the next unit drops below a threshold.  [blog.dailydoseofds](https://blog.dailydoseofds.com/p/5-chunking-strategies-for-rag)  
   - This tends to yield chunks that correspond to “one idea per chunk.”

2. **Hybrid with structure**

   - Start from Docling’s structural hierarchy or Markdown headings.  
   - Within a section, use semantic grouping to avoid mixing unrelated sub‑topics into a single chunk.  [github](https://github.com/DS4SD/docling/discussions/191)

3. **Evaluation and A/B testing**

   - Use retrieval‑accuracy benchmarks or simple “question → answer” tests to compare:  
     - Fixed window,  
     - Structure‑only,  
     - Structure + semantic.  [reddit](https://www.reddit.com/r/Rag/comments/1r47duk/we_benchmarked_7_chunking_strategies_most_best/)  
   - Keep the semantic strategies optional/configurable, since they add compute overhead at ingestion time.

***

### 5. Interaction with Summaries and Tags

Improved chunking should be designed to play well with downstream metadata:

- **Per‑chunk summaries**  
  - Once chunks are coherent, per‑chunk summaries become far more meaningful and compact, and they can be embedded or shown in the UI.  [docs.databricks](https://docs.databricks.com/aws/en/generative-ai/tutorials/ai-cookbook/quality-data-pipeline-rag)  

- **Per‑chunk tags**  
  - A small classifier model can assign tags (e.g., "auth", "billing", "error handling") using the chunk text and/or its summary as input.  
  - Better chunk boundaries → less noisy tags and more targeted retrieval.

By making chunking a clear, configurable stage in the ingestion pipeline, we can evolve strategies over time (and experiment with new ones) without breaking existing datasets.

***

### 6. Phase 4 – TreeSitter Integration (Future)

**Goal:** Use TreeSitter for accurate code parsing, both for chunking and code intelligence for MCP agents.

**Background:**

TreeSitter is a battle-tested parser generator used by GitHub, Neovim, and VS Code. It parses code into an Abstract Syntax Tree (AST), enabling accurate detection of functions, classes, methods, and other code structures.

- **Python package**: `tree-sitter` + language-specific parsers (e.g., `tree-sitter-python`, `tree-sitter-javascript`)
- **30+ languages supported**: Python, JavaScript, TypeScript, Go, Rust, Java, C++, etc.
- **Official bindings**: Available for Python, Go, Rust, JavaScript, etc.

**Key ideas:**

1. **Code intelligence for MCP agents**
   - Provide accurate code understanding to AI agents
   - Find function definitions, class hierarchies, imports, etc.
   - Enable code search and navigation

2. **Accurate code chunking**
   - Replace regex-based approaches with AST-based parsing
   - Detect function/class boundaries accurately
   - Extract docstrings alongside code

3. **Refactor existing code extraction**
   - Current `code_extraction_service.py` uses regex patterns
   - When TreeSitter is integrated, refactor to use unified approach
   - Avoid having multiple libraries doing similar things

**API Design for Chunking:**

The existing `ChunkResult` dataclass is already well-suited for TreeSitter integration:

```python
# Additional fields for TreeSitter chunker:
element_type: "function" | "class" | "method" | "statement"  # extends current
metadata: {
    "language": "python",           # detected language
    "function_name": "foo",         # if function
    "class_name": "Bar",           # if class
    "docstring": "...",            # extracted docstring
    "ast_node_type": "function_definition"
}
```

TreeSitter chunker would be another strategy in the factory:

```python
CHUNKER_STRATEGIES = {
    "basic": BasicChunker,
    "token_aware": TokenAwareChunker,
    "markdown_aware": MarkdownAwareChunker,
    "code_aware": CodeAwareChunker,      # current - markdown code blocks
    "treesitter": TreeSitterChunker,      # future - AST-based
    "docling_hierarchical": ...,
    "docling_hybrid": ...,
}
```

**Implementation approach:**

1. Install `tree-sitter` and language-specific parsers (tree-sitter-python, etc.)
2. Create `TreeSitterCodeService` for MCP agent code intelligence
3. Create `TreeSitterChunker` following existing factory pattern
4. Detect language automatically, fall back to CodeAwareChunker if unsupported
5. Extract: function_name, class_name, docstrings into chunk metadata

**Note:** This will replace/refactor the existing regex-based code extraction in `code_extraction_service.py` for consistency.

***

### 7. Next Steps

1. **Implement Phase 1** in the ingestion worker: paragraph/heading‑aware chunking with token budgets for prose and structure‑respecting chunking for code.  [docs.databricks](https://docs.databricks.com/aws/en/generative-ai/tutorials/ai-cookbook/quality-data-pipeline-rag)  
2. **Add a chunker abstraction** that can later call into Docling or semantic strategies without changing the rest of the pipeline.  [github](https://github.com/coleam00/Archon/issues/756)  
3. **Prototype Phase 2 with Docling** on a subset of PDFs/Office docs, using HybridChunker‑style logic for 400–800 token targets.  [github](https://github.com/DS4SD/docling/discussions/191)  
4. **Document and link to existing discussions** (Docling’s RAG chunking thread and any Archon forum/Discord discussions) so contributors know what prior art we’re aligning with.  [github](https://github.com/coleam00/Archon/issues/756)

This roadmap aligns with what’s already being talked about in the forums and external tools, and it fits naturally into the ingestion work that’s currently underway.

---

### Implementation Status

#### Phase 1 - Completed ✅
- BasicChunker, TokenAwareChunker, MarkdownAwareChunker, CodeAwareChunker
- All 56 chunking tests passing
- Hybrid schema migration (section_path, page_number, element_type, order_index, metadata)
- Chunking runs table for A/B Chunking factory with testing support
- pluggable strategies

#### Phase 2 - In Progress 🚧
- Docling integration pending (requires docling package installation)
- Stub implementations in place, awaiting real implementation

#### Phase 3 - Pending ⏳
- Semantic/adaptive chunking

#### Phase 4 - Future 📋
- TreeSitter integration for code intelligence

---

### Related Files

**Chunking Module:**
- `python/src/server/services/chunking/__init__.py`
- `python/src/server/services/chunking/chunker_base.py` - ChunkResult dataclass
- `python/src/server/services/chunking/factory.py` - get_chunker()
- `python/src/server/services/chunking/chunkers/basic.py`
- `python/src/server/services/chunking/chunkers/token_aware.py`
- `python/src/server/services/chunking/chunkers/markdown_aware.py`
- `python/src/server/services/chunking/chunkers/code_aware.py`
- `python/src/server/services/chunking/chunkers/docling_chunkers.py`

**Integration Points:**
- `python/src/server/services/ingestion/pipeline_orchestrator.py`
- `python/src/server/services/ingestion/ingestion_state_service.py`
- `python/src/server/services/crawling/document_storage_operations.py`

**Tests:**
- `python/tests/chunking/` - 56 passing tests

**Database:**
- `migration/0.1.0/016_add_chunking_metadata.sql`

**Documentation:**
- `docs/todos/feature-improved-chunking.md` - Current work TODO
