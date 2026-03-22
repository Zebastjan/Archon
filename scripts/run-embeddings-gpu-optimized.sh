#!/bin/bash
# GPU-Optimized embedding runner with auto-scaling

export ARCHON_DATABASE_URL="postgresql://archon:archon_local_dev@localhost:5434/archon"
export OLLAMA_URL="http://localhost:11434"

LOG_FILE="${HOME}/.local/log/archon-embeddings-gpu.log"
PID_FILE="${HOME}/.local/run/archon-embeddings.pid"

mkdir -p "$(dirname "$LOG_FILE")"
mkdir -p "$(dirname "$PID_FILE")"

# Kill old process
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "Stopping old process..."
        kill "$OLD_PID" 2>/dev/null
        sleep 2
    fi
    rm -f "$PID_FILE"
fi

echo "═══════════════════════════════════════════════════════════════════"
echo "  GPU-Optimized Embedding Generator"
echo "═══════════════════════════════════════════════════════════════════"
echo ""
echo "Features:"
echo "  - Auto-scaling batch size (25-150)"
echo "  - GPU utilization monitoring"
echo "  - Dynamic optimization every 30s"
echo "  - Targets 80% GPU utilization"
echo ""

cd /home/zebastjan/dev/archon
nohup python/.venv/bin/python scripts/embedding_generator_gpu_optimized.py >> "$LOG_FILE" 2>&1 &
PID=$!
echo $PID > "$PID_FILE"

sleep 2

if ps -p $PID > /dev/null 2>&1; then
    echo "✅ Started (PID: $PID)"
    echo ""
    echo "Commands:"
    echo "  Watch:    tail -f $LOG_FILE"
    echo "  GPU:      watch -n 2 nvidia-smi"
    echo "  Stop:     kill $PID"
else
    echo "❌ Failed to start"
    tail -20 "$LOG_FILE"
    rm -f "$PID_FILE"
    exit 1
fi
