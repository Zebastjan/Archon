#!/bin/bash
# Final embedding runner - uses correct Ollama patterns

export ARCHON_DATABASE_URL="postgresql://archon:archon_local_dev@localhost:5434/archon"
export OLLAMA_URL="http://localhost:11434"

LOG_FILE="${HOME}/.local/log/archon-embeddings-final.log"
PID_FILE="${HOME}/.local/run/archon-embeddings.pid"

mkdir -p "$(dirname "$LOG_FILE")"
mkdir -p "$(dirname "$PID_FILE")"

# Activate venv
VENV_PATH="/home/zebastjan/dev/archon/python/.venv"
if [ -f "$VENV_PATH/bin/activate" ]; then
    source "$VENV_PATH/bin/activate"
fi

# Kill old process
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
echo "  Embedding Generator - Final Version"
echo "═══════════════════════════════════════════════════════════════════"
echo ""
echo "Features:"
echo "  - Uses /api/embed (batch-capable endpoint)"
echo "  - Batch size 16 (Ollama optimal)"
echo "  - Sequential processing (Ollama serializes anyway)"
echo "  - Proper error handling"
echo ""

cd /home/zebastjan/dev/archon

# Run in background
nohup python/.venv/bin/python scripts/embedding_generator_final.py >> "$LOG_FILE" 2>&1 &
PID=$!
echo $PID > "$PID_FILE"

sleep 3

if ps -p $PID > /dev/null 2>&1; then
    echo "✅ Started (PID: $PID)"
    echo ""
    echo "Commands:"
    echo "  Watch:    tail -f $LOG_FILE"
    echo "  GPU:      watch -n 2 nvidia-smi"
    echo "  Stop:     kill $PID"
    echo ""
    echo "Viewing log..."
    sleep 2
    tail -30 "$LOG_FILE"
else
    echo "❌ Failed to start"
    tail -20 "$LOG_FILE"
    rm -f "$PID_FILE"
    exit 1
fi
