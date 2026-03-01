"""
Debug Ingestion Configuration

Settings to enable detailed logging and bypass filters during ingestion debugging.
Helps verify each stage of the pipeline: crawl → preprocess → chunk → embed → DB write → UI search.
"""

import os
from dataclasses import dataclass


@dataclass
class DebugIngestionSettings:
    """
    Debug settings for ingestion pipeline.

    Enable these via environment variables to get detailed visibility into
    what's happening at each stage and prevent silent filtering/failures.
    """

    # Master debug switch - enables all debug logging
    debug_ingestion: bool = False

    # Limit number of pages crawled (useful for single-page testing)
    # None = no limit, 1 = single page golden path test
    max_crawl_pages: int | None = None

    # Bypass keyword-based content filtering that might drop documents
    disable_keyword_filtering: bool = False

    # Bypass length/relevance filtering that might drop documents
    disable_length_filtering: bool = False

    # Fail hard on DB errors instead of logging and continuing
    # Useful for debugging to catch issues immediately
    fail_on_db_error: bool = True

    # Save intermediate outputs (crawl results, chunks) to /tmp/archon_debug/
    log_intermediate_outputs: bool = False

    # Force a specific crawl provider (crawl4ai, tavily, or None for default)
    force_crawl_provider: str | None = None


# Singleton instance
_debug_settings: DebugIngestionSettings | None = None


def get_debug_settings() -> DebugIngestionSettings:
    """
    Get debug ingestion settings singleton.

    Reads from environment variables:
    - DEBUG_INGESTION (bool)
    - MAX_CRAWL_PAGES (int or empty)
    - DISABLE_KEYWORD_FILTERING (bool)
    - DISABLE_LENGTH_FILTERING (bool)
    - FAIL_ON_DB_ERROR (bool)
    - LOG_INTERMEDIATE_OUTPUTS (bool)
    - FORCE_CRAWL_PROVIDER (str or empty)
    """
    global _debug_settings
    if _debug_settings is None:
        # Parse MAX_CRAWL_PAGES
        max_pages_str = os.getenv("MAX_CRAWL_PAGES")
        max_pages = int(max_pages_str) if max_pages_str and max_pages_str.strip() else None

        _debug_settings = DebugIngestionSettings(
            debug_ingestion=os.getenv("DEBUG_INGESTION", "false").lower() in ("true", "1", "yes"),
            max_crawl_pages=max_pages,
            disable_keyword_filtering=os.getenv("DISABLE_KEYWORD_FILTERING", "false").lower() in ("true", "1", "yes"),
            disable_length_filtering=os.getenv("DISABLE_LENGTH_FILTERING", "false").lower() in ("true", "1", "yes"),
            fail_on_db_error=os.getenv("FAIL_ON_DB_ERROR", "true").lower() in ("true", "1", "yes"),
            log_intermediate_outputs=os.getenv("LOG_INTERMEDIATE_OUTPUTS", "false").lower()
            in ("true", "1", "yes"),
            force_crawl_provider=os.getenv("FORCE_CRAWL_PROVIDER") or None,
        )
    return _debug_settings
