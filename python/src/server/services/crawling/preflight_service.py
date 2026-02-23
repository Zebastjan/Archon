"""Pre-flight check service for estimating crawl scope before execution.

This service provides visibility into crawl scope and resource requirements
before users commit to large crawls. It estimates:
- URL count
- Token cost
- Processing time
- Quality signals
- Domain boundary violations
"""

from __future__ import annotations

import hashlib
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from typing import Any
from urllib.parse import urljoin, urlparse

from pydantic import BaseModel, Field, field_validator
from requests import get as requests_get


class PreflightRequest(BaseModel):
    """Request model for pre-flight check endpoint."""

    url: str = Field(..., description="URL to estimate crawl scope for")
    max_depth: int = Field(default=2, ge=1, le=10, description="Maximum crawl depth")
    strategy: str = Field(
        default="auto",
        pattern="^(auto|sitemap|llms.txt|recursive)$",
        description="Crawl strategy to use",
    )
    sample_size: int = Field(default=5, ge=1, le=10, description="Number of pages to sample for quality")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        parsed = urlparse(v)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("Invalid URL format")
        if parsed.scheme not in ("http", "https"):
            raise ValueError("URL must use http or https scheme")
        return v


@dataclass
class QualitySignals:
    """Quality signals extracted from page content.

    This is extensible - additional fields can be added for different
    types of content quality assessment.
    """

    content_to_markup_ratio: float = 0.0
    code_snippet_density: float = 0.0
    has_structure: bool = False
    word_count: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.extra, bool):
            self.extra = {}

    def __getattr__(self, name: str) -> Any:
        if name in ("content_to_markup_ratio", "code_snippet_density", "has_structure", "word_count"):
            try:
                return super().__getattr__(name)
            except AttributeError:
                return self.extra.get(name)
        if name == "extra":
            raise AttributeError(name)
        return self.extra.get(name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in ("content_to_markup_ratio", "code_snippet_density", "has_structure", "word_count"):
            object.__setattr__(self, name, value)
        elif name == "extra":
            object.__setattr__(self, name, value)
        else:
            if not hasattr(self, "extra"):
                object.__setattr__(self, "extra", {})
            self.extra[name] = value

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result.pop("extra", None)
        result.update(self.extra)
        return result


@dataclass
class PreflightEstimate:
    """Response model for pre-flight check results."""

    url_count_estimate: int = 0
    estimated_tokens: int = 0
    estimated_duration_minutes: int = 0
    quality_score: float = 0.0
    quality_signals: QualitySignals = field(default_factory=QualitySignals)
    discovered_via: str = "unknown"
    crawl_strategy_recommendation: str = "recursive"
    sample_urls: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    domain_violations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "url_count_estimate": self.url_count_estimate,
            "estimated_tokens": self.estimated_tokens,
            "estimated_duration_minutes": self.estimated_duration_minutes,
            "quality_score": self.quality_score,
            "quality_signals": self.quality_signals.to_dict(),
            "discovered_via": self.discovered_via,
            "crawl_strategy_recommendation": self.crawl_strategy_recommendation,
            "sample_urls": self.sample_urls,
            "warnings": self.warnings,
            "domain_violations": self.domain_violations,
        }


class CrawlPreflightService:
    """Service for pre-flight crawl estimation."""

    _cache: dict[str, tuple[float, PreflightEstimate]] = {}
    _cache_ttl: int = 300

    def __init__(self):
        self._discovery_service = None

    @property
    def discovery_service(self):
        if self._discovery_service is None:
            from src.server.services.crawling.discovery_service import DiscoveryService

            self._discovery_service = DiscoveryService()
        return self._discovery_service

    async def estimate_crawl(
        self,
        url: str,
        max_depth: int = 2,
        strategy: str = "auto",
        sample_size: int = 5,
    ) -> PreflightEstimate:
        """Estimate crawl scope and resource requirements.

        Args:
            url: URL to estimate
            max_depth: Maximum crawl depth
            strategy: Crawl strategy (auto, sitemap, llms.txt, recursive)
            sample_size: Number of pages to sample

        Returns:
            PreflightEstimate with scope and quality estimates
        """
        request = PreflightRequest(url=url, max_depth=max_depth, strategy=strategy, sample_size=sample_size)

        cached = self._get_cached_result(request.url, request.max_depth)
        if cached:
            return cached

        discovered_url = self.discovery_service.discover_files(request.url)

        if request.strategy == "auto":
            crawl_strategy = self._recommend_strategy(discovered_url, request.url)
        else:
            crawl_strategy = request.strategy

        enumerate_result = self._discover_and_enumerate(request.url, crawl_strategy, request.max_depth)

        url_count = enumerate_result.get("url_count", 0)
        sample_urls = enumerate_result.get("sample_urls", [])[:10]

        sampled_content = await self._sample_pages(sample_urls[: request.sample_size])

        quality_signals = self._aggregate_quality_signals(sampled_content)
        quality_score = self._calculate_overall_quality(quality_signals)

        domain_violations = []
        for content in sampled_content:
            violations = self._detect_domain_violations(content, request.url)
            domain_violations.extend(violations)

        estimated_tokens = self._estimate_total_tokens([len(c) for c in sampled_content], url_count)

        warnings = []
        if url_count > 1000:
            warnings.append(f"Large site detected: {url_count} URLs estimated")
        if domain_violations:
            warnings.append(f"External domains found: {len(set(domain_violations))} unique")
        if quality_score < 0.3:
            warnings.append("Low quality score detected")

        result = PreflightEstimate(
            url_count_estimate=url_count,
            estimated_tokens=estimated_tokens,
            estimated_duration_minutes=max(1, url_count // 50),
            quality_score=quality_score,
            quality_signals=quality_signals,
            discovered_via=crawl_strategy,
            crawl_strategy_recommendation=crawl_strategy,
            sample_urls=sample_urls,
            warnings=warnings,
            domain_violations=list(set(domain_violations)),
        )

        self._cache_result(request.url, request.max_depth, result)
        return result

    def _get_cache_key(self, url: str, depth: int) -> str:
        return hashlib.sha256(f"{url}:{depth}".encode()).hexdigest()

    def _get_cached_result(self, url: str, depth: int) -> PreflightEstimate | None:
        key = self._get_cache_key(url, depth)
        if key in self._cache:
            timestamp, estimate = self._cache[key]
            if time.time() - timestamp < self._cache_ttl:
                return estimate
        return None

    def _cache_result(self, url: str, depth: int, estimate: PreflightEstimate) -> None:
        key = self._get_cache_key(url, depth)
        self._cache[key] = (time.time(), estimate)

    def _recommend_strategy(self, discovered_url: str | None, base_url: str) -> str:
        if discovered_url is None:
            return "recursive"
        if "llms" in discovered_url:
            return "llms.txt"
        if "sitemap" in discovered_url:
            return "sitemap"
        return "recursive"

    def _discover_and_enumerate(self, url: str, strategy: str, max_depth: int) -> dict[str, Any]:
        if strategy == "sitemap":
            return self._enumerate_sitemap(url)
        elif strategy == "llms.txt":
            return self._enumerate_llms(url)
        else:
            return self._estimate_recursive(url, max_depth)

    def _enumerate_sitemap(self, url: str) -> dict[str, Any]:
        discovered = self.discovery_service.discover_files(url)
        if not discovered or "sitemap" not in discovered:
            return self._estimate_recursive(url, 2)

        urls = self._enumerate_sitemap_urls(discovered)
        return {"url_count": len(urls), "sample_urls": urls[:20]}

    def _enumerate_sitemap_urls(self, sitemap_url: str) -> list[str]:
        try:
            response = requests_get(sitemap_url, timeout=30, stream=True)
            if response.status_code != 200:
                return []

            content = response.text

            if "<sitemapindex" in content.lower():
                return self._parse_sitemap_index(content, sitemap_url)

            return self._parse_sitemap_urls(content)
        except Exception:
            return []

    def _parse_sitemap_urls(self, xml_content: str) -> list[str]:
        urls = []
        try:
            root = ET.fromstring(xml_content)
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            for url_elem in root.findall(".//sm:loc", ns) or root.findall(".//loc"):
                loc = url_elem.text
                if loc:
                    urls.append(loc)
        except ET.ParseError:
            pass
        return urls

    def _parse_sitemap_index(self, content: str, base_url: str) -> list[str]:
        urls = []
        try:
            root = ET.fromstring(content)
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            for sitemap in root.findall(".//sm:sitemap", ns) or root.findall(".//sitemap"):
                loc_elem = sitemap.find("sm:loc", ns) or sitemap.find("loc")
                if loc_elem is not None and loc_elem.text:
                    child_urls = self._enumerate_sitemap_urls(loc_elem.text)
                    urls.extend(child_urls)
        except ET.ParseError:
            pass
        return urls

    def _enumerate_llms(self, url: str) -> dict[str, Any]:
        base_url = url.rstrip("/")
        discovered = self.discovery_service.discover_files(base_url)
        if not discovered or "llms" not in discovered:
            return self._estimate_recursive(url, 2)

        urls = self._enumerate_llms_urls(discovered)
        return {"url_count": len(urls), "sample_urls": urls[:20]}

    def _enumerate_llms_urls(self, llms_url: str) -> list[str]:
        try:
            response = requests_get(llms_url, timeout=30)
            if response.status_code != 200:
                return []

            content = response.text
            urls = []

            url_pattern = re.compile(r"https?://[^\s\)\]\>]+")
            for match in url_pattern.finditer(content):
                url = match.group(0).rstrip(".,;:)")
                if url:
                    urls.append(url)

            return list(set(urls))
        except Exception:
            return []

    def _estimate_recursive(self, url: str, max_depth: int) -> dict[str, Any]:
        html = self._fetch_page(url)
        if not html:
            return {"url_count": 1, "sample_urls": [url]}

        links = self._extract_links(html, url)
        sample_urls = [url] + links[:5]

        links_on_page = len(links)
        estimated = self._calculate_recursive_estimate(links_on_page, max_depth)

        return {"url_count": estimated, "sample_urls": sample_urls}

    def _calculate_recursive_estimate(self, links_on_page: int, max_depth: int) -> int:
        multiplier = 1.5**max_depth
        return int(links_on_page * multiplier)

    def _fetch_page(self, url: str) -> str | None:
        try:
            response = requests_get(url, timeout=30, stream=True)
            if response.status_code == 200:
                return response.text
        except Exception:
            pass
        return None

    def _extract_links(self, html: str, base_url: str) -> list[str]:
        links = []
        anchor_pattern = re.compile(r'<a[^>]+href=["\']([^"\']+)["\']', re.IGNORECASE)
        for match in anchor_pattern.finditer(html):
            href = match.group(1)
            if href.startswith(("http://", "https://")):
                links.append(href)
            elif href.startswith("/"):
                links.append(urljoin(base_url, href))
        return list(set(links))

    async def _sample_pages(self, urls: list[str]) -> list[str]:
        content_list = []
        for url in urls:
            content = self._fetch_page(url)
            if content:
                content_list.append(content)
        return content_list

    def _aggregate_quality_signals(self, content_list: list[str]) -> QualitySignals:
        if not content_list:
            return QualitySignals()

        total_content_ratio: float = 0.0
        total_code_density: float = 0.0
        total_words = 0
        has_structure_count = 0

        for content in content_list:
            total_content_ratio += self._calculate_content_ratio(content)
            total_code_density += self._calculate_code_density(content)
            has_structure_count += 1 if self._check_structure(content) else 0
            total_words += len(content.split())

        count = len(content_list)
        return QualitySignals(
            content_to_markup_ratio=total_content_ratio / count,
            code_snippet_density=total_code_density / count,
            has_structure=has_structure_count > count / 2,
            word_count=total_words // count,
        )

    def _calculate_content_ratio(self, html: str) -> float:
        text_only = re.sub(r"<[^>]+>", "", html)
        text_len = len(text_only.strip())
        html_len = len(html)
        if html_len == 0:
            return 0.0
        return min(text_len / html_len, 1.0)

    def _calculate_code_density(self, html: str) -> float:
        code_matches = len(re.findall(r"<pre[^>]*>|<code[^>]*>", html, re.IGNORECASE))
        if len(html) == 0:
            return 0.0
        return code_matches / (len(html) / 1000)

    def _check_structure(self, html: str) -> bool:
        has_headings = bool(re.search(r"<h[1-6][^>]*>", html, re.IGNORECASE))
        has_semantic = bool(
            re.search(
                r"<header|<nav|<main|<article|<section|<aside|<footer",
                html,
                re.IGNORECASE,
            )
        )
        return has_headings or has_semantic

    def _detect_domain_violations(self, html: str, base_url: str) -> list[str]:
        violations = []
        base_domain = urlparse(base_url).netloc

        anchor_pattern = re.compile(r'<a[^>]+href=["\']([^"\']+)["\']', re.IGNORECASE)
        for match in anchor_pattern.finditer(html):
            href = match.group(1)
            if href.startswith(("http://", "https://")):
                parsed = urlparse(href)
                if parsed.netloc and parsed.netloc != base_domain:
                    if not parsed.netloc.endswith(f".{base_domain}"):
                        violations.append(href)

        return violations

    def _calculate_overall_quality(self, signals: QualitySignals) -> float:
        content_weight = 0.4
        code_weight = 0.2
        structure_weight = 0.2
        words_weight = 0.2

        content_score = min(signals.content_to_markup_ratio / 0.5, 1.0)
        code_score = min(signals.code_snippet_density / 0.2, 1.0)
        structure_score = 1.0 if signals.has_structure else 0.3
        words_score = min(signals.word_count / 2000, 1.0)

        return (
            content_score * content_weight
            + code_score * code_weight
            + structure_score * structure_weight
            + words_score * words_weight
        )

    def _estimate_tokens(self, content: str) -> int:
        return len(content) // 4

    def _estimate_total_tokens(self, sample_sizes: list[int], url_count: int) -> int:
        if not sample_sizes or url_count == 0:
            return 0
        avg_tokens = sum(s // 4 for s in sample_sizes) // len(sample_sizes)
        return avg_tokens * url_count
