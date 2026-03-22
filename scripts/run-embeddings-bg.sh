#!/bin/bash
# Background embedding runner with proper environment

export ARCHON_DATABASE_URL="postgresql://archon:archon_local_dev@localhost:5434/archon"
export OLLAMA_URL="http://localhost:11434"
export OPENAI_API_KEY=""  # Disable OpenAI

LOG_FILE="${HOME}/.local/log/archon-embeddings.log"
PID_FILE="${HOME}/.local/run/archon-embeddings.pid"

mkdir -p "$(dirname "$LOG_FILE")"
mkdir -p "$(dirname "$PID_FILE")"

# Check if already running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "Already running (PID: $OLD_PID)"
        echo "Check log: tail -f $LOG_FILE"
        exit 0
    fi
    rm -f "$PID_FILE"
fi

echo "Starting embedding generator..."
echo "Log: $LOG_FILE"

cd /home/zebastjan/dev/archon

# Run in background
(
    while true; do
        echo "=== Starting batch at $(date) ===" >> "$LOG_FILE"
        python/.venv/bin/python scripts/embedding_generator_v2.py >> "$LOG_FILE" 2>&1
        echo "=== Batch complete at $(date) ===" >> "$LOG_FILE"
        echo "" >> "$LOG_FILE"
        sleep 5
    done
) &

PID=$!
echo $PID > "$PID_FILE"

echo "Started (PID: $PID)"
echo ""
echo "Commands:"
echo "  Watch:   tail -f $LOG_FILE"
echo "  Check:   ps aux | grep $PID"
echo "  Stop:    kill $PID && rm $PID_FILE"
