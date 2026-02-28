# Tavily Web Crawling Integration - Implementation Status

## Stage 1: Provider Abstraction & Basic Integration

### ✅ Phase 1: Provider Abstraction (COMPLETED)

**Created Files:**
1. `python/src/server/services/crawling/providers/__init__.py` - Package initialization
2. `python/src/server/services/crawling/providers/base_provider.py` - Abstract provider interface
3. `python/src/server/services/crawling/providers/crawl4ai_provider.py` - Crawl4AI wrapper
4. `python/src/server/services/crawling/providers/tavily_provider.py` - Tavily implementation
5. `python/src/server/services/crawling/provider_factory.py` - Provider factory with fallback

**Key Features:**
- **BaseWebCrawlProvider**: Abstract interface that all providers must implement
  - `crawl()`: Execute crawl with standardized parameters
  - `get_capabilities()`: Return supported features
  - `validate_configuration()`: Check provider setup

- **CrawlResult**: Standardized result format
  - `url`: Crawled URL
  - `markdown`: Extracted content
  - `title`: Page title
  - `metadata`: Provider-specific data

- **CrawlCapability Enum**: Feature flags
  - RECURSIVE_CRAWL, SITEMAP_PARSE, SINGLE_PAGE, BATCH_CRAWL
  - PROGRESS_TRACKING, CANCELLATION, PAUSE_RESUME

- **Error Handling**:
  - `CrawlProviderError`: Base exception with fallback flag
  - `TavilyRateLimitError`: Rate limit handling
  - `TavilyAPIError`: API error handling

**Tavily Provider Implementation:**
- Stage 1 conservative limits:
  - Max depth: 1-3 (clamped from Tavily's 1-5)
  - Max pages: 100 per crawl
  - Timeout: 150 seconds
- Features:
  - Automatic depth clamping
  - Progress simulation (Tavily doesn't provide real-time progress)
  - Title extraction from markdown
  - Credit usage tracking in metadata
  - Fallback on error (rate limit, API errors, empty content)

**Crawl4AI Provider Wrapper:**
- Adapter pattern wrapping existing strategies
- Maintains all current functionality:
  - Batch, recursive, single-page, sitemap strategies
  - Pause/resume support
  - Progress tracking
  - Cancellation support

**Provider Factory:**
- Automatic provider selection based on settings
- Fallback chain: Tavily → Crawl4AI
- Configuration validation
- API key checking

### ✅ Phase 2: Database Schema (COMPLETED)

**Created Files:**
1. `migration/0.1.0/019_add_crawl_provider.sql` - Database migration

**Schema Changes:**
- Added `crawl_provider` column to `archon_sources` (default: 'crawl4ai')
- Added `provider_metadata` JSONB column for provider-specific data
- Added indices for performance
- Added settings:
  - `TAVILY_API_KEY` (encrypted)
  - `DEFAULT_CRAWL_PROVIDER` (tavily/crawl4ai)
  - `TAVILY_MAX_PAGES` (100)
  - `TAVILY_MAX_DEPTH` (3)

### ✅ Phase 3: Tavily Provider (COMPLETED)

**Dependencies Added:**
- `tavily-python>=0.5.0` added to `pyproject.toml` in server group

**Implementation:**
- Full Tavily provider with Stage 1 features
- Conservative limits per plan
- Comprehensive error handling
- Progress simulation
- Fallback support

### ✅ Phase 4: API Updates (COMPLETED)

**Modified Files:**
1. `python/src/server/api_routes/knowledge_api.py`

**Changes:**
- Added `crawl_provider` field to `KnowledgeItemRequest`
- Added `crawl_provider` field to `CrawlRequest`
- Both fields optional (None = use default from settings)
- Backward compatible (existing API calls work unchanged)

### ✅ Phase 5: Service Integration (COMPLETED)

**Modified Files:**
1. `python/src/server/services/crawling/crawling_service.py`

**Changes Made:**

**1. Added Provider Factory Integration:**
- Imported `CrawlProviderFactory` and base provider classes
- Created new method `_crawl_with_provider()` that:
  - Gets provider instance from factory based on request
  - Attempts crawl with requested provider (Tavily or Crawl4AI)
  - Handles fallback on provider errors
  - Tracks provider metadata (credits, pages, fallback info)

**2. Provider-Specific Crawling Logic:**
- **Tavily Provider Path:**
  - Direct call to Tavily API with progress callbacks
  - Converts CrawlResult objects to dict format for pipeline compatibility
  - Extracts credit usage and metadata
  - Returns results with provider metadata

- **Crawl4AI Provider Path:**
  - Delegates to existing `_crawl_by_url_type()` method
  - Maintains all current functionality (sitemap, llms.txt, recursive crawl)
  - Tracks pages crawled in metadata

**3. Fallback Handling:**
- Catches `CrawlProviderError` with fallback support
- Automatically falls back to Crawl4AI on provider failures
- Logs fallback reason in provider_metadata
- Handles unexpected errors gracefully

**4. Provider Metadata Storage:**
- Stores `crawl_provider` field in `archon_sources` table
- Stores `provider_metadata` JSONB with:
  - `provider`: Actual provider used
  - `requested_provider`: What was requested
  - `pages_crawled`: Number of pages processed
  - `total_credits_used`: Tavily credits consumed (if applicable)
  - `fallback_used`: Whether fallback occurred
  - `fallback_reason`: Why fallback was triggered

**5. Updated Orchestration Flow:**
- Both discovery and normal crawl paths use `_crawl_with_provider()`
- Provider metadata unpacked from crawl results
- Metadata stored in database after document processing
- Progress tracking updated to show provider type

**6. Helper Method:**
- `_convert_crawl_results_to_dicts()`: Converts CrawlResult objects to dict format
  - Ensures compatibility with existing document storage pipeline
  - Preserves url, markdown, title, metadata fields

**Key Features:**
- ✅ Seamless integration with existing pipeline
- ✅ No breaking changes to existing code
- ✅ Full fallback support (Tavily → Crawl4AI)
- ✅ Provider metadata tracking for monitoring
- ✅ Progress callbacks work with both providers
- ✅ Cancellation support maintained
- ✅ Error handling per CLAUDE.md guidelines

### ⏳ Phase 6: Frontend Updates (PENDING)

**Next Steps:**
1. Add Tavily API key input to Settings UI
2. Add default provider dropdown
3. Add provider selector to crawl form
4. Display provider on source cards

**Files to Modify:**
- `archon-ui-main/src/features/knowledge/` (Settings and crawl UI)

### ⏳ Phase 7: Testing & Validation (PENDING)

**Created Test Files:**
1. `python/tests/server/services/crawling/providers/test_base_provider.py`
2. `python/tests/server/services/crawling/providers/test_tavily_provider.py`
3. `python/tests/server/services/crawling/providers/test_provider_simple.py`

**Test Coverage:**
- Base provider interface and error classes ✅
- Tavily provider with mocked API calls ✅
- Crawl4AI provider wrapper (TODO)
- Provider factory (TODO)
- End-to-end integration (TODO)

**Known Issues:**
- Test imports have dependency chain issues (openai.__spec__ is None)
- Need to run tests in isolation or fix import structure

## Summary

**Completed (Phases 1-5):**
- ✅ Provider abstraction layer designed and implemented
- ✅ Tavily provider fully implemented with Stage 1 features
- ✅ Crawl4AI wrapper created (adapter pattern)
- ✅ Provider factory with fallback logic
- ✅ Database migration prepared
- ✅ API models updated for provider selection
- ✅ tavily-python package added to dependencies
- ✅ **Service integration completed** - CrawlingService now uses providers
- ✅ **Provider metadata storage** - Tracks provider usage in database
- ✅ **Fallback logic implemented** - Graceful degradation on errors

**Pending (Phases 6-7):**
- ⏳ Frontend UI updates
- ⏳ Testing and validation
- ⏳ Production hardening

## Next Actions

1. **Run Database Migration**:
   ```bash
   psql -h localhost -U postgres -d archon < migration/0.1.0/019_add_crawl_provider.sql
   ```

2. **Test Backend Integration**:
   ```bash
   # Start backend
   uv run python -m src.server.main

   # Test with Crawl4AI (default, no API key needed)
   curl -X POST http://localhost:8181/api/knowledge-items/crawl \
     -H "Content-Type: application/json" \
     -d '{
       "url": "https://example.com",
       "max_depth": 2,
       "crawl_provider": "crawl4ai"
     }'

   # Test with Tavily (requires API key in settings)
   curl -X POST http://localhost:8181/api/knowledge-items/crawl \
     -H "Content-Type: application/json" \
     -d '{
       "url": "https://example.com",
       "max_depth": 2,
       "crawl_provider": "tavily"
     }'
   ```

3. **Verify Database Storage**:
   ```bash
   # Check provider metadata is stored
   psql -h localhost -U postgres -d archon -c \
     "SELECT source_id, crawl_provider, provider_metadata FROM archon_sources ORDER BY created_at DESC LIMIT 5;"
   ```

4. **Frontend Updates** (Phase 6):
   - Settings UI for Tavily API key
   - Provider selection dropdown in crawl form
   - Provider display on source cards
   - Display credit usage for Tavily crawls

5. **Testing** (Phase 7):
   - Fix test import issues
   - Write integration tests
   - Manual testing with real Tavily API
   - Test fallback scenarios (invalid API key, rate limits)
   - Performance testing (compare Tavily vs Crawl4AI)

## Architecture Decisions

**Provider Abstraction Pattern:**
- Chose abstract base class over protocol for explicit interface contract
- Standardized `CrawlResult` format ensures pipeline compatibility
- Capabilities enum allows feature detection

**Fallback Strategy:**
- Tavily → Crawl4AI fallback chain
- Graceful degradation on API key missing
- Configurable fallback behavior

**Error Handling:**
- Fail fast for configuration errors (per CLAUDE.md)
- Complete but log errors for batch operations
- Never accept corrupted data (empty content raises error)

**Stage 1 Limitations:**
- No preflight mapping or cost estimation (future stages)
- Simulated progress (Tavily doesn't provide real-time updates)
- Conservative limits (100 pages, depth 1-3)

## References

- [ADR-005](/home/zebastjan/dev/archon/docs/ADRs/ ADR-005: Adopt Tavily for Web Crawling in Archon Ingestion.md) - Source requirements
- [Tavily Crawl API Docs](https://docs.tavily.com/documentation/api-reference/endpoint/crawl)
- [Tavily Python SDK](https://github.com/tavily-ai/tavily-python)
