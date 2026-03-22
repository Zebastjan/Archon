#!/bin/bash
# GPU Priority Manager for Ollama
# Ensures transcription (real-time) gets priority over batch jobs

OLLAMA_PAUSE_FILE="/tmp/ollama-pause-embeddings"

case "$1" in
  pause)
    # Called by transcription software before starting
    touch "$OLLAMA_PAUSE_FILE"
    echo "Pausing embeddings..."
    # Could also send SIGSTOP to embedding process
    ;;
  resume)
    # Called by transcription software when done
    rm -f "$OLLAMA_PAUSE_FILE"
    echo "Resuming embeddings..."
    ;;
  status)
    if [ -f "$OLLAMA_PAUSE_FILE" ]; then
      echo "Embeddings PAUSED (transcription active)"
    else
      echo "Embeddings RUNNING"
    fi
    ;;
  *)
    echo "Usage: $0 {pause|resume|status}"
    echo ""
    echo "Add to transcription software:"
    echo "  Pre-hook: $0 pause"
    echo "  Post-hook: $0 resume"
    ;;
esac
