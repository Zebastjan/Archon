# DB Schema Validation Logging - Complete

## Overview

Comprehensive schema validation has been added before all database writes to verify that documents have all required fields and expected metadata. This prevents "data is there but UI can't see it" issues by catching schema mismatches before insertion.

## Validation Checks

### 1. Required Fields Validation

**Fields checked** (archon_crawled_pages table):
- `url` - Document URL (required for tracking)
- `chunk_number` - Chunk sequence number
- `content` - Actual text content
- `metadata` - Metadata object
- `source_id` - Source identifier

**Log output when missing**:
```
DB_WRITE_SCHEMA_ISSUES | batch_num=1 | issues_count=2 | sample_issues=[
  {'record_index': 5, 'url': 'https://...', 'missing_fields': ['source_id']},
  {'record_index': 8, 'url': 'https://...', 'missing_fields': ['metadata']}
]
```

### 2. Embedding Field Validation

**Checks for at least one of**:
- `embedding_1536` (OpenAI text-embedding-3-small/ada-002)
- `embedding_3072` (OpenAI text-embedding-3-large)
- `embedding_768` (Alternative models)

**Log output when missing**:
```
DB_WRITE_SCHEMA_ISSUES | issues_count=1 | sample_issues=[
  {'record_index': 3, 'url': 'https://...', 'missing_fields': ['embedding (no embedding_* field found)']}
]
```

### 3. Required Metadata Fields

**Fields checked** (within metadata object):
- `source_type` - Type of source (url, file, pdf, etc.)
- `knowledge_type` - Knowledge category (technical, general, etc.)

**Log output when missing**:
```
DB_WRITE_SCHEMA_ISSUES | issues_count=1 | sample_issues=[
  {'record_index': 0, 'url': 'https://...', 'missing_metadata_fields': ['source_type']}
]
```

### 4. Recommended Metadata Fields

**Fields recommended for UI** (warns if missing):
- `title` - Document/chunk title (used by UI for display)
- `headers` - Section headers (used for breadcrumbs)

**Log output when missing**:
```
DB_WRITE_METADATA_RECOMMENDATION | missing_recommended=['title', 'headers'] | note=UI may use these fields for display
```

### 5. Data Quality Checks

**Quality issues detected**:

**Very Short Content** (< 10 chars):
```
DB_WRITE_QUALITY_ISSUES | issues_count=1 | sample_issues=[
  {'record_index': 2, 'issue': 'very_short_content', 'content_length': 5}
]
```

**Zero Embeddings** (all values are 0):
```
DB_WRITE_QUALITY_ISSUES | issues_count=1 | sample_issues=[
  {'record_index': 4, 'issue': 'zero_embedding', 'field': 'embedding_1536'}
]
```

## Complete Log Flow

### Perfect Document (No Issues)

```
DB_WRITE_START | table=archon_crawled_pages | batch_num=1/3 | row_count=25
DB_WRITE_SCHEMA_CHECK | required_fields=['url', 'chunk_number', 'content', 'metadata', 'source_id'] | all_fields_present=['url', 'chunk_number', 'content', 'metadata', 'source_id', 'embedding_1536', 'llm_chat_model', 'embedding_model', 'embedding_dimension', 'page_id'] | embedding_field=embedding_1536 | embedding_dim=1536
DB_WRITE_SAMPLE_RECORD | url=https://docs.example.com/intro | content_length=2345 | metadata_fields=['source_type', 'knowledge_type', 'title', 'headers'] | source_id=abc123
DB_WRITE_BATCH_SUCCESS | batch_num=1/3 | rows_inserted=25 | total_stored=25
```

### Document with Issues

```
DB_WRITE_START | table=archon_crawled_pages | batch_num=1/1 | row_count=10
DB_WRITE_SCHEMA_ISSUES | batch_num=1 | issues_count=2 | sample_issues=[
  {'record_index': 3, 'url': 'https://bad.com/page', 'missing_fields': ['source_id']},
  {'record_index': 5, 'url': 'https://bad.com/doc', 'missing_metadata_fields': ['source_type']}
]
DB_WRITE_METADATA_RECOMMENDATION | missing_recommended=['title'] | note=UI may use these fields for display
DB_WRITE_QUALITY_ISSUES | batch_num=1 | issues_count=1 | sample_issues=[
  {'record_index': 7, 'issue': 'very_short_content', 'content_length': 8}
]
DB_WRITE_SCHEMA_CHECK | required_fields=[...] | all_fields_present=[...] | embedding_field=embedding_1536 | embedding_dim=1536
DB_WRITE_SAMPLE_RECORD | url=https://example.com/doc | content_length=2100 | metadata_fields=['source_type', 'knowledge_type', 'headers'] | source_id=abc123
DB_WRITE_BATCH_SUCCESS | batch_num=1/1 | rows_inserted=10 | total_stored=10
```

## Validation Logic Location

**File**: `python/src/server/services/storage/document_storage_service.py`
**Lines**: 478-560 (approximately)

### Validation Sequence

1. **Define schema** (lines 480-483):
   ```python
   REQUIRED_FIELDS = ["url", "chunk_number", "content", "metadata", "source_id"]
   REQUIRED_METADATA_FIELDS = ["source_type", "knowledge_type"]
   RECOMMENDED_METADATA_FIELDS = ["title", "headers"]
   EMBEDDING_FIELDS = ["embedding_1536", "embedding_3072", "embedding_768"]
   ```

2. **Validate each record** (lines 486-520):
   - Check required fields present
   - Check at least one embedding field exists
   - Check required metadata fields
   - Collect all issues

3. **Check recommended fields** (lines 523-530):
   - Warn if missing but don't fail

4. **Quality checks** (lines 532-555):
   - Empty/short content detection
   - Zero embedding detection

5. **Log results** (lines 536-560):
   - Log schema issues if found
   - Log sample record structure
   - Log quality issues if found

## Common Schema Issues and Solutions

### Issue: Missing source_id

**Log**:
```
DB_WRITE_SCHEMA_ISSUES | sample_issues=[{'missing_fields': ['source_id']}]
```

**Cause**: Document not associated with a source during processing
**Fix**: Ensure `original_source_id` is passed through pipeline
**Location**: Check `document_storage_operations.py` line 146

### Issue: Missing embedding field

**Log**:
```
DB_WRITE_SCHEMA_ISSUES | sample_issues=[{'missing_fields': ['embedding (no embedding_* field found)']}]
```

**Cause**: Embedding generation failed or wrong column name used
**Fix**: Check embedding service API key, verify dimension mapping
**Location**: Check `document_storage_service.py` lines 420-433

### Issue: Missing metadata.source_type

**Log**:
```
DB_WRITE_SCHEMA_ISSUES | sample_issues=[{'missing_metadata_fields': ['source_type']}]
```

**Cause**: Metadata not populated correctly during crawl
**Fix**: Check metadata construction in crawling strategies
**Location**: Check crawl result metadata assembly

### Issue: Zero embeddings

**Log**:
```
DB_WRITE_QUALITY_ISSUES | sample_issues=[{'issue': 'zero_embedding', 'field': 'embedding_1536'}]
```

**Cause**: Embedding API returned zeros (rate limit, auth failure, network error)
**Fix**: Check embedding service logs, verify API key, check rate limits
**Location**: Check `embedding_service.py` for API errors

### Issue: Very short content

**Log**:
```
DB_WRITE_QUALITY_ISSUES | sample_issues=[{'issue': 'very_short_content', 'content_length': 5}]
```

**Cause**: Chunking produced tiny chunks or content extraction failed
**Fix**: Review chunking configuration, verify content extraction
**Location**: Check `document_storage_operations.py` chunking section

## UI Field Mapping

The UI expects these fields from `archon_crawled_pages`:

**For chunk display**:
- `content` → Text to display
- `url` → Source URL
- `metadata.title` → Chunk title
- `metadata.headers` → Breadcrumb/section path
- `metadata.source_type` → Source type badge
- `metadata.knowledge_type` → Category filter

**For search**:
- `embedding_*` → Vector similarity search
- `content` → Full-text search
- `metadata` → Metadata filtering

## Testing

### Enable Debug Mode

```bash
DEBUG_INGESTION=true
```

### Test Schema Validation

1. **Run a normal crawl** and check logs for:
   ```
   DB_WRITE_SCHEMA_CHECK | required_fields=[...] | all_fields_present=[...]
   ```

2. **Verify no schema issues**:
   - Should NOT see `DB_WRITE_SCHEMA_ISSUES`
   - Should NOT see `DB_WRITE_QUALITY_ISSUES`

3. **Check recommended fields**:
   - May see `DB_WRITE_METADATA_RECOMMENDATION` (just a warning)
   - Verify `missing_recommended` doesn't include critical fields

### Simulate Schema Issues

To test validation, temporarily modify document construction to omit a field:

```python
# In document_storage_service.py, comment out a field:
data = {
    "url": batch_urls[j],
    # "source_id": source_id,  # TEMPORARILY COMMENTED FOR TESTING
    "chunk_number": batch_chunk_numbers[j],
    # ...
}
```

Expected log:
```
DB_WRITE_SCHEMA_ISSUES | issues_count=25 | sample_issues=[{'missing_fields': ['source_id']}, ...]
```

## Next Steps

- Task #5: Add UI literal text search verification
- Task #6: Create golden path test script
