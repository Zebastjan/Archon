# Docling + Chunking Integration: Testing Strategy

This document describes how we want to test Archon’s integration between **Docling** (document conversion) and our **chunking pipeline**.

The goal is to ensure that:

1. We call Docling correctly for various document formats.
2. We handle Docling’s outputs correctly (DoclingDocument / markdown / text).
3. Our chunker produces reasonable, useful chunks from those outputs.
4. RAG/search over those chunks can answer simple questions about the original documents.

We **do not** try to re‑test Docling itself in depth; we assume Docling’s core conversion is correct and focus on how Archon uses it. [github](https://github.com/docling-project/docling/blob/main/docs/usage.md)

***

## 1. Scope: what we are testing

End‑to‑end path for document ingestion via Docling:

1. Given a document file (PDF, DOCX, PPTX, etc.),  
2. Archon calls Docling to convert it into a structured representation (DoclingDocument, markdown, or text). [github](https://github.com/docling-project/docling/blob/main/README.md)
3. Archon feeds that representation into our **chunking pipeline**.  
4. Chunks and metadata are stored in our DB (Supabase / PGVector / etc.).  
5. RAG/search tools can answer simple, deterministic questions about the content.

We want tests that cover:

- Multiple formats (PDF, DOCX, possibly PPTX/HTML).
- Basic vs slightly complex layout (plain text, tables, headings).
- Size/limit behavior (max pages / file size).
- Basic RAG correctness on a small number of canned questions.

***

## 2. Test data and fixtures

We will use a combination of **Docling example/test files** and **our own small fixtures**.

### 2.1 Reusing Docling example/test files

The Docling project ships sample documents and usage patterns: [github](https://github.com/docling-project/docling/blob/main/docs/v2.md)

- Example files for:
  - PDFs (e.g., reports, articles, technical docs).
  - DOCX / Word files.
  - PPTX / slide decks (optional, nice‑to‑have).
  - Possibly HTML or other formats.

We should:

- Copy a small subset of these files into `testdata/docling/` in Archon (or maintain them as test‑only fixtures).
- Document in a README:
  - Where they came from (Docling project / docs).
  - What each file is meant to exercise (simple text, tables, etc.).

### 2.2 Archon‑specific fixtures (optional)

If needed, we can create one or two tiny custom docs:

- `simple-report.pdf`
  - 2–3 pages.
  - Clear headings (`Introduction`, `Methods`, `Results`).
  - A couple of short paragraphs per section.

- `table-heavy.pdf`
  - 1–2 pages with at least one table and surrounding text.

These are optional; existing Docling examples may already cover similar patterns. [arxiv](https://arxiv.org/html/2501.17887v1)

***

## 3. Test scenarios

### 3.1 Simple PDF: “happy path”

**Goal:** Prove that a basic PDF goes through Docling → chunking → RAG successfully.

- Fixture:
  - A simple PDF with headings and paragraphs (Docling example or our own). [github](https://github.com/docling-project/docling/blob/main/docs/usage.md)

- Steps:
  1. Run Docling conversion via our integration:
     - e.g., `DocumentConverter().convert(path)` → `DocumentConversionResult.document` or markdown. [github](https://github.com/docling-project/docling/blob/main/docs/v2.md)
  2. Pass the resulting representation (DoclingDocument or markdown/text) into the Archon chunker.
  3. Store chunks as we normally do for documents.
  4. Use RAG/search to ask a simple canned question:
     - “What is the main topic of this document?”
     - Or “What section headings does this document have?”

- Assertions:
  - Conversion completes without error.
  - Chunk count is within a sane range (e.g. > 3 and < 200 for a short PDF).
  - At least one chunk contains a known phrase from the document.
  - RAG returns an answer that:
    - Mentions a known section heading or key phrase.
    - Is not obviously garbage.

### 3.2 PDF with tables and figures

**Goal:** Ensure we don’t silently drop structured content like tables.

- Fixture:
  - A PDF with at least one table (Docling’s examples or similar). [docling-project.github](https://docling-project.github.io/docling/)

- Steps:
  1. Convert via Docling.
  2. Chunk the resulting content.
  3. Run a RAG/search query such as:
     - “What does the table in the document describe?”
     - Or a question whose answer is only in the table (e.g. “What is the value in row X, column Y?” if reasonable).

- Assertions:
  - At least one chunk clearly includes table content (e.g. multiple cells or tabular text).
  - RAG returns an answer that references table content (not just generic text).

We are not validating perfect table reconstruction; we just verify the table is not effectively invisible to our pipeline.

### 3.3 DOCX / Office formats

**Goal:** Validate that non‑PDF formats also flow through Docling → chunker → RAG.

- Fixture:
  - A DOCX example with headings and paragraphs (Docling’s example data). [datacamp](https://www.datacamp.com/tutorial/docling)

- Steps:
  1. Convert DOCX via Docling (same integration as PDFs).
  2. Chunk and store.
  3. Query RAG:
     - “What is the title of the document?”
     - “What is the first heading?”

- Assertions:
  - Conversion and chunking succeed without errors.
  - Chunk count is reasonable.
  - RAG answers align with content (title/heading matches the file).

PPTX or other formats can be added later in the same pattern.

### 3.4 Size and limits (max pages / file size)

**Goal:** Ensure we respect size limits and degrade gracefully.

- Fixtures:
  - A document that is:
    - Slightly above a configured page limit (e.g. > N pages).
    - Or above a configured file size limit.

- Steps:
  1. Configure Docling or our integration with limits:
     - e.g., `max_num_pages`, `max_file_size` or similar. [github](https://github.com/docling-project/docling/blob/main/docs/usage.md)
  2. Attempt conversion via our integration.
  3. Chunk whatever content we do receive (if partial).
  4. Observe behavior and RAG results.

- Assertions:
  - Over‑limit docs are:
    - Explicitly rejected **or**
    - Truncated according to our configuration (documented behavior).
  - We **do not crash** or hang.
  - For truncated docs:
    - We still get some chunks.
    - RAG can answer questions about the included portion (e.g., first section).

***

## 4. Responsibilities and boundaries

We assume:

- Docling’s core conversion is tested in its own repo and works as advertised. [github](https://github.com/docling-project/docling)

We focus our tests on:

- Calling Docling with the right options and handling errors.
- Correctly traversing the Docling output (DoclingDocument / markdown) and extracting text/structure for chunking.
- Chunking behavior (chunk sizes, structure alignment, non‑dropping of key content).
- RAG/search correctness on a few predictable questions.

We do **not**:

- Test every possible document format or layout edge case.
- Validate every minor detail of Docling’s formatting.

***

## 5. Implementation notes (for agents / contributors)

When implementing this test suite:

1. **Use real Docling APIs**  
   - Follow Docling’s documented usage:
     - `DocumentConverter().convert(path_or_url)` for single documents. [github](https://github.com/docling-project/docling/blob/main/docs/v2.md)
   - Use either:
     - The `document` (DoclingDocument) object directly, or
     - Export to markdown/text and feed that to the chunker.

2. **Keep tests deterministic and offline**  
   - Use local fixture files, not remote URLs.  
   - Avoid network access in tests.

3. **Structure tests as integration tests**  
   - Place them in an appropriate `tests/` module (e.g. `tests/integration/test_docling_chunking.py`).  
   - Use Archon’s actual chunking API, not test‑only shortcuts, so we exercise real behavior.

4. **Be conservative with fixture size**  
   - Keep fixture docs small enough that tests run quickly.  
   - If a Docling example is large, consider cropping it or picking a smaller one.

5. **Log enough to debug failures**  
   - Log:
     - Which fixture is being converted.
     - Conversion status.
     - Number of chunks produced.
   - This will help diagnose “0 chunks” or conversion failures without deep digging.

***

## 6. Success criteria

We consider Docling + chunking integration “basically trustworthy” when:

- The simple PDF “happy path” test passes reliably.
- The table/figure test shows that table content is not silently lost.
- The DOCX test passes.
- Size/limit tests show controlled behavior (reject or truncate) with no crashes.
- RAG answers for a small set of canned questions are sensible and tied to the underlying content.

From there, we can add more fixtures and more sophisticated assertions, but the above is the minimum bar for “we think Docling + our new chunker are wired correctly.”