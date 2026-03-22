#!/bin/bash
# Robust embedding runner with timeout protection

export ARCHON_DATABASE_URL="postgresql://archon:archon_local_dev@localhost:5434/archon"
export OLLAMA_URL="http://localhost:11434"

LOG_FILE="${HOME}/.local/log/archon-embeddings.log"
PID_FILE="${HOME}/.local/run/archon-embeddings.pid"

mkdir -p "$(dirname "$LOG_FILE")"
mkdir -p "$(dirname "$PID_FILE")"

# Kill old process if exists
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "Stopping old process (PID: $OLD_PID)..."
        kill "$OLD_PID" 2>/dev/null
        sleep 2
    fi
    rm -f "$PID_FILE"
fi

echo "═══════════════════════════════════════════════════════════════════"
echo "  Starting Robust Embedding Generator"
echo "═══════════════════════════════════════════════════════════════════"
echo ""
echo "Log: $LOG_FILE"
echo "Features:"
echo "  - 30s timeout per entity"
echo "  - Individual progress tracking"
echo "  - Auto-skip failed entities"
echo "  - Checkpoint every 10 batches"
echo ""

cd /home/zebastjan/dev/archon

# Run with nohup for background persistence
nohup python/.venv/bin/python scripts/embedding_generator_robust.py >> "$LOG_FILE" 2>&1 &
PID=$!
echo $PID > "$PID_FILE"

sleep 2

# Check if actually running
if ps -p $PID > /dev/null 2>&1; then
    echo "✅ Started (PID: $PID)"
    echo ""
    echo "Commands:"
    echo "  Watch:    tail -f $LOG_FILE"
    echo "  Status:   ps aux | grep $PID"
    echo "  Stop:     kill $PID"
else
    echo "❌ Failed to start - check log:"
    tail -20 "$LOG_FILE"
    rm -f "$PID_FILE"
    exit 1
fi

echo ""
