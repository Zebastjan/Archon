# Filtering Bypass and Document Count Invariant - Complete

## Overview

All document filtering has been identified and bypass logic has been added. When `DEBUG_INGESTION=true` and filtering is disabled, documents will flow through the pipeline without being dropped by quality/relevance heuristics.

## Filtering Locations Identified and Fixed

### 1. Keyword Filtering (recursive.py:345-369)

**Location**: `python/src/server/services/crawling/strategies/recursive.py`

**What it filters**: URLs containing excluded keywords (e.g., "api", "changelog", "blog") during recursive crawling

**Bypass logic added**:
```python
if has_doc_sites and not debug_settings.disable_keyword_filtering:
    # Normal keyword filtering logic
elif has_doc_sites and debug_settings.disable_keyword_filtering:
    logger.info("FILTER_BYPASSED | filter_type=keyword | url=...")
```

**Environment variable**: `DISABLE_KEYWORD_FILTERING=true`

**Log output when bypassed**:
```
FILTER_BYPASSED | filter_type=keyword | url=https://... | reason=DEBUG_INGESTION disabled keyword filtering
```

### 2. Empty Content Filtering (document_storage_operations.py:165-167)

**Location**: `python/src/server/services/crawling/document_storage_operations.py` (old pipeline)

**What it filters**: Documents with no content or missing URLs

**Bypass logic added**:
```python
if not doc_url:
    should_skip = True  # Always skip if no URL
elif not markdown_content and not debug_settings.disable_length_filtering:
    should_skip = True  # Skip empty content normally
elif not markdown_content and debug_settings.disable_length_filtering:
    # Allow empty content in debug mode
    logger.info("FILTER_BYPASSED | filter_type=empty_content | ...")
```

**Environment variable**: `DISABLE_LENGTH_FILTERING=true`

**Log output when bypassed**:
```
FILTER_BYPASSED | filter_type=empty_content | url=https://... | content_length=0 | reason=DEBUG_INGESTION disabled length filtering
```

### 3. Empty Content Filtering - New Pipeline (document_storage_operations.py:647-670)

**Location**: `python/src/server/services/crawling/document_storage_operations.py` (_process_with_new_pipeline method)

**What it filters**: Documents with no content in the new restartable pipeline

**Bypass logic added**: Same as #2, but with different log identifier

**Log output when bypassed**:
```
FILTER_BYPASSED | filter_type=empty_content_new_pipeline | url=https://... | reason=DEBUG_INGESTION disabled length filtering
```

### 4. Minimum Content Length (single_page.py:181-200)

**Location**: `python/src/server/services/crawling/strategies/single_page.py`

**What it filters**: Pages with < 50 characters of content during crawl

**Bypass logic added**:
```python
min_length = 1 if debug_settings.disable_length_filtering else 50
content_length = len(result.markdown.strip()) if result.markdown else 0

if content_length < min_length:
    # Retry with different crawl config
elif debug_settings.disable_length_filtering and content_length < 50:
    logger.info("FILTER_BYPASSED | filter_type=min_length | ...")
```

**Environment variable**: `DISABLE_LENGTH_FILTERING=true`

**Log output when bypassed**:
```
FILTER_BYPASSED | filter_type=min_length | url=https://... | content_length=35 | normal_min=50 | debug_min=1 | reason=DEBUG_INGESTION disabled length filtering
```

## Document Count Invariant

### Purpose
Detect silent document drops during processing by tracking document count from crawl through to DB write.

### Implementation

**Start tracking** (document_storage_operations.py:113-116):
```python
initial_doc_count = len(crawl_results)
if debug_settings.debug_ingestion:
    logger.info(f"DOC_COUNT_INVARIANT_START | initial_count={initial_doc_count} | source_id={source_id}")
```

**Verification before DB write** (document_storage_operations.py:374-390):
```python
docs_dropped = initial_doc_count - processed_docs
if docs_dropped > 0:
    logger.warning(
        f"DOC_COUNT_INVARIANT_VIOLATION | initial_docs={initial_doc_count} | "
        f"processed_docs={processed_docs} | dropped={docs_dropped} | "
        f"reason=Documents were filtered/dropped during processing"
    )
```

### Expected Logs

**Normal flow (no drops)**:
```
DOC_COUNT_INVARIANT_START | initial_count=5 | source_id=abc123
DOCS_BEFORE_WRITE_COUNT | count=10 | processed_docs=5/5 | avg_chunks_per_doc=2.0
```

**Detected drop (PROBLEM)**:
```
DOC_COUNT_INVARIANT_START | initial_count=5 | source_id=abc123
DOC_COUNT_INVARIANT_VIOLATION | initial_docs=5 | processed_docs=3 | dropped=2 | reason=...
DOCS_BEFORE_WRITE_COUNT | count=6 | processed_docs=3/5 | avg_chunks_per_doc=2.0
```

## Legitimate Filtering (NOT Bypassed)

These filters are **always applied** even in debug mode:

1. **Missing URLs**: Documents without a URL are always skipped
   - Reason: Cannot store or track without URL
   - Location: All storage operations

2. **Binary files**: PDFs, images, videos skipped during recursive crawl
   - Reason: Different processing pipeline needed
   - Location: recursive.py:340-343

3. **Already-embedded URLs**: Resume filtering for incremental updates
   - Reason: Avoid re-processing same content
   - Location: recursive.py:169-174

## Files Modified

1. **python/src/server/services/crawling/strategies/recursive.py**
   - Lines 345-369: Keyword filtering bypass

2. **python/src/server/services/crawling/strategies/single_page.py**
   - Lines 181-200: Minimum length bypass

3. **python/src/server/services/crawling/document_storage_operations.py**
   - Lines 113-116: Document count invariant start
   - Lines 165-187: Empty content filtering bypass (old pipeline)
   - Lines 374-390: Document count invariant verification
   - Lines 647-670: Empty content filtering bypass (new pipeline)

## Testing

### Enable All Bypasses

```bash
DEBUG_INGESTION=true
DISABLE_KEYWORD_FILTERING=true
DISABLE_LENGTH_FILTERING=true
```

### Expected Behavior

1. **Keyword-filtered URLs are crawled**:
   - URLs with "api", "blog", etc. are NOT skipped
   - Log: `FILTER_BYPASSED | filter_type=keyword`

2. **Short content is accepted**:
   - Pages with < 50 chars are NOT rejected during crawl
   - Log: `FILTER_BYPASSED | filter_type=min_length`

3. **Empty content is processed** (if not truly empty):
   - Documents with 0 chars are logged but attempted
   - Log: `FILTER_BYPASSED | filter_type=empty_content`

4. **Document drops are detected**:
   - Any reduction in count triggers warning
   - Log: `DOC_COUNT_INVARIANT_VIOLATION`

### Verification

Run a test crawl and check logs for:
```
DOC_COUNT_INVARIANT_START | initial_count=N
FILTER_BYPASSED | filter_type=...  (multiple times)
DOCS_BEFORE_WRITE_COUNT | processed_docs=N/N  (no drops)
```

If you see `processed_docs=M/N` where M < N, investigate why documents were dropped.

## Next Steps

Task #3: Add RawDocument format detection for PDFs
Task #4: Add DB schema validation
Task #5: Add UI literal text search verification
Task #6: Create golden path test script
