#!/bin/bash
# Monitor embedding progress

export PGPASSWORD=archon_local_dev

echo "Monitoring embedding progress (Ctrl+C to stop)..."
echo ""

while true; do
    DONE=$(psql -h localhost -p 5434 -U archon -d archon -t -c "SELECT COUNT(*) FROM archon_code_entities WHERE embedding_1024 IS NOT NULL;" 2>/dev/null | xargs)
    TOTAL=$(psql -h localhost -p 5434 -U archon -d archon -t -c "SELECT COUNT(*) FROM archon_code_entities;" 2>/dev/null | xargs)

    if [ -n "$DONE" ] && [ -n "$TOTAL" ]; then
        PCT=$((DONE * 100 / TOTAL))
        echo -ne "\r$(date +%H:%M:%S) | Done: $DONE / $TOTAL (${PCT}%) | Remaining: $((TOTAL - DONE))    "
    fi

    sleep 5
done
