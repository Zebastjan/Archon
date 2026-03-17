#!/bin/bash
# Quick reload script for MCP container during development
# Usage: ./scripts/mcp-reload.sh

set -e

echo "🔄 Reloading MCP container..."

# Kill MCP server inside container to force restart
docker exec archon-mcp pkill -f "mcp_server" || true

# Wait a moment
sleep 1

# Check if it came back
sleep 2
if docker ps | grep -q "archon-mcp"; then
    echo "✅ MCP container is running"
    docker logs archon-mcp --tail 5
else
    echo "❌ MCP container failed to restart, trying full restart..."
    docker-compose restart archon-mcp
    sleep 3
    docker logs archon-mcp --tail 5
fi
