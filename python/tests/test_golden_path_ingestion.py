#!/usr/bin/env python3
"""
Golden Path Ingestion Test

This script runs an end-to-end test of the ingestion pipeline with all debug flags enabled.
It crawls a single known-good documentation page and verifies that all pipeline stages
complete successfully with proper logging.

Usage:
    # Run with default URL (Pydantic docs)
    uv run python tests/test_golden_path_ingestion.py

    # Run with custom URL
    uv run python tests/test_golden_path_ingestion.py --url https://docs.python.org/3/library/asyncio.html

    # Run with custom match criteria
    uv run python tests/test_golden_path_ingestion.py --expected-word "asyncio"

Exit Codes:
    0 - All stages passed
    1 - One or more stages failed
    2 - Script execution error
"""

import argparse
import asyncio
import os
import sys
import time
from datetime import datetime
from io import StringIO
from typing import Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class LogCapture:
    """Capture log output for analysis"""

    def __init__(self):
        self.buffer = StringIO()
        self.logs: list[str] = []

    def write(self, message: str):
        """Capture log message"""
        self.logs.append(message)
        self.buffer.write(message)
        # Also print to stdout for visibility
        print(message, end="")

    def get_logs(self) -> list[str]:
        """Get all captured logs"""
        return self.logs

    def find_logs(self, pattern: str) -> list[str]:
        """Find logs matching pattern"""
        return [log for log in self.logs if pattern in log]


class PipelineStageVerifier:
    """Verifies each stage of the ingestion pipeline"""

    def __init__(self, log_capture: LogCapture):
        self.log_capture = log_capture
        self.results: dict[str, dict[str, Any]] = {}

    def verify_stage(self, stage_name: str, log_markers: list[str], required_count: int = 1) -> bool:
        """
        Verify a pipeline stage by checking for required log markers.

        Args:
            stage_name: Human-readable stage name
            log_markers: List of log message patterns to look for
            required_count: Minimum number of matches required (default 1)

        Returns:
            True if stage passed, False otherwise
        """
        print(f"\n{'='*80}")
        print(f"Verifying Stage: {stage_name}")
        print(f"{'='*80}")

        stage_passed = True
        details = []

        for marker in log_markers:
            matching_logs = self.log_capture.find_logs(marker)
            found_count = len(matching_logs)

            if found_count >= required_count:
                status = "✅ PASS"
                details.append(f"{status}: Found {found_count} occurrences of '{marker}'")
                if matching_logs:
                    # Show first match as example
                    details.append(f"   Example: {matching_logs[0].strip()[:120]}...")
            else:
                status = "❌ FAIL"
                stage_passed = False
                details.append(f"{status}: Expected {required_count}+ occurrences of '{marker}', found {found_count}")

        # Store results
        self.results[stage_name] = {
            "passed": stage_passed,
            "markers_checked": log_markers,
            "details": details,
        }

        # Print details
        for detail in details:
            print(detail)

        return stage_passed

    def verify_no_errors(self, stage_name: str, error_markers: list[str]) -> bool:
        """
        Verify that certain error markers are NOT present.

        Args:
            stage_name: Human-readable stage name
            error_markers: List of error patterns that should NOT appear

        Returns:
            True if no errors found, False otherwise
        """
        print(f"\n{'='*80}")
        print(f"Verifying No Errors: {stage_name}")
        print(f"{'='*80}")

        stage_passed = True
        details = []

        for marker in error_markers:
            matching_logs = self.log_capture.find_logs(marker)
            found_count = len(matching_logs)

            if found_count == 0:
                status = "✅ PASS"
                details.append(f"{status}: No occurrences of error '{marker}'")
            else:
                status = "❌ FAIL"
                stage_passed = False
                details.append(f"{status}: Found {found_count} occurrences of error '{marker}'")
                # Show first error as example
                if matching_logs:
                    details.append(f"   Example: {matching_logs[0].strip()[:120]}...")

        # Store results
        self.results[f"{stage_name}_no_errors"] = {
            "passed": stage_passed,
            "markers_checked": error_markers,
            "details": details,
        }

        # Print details
        for detail in details:
            print(detail)

        return stage_passed

    def print_summary(self):
        """Print final test summary"""
        print(f"\n{'='*80}")
        print("FINAL SUMMARY")
        print(f"{'='*80}\n")

        total_stages = len(self.results)
        passed_stages = sum(1 for result in self.results.values() if result["passed"])
        failed_stages = total_stages - passed_stages

        for stage_name, result in self.results.items():
            status = "✅ PASS" if result["passed"] else "❌ FAIL"
            print(f"{status}: {stage_name}")

        print(f"\n{'-'*80}")
        print(f"Total Stages: {total_stages}")
        print(f"Passed: {passed_stages}")
        print(f"Failed: {failed_stages}")
        print(f"{'-'*80}\n")

        return failed_stages == 0


async def run_golden_path_test(test_url: str, expected_word: str | None = None) -> bool:
    """
    Run the golden path ingestion test.

    Args:
        test_url: URL to crawl for testing
        expected_word: Optional word to verify in search results

    Returns:
        True if all stages passed, False otherwise
    """
    print(f"\n{'#'*80}")
    print(f"# Golden Path Ingestion Test")
    print(f"# Started: {datetime.now().isoformat()}")
    print(f"# Test URL: {test_url}")
    print(f"# Expected Word: {expected_word or 'auto-detect'}")
    print(f"{'#'*80}\n")

    # Set up environment for debug mode
    os.environ["DEBUG_INGESTION"] = "true"
    os.environ["MAX_CRAWL_PAGES"] = "1"
    os.environ["DISABLE_KEYWORD_FILTERING"] = "true"
    os.environ["DISABLE_LENGTH_FILTERING"] = "true"

    print("Environment Configuration:")
    print(f"  DEBUG_INGESTION = {os.environ.get('DEBUG_INGESTION')}")
    print(f"  MAX_CRAWL_PAGES = {os.environ.get('MAX_CRAWL_PAGES')}")
    print(f"  DISABLE_KEYWORD_FILTERING = {os.environ.get('DISABLE_KEYWORD_FILTERING')}")
    print(f"  DISABLE_LENGTH_FILTERING = {os.environ.get('DISABLE_LENGTH_FILTERING')}\n")

    # Create log capture
    log_capture = LogCapture()

    # Set up logging to capture output
    import logging

    # Get root logger and add our handler
    root_logger = logging.getLogger()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.DEBUG)
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.DEBUG)

    # Import after setting environment variables
    from src.server.services.crawler_manager import get_crawler
    from src.server.services.crawling import CrawlingService
    from src.server.utils import get_supabase_client

    try:
        # Initialize services
        print("Initializing services...")
        crawler = await get_crawler()
        if crawler is None:
            print("❌ ERROR: Failed to initialize crawler")
            return False

        supabase_client = get_supabase_client()
        crawl_service = CrawlingService(crawler, supabase_client)

        # Prepare crawl request
        request_dict = {
            "url": test_url,
            "knowledge_type": "technical",
            "tags": ["golden-path-test"],
            "max_depth": 1,
            "extract_code_examples": True,
            "generate_summary": False,
            "use_new_pipeline": False,  # Use old pipeline for comprehensive logging
        }

        print(f"\nStarting crawl: {test_url}\n")
        start_time = time.time()

        # Run the crawl
        result = await crawl_service.orchestrate_crawl(request_dict)
        crawl_task = result.get("task")

        if crawl_task:
            # Wait for the task to complete
            try:
                await crawl_task
            except Exception as e:
                print(f"❌ Crawl task error: {e}")
                import traceback

                traceback.print_exc()

        elapsed_time = time.time() - start_time
        print(f"\nCrawl completed in {elapsed_time:.2f} seconds\n")

        # Give logs a moment to flush
        await asyncio.sleep(1)

        # Verify each pipeline stage
        verifier = PipelineStageVerifier(log_capture)

        # Stage 1: Crawl Fetch
        verifier.verify_stage(
            "Stage 1: Crawl Fetch",
            [
                "CRAWL_FETCH_START",
                "CRAWL_FETCH_CONFIG",
                "CRAWL_FETCH_SUCCESS",
            ],
        )

        # Stage 2: RawDocument Processing
        verifier.verify_stage(
            "Stage 2: RawDocument Processing",
            [
                "PREPROCESS_RAWDOC",
                "CHUNKING_START",
                "CHUNKING_COMPLETE",
            ],
        )

        # Stage 3: Embedding Generation
        verifier.verify_stage(
            "Stage 3: Embedding Generation",
            [
                "EMBEDDING_START",
                "EMBEDDING_RESULT",
            ],
        )

        # Stage 4: Database Write
        verifier.verify_stage(
            "Stage 4: Database Write",
            [
                "DB_WRITE_START",
                "DB_WRITE_SCHEMA_CHECK",
                "DB_WRITE_BATCH_SUCCESS",
            ],
        )

        # Stage 5: Literal Text Search Verification
        verifier.verify_stage(
            "Stage 5: Search Verification",
            [
                "LITERAL_TEXT_SEARCH_VERIFICATION_START",
                "LITERAL_TEXT_SEARCH_VERIFICATION_WORD",
            ],
        )

        # Verify search passed (if word was found)
        search_pass_logs = log_capture.find_logs("LITERAL_TEXT_SEARCH_VERIFICATION_PASS")
        search_fail_logs = log_capture.find_logs("LITERAL_TEXT_SEARCH_VERIFICATION_FAIL")

        if search_pass_logs:
            print("\n✅ Search verification PASSED - documents are searchable")
        elif search_fail_logs:
            print("\n❌ Search verification FAILED - documents may not be searchable")
            for fail_log in search_fail_logs[:3]:  # Show first 3 failures
                print(f"   {fail_log.strip()}")

        # Check for common errors
        verifier.verify_no_errors(
            "Error Checking",
            [
                "DB_WRITE_SCHEMA_ISSUES",
                "DB_WRITE_QUALITY_ISSUES",
                "DOC_COUNT_INVARIANT_VIOLATION",
                "LITERAL_TEXT_SEARCH_VERIFICATION_FAIL",
            ],
        )

        # Check filtering was bypassed
        filter_bypass_logs = log_capture.find_logs("FILTER_BYPASSED")
        if filter_bypass_logs:
            print(f"\n✅ Filtering bypass active ({len(filter_bypass_logs)} bypasses detected)")
        else:
            print("\n⚠️  No filter bypass logs found (may indicate no filtering occurred)")

        # Print final summary
        all_passed = verifier.print_summary()

        return all_passed

    except Exception as e:
        print(f"\n❌ CRITICAL ERROR during test execution:")
        print(f"   {type(e).__name__}: {str(e)}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        # Clean up environment
        os.environ.pop("DEBUG_INGESTION", None)
        os.environ.pop("MAX_CRAWL_PAGES", None)
        os.environ.pop("DISABLE_KEYWORD_FILTERING", None)
        os.environ.pop("DISABLE_LENGTH_FILTERING", None)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Run golden path ingestion test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--url",
        default="https://docs.pydantic.dev/latest/",
        help="URL to crawl for testing (default: Pydantic docs)",
    )
    parser.add_argument(
        "--expected-word",
        default=None,
        help="Expected word to find in search results (default: auto-detect from content)",
    )

    args = parser.parse_args()

    # Run the async test
    try:
        all_passed = asyncio.run(run_golden_path_test(args.url, args.expected_word))

        if all_passed:
            print("\n🎉 Golden Path Test: ALL STAGES PASSED")
            sys.exit(0)
        else:
            print("\n❌ Golden Path Test: ONE OR MORE STAGES FAILED")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(2)
    except Exception as e:
        print(f"\n\n❌ Test execution error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    main()
