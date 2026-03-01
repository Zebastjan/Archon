# RawDocument Format Detection and Logging - Complete

## Overview

Comprehensive format detection and logging has been added throughout the ingestion pipeline to make document structure and conversions visible. This is especially important for PDF processing via Docling, where metadata like page counts, tables, and images help verify extraction quality.

## Format Detection Locations

### 1. Old Pipeline - document_storage_operations.py (Lines 154-210)

**Location**: `python/src/server/services/crawling/document_storage_operations.py`

**Detection logic**:
```python
# Multi-source format detection
if doc.get("format"):
    doc_format = doc.get("format")  # Explicit format from document
elif doc_url.lower().endswith(".pdf"):
    doc_format = "pdf"  # URL-based detection
elif "--- Page" in markdown_content:
    doc_format = "pdf"  # Content-based detection (page markers)
elif markdown_content and not html_content:
    doc_format = "markdown"  # Inferred from content types
else:
    doc_format = "html"  # Default
```

**Log output**:
```
PREPROCESS_RAWDOC | url=https://docs.example.com/guide.pdf | format=pdf | title=Installation Guide | text_len=24531 | html_len=0 | metadata_keys=['source_type', 'page_count', 'has_tables']
```

### 2. PDF-Specific Logging (Lines 191-210)

**Additional fields logged for PDFs**:
- `page_count`: Number of pages (from metadata or counted from page markers)
- `has_tables`: Boolean indicating table presence
- `has_images`: Boolean indicating image presence
- `has_code_blocks`: Boolean indicating code block presence
- `code_block_markers`: Count of ``` markers found
- `extraction_method`: How PDF was processed (e.g., "docling", "pdfplumber")

**Log output**:
```
PREPROCESS_PDF | url=file://api_reference.pdf | page_count=15 | has_tables=true | has_images=false | has_code_blocks=true | code_block_markers=12 | extraction_method=pdfplumber
PREPROCESS_PDF_SAMPLE | first_page_preview=# API Reference\n\nThis document describes...
```

### 3. New Pipeline - document_storage_operations.py (Lines 720-739)

**Location**: New restartable pipeline path

**Log output**:
```
PREPROCESS_RAWDOC_NEW_PIPELINE | url=https://example.com/doc.pdf | format=pdf | title=User Guide | text_len=18420
```

### 4. Format Conversion Logging - document_processing.py (Lines 175-230)

**Location**: `python/src/server/utils/document_processing.py`

**Conversions logged**:

**PDF → Text**:
```
FORMAT_CONVERSION | filename=whitepaper.pdf | from=PDF | to=text | input_size=1048576 bytes | extraction_method=pdfplumber+PyPDF2
FORMAT_CONVERSION_RESULT | filename=whitepaper.pdf | output_length=24531 | has_page_markers=true | has_code_blocks=true
```

**DOCX → Text**:
```
FORMAT_CONVERSION | filename=report.docx | from=DOCX | to=text | input_size=245760 bytes
FORMAT_CONVERSION_RESULT | filename=report.docx | output_length=18420
```

**HTML → Text**:
```
FORMAT_CONVERSION | filename=page.html | from=HTML | to=text | input_length=45123
FORMAT_CONVERSION_RESULT | filename=page.html | output_length=32100
```

## Format Detection Strategy

### Multi-Source Detection

The system checks **4 sources** in priority order:

1. **Explicit format field**: `doc.get("format")` if set by upstream processors
2. **URL extension**: `.pdf`, `.html`, `.md` from the URL
3. **Content markers**: `--- Page N ---` indicates PDF, triple backticks suggest markdown
4. **Metadata**: `source_type` or other metadata fields
5. **Content analysis**: Presence/absence of HTML vs markdown

### PDF-Specific Metadata Extraction

For PDFs, the system attempts to extract:

```python
# From metadata
page_count = doc_metadata.get("page_count") or doc_metadata.get("pages")
has_tables = doc_metadata.get("has_tables", False)
has_images = doc_metadata.get("has_images", False)
extraction_method = doc_metadata.get("extraction_method", "unknown")

# From content analysis (fallback)
if page_count == "unknown" and "--- Page" in markdown_content:
    page_markers = re.findall(r"--- Page (\d+) ---", markdown_content)
    page_count = len(page_markers)

code_block_count = markdown_content.count("```")
has_code_blocks = code_block_count > 0
```

## Expected Log Flows

### PDF Upload Flow

```
1. FORMAT_CONVERSION | filename=guide.pdf | from=PDF | to=text | input_size=524288 bytes
2. FORMAT_CONVERSION_RESULT | filename=guide.pdf | output_length=15234 | has_page_markers=true | has_code_blocks=true
3. PREPROCESS_RAWDOC | url=file://guide.pdf | format=pdf | title=Installation Guide | text_len=15234 | html_len=0
4. PREPROCESS_PDF | url=file://guide.pdf | page_count=8 | has_tables=false | has_images=true | has_code_blocks=true | code_block_markers=6
5. PREPROCESS_PDF_SAMPLE | first_page_preview=# Installation Guide\n\nWelcome to...
```

### HTML Crawl Flow

```
1. CRAWL_FETCH_SUCCESS | url=https://docs.example.com/intro.html | content_length=8942 | has_html=True | html_length=12453
2. PREPROCESS_RAWDOC | url=https://docs.example.com/intro.html | format=html | title=Introduction | text_len=8942 | html_len=12453
3. CHUNKING_START | url=https://docs.example.com/intro.html | total_text_length=8942
```

### Markdown File Flow

```
1. CRAWL_FETCH_SUCCESS | url=https://raw.github.com/README.md | content_length=4521 | has_html=False
2. PREPROCESS_RAWDOC | url=https://raw.github.com/README.md | format=markdown | title=README | text_len=4521 | html_len=0
3. CHUNKING_START | url=https://raw.github.com/README.md | total_text_length=4521
```

## Debugging PDF Issues

### Common PDF Problems and Log Signatures

**Problem: PDF content is empty or truncated**
```
FORMAT_CONVERSION_RESULT | output_length=45  # Too short!
PREPROCESS_PDF | page_count=12 | has_code_blocks=false  # Expected code blocks missing
```
→ Check PDF extraction library (pdfplumber vs PyPDF2), try Docling

**Problem: Code blocks lost during PDF extraction**
```
PREPROCESS_PDF | code_block_markers=0  # No ``` found
```
→ Check `_preserve_code_blocks_across_pages()` function, verify page markers

**Problem: Tables not detected**
```
PREPROCESS_PDF | has_tables=false  # But tables exist in PDF
```
→ Verify Docling table structure extraction is enabled

**Problem: Page markers breaking code blocks**
```
PREPROCESS_PDF_SAMPLE | first_page_preview=```python\ndef hello():\n--- Page 2 ---\n    return...
```
→ Check `_preserve_code_blocks_across_pages()` post-processing

## Files Modified

1. **python/src/server/services/crawling/document_storage_operations.py**
   - Lines 154-210: Enhanced RawDocument logging with format detection (old pipeline)
   - Lines 191-210: PDF-specific metadata logging
   - Lines 720-739: Format detection for new pipeline

2. **python/src/server/utils/document_processing.py**
   - Lines 175-193: PDF conversion logging
   - Lines 196-204: DOCX conversion logging
   - Lines 207-217: HTML conversion logging

## Testing

### Enable Debug Mode

```bash
DEBUG_INGESTION=true
```

### Test PDF Upload

1. Upload a PDF with known characteristics (e.g., 5 pages, 2 code blocks, 1 table)
2. Check logs for:
   ```
   FORMAT_CONVERSION | from=PDF
   PREPROCESS_PDF | page_count=5 | has_code_blocks=true | code_block_markers=4
   ```
3. Verify `code_block_markers=4` (2 blocks × 2 ``` markers each)
4. Check first page preview contains expected content

### Test HTML Crawl

1. Crawl an HTML documentation page
2. Check logs for:
   ```
   PREPROCESS_RAWDOC | format=html | html_len=... | text_len=...
   ```
3. Verify both HTML and markdown content are present

### Test Markdown File

1. Crawl a raw markdown file (e.g., GitHub README)
2. Check logs for:
   ```
   PREPROCESS_RAWDOC | format=markdown | html_len=0 | text_len=...
   ```
3. Verify no HTML content is logged

## Next Steps

- Task #4: Add DB schema validation logging
- Task #5: Add UI literal text search verification
- Task #6: Create golden path test script
