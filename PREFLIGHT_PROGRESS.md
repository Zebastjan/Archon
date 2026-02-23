# Pre-flight Check Service - Work in Progress

## Status: In Progress

### What We're Building
A pre-flight check service that estimates crawl scope before execution:
- URL count estimates
- Token cost estimates  
- Processing time estimates
- Quality signals (content ratio, code density, structure)
- Domain boundary violation detection

### Files Created

1. **`python/src/server/services/crawling/preflight_service.py`** (456 lines)
   - `PreflightRequest` - Pydantic model for API requests
   - `PreflightEstimate` - Response with estimates and quality signals
   - `QualitySignals` - Extensible dataclass for content quality
   - `CrawlPreflightService` - Core service logic
   - Discovery strategies: sitemap, llms.txt, recursive
   - Built-in caching (5 minute TTL)

2. **`python/tests/test_preflight_service.py`** (840 lines)
   - ~36 tests covering:
     - Request validation (URL, depth, strategy)
     - Response structure and serialization
     - URL enumeration (sitemap, llms.txt, recursive)
     - Token estimation
     - Quality signals extraction
     - Domain violation detection
     - Error handling
     - Caching behavior
     - Discovery strategy recommendations

### Test Results
- ✅ ~28 tests passing (core functionality works)
- ⚠️ ~8 tests failing (need better HTTP mocks for integration-style tests)

### Completed
- ✅ Ruff linting passes on both files

### What's Left
1. Fix remaining ~8 failing tests (or simplify them)
2. Add API endpoint in `knowledge_api.py` (POST /api/knowledge-items/preflight)
3. Connect to frontend when ready

### API Design (from tests)
```python
# Request
{
  "url": "https://docs.example.com/",
  "max_depth": 2,           # 1-10, default 2
  "strategy": "auto",       # "auto", "sitemap", "llms.txt", "recursive"
  "sample_size": 5          # 1-10, default 5
}

# Response
{
  "url_count_estimate": 150,
  "estimated_tokens": 45000,
  "estimated_duration_minutes": 8,
  "quality_score": 0.72,
  "quality_signals": {
    "content_to_markup_ratio": 0.45,
    "code_snippet_density": 0.12,
    "has_structure": true,
    "word_count": 3200
  },
  "discovered_via": "sitemap",
  "crawl_strategy_recommendation": "sitemap",
  "sample_urls": ["https://docs.example.com/", "..."],
  "warnings": ["Large site detected"],
  "domain_violations": ["https://external.example.com"]
}
```

### Notes
- Chunking work is orthogonal - not part of this task
- Pre-flight is independent of pause/resume pipeline - can be worked on in parallel
- Quality signals are extensible - can add new metrics without breaking API
- Caching prevents re-computation for same URL+depth combinations
