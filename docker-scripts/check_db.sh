#!/bin/bash
# Run inside the archon container to index all repos
# This script accesses the code from the host via volume mounts

set -e

echo "========================================"
echo "INDEXING ALL REPOSITORIES"
echo "========================================"
echo ""

# Database config
export ARCHON_DATABASE_URL="postgresql://archon:archon_local_dev@localhost:5432/archon"
export PYTHONPATH="/app/src"
export PATH="/venv/bin:$PATH"

cd /app

# Wait for postgres to be ready
echo "Checking database..."
for i in {1..30}; do
    if su - postgres -c "psql -U archon -d archon -c 'SELECT 1'" >/dev/null 2>&1; then
        echo "Database ready!"
        break
    fi
    echo "Waiting for database... ($i)"
    sleep 1
done

# Define repos (path on HOST, not container)
# We'll mount these from host or access via docker cp
echo ""
echo "Repositories to index:"
echo "  1. archon-python: /home/zebastjan/dev/archon/python/src"
echo "  2. syllablaze: /home/zebastjan/dev/syllablaze"
echo "  3. octofriend: /home/zebastjan/dev/octofriend"
echo "  4. Omnibus: /home/zebastjan/dev/Omnibus"
echo ""

# Check current repo state
echo "Current entity count:"
su - postgres -c "psql -U archon -d archon -c 'SELECT COUNT(*) FROM archon_code_entities;'"

echo ""
echo "Ready to index!"
echo "The Python script will be provided separately."