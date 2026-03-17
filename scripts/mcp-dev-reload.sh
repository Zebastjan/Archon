#!/bin/bash
# MCP Development Quick Reload - Restarts MCP server without rebuilding container
# Usage: ./scripts/mcp-dev-reload.sh

set -e

echo "🔄 Quick MCP reload (no rebuild needed)..."

# Check if container is running
if ! docker ps | grep -q "archon-mcp"; then
    echo "❌ MCP container not running, starting fresh..."
    docker-compose up -d archon-mcp
    sleep 5
    docker logs archon-mcp --tail 10
    exit 0
fi

# Kill the Python process inside the container - watchdog will restart it
echo "Sending restart signal to MCP server..."
docker exec archon-mcp pkill -f "mcp_server" 2>/dev/null || true
docker exec archon-mcp pkill -f "mcp_dev_wrapper" 2>/dev/null || true

# Wait for restart
echo "⏳ Waiting for restart..."
sleep 2

# Verify it's running
for i in 1 2 3; do
    if docker exec archon-mcp python -c "import socket; s=socket.socket(); s.connect(('localhost', 8051)); s.close()" 2>/dev/null; then
        echo "✅ MCP server is responsive"
        docker logs archon-mcp --tail 5
        exit 0
    fi
    echo "  Attempt $i/3..."
    sleep 1
done

echo "⚠️  MCP server not responding yet, checking logs..."
docker logs archon-mcp --tail 10
