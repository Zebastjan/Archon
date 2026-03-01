# Literal Text Search Verification - Complete

## Overview

End-to-end verification has been added to confirm that documents written to the database are immediately searchable via the UI search API. This verification extracts a distinctive word from stored content, performs a RAG search, and validates the word is findable - confirming the complete pipeline from DB write → vector search → UI results.

## Verification Flow

### 1. Trigger Conditions

The verification runs automatically after successful document storage when:
- `DEBUG_INGESTION=true` is set
- At least one chunk was stored (`total_chunks_stored > 0`)

### 2. Verification Steps

**Step 1: Extract Distinctive Word**
```python
# Find rare/distinctive words (8+ characters, alphabetic, not common)
words = re.findall(r'\b[A-Za-z]{8,}\b', test_content)
# Filter out common words like "document", "function", "implementation"
distinctive_words = [w for w in words if w.lower() not in common_words]
test_word = distinctive_words[0]
```

**Step 2: Wait for DB Commit**
```python
# Brief delay to ensure DB write is fully committed
await asyncio.sleep(0.5)
```

**Step 3: Perform RAG Search**
```python
from ..search.rag_service import RAGService
rag_service = RAGService(client)

success, result = await rag_service.perform_rag_query(
    query=test_word,
    source=None,  # Search across all sources
    match_count=5,
    return_mode="chunks"
)
```

**Step 4: Validate Results**
```python
# Check if the test word appears in any returned chunks
for chunk in results:
    if test_word.lower() in chunk.get("content", "").lower():
        found_in_results = True
        break
```

## Log Output Formats

### Verification Start

```
LITERAL_TEXT_SEARCH_VERIFICATION_START | Verifying documents are searchable via UI
```

### Word Selection

```
LITERAL_TEXT_SEARCH_VERIFICATION_WORD | test_word=installation | source_url=https://docs.example.com/guide | word_length=12
```

### Verification Success

```
LITERAL_TEXT_SEARCH_VERIFICATION_PASS | test_word=installation | found_in_results=true | results_count=5 | match_details={'result_index': 0, 'similarity_score': 0.92, 'chunk_id': 'abc123', 'content_preview': 'Installation instructions for...'}
```

### Verification Failures

**Word not found in results:**
```
LITERAL_TEXT_SEARCH_VERIFICATION_FAIL | test_word=installation | found_in_results=false | results_count=5 | reason=word_not_in_returned_chunks
```

**Search API failed:**
```
LITERAL_TEXT_SEARCH_VERIFICATION_FAIL | test_word=installation | search_failed=true | error=Connection timeout
```

**No distinctive words found:**
```
LITERAL_TEXT_SEARCH_VERIFICATION_SKIP | reason=no_distinctive_words_found | content_preview=This is a short document...
```

**Verification error (storage still succeeded):**
```
LITERAL_TEXT_SEARCH_VERIFICATION_ERROR | error=RAGService initialization failed | verification_failed_but_storage_succeeded
```

## Implementation Location

**File**: `python/src/server/services/storage/document_storage_service.py`
**Lines**: 708-788 (approximately)

### Code Structure

```python
# Task #5: UI Literal Text Search Verification
if debug_settings.debug_ingestion and total_chunks_stored > 0:
    try:
        # 1. Extract distinctive word (8+ chars, rare)
        words = re.findall(r'\b[A-Za-z]{8,}\b', test_content)
        distinctive_words = [w for w in words if w.lower() not in common_words]

        if distinctive_words:
            test_word = distinctive_words[0]

            # 2. Wait for DB commit
            await asyncio.sleep(0.5)

            # 3. Perform RAG search
            rag_service = RAGService(client)
            success, result = await rag_service.perform_rag_query(
                query=test_word,
                source=None,
                match_count=5,
                return_mode="chunks"
            )

            # 4. Validate results
            for chunk in results:
                if test_word.lower() in chunk_content.lower():
                    found_in_results = True
                    break

            # 5. Log pass/fail
            if found_in_results:
                logger.info("LITERAL_TEXT_SEARCH_VERIFICATION_PASS | ...")
            else:
                logger.warning("LITERAL_TEXT_SEARCH_VERIFICATION_FAIL | ...")

    except Exception as e:
        logger.warning("LITERAL_TEXT_SEARCH_VERIFICATION_ERROR | ...")
```

## Common Verification Issues and Solutions

### Issue: No distinctive words found

**Log**:
```
LITERAL_TEXT_SEARCH_VERIFICATION_SKIP | reason=no_distinctive_words_found | content_preview=...
```

**Cause**: Content is too short or contains only common words
**Fix**: Normal behavior for very short documents (e.g., single-sentence chunks)
**Action**: Verify content is being chunked properly

### Issue: Word not found in results

**Log**:
```
LITERAL_TEXT_SEARCH_VERIFICATION_FAIL | test_word=installation | found_in_results=false | results_count=5
```

**Cause**: Potential issues:
- Embedding generation failed (zero vectors)
- Vector similarity too low
- Word was filtered out during preprocessing
- DB write partially failed

**Fix**: Check earlier logs for:
1. `DB_WRITE_QUALITY_ISSUES` - zero embeddings or short content
2. `EMBEDDING_RESULT` - verify embeddings were generated
3. `DB_WRITE_BATCH_SUCCESS` - confirm all batches inserted

### Issue: Search API failed

**Log**:
```
LITERAL_TEXT_SEARCH_VERIFICATION_FAIL | search_failed=true | error=...
```

**Cause**: RAG service or database error
**Fix**: Check:
- Supabase connection is active
- Embedding provider API key is valid
- Database has vector extension enabled (`pgvector`)

### Issue: Verification timeout

**Log**:
```
LITERAL_TEXT_SEARCH_VERIFICATION_ERROR | error=Task timeout | verification_failed_but_storage_succeeded
```

**Cause**: RAG search taking too long
**Fix**: Increase the sleep delay or check database performance

## Expected Log Flow

### Successful End-to-End Verification

```
1. DB_WRITE_BATCH_SUCCESS | batch_num=1/1 | rows_inserted=25 | total_stored=25
2. LITERAL_TEXT_SEARCH_VERIFICATION_START | Verifying documents are searchable via UI
3. LITERAL_TEXT_SEARCH_VERIFICATION_WORD | test_word=installation | source_url=https://docs.example.com/guide | word_length=12
4. LITERAL_TEXT_SEARCH_VERIFICATION_PASS | test_word=installation | found_in_results=true | results_count=5 | match_details={'result_index': 0, 'similarity_score': 0.92}
```

### Failed Verification (Documents Not Searchable)

```
1. DB_WRITE_BATCH_SUCCESS | batch_num=1/1 | rows_inserted=25 | total_stored=25
2. LITERAL_TEXT_SEARCH_VERIFICATION_START | Verifying documents are searchable via UI
3. LITERAL_TEXT_SEARCH_VERIFICATION_WORD | test_word=installation | source_url=https://docs.example.com/guide | word_length=12
4. LITERAL_TEXT_SEARCH_VERIFICATION_FAIL | test_word=installation | found_in_results=false | results_count=0 | reason=word_not_in_returned_chunks
```

## What This Verification Confirms

✅ **Documents were written to database** - Storage completed successfully
✅ **Embeddings were generated** - RAG search can find similar content
✅ **Vector similarity works** - Search returns relevant chunks
✅ **UI search API is functional** - End-to-end search pipeline works
✅ **Content is retrievable** - Exact word match found in results

## What This Verification Does NOT Check

❌ **UI rendering** - Only verifies API layer, not frontend display
❌ **Complex search queries** - Only tests literal word matching
❌ **Pagination** - Only checks first 5 results
❌ **Metadata filtering** - Searches across all sources
❌ **Hybrid search** - Uses default RAG settings

## Integration with Other Debug Tasks

This verification completes the end-to-end pipeline validation:

1. **Task #1: Debug Logging** - Provides visibility into each stage
2. **Task #2: Filtering Bypass** - Ensures documents aren't dropped silently
3. **Task #3: Format Detection** - Confirms document type is correct
4. **Task #4: Schema Validation** - Verifies all required fields are present
5. **Task #5: Literal Text Search** ✅ - Confirms documents are searchable
6. **Task #6: Golden Path Test** (pending) - Automated test combining all tasks

## Testing

### Enable Debug Mode

```bash
DEBUG_INGESTION=true
```

### Test Successful Verification

1. Run a normal crawl or document upload
2. Check logs for:
   ```
   LITERAL_TEXT_SEARCH_VERIFICATION_PASS | test_word=... | found_in_results=true
   ```
3. Verify the test word appears in the UI search results manually

### Test Failure Detection

1. Temporarily disable vector embedding:
   ```python
   # In document_storage_service.py, set embeddings to zeros
   embedding_1536 = [0.0] * 1536  # Force zero embedding
   ```
2. Run crawl/upload
3. Expected log:
   ```
   DB_WRITE_QUALITY_ISSUES | issue=zero_embedding
   LITERAL_TEXT_SEARCH_VERIFICATION_FAIL | found_in_results=false
   ```

### Verify Word Selection

1. Upload a document with known distinctive words
2. Check log for:
   ```
   LITERAL_TEXT_SEARCH_VERIFICATION_WORD | test_word=...
   ```
3. Verify word is actually distinctive (8+ chars, not common)

## Next Steps

- Task #6: Create golden path test script (automated end-to-end test)

## Configuration

### Environment Variables

- `DEBUG_INGESTION` - Enables verification (default: false)

### Customization Options

**Adjust word selection criteria**:
```python
# Minimum word length (currently 8 characters)
words = re.findall(r'\b[A-Za-z]{8,}\b', test_content)

# Common words to exclude
common_words = {"document", "function", "example", ...}
```

**Adjust DB commit wait time**:
```python
# Currently 0.5 seconds
await asyncio.sleep(0.5)  # Increase if needed
```

**Adjust search parameters**:
```python
# Currently searches top 5 results
match_count=5  # Increase to check more results
```

## Troubleshooting

### Verification always skips

**Check**: Is `DEBUG_INGESTION=true` set?
```bash
echo $DEBUG_INGESTION  # Should output "true"
```

### Verification fails but UI search works

**Cause**: Test word might not be in top 5 results
**Fix**: Increase `match_count` parameter or choose more distinctive words

### Verification passes but UI shows no results

**Cause**: UI might be filtering by source or using different search parameters
**Fix**: Check UI search filters and compare with verification search query

## Files Modified

1. **python/src/server/services/storage/document_storage_service.py**
   - Lines 708-788: Added literal text search verification after DB write
   - Imports: Added `re` module for word extraction
   - Dependencies: Uses RAGService for search verification

## Dependencies

- `RAGService` - Performs the actual search
- `re` module - Extracts distinctive words from content
- `asyncio.sleep` - Waits for DB commit to complete
- Debug settings from `config/debug_ingestion.py`
