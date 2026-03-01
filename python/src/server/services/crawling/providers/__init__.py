"""
Crawling Provider Abstractions

This module provides provider abstractions for different web crawling services.
Each provider implements the BaseWebCrawlProvider interface to ensure consistent
behavior across different crawling backends.
"""

from .base_provider import BaseWebCrawlProvider, CrawlCapability, CrawlProviderType, CrawlResult

__all__ = ["BaseWebCrawlProvider", "CrawlCapability", "CrawlProviderType", "CrawlResult"]
