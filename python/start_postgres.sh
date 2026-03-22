#!/bin/bash
# Start PostgreSQL with pgvector support

DATA_DIR="$HOME/.local/share/archon/postgres"
LOG_FILE="$HOME/.local/share/archon/logs/postgres.log"

# Set library path for pgvector
export LD_LIBRARY_PATH="$HOME/.local/share/archon/postgres/lib:$LD_LIBRARY_PATH"

# Start postgres
pg_ctl -D "$DATA_DIR" -l "$LOG_FILE" start
