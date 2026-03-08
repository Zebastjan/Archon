# TODO: Pre-flight Checks for Crawling

**Status**: Planned - Waiting for restart functionality to complete

**Priority**: Medium (referenced in ROADMAP.md as "Batch Processing & Bootstrapping")

## Summary

Implement pre-flight checks that estimate crawl scope and resource requirements **before** users commit to large crawls.

**Problem**: Users currently have no visibility into what they're about to ingest until the crawl is running. Large documentation sites can consume significant resources unexpectedly.

**Solution**: Add lightweight `/api/knowledge-items/preflight` endpoint that:
- Auto-discovers crawl strategy (sitemap, llms.txt, recursive)
- Estimates URL count, token cost, processing time
- Samples 3-5 pages for quality signals (content ratio, code density)
- Flags domain violations (e.g., GitHub #905 issue)

## Scope (MVP)

**Backend Only:**
- New service: `python/src/server/services/crawling/preflight_service.py` (~300-400 lines)
- New endpoint: `POST /api/knowledge-items/preflight` in `knowledge_api.py`
- Simple heuristics for quality scoring (no ML models)
- Character-based token estimation (no tiktoken dependency)

**Deferred to Later:**
- Batch processing (multiple URLs at once)
- Re-crawl depth adjustment
- Frontend UI
- Quality filtering during actual crawls
- Advanced quality scoring (ML vs heuristics - needs discussion)

## Implementation Plan

**Detailed plan**: `/home/zebastjan/.claude/plans/flickering-spinning-hanrahan.md`

**Key reuse:**
- `discovery_service.py` - Auto-detection of llms.txt, sitemaps
- `url_handler.py` - URL validation
- `site_config.py` - Sitemap parsing

**Success criteria:**
- URL count estimates within 30% accuracy
- Token estimates within 40% accuracy
- Pre-flight completes in < 10 seconds
- Domain violations detected in sample pages

## Related Issues

- GitHub #905: Domain boundary violations (spade-mas docs crawling external aiohttp docs)
  - Pre-flight will **detect and warn** about violations
  - Fixing actual crawler is deferred to future work

## Testing Strategy

1. Unit tests for URL enumeration, quality signals
2. Integration test: Pre-flight vs actual crawl accuracy validation
3. Manual API testing with FastAPI, LangChain, and spade-mas docs
4. Performance testing (< 10 second target)

## Next Steps

When ready to implement:
1. Review detailed plan in `.claude/plans/flickering-spinning-hanrahan.md`
2. Create `preflight_service.py` with URL enumeration strategies
3. Add `/api/knowledge-items/preflight` endpoint
4. Write unit and integration tests
5. Validate accuracy on real documentation sites

---

**Note**: This work is paused until restart/checkpoint functionality is complete.
