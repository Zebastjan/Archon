# Crawl4AI Audit Report for Archon

**Date:** February 2026  
**Version Analyzed:** Crawl4AI 0.7.4

---

## 1. How Archon Uses Crawl4AI

### Version
**crawl4ai==0.7.4** (specified in `python/pyproject.toml` lines 47 and 135)

### Interface
Archon uses the **Python library directly** (`from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig`), NOT the Docker API server. The crawler runs within the `archon-server` container using Playwright-managed browsers.

### Entry Points
1. **CrawlerManager** (`crawler_manager.py`) - Initializes `AsyncWebCrawler` with `BrowserConfig`
2. **Crawl4aiProvider** (`crawl4ai_provider.py`) - Provider interface wrapping strategies
3. **Three crawling strategies:**
   - `RecursiveCrawlStrategy` - Default, follows internal links
   - `BatchCrawlStrategy` - Flat list of URLs
   - `SinglePageCrawlStrategy` - Individual URLs with retry logic

### Current Configuration

| Parameter | Default | Used In |
|-----------|---------|---------|
| `browser_type` | chromium | BrowserConfig |
| `viewport` | 1920x1080 | BrowserConfig |
| `headless` | true | BrowserConfig |
| **max_depth** | **2** | Recursive (user input) |
| **CRAWL_BATCH_SIZE** | **50** | URLs per depth level |
| **CRAWL_MAX_CONCURRENT** | **10** | Parallel browser sessions |
| **CRAWL_PAGE_TIMEOUT** | **30000-45000ms** | Docs: 30s, Regular: 45s |
| **CRAWL_WAIT_STRATEGY** | **domcontentloaded** | Wait strategy |
| **CRAWL_DELAY_BEFORE_HTML** | **0.5-1.0s** | JS rendering wait |
| `cache_mode` | BYPASS (recursive) | Recursive |
| `scan_full_page` | true | Lazy loading |

### Content Processing
- **MarkdownGenerator**: `DefaultMarkdownGenerator` with code block preservation
- **Content Filter**: `PruningContentFilter(threshold=0.2, threshold_type="fixed")` for recursive crawling
- **Special handling**: Documentation sites (Docusaurus, VitePress, GitBook, MkDocs, Docsify) get wait selectors and enhanced timeouts

---

## 2. Version Analysis & Upgrade Considerations

### Current State
Archon is on **v0.7.4** (released around August 2025 based on PyPI timestamps).

### Available Versions
| Version | Release Date | Key Changes |
|---------|--------------|-------------|
| v0.7.5 | Sep 2025 | Docker Hooks System, LLM integration improvements |
| v0.7.6 | Oct 2025 | Webhook support for Docker job queue API |
| v0.7.7 | Nov 2025 | Self-hosting/monitoring, Prometheus, browser pool management |
| **v0.8.0** | Jan 2026 | **Security fixes** (RCE, LFI), breaking changes |

### Security Concerns (Critical)
**v0.8.0 contains critical security fixes** that don't affect us since we use the Python library, not Docker API:
- RCE via hooks (Docker API only)
- LFI via file:// URLs (Docker API only)

### Upgrade Recommendation

**Stay on v0.7.4 for now** OR upgrade to **v0.7.7** (latest stable before v0.8.0):

**Why stay:**
- v0.8.0 breaking changes don't affect Python library usage
- Current config works well
- No critical fixes for our use case

**Why upgrade to v0.7.7:**
- Browser pool management improvements
- Better monitoring capabilities
- Bug fixes for async LLM extraction, DFS crawling
- Still no breaking changes for Python library users

**Action:** Update to v0.7.7 when ready. The change is just version bump in pyproject.toml.

---

## 3. Configuration vs. Workflow Analysis

### What Archon Does Right
- ✅ Documentation site detection with specific wait selectors
- ✅ Retry logic (3 attempts with exponential backoff)
- ✅ Code block preservation in markdown
- ✅ MemoryAdaptiveDispatcher prevents resource exhaustion
- ✅ Image disabled for speed
- ✅ Proper timeout configuration

### Problems Identified

| Issue | Impact | Root Cause |
|-------|--------|------------|
| **No max_pages cap** | Users can accidentally crawl thousands of pages | `CRAWL_BATCH_SIZE` limits batch but not total |
| **Depth = 2 default** | May crawl too many pages for targeted use | No user-facing depth clamping |
| **domcontentloaded** | May miss JS-rendered content | Fast but potentially incomplete |
| **Fixed prune threshold** | May filter valid content or keep too much junk | No adaptive filtering |
| **No URL filtering** | Crawls all internal links, including blogroll, tags | No keyword/domain filters |

### Why Users See Slowness/Junk
1. **No max_pages**: A depth=2 crawl on a large site could explore 50+ pages × 50 batch = thousands
2. **Broad link following**: No filtering for "docs", "api", "guide" - catches everything
3. **Low prune threshold (0.2)**: Keeps more content including navigation junk

---

## 4. Recommended Best-Practice Settings

### For Archon's Use Case (Targeted Site Crawling)

```python
# Recommended CrawlerRunConfig for targeted crawling
CrawlerRunConfig(
    # Performance
    cache_mode=CacheMode.BYPASS,  # Fresh crawl each time
    stream=True,
    page_timeout=45000,  # 45s for regular, 60s for docs
    
    # Wait strategy - use networkidle for more complete content
    wait_until="networkidle",  # Changed from domcontentloaded
    delay_before_return_html=0.5,
    
    # Content quality
    markdown_generator=markdown_generator,
    exclude_all_images=True,  # Already disabled in BrowserConfig
    
    # Anti-detection
    remove_overlay_elements=True,
    process_iframes=True,
    scan_full_page=True,
)
```

### Recommended Default Settings

| Setting | Current | Recommended | Why |
|---------|---------|-------------|-----|
| max_depth (user input) | 1-5 | **Clamp to 1-3** | Prevent runaway crawls |
| max_pages (hard cap) | None | **100-200** | Prevent accidental large crawls |
| CRAWL_BATCH_SIZE | 50 | **30** | Smaller batches = better progress reporting |
| CRAWL_MAX_CONCURRENT | 10 | **5-8** | Lower memory, more stable |
| CRAWL_WAIT_STRATEGY | domcontentloaded | **networkidle** | More complete JS rendering |
| Pruning threshold | 0.2 | **0.3** | More aggressive junk removal |

### Content Filter Recommendations

For targeted crawling, add **keyword-based filtering**:

```python
# Option 1: Use BM25ContentFilter (if available in 0.7.x)
from crawl4ai.content_filter_strategy import BM25ContentFilter

filter = BM25ContentFilter(
    keywords=["docs", "api", "guide", "tutorial", "reference"],  # Subject-specific
    min_score=1.0,
)

# Option 2: Increase pruning threshold
prune_filter = PruningContentFilter(
    threshold=0.3,  # Increased from 0.2
    threshold_type="fixed"
)
```

### Example Recommended Configuration (Python)

```python
# In recursive.py - Recommended settings

# For documentation sites (aggressive filtering)
run_config = CrawlerRunConfig(
    cache_mode=CacheMode.BYPASS,
    stream=True,
    markdown_generator=self.markdown_generator,
    wait_until="networkidle",  # Changed: wait for network idle
    page_timeout=60000,       # Increased: 60s for docs
    delay_before_return_html=1.0,  # Increased: more JS time
    wait_for_images=False,
    scan_full_page=True,
    exclude_all_images=True,
    remove_overlay_elements=True,
    process_iframes=True,
)

# Max pages enforcement (add to recursive.py)
MAX_PAGES_HARD_CAP = 200  # Add this guard

async def crawl_recursive_with_progress(...):
    # Add early termination
    if total_processed >= MAX_PAGES_HARD_CAP:
        logger.warning(f"Hit max_pages cap ({MAX_PAGES_HARD_CAP}), stopping crawl")
        break
```

---

## 5. Data Validation Layer

### Per-Page Validation (Implement Now)

```python
def validate_crawl_result(result: dict) -> tuple[bool, str]:
    """
    Validate a single page crawl result.
    Returns (is_valid, reason_if_invalid)
    """
    markdown = result.get("markdown", "")
    url = result.get("url", "")
    
    # 1. Minimum content length
    if len(markdown) < 500:  # Too short = likely junk
        return False, f"Content too short ({len(markdown)} chars)"
    
    # 2. Check for error pages
    error_patterns = [
        "404 not found", "page not found", "not found",
        "login required", "sign in", "access denied",
        "forbidden", "error 403", "error 404",
        "captcha", "verify you're human"
    ]
    markdown_lower = markdown.lower()
    if any(pattern in markdown_lower for pattern in error_patterns):
        return False, "Error page detected"
    
    # 3. Check for login/redirect pages
    if any(x in markdown_lower for x in ["click here to login", "sign in to continue"]):
        return False, "Login page detected"
    
    # 4. Text-to-markup ratio (rough proxy)
    # If very little actual text vs HTML tags, likely not useful
    word_count = len(markdown.split())
    if word_count < 100:
        return False, f"Too few words ({word_count})"
    
    return True, "OK"
```

### Job-Level Sanity Checks (Implement Now)

```python
def validate_crawl_job(results: list[dict], max_depth: int) -> dict:
    """
    Validate entire crawl job for sanity.
    Returns dict with warnings and stats.
    """
    total = len(results)
    if total == 0:
        return {"status": "error", "reason": "No pages crawled"}
    
    # Check short content ratio
    short_pages = sum(1 for r in results if len(r.get("markdown", "")) < 1000)
    short_ratio = short_pages / total if total > 0 else 0
    
    warnings = []
    if short_ratio > 0.5:
        warnings.append(f"High junk ratio: {short_ratio:.0%} pages are very short")
    
    if total >= 150:  # Arbitrary threshold
        warnings.append(f"Large crawl: {total} pages - verify this was intentional")
    
    # Check for depth exhaustion
    expected_max = sum(50 * (i + 1) for i in range(max_depth))  # Rough estimate
    if total >= expected_max * 0.9:
        warnings.append("Crawl may have hit site limits or be larger than expected")
    
    return {
        "status": "ok" if not warnings else "warning",
        "warnings": warnings,
        "stats": {
            "total_pages": total,
            "short_pages": short_pages,
            "short_ratio": short_ratio,
        }
    }
```

### Use LLM-Based Scoring (Later Phase)

For a "smart quality scoring" phase:
- Use lightweight embedding to score page relevance
- Check topical relevance against source metadata/tags
- Flag pages that look "off-topic" for exclusion

---

## Summary

### Current State
- **Version:** 0.7.4 (OK to upgrade to 0.7.7)
- **Interface:** Python library (not Docker API)
- **Default depth:** 2
- **No max_pages cap** ⚠️
- **Uses PruningContentFilter** with threshold=0.2

### Key Recommendations

1. **Add max_pages hard cap** (200) to prevent runaway crawls
2. **Clamp user depth** to 1-3 range
3. **Change wait_until** from domcontentloaded to networkidle for better JS rendering
4. **Increase prune threshold** to 0.3 or add keyword-based filtering
5. **Add per-page validation** (min length, error detection)
6. **Add job-level sanity checks** (warn on high junk ratio, large crawls)
7. **Upgrade to v0.7.7** when ready (simple version bump)
