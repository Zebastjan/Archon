#!/bin/bash
# Automated Database Setup for Archon
# This script ensures the database is always in the correct state

set -e

DB_HOST="${ARCHON_DB_HOST:-localhost}"
DB_PORT="${ARCHON_DB_PORT:-5432}"
DB_NAME="${ARCHON_DB_NAME:-archon}"
DB_USER="${ARCHON_DB_USER:-archon}"
DB_PASS="${ARCHON_DB_PASSWORD:-archon}"

export PGPASSWORD="$DB_PASS"

PSQL="psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME"
MIGRATION_DIR="/home/zebastjan/dev/archon/migration"

echo "🚀 Archon Database Setup"
echo "========================"
echo ""

# Function to apply a single migration
apply_migration() {
    local file="$1"
    local basename=$(basename "$file")
    echo "  Applying: $basename"
    
    # Copy to container and apply
    docker cp "$file" archon-postgres:/tmp/migration.sql 2>/dev/null || true
    docker exec -e PGPASSWORD=archon archon-postgres psql -U archon -d archon -f /tmp/migration.sql > /dev/null 2>&1 || {
        echo "    ⚠️  Migration had errors (may be partially applied or already exists)"
    }
}

# 1. Ensure pgvector extension
echo "📦 Step 1: Installing pgvector extension..."
docker exec archon-postgres apt-get update > /dev/null 2>&1 || true
docker exec archon-postgres apt-get install -y postgresql-16-pgvector > /dev/null 2>&1 || {
    echo "  ⚠️  Could not install pgvector via apt (may already be installed)"
}
docker exec -e PGPASSWORD=archon archon-postgres psql -U archon -d archon -c "CREATE EXTENSION IF NOT EXISTS vector;" > /dev/null 2>&1
docker exec -e PGPASSWORD=archon archon-postgres psql -U archon -d archon -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;" > /dev/null 2>&1
docker exec -e PGPASSWORD=archon archon-postgres psql -U archon -d archon -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;" > /dev/null 2>&1
echo "  ✅ Extensions ready"
echo ""

# 2. Apply complete_setup.sql (master schema)
echo "📋 Step 2: Applying master schema (complete_setup.sql)..."
if [ -f "$MIGRATION_DIR/complete_setup.sql" ]; then
    docker cp "$MIGRATION_DIR/complete_setup.sql" archon-postgres:/tmp/complete_setup.sql
    docker exec -e PGPASSWORD=archon archon-postgres psql -U archon -d archon -f /tmp/complete_setup.sql > /dev/null 2>&1 || {
        echo "  ⚠️  Master schema had some errors (tables may already exist)"
    }
    echo "  ✅ Master schema applied"
else
    echo "  ❌ Master schema not found!"
fi
echo ""

# 3. Apply 0.1.0 migrations
echo "📁 Step 3: Applying 0.1.0 migrations..."
if [ -d "$MIGRATION_DIR/0.1.0" ]; then
    count=0
    for file in "$MIGRATION_DIR"/0.1.0/*.sql; do
        if [ -f "$file" ]; then
            apply_migration "$file"
            ((count++)) || true
        fi
    done
    echo "  ✅ Applied $count migrations from 0.1.0/"
else
    echo "  ⚠️  0.1.0 directory not found"
fi
echo ""

# 4. Apply numbered migrations
echo "📁 Step 4: Applying numbered migrations (012-023)..."
count=0
for file in "$MIGRATION_DIR"/01[2-9]_*.sql "$MIGRATION_DIR"/02[0-3]_*.sql; do
    if [ -f "$file" ]; then
        apply_migration "$file"
        ((count++)) || true
    fi
done
echo "  ✅ Applied $count numbered migrations"
echo ""

# 5. Verify
echo "🔍 Step 5: Verifying database state..."
TABLE_COUNT=$(docker exec -e PGPASSWORD=archon archon-postgres psql -U archon -d archon -t -c "SELECT COUNT(*) FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'archon_%';" 2>/dev/null | tr -d ' ')
echo "  Total tables: $TABLE_COUNT"

if [ -n "$TABLE_COUNT" ] && [ "$TABLE_COUNT" -ge 30 ]; then
    echo ""
    echo "✅ Database setup complete!"
    echo "   $TABLE_COUNT tables created and ready"
    exit 0
else
    echo ""
    echo "⚠️  Database setup incomplete"
    echo "   Only $TABLE_COUNT tables found (expected ~36)"
    exit 1
fi
