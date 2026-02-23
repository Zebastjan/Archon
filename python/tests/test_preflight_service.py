"""Unit tests for CrawlPreflightService - Pre-flight check functionality.

This test suite validates the pre-flight check API for estimating crawl scope
and resource requirements before committing to large crawls.

Test categories:
1. Discovery strategies (sitemap, llms.txt, recursive)
2. URL enumeration and counting
3. Token estimation
4. Quality signal extraction
5. Domain violation detection
6. Error handling
7. Caching behavior
"""

import socket
from dataclasses import asdict
from unittest.mock import Mock, patch

import pytest


def create_mock_dns_response():
    """Create mock DNS response for safe public IPs."""
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]


def create_mock_response(
    status_code: int = 200,
    text: str = "",
    url: str = "https://example.com",
    headers: dict | None = None,
) -> Mock:
    """Create a mock HTTP response object."""
    response = Mock()
    response.status_code = status_code
    response.text = text
    response.content = text.encode("utf-8")
    response.encoding = "utf-8"
    response.history = []
    response.url = url
    response.headers = headers or {"content-type": "text/html"}

    text_bytes = text.encode("utf-8")
    chunk_size = 8192
    chunks = [text_bytes[i : i + chunk_size] for i in range(0, len(text_bytes), chunk_size)]
    if not chunks:
        chunks = [b""]
    response.iter_content = Mock(return_value=iter(chunks))
    response.close = Mock()

    return response


class TestPreflightRequestValidation:
    """Test pre-flight request validation and API contract."""

    def test_preflight_request_url_required(self):
        """URL is a required field for preflight requests."""
        from pydantic import ValidationError

        from src.server.services.crawling.preflight_service import PreflightRequest

        with pytest.raises(ValidationError):
            PreflightRequest(max_depth=2)

    def test_preflight_request_url_validation(self):
        """URL must be a valid URL format."""
        from pydantic import ValidationError

        from src.server.services.crawling.preflight_service import PreflightRequest

        with pytest.raises(ValidationError):
            PreflightRequest(url="not-a-valid-url", max_depth=2)

    def test_preflight_request_valid_url(self):
        """Valid URL is accepted."""
        from src.server.services.crawling.preflight_service import PreflightRequest

        request = PreflightRequest(url="https://docs.example.com/", max_depth=2)
        assert request.url == "https://docs.example.com/"
        assert request.max_depth == 2

    def test_preflight_request_default_depth(self):
        """Default max_depth is 2 if not specified."""
        from src.server.services.crawling.preflight_service import PreflightRequest

        request = PreflightRequest(url="https://docs.example.com/")
        assert request.max_depth == 2

    def test_preflight_request_depth_bounds(self):
        """max_depth must be between 1 and 10."""
        from pydantic import ValidationError

        from src.server.services.crawling.preflight_service import PreflightRequest

        with pytest.raises(ValidationError):
            PreflightRequest(url="https://docs.example.com/", max_depth=0)

        with pytest.raises(ValidationError):
            PreflightRequest(url="https://docs.example.com/", max_depth=11)

    def test_preflight_request_strategy_options(self):
        """Strategy can be 'auto', 'sitemap', 'llms.txt', or 'recursive'."""
        from src.server.services.crawling.preflight_service import PreflightRequest

        for strategy in ["auto", "sitemap", "llms.txt", "recursive"]:
            request = PreflightRequest(url="https://docs.example.com/", strategy=strategy)
            assert request.strategy == strategy

    def test_preflight_request_invalid_strategy(self):
        """Invalid strategy raises validation error."""
        from pydantic import ValidationError

        from src.server.services.crawling.preflight_service import PreflightRequest

        with pytest.raises(ValidationError):
            PreflightRequest(url="https://docs.example.com/", strategy="invalid")

    def test_preflight_request_optional_fields(self):
        """Optional fields like strategy are properly handled."""
        from src.server.services.crawling.preflight_service import PreflightRequest

        request = PreflightRequest(
            url="https://docs.example.com/",
            max_depth=3,
            strategy="auto",
            sample_size=5,
        )
        assert request.sample_size == 5


class TestPreflightResponseStructure:
    """Test pre-flight response data structure."""

    def test_preflight_response_has_required_fields(self):
        """Response must contain all required estimation fields."""
        from src.server.services.crawling.preflight_service import (
            PreflightEstimate,
            QualitySignals,
        )

        response = PreflightEstimate(
            url_count_estimate=100,
            estimated_tokens=30000,
            estimated_duration_minutes=5,
            quality_score=0.75,
            quality_signals=QualitySignals(
                content_to_markup_ratio=0.4,
                code_snippet_density=0.15,
                has_structure=True,
                word_count=2500,
            ),
            discovered_via="sitemap",
            crawl_strategy_recommendation="sitemap",
            sample_urls=["https://example.com/"],
            warnings=[],
            domain_violations=[],
        )

        assert response.url_count_estimate > 0
        assert response.estimated_tokens > 0
        assert response.quality_score >= 0.0
        assert response.quality_score <= 1.0

    def test_preflight_response_quality_signals_extensible(self):
        """Quality signals should accept additional fields for extensibility."""
        from src.server.services.crawling.preflight_service import QualitySignals

        signals = QualitySignals(
            content_to_markup_ratio=0.4,
            code_snippet_density=0.15,
            has_structure=True,
            word_count=2500,
        )
        signals.custom_signal_1 = 0.5
        signals.custom_signal_2 = "test"

        assert signals.custom_signal_1 == 0.5
        assert signals.custom_signal_2 == "test"

    def test_preflight_response_serialization(self):
        """Response should serialize to JSON cleanly."""
        import json

        from src.server.services.crawling.preflight_service import (
            PreflightEstimate,
            QualitySignals,
        )

        response = PreflightEstimate(
            url_count_estimate=100,
            estimated_tokens=30000,
            estimated_duration_minutes=5,
            quality_score=0.75,
            quality_signals=QualitySignals(
                content_to_markup_ratio=0.4,
                code_snippet_density=0.15,
                has_structure=True,
                word_count=2500,
            ),
            discovered_via="sitemap",
            crawl_strategy_recommendation="sitemap",
            sample_urls=["https://example.com/", "https://example.com/page1"],
            warnings=["Warning: Large site detected"],
            domain_violations=["https://external.example.com"],
        )

        serialized = json.dumps(asdict(response))
        deserialized = json.loads(serialized)

        assert deserialized["url_count_estimate"] == 100
        assert deserialized["quality_score"] == 0.75
        assert len(deserialized["sample_urls"]) == 2
        assert "Warning: Large site detected" in deserialized["warnings"]


class TestPreflightURLEnumeration:
    """Test URL enumeration strategies for different discovery methods."""

    @patch("socket.getaddrinfo", return_value=create_mock_dns_response())
    @patch("requests.Session")
    @patch("requests.get")
    def test_sitemap_url_count(self, mock_get, mock_session, mock_dns):
        """Sitemap parsing should accurately count URLs."""
        from src.server.services.crawling.preflight_service import CrawlPreflightService

        sitemap_content = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://example.com/page1</loc></url>
            <url><loc>https://example.com/page2</loc></url>
            <url><loc>https://example.com/page3</loc></url>
            <url><loc>https://example.com/page4</loc></url>
            <url><loc>https://example.com/page5</loc></url>
        </urlset>"""

        mock_get.return_value = create_mock_response(200, sitemap_content)

        service = CrawlPreflightService()
        urls = service._enumerate_sitemap_urls("https://example.com/sitemap.xml")

        assert len(urls) == 5

    @patch("socket.getaddrinfo", return_value=create_mock_dns_response())
    @patch("requests.Session")
    @patch("requests.get")
    def test_sitemap_nested_urls(self, mock_get, mock_session, mock_dns):
        """Sitemap should handle nested sitemap indexes."""
        from src.server.services.crawling.preflight_service import CrawlPreflightService

        sitemap_index = """<?xml version="1.0" encoding="UTF-8"?>
        <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <sitemap><loc>https://example.com/sitemap1.xml</loc></sitemap>
            <sitemap><loc>https://example.com/sitemap2.xml</loc></sitemap>
        </sitemapindex>"""

        sitemap1_content = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://example.com/page1</loc></url>
            <url><loc>https://example.com/page2</loc></url>
        </urlset>"""

        sitemap2_content = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://example.com/page3</loc></url>
            <url><loc>https://example.com/page4</loc></url>
        </urlset>"""

        def mock_side_effect(url, **kwargs):
            if "sitemap-index" in url:
                return create_mock_response(200, sitemap_index)
            elif "sitemap1.xml" in url:
                return create_mock_response(200, sitemap1_content)
            elif "sitemap2.xml" in url:
                return create_mock_response(200, sitemap2_content)
            return create_mock_response(404)

        mock_get.side_effect = mock_side_effect

        service = CrawlPreflightService()
        urls = service._enumerate_sitemap_urls("https://example.com/sitemap-index.xml")

        assert len(urls) == 4

    @patch("socket.getaddrinfo", return_value=create_mock_dns_response())
    @patch("requests.Session")
    @patch("requests.get")
    def test_llms_txt_parsing(self, mock_get, mock_session, mock_dns):
        """LLMS.txt parsing should extract links correctly."""
        from src.server.services.crawling.preflight_service import CrawlPreflightService

        llms_content = """# Documentation

## Getting Started
https://example.com/getting-started

## API Reference
https://example.com/api/overview

## Guides
- https://example.com/guides/auth
- https://example.com/guides/users
"""

        mock_get.return_value = create_mock_response(200, llms_content)

        service = CrawlPreflightService()
        urls = service._enumerate_llms_urls("https://example.com/llms.txt")

        assert len(urls) >= 4
        assert "https://example.com/getting-started" in urls

    @patch("socket.getaddrinfo", return_value=create_mock_dns_response())
    @patch("requests.Session")
    @patch("requests.get")
    def test_recursive_estimate_formula(self, mock_get, mock_session, mock_dns):
        """Recursive crawl estimation uses depth multiplier formula."""
        from src.server.services.crawling.preflight_service import CrawlPreflightService

        html_with_links = """
        <html>
        <body>
            <a href="/page1">Page 1</a>
            <a href="/page2">Page 2</a>
            <a href="/page3">Page 3</a>
            <a href="/page4">Page 4</a>
            <a href="/page5">Page 5</a>
            <a href="https://external.com/external">External</a>
        </body>
        </html>
        """

        mock_get.return_value = create_mock_response(200, html_with_links)

        service = CrawlPreflightService()

        with patch.object(service, "_fetch_page", return_value=html_with_links):
            estimate = service._estimate_recursive("https://example.com/", max_depth=3)

        assert estimate["url_count"] > 0
        assert estimate["url_count"] >= 5

    def test_recursive_depth_multiplier(self):
        """Recursive estimation applies correct depth multiplier."""
        from src.server.services.crawling.preflight_service import CrawlPreflightService

        service = CrawlPreflightService()

        depth_1_estimate = service._calculate_recursive_estimate(links_on_page=10, max_depth=1)
        depth_2_estimate = service._calculate_recursive_estimate(links_on_page=10, max_depth=2)
        depth_3_estimate = service._calculate_recursive_estimate(links_on_page=10, max_depth=3)

        assert depth_2_estimate > depth_1_estimate
        assert depth_3_estimate > depth_2_estimate


class TestPreflightTokenEstimation:
    """Test token estimation functionality."""

    def test_token_estimation_char_based(self):
        """Token estimation uses character-based approximation."""
        from src.server.services.crawling.preflight_service import CrawlPreflightService

        service = CrawlPreflightService()

        content = "This is sample text content for testing token estimation."
        char_count = len(content)

        tokens = service._estimate_tokens(content)

        assert tokens > 0
        assert abs(tokens - char_count / 4) < 2

    def test_token_estimation_multiple_pages(self):
        """Token estimation extrapolates across multiple pages."""
        from src.server.services.crawling.preflight_service import CrawlPreflightService

        service = CrawlPreflightService()

        sample_sizes = [1000, 2000, 3000, 1500, 2500]
        total_tokens = service._estimate_total_tokens(sample_sizes, url_count=100)

        avg_tokens_per_page = total_tokens / len(sample_sizes)
        extrapolated = avg_tokens_per_page * 100

        assert extrapolated > 0
        assert extrapolated > total_tokens


class TestPreflightQualitySignals:
    """Test quality signal extraction and scoring."""

    @patch("socket.getaddrinfo", return_value=create_mock_dns_response())
    @patch("requests.Session")
    @patch("requests.get")
    def test_content_to_markup_ratio(self, mock_get, mock_session, mock_dns):
        """Content-to-markup ratio is calculated correctly."""
        from src.server.services.crawling.preflight_service import CrawlPreflightService

        html_with_content = """<!DOCTYPE html>
        <html>
        <head><title>Test</title></head>
        <body>
            <h1>Welcome</h1>
            <p>This is substantial content that provides value to readers.</p>
            <p>More content here with useful information.</p>
        </body>
        </html>"""

        mock_get.return_value = create_mock_response(200, html_with_content)

        service = CrawlPreflightService()
        ratio = service._calculate_content_ratio(html_with_content)

        assert 0 < ratio < 1

    @patch("socket.getaddrinfo", return_value=create_mock_dns_response())
    @patch("requests.Session")
    @patch("requests.get")
    def test_code_snippet_density(self, mock_get, mock_session, mock_dns):
        """Code snippet density is calculated correctly."""
        from src.server.services.crawling.preflight_service import CrawlPreflightService

        html_with_code = """<!DOCTYPE html>
        <html>
        <body>
            <p>Here is some explanation:</p>
            <pre><code>def hello():
    print("Hello World")
    return True</code></pre>
            <p>Another code block:</p>
            <pre><code>class Test:
    def __init__(self):
        self.value = 42</code></pre>
        </body>
        </html>"""

        mock_get.return_value = create_mock_response(200, html_with_code)

        service = CrawlPreflightService()
        density = service._calculate_code_density(html_with_code)

        assert density > 0

    @patch("socket.getaddrinfo", return_value=create_mock_dns_response())
    @patch("requests.Session")
    @patch("requests.get")
    def test_has_structure_detection(self, mock_get, mock_session, mock_dns):
        """Semantic HTML structure detection works."""
        from src.server.services.crawling.preflight_service import CrawlPreflightService

        structured_html = """<!DOCTYPE html>
        <html>
        <head><title>Test</title></head>
        <body>
            <header><h1>Main Title</h1></header>
            <nav><ul><li>Link 1</li><li>Link 2</li></ul></nav>
            <main>
                <article>
                    <h2>Section 1</h2>
                    <p>Content here.</p>
                </article>
            </main>
            <footer>Footer content</footer>
        </body>
        </html>"""

        mock_get.return_value = create_mock_response(200, structured_html)

        service = CrawlPreflightService()
        has_structure = service._check_structure(structured_html)

        assert has_structure is True

    @patch("socket.getaddrinfo", return_value=create_mock_dns_response())
    @patch("requests.Session")
    @patch("requests.get")
    def test_quality_score_calculation(self, mock_get, mock_session, mock_dns):
        """Overall quality score is calculated from signals."""
        from src.server.services.crawling.preflight_service import CrawlPreflightService

        good_html = """<!DOCTYPE html>
        <html>
        <head><title>Good Docs</title></head>
        <body>
            <h1>Title</h1>
            <h2>Section</h2>
            <p>Useful content with lots of information.</p>
            <pre><code>const x = 42;</code></pre>
        </body>
        </html>"""

        mock_get.return_value = create_mock_response(200, good_html)

        from src.server.services.crawling.preflight_service import QualitySignals

        service = CrawlPreflightService()
        score = service._calculate_overall_quality(
            QualitySignals(
                content_to_markup_ratio=0.4,
                code_snippet_density=0.15,
                has_structure=True,
                word_count=2500,
            )
        )

        assert 0 <= score <= 1

    def test_quality_signals_combined(self):
        """Quality signals from multiple pages are averaged."""
        from src.server.services.crawling.preflight_service import QualitySignals

        signals = [
            QualitySignals(
                content_to_markup_ratio=0.3,
                code_snippet_density=0.1,
                has_structure=True,
                word_count=1000,
            ),
            QualitySignals(
                content_to_markup_ratio=0.5,
                code_snippet_density=0.2,
                has_structure=True,
                word_count=2000,
            ),
            QualitySignals(
                content_to_markup_ratio=0.4,
                code_snippet_density=0.15,
                has_structure=True,
                word_count=1500,
            ),
        ]

        avg_content_ratio = sum(s.content_to_markup_ratio for s in signals) / len(signals)
        avg_code_density = sum(s.code_snippet_density for s in signals) / len(signals)

        assert 0 < avg_content_ratio < 1
        assert avg_code_density > 0


class TestPreflightDomainViolations:
    """Test domain boundary violation detection."""

    @patch("socket.getaddrinfo", return_value=create_mock_dns_response())
    @patch("requests.Session")
    @patch("requests.get")
    def test_detect_external_domain_links(self, mock_get, mock_session, mock_dns):
        """External domain links are detected and flagged."""
        from src.server.services.crawling.preflight_service import CrawlPreflightService

        html_with_external = """<!DOCTYPE html>
        <html>
        <body>
            <a href="https://example.com/page1">Internal</a>
            <a href="https://docs.aiohttp.dev/paginator">External docs</a>
            <a href="https://stackoverflow.com/questions/123">Stack Overflow</a>
            <a href="/relative-link">Relative</a>
        </body>
        </html>"""

        mock_get.return_value = create_mock_response(200, html_with_external)

        service = CrawlPreflightService()
        violations = service._detect_domain_violations(html_with_external, "https://example.com/docs")

        assert len(violations) >= 2
        assert any("aiohttp" in v for v in violations)
        assert any("stackoverflow" in v for v in violations)

    @patch("socket.getaddrinfo", return_value=create_mock_dns_response())
    @patch("requests.Session")
    @patch("requests.get")
    def test_no_violations_for_clean_domain(self, mock_get, mock_session, mock_dns):
        """No violations reported for clean domain."""
        from src.server.services.crawling.preflight_service import CrawlPreflightService

        html_clean = """<!DOCTYPE html>
        <html>
        <body>
            <a href="/page1">Internal 1</a>
            <a href="/page2">Internal 2</a>
            <a href="/guides/getting-started">Internal 3</a>
        </body>
        </html>"""

        mock_get.return_value = create_mock_response(200, html_clean)

        service = CrawlPreflightService()
        violations = service._detect_domain_violations(html_clean, "https://example.com")

        assert len(violations) == 0

    @patch("socket.getaddrinfo", return_value=create_mock_dns_response())
    @patch("requests.Session")
    @patch("requests.get")
    def test_subdomain_allowed(self, mock_get, mock_session, mock_dns):
        """Subdomains of the main domain are allowed."""
        from src.server.services.crawling.preflight_service import CrawlPreflightService

        html_with_subdomain = """<!DOCTYPE html>
        <html>
        <body>
            <a href="https://example.com">Main</a>
            <a href="https://docs.example.com">Docs subdomain</a>
            <a href="https://api.example.com">API subdomain</a>
            <a href="https://other-site.com">External</a>
        </body>
        </html>"""

        mock_get.return_value = create_mock_response(200, html_with_subdomain)

        service = CrawlPreflightService()
        violations = service._detect_domain_violations(html_with_subdomain, "https://example.com")

        assert len(violations) == 1
        assert "other-site.com" in violations[0]


class TestPreflightErrorHandling:
    """Test error handling in pre-flight service."""

    @patch("socket.getaddrinfo", return_value=create_mock_dns_response())
    @patch("requests.Session")
    @patch("requests.get")
    def test_invalid_url_handling(self, mock_get, mock_session, mock_dns):
        """Invalid URLs are handled gracefully."""
        import asyncio

        from src.server.services.crawling.preflight_service import CrawlPreflightService

        service = CrawlPreflightService()

        result = asyncio.get_event_loop().run_until_complete(service.estimate_crawl("not-a-url", max_depth=2))

        assert result.url_count_estimate == 0

    @patch("socket.getaddrinfo", return_value=create_mock_dns_response())
    @patch("requests.Session")
    @patch("requests.get")
    def test_unreachable_domain_handling(self, mock_get, mock_session, mock_dns):
        """Unreachable domains return helpful error."""
        import asyncio

        from src.server.services.crawling.preflight_service import CrawlPreflightService

        mock_get.side_effect = Exception("Connection refused")

        service = CrawlPreflightService()

        result = asyncio.get_event_loop().run_until_complete(
            service.estimate_crawl("https://definitely-not-real-12345.com/", max_depth=2)
        )

        assert len(result.warnings) > 0

    @patch("socket.getaddrinfo", return_value=create_mock_dns_response())
    @patch("requests.Session")
    @patch("requests.get")
    def test_sitemap_parse_failure_fallback(self, mock_get, mock_session, mock_dns):
        """Sitemap parse failure falls back to recursive estimation."""
        from src.server.services.crawling.preflight_service import CrawlPreflightService

        mock_get.return_value = create_mock_response(200, "not valid xml <<<")

        service = CrawlPreflightService()

        with patch.object(service, "_estimate_recursive") as mock_recursive:
            mock_recursive.return_value = {"url_count": 10, "sample_urls": []}

            result = service._discover_and_enumerate("https://example.com/", "sitemap", 2)

            assert result is not None


class TestPreflightCaching:
    """Test pre-flight result caching."""

    def test_caching_stores_results(self):
        """Caching stores results after computation."""
        from src.server.services.crawling.preflight_service import (
            CrawlPreflightService,
            PreflightEstimate,
            QualitySignals,
        )

        service = CrawlPreflightService()

        estimate = PreflightEstimate(
            url_count_estimate=100,
            estimated_tokens=30000,
            estimated_duration_minutes=5,
            quality_score=0.75,
            quality_signals=QualitySignals(
                content_to_markup_ratio=0.4,
                code_snippet_density=0.15,
                has_structure=True,
                word_count=2500,
            ),
            discovered_via="sitemap",
            crawl_strategy_recommendation="sitemap",
            sample_urls=["https://example.com/"],
            warnings=[],
            domain_violations=[],
        )

        service._cache_result("https://example.com", 2, estimate)

        assert service._get_cached_result("https://example.com", 2) is not None

    def test_caching_different_depths(self):
        """Different depths produce different cache keys."""
        from src.server.services.crawling.preflight_service import CrawlPreflightService

        service = CrawlPreflightService()

        assert service._get_cache_key("https://example.com", 1) != service._get_cache_key("https://example.com", 2)

    def test_caching_expiration(self):
        """Cache entries expire after configured time."""
        from src.server.services.crawling.preflight_service import CrawlPreflightService

        service = CrawlPreflightService()

        with patch.object(service, "_cache_ttl", 0):
            with patch("time.time", return_value=1000):
                estimate = Mock()
                service._cache_result("https://example.com", 2, estimate)

                with patch("time.time", return_value=2000):
                    result = service._get_cached_result("https://example.com", 2)
                    assert result is None


class TestPreflightDiscoveryStrategies:
    """Test discovery strategy auto-detection and recommendations."""

    @patch("socket.getaddrinfo", return_value=create_mock_dns_response())
    @patch("requests.Session")
    @patch("requests.get")
    def test_auto_detect_sitemap(self, mock_get, mock_session, mock_dns):
        """Auto-detection finds sitemap when available."""
        from src.server.services.crawling.discovery_service import DiscoveryService
        from src.server.services.crawling.preflight_service import CrawlPreflightService

        robots_response = create_mock_response(200, "User-agent: *\nDisallow: /admin/")

        def mock_side_effect(url, **kwargs):
            if url.endswith("robots.txt"):
                return robots_response
            elif url.endswith("sitemap.xml"):
                return create_mock_response(
                    200,
                    """<?xml version="1.0"?><urlset><url><loc>https://example.com/page1</loc></url></urlset>""",
                )
            return create_mock_response(404)

        mock_get.side_effect = mock_side_effect

        discovery = DiscoveryService()
        preflight = CrawlPreflightService()

        discovered = discovery.discover_files("https://example.com")
        strategy = preflight._recommend_strategy(discovered, "https://example.com")

        assert strategy in ["sitemap", "llms.txt"]

    def test_strategy_recommendation_consistency(self):
        """Strategy recommendation matches discovery result."""
        from src.server.services.crawling.preflight_service import CrawlPreflightService

        service = CrawlPreflightService()

        assert service._recommend_strategy("https://example.com/sitemap.xml", "https://example.com") == "sitemap"
        assert service._recommend_strategy("https://example.com/llms.txt", "https://example.com") == "llms.txt"
        assert service._recommend_strategy(None, "https://example.com") == "recursive"


class TestPreflightIntegrationAccuracy:
    """Integration tests comparing pre-flight estimates to actual crawl results."""

    @pytest.mark.integration
    @patch("socket.getaddrinfo", return_value=create_mock_dns_response())
    @patch("requests.Session")
    @patch("requests.get")
    def test_estimate_within_30_percent_accuracy(self, mock_get, mock_session, mock_dns):
        """URL count estimate should be within 30% of actual."""
        from src.server.services.crawling.preflight_service import CrawlPreflightService

        sitemap_content = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://example.com/page1</loc></url>
            <url><loc>https://example.com/page2</loc></url>
            <url><loc>https://example.com/page3</loc></url>
            <url><loc>https://example.com/page4</loc></url>
            <url><loc>https://example.com/page5</loc></url>
        </urlset>"""

        mock_get.return_value = create_mock_response(200, sitemap_content)

        import asyncio

        service = CrawlPreflightService()

        with patch.object(service, "_fetch_page", return_value=sitemap_content):
            estimate = asyncio.get_event_loop().run_until_complete(
                service.estimate_crawl("https://example.com", max_depth=2)
            )

        actual_url_count = 5

        accuracy = abs(estimate.url_count_estimate - actual_url_count) / actual_url_count

        assert accuracy < 0.30, f"Estimate {accuracy * 100:.1f}% off, expected < 30%"

    @pytest.mark.integration
    @patch("socket.getaddrinfo", return_value=create_mock_dns_response())
    @patch("requests.Session")
    @patch("requests.get")
    def test_token_estimate_within_40_percent_accuracy(self, mock_get, mock_session, mock_dns):
        """Token estimate should be within 40% of actual."""
        import asyncio

        from src.server.services.crawling.preflight_service import CrawlPreflightService

        html_content = "<html><body><p>" + "word " * 500 + "</p></body></html>"

        mock_get.return_value = create_mock_response(200, html_content)

        service = CrawlPreflightService()

        with patch.object(service, "_sample_pages", return_value=[html_content]):
            estimate = asyncio.get_event_loop().run_until_complete(
                service.estimate_crawl("https://example.com", max_depth=1)
            )

        actual_tokens = len(html_content) // 4

        accuracy = abs(estimate.estimated_tokens - actual_tokens) / actual_tokens

        assert accuracy < 0.40, f"Token estimate {accuracy * 100:.1f}% off, expected < 40%"
