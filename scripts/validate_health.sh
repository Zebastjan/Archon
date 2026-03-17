#!/bin/bash
# Archon Health Check Validation Script
# Verifies all required services are healthy after cold boot

set -e

ARCHON_SERVER_PORT=${ARCHON_SERVER_PORT:-8181}
ARCHON_MCP_PORT=${ARCHON_MCP_PORT:-8051}
MAX_WAIT=120  # Maximum seconds to wait for services

echo "🔍 Archon Health Check Validation"
echo "================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_passed() {
    echo -e "${GREEN}✓${NC} $1"
}

check_failed() {
    echo -e "${RED}✗${NC} $1"
}

check_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Check 1: Archon Server /health
wait_for_server() {
    echo "Check 1: Archon Server health"
    local attempts=0
    local max_attempts=$((MAX_WAIT / 2))
    
    while [ $attempts -lt $max_attempts ]; do
        if curl -s "http://localhost:${ARCHON_SERVER_PORT}/health" > /tmp/server_health.json 2>/dev/null; then
            if jq -e '.ready == true' /tmp/server_health.json > /dev/null 2>&1; then
                check_passed "Archon Server healthy (ready=true)"
                return 0
            fi
        fi
        
        attempts=$((attempts + 1))
        if [ $attempts -eq 1 ]; then
            echo "  Waiting for archon-server..."
        fi
        sleep 2
    done
    
    check_failed "Archon Server not healthy after ${MAX_WAIT}s"
    if [ -f /tmp/server_health.json ]; then
        echo "  Response: $(cat /tmp/server_health.json)"
    fi
    return 1
}

# Check 2: MCP Server health endpoint (HTTP)
wait_for_mcp() {
    echo ""
    echo "Check 2: MCP Server health"
    local attempts=0
    local max_attempts=$((MAX_WAIT / 2))
    
    while [ $attempts -lt $max_attempts ]; do
        if curl -s "http://localhost:${ARCHON_MCP_PORT}/health" > /tmp/mcp_health.json 2>/dev/null; then
            if jq -e '.success == true' /tmp/mcp_health.json > /dev/null 2>&1; then
                # Check if database is healthy
                if jq -e '.health.database == true' /tmp/mcp_health.json > /dev/null 2>&1; then
                    check_passed "MCP Server healthy with DB connectivity"
                else
                    check_warning "MCP Server running but DB connectivity issue"
                    echo "  Full response:"
                    cat /tmp/mcp_health.json | jq .
                fi
                return 0
            fi
        fi
        
        attempts=$((attempts + 1))
        if [ $attempts -eq 1 ]; then
            echo "  Waiting for archon-mcp..."
        fi
        sleep 2
    done
    
    check_failed "MCP Server not healthy after ${MAX_WAIT}s"
    return 1
}

# Check 3: MCP DB-backed tool (indirect DB connectivity test)
check_mcp_db_tool() {
    echo ""
    echo "Check 3: MCP DB-backed tool"
    
    # Use curl to call the MCP server's SSE endpoint with a health check
    # The HTTP health endpoint already includes DB status, so we verify that
    if curl -s "http://localhost:${ARCHON_MCP_PORT}/health" > /tmp/mcp_db_check.json 2>/dev/null; then
        if jq -e '.health.database == true' /tmp/mcp_db_check.json > /dev/null 2>&1; then
            check_passed "MCP DB connectivity confirmed (database=true in health)"
            return 0
        else
            check_failed "MCP DB connectivity failed"
            echo "  Response:"
            cat /tmp/mcp_db_check.json | jq .
            return 1
        fi
    else
        check_failed "Cannot reach MCP health endpoint"
        return 1
    fi
}

# Main execution
main() {
    local failed=0
    
    # Check dependencies
    if ! command -v curl &> /dev/null; then
        echo "Error: curl is required but not installed"
        exit 1
    fi
    
    if ! command -v jq &> /dev/null; then
        echo "Error: jq is required but not installed"
        exit 1
    fi
    
    # Run checks
    if ! wait_for_server; then
        failed=1
    fi
    
    if ! wait_for_mcp; then
        failed=1
    fi
    
    if ! check_mcp_db_tool; then
        failed=1
    fi
    
    echo ""
    echo "================================"
    if [ $failed -eq 0 ]; then
        echo -e "${GREEN}All health checks passed!${NC}"
        echo ""
        echo "Archon infrastructure is booted and healthy."
        echo "You can now safely run MCP tools."
        exit 0
    else
        echo -e "${RED}Some health checks failed.${NC}"
        echo ""
        echo "Troubleshooting:"
        echo "  1. Check service logs: docker compose logs"
        echo "  2. Verify .env has correct ARCHON_DATABASE_URL"
        echo "  3. Ensure Postgres container is running: docker compose ps"
        echo ""
        echo "See: docs/HEALTH_CHECK_PROTOCOL.md"
        exit 1
    fi
}

main "$@"
