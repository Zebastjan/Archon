#!/bin/bash
# Golden Path Test Runner
#
# This script runs the golden path ingestion test with all debug flags enabled.
# It verifies that the entire ingestion pipeline works end-to-end.
#
# Usage:
#   ./test_golden_path.sh                    # Test with default URL (Pydantic docs)
#   ./test_golden_path.sh CUSTOM_URL         # Test with custom URL
#
# Example:
#   ./test_golden_path.sh https://docs.python.org/3/library/asyncio.html

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default test URL
TEST_URL="${1:-https://docs.pydantic.dev/latest/}"

echo "=================================================="
echo "Golden Path Ingestion Test"
echo "=================================================="
echo ""
echo "Test URL: $TEST_URL"
echo "Timestamp: $(date -Iseconds)"
echo ""
echo "This test will:"
echo "  1. Enable all debug logging"
echo "  2. Crawl a single page from the test URL"
echo "  3. Verify all pipeline stages (fetch, process, embed, store, search)"
echo "  4. Report pass/fail for each stage"
echo ""
echo "=================================================="
echo ""

# Change to python directory
cd "$(dirname "$0")"

# Ensure we're using uv
if ! command -v uv &> /dev/null; then
    echo -e "${RED}ERROR: uv is not installed${NC}"
    echo "Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 2
fi

# Run the test
echo "Starting test..."
echo ""

if uv run python tests/test_golden_path_ingestion.py --url "$TEST_URL"; then
    echo ""
    echo -e "${GREEN}=================================================="
    echo "✅ GOLDEN PATH TEST PASSED"
    echo -e "==================================================${NC}"
    exit 0
else
    EXIT_CODE=$?
    echo ""
    echo -e "${RED}=================================================="
    echo "❌ GOLDEN PATH TEST FAILED"
    echo -e "==================================================${NC}"
    exit $EXIT_CODE
fi
