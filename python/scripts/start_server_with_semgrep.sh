#!/bin/bash
# Start Archon server with Semgrep in PATH
# This script ensures semgrep is available for the audit service

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Ensure local bin is in PATH (for semgrep symlink)
export PATH="$HOME/.local/bin:$PATH"

# Ensure venv bin is in PATH
export PATH="$PROJECT_ROOT/.venv/bin:$PATH"

# Verify semgrep is available
if ! command -v semgrep &> /dev/null; then
    echo "❌ Error: semgrep not found in PATH"
    echo "   Searched in: $HOME/.local/bin and $PROJECT_ROOT/.venv/bin"
    echo "   Run: pip install semgrep"
    exit 1
fi

# Verify pysemgrep is available (semgrep needs this)
if ! command -v pysemgrep &> /dev/null; then
    echo "❌ Error: pysemgrep not found in PATH"
    echo "   This should be installed alongside semgrep"
    exit 1
fi

echo "✅ Semgrep found: $(semgrep --version 2>/dev/null | tail -1)"
echo "✅ pysemgrep found: $(pysemgrep --version 2>/dev/null | tail -1)"

# Set database URL if not already set
if [ -z "$ARCHON_DATABASE_URL" ]; then
    export ARCHON_DATABASE_URL="postgresql://archon:archon_local_dev@localhost:5434/archon"
    echo "ℹ️  Using default ARCHON_DATABASE_URL"
fi

# Set port
export ARCHON_SERVER_PORT="${ARCHON_SERVER_PORT:-8181}"
echo "ℹ️  Server will run on port $ARCHON_SERVER_PORT"

# Kill any existing server on this port
echo "🧹 Cleaning up existing processes..."
fuser -k ${ARCHON_SERVER_PORT}/tcp 2>/dev/null || true
sleep 2

# Start server
echo "🚀 Starting Archon server..."
cd "$PROJECT_ROOT"
exec python -m uvicorn src.server.main:app \
    --host 0.0.0.0 \
    --port ${ARCHON_SERVER_PORT} \
    --reload \
    --log-level info
