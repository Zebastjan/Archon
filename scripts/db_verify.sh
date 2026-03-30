#!/bin/bash
# Database Verification Script - Standalone, no Python dependencies
# Usage: ./db_verify.sh

set -e

DB_HOST="${ARCHON_DB_HOST:-localhost}"
DB_PORT="${ARCHON_DB_PORT:-5432}"
DB_NAME="${ARCHON_DB_NAME:-archon}"
DB_USER="${ARCHON_DB_USER:-archon}"
DB_PASS="${ARCHON_DB_PASSWORD:-archon}"

export PGPASSWORD="$DB_PASS"

PSQL="psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t -A"

echo "🔍 Archon Database Verification"
echo "================================"
echo "Host: $DB_HOST:$DB_PORT"
echo "Database: $DB_NAME"
echo "User: $DB_USER"
echo ""

# Check connection
echo "📡 Checking database connection..."
if ! $PSQL -c "SELECT 1;" > /dev/null 2>&1; then
    echo "❌ FAILED: Cannot connect to database"
    echo "   Check: docker ps | grep postgres"
    exit 1
fi
echo "✅ Database connection OK"
echo ""

# Check extensions
echo "🔧 Checking PostgreSQL extensions..."
EXTENSIONS=("vector" "pgcrypto" "pg_trgm")
for ext in "${EXTENSIONS[@]}"; do
    result=$($PSQL -c "SELECT extname FROM pg_extension WHERE extname = '$ext';" 2>/dev/null)
    if [ -n "$result" ]; then
        echo "  ✅ $ext"
    else
        echo "  ❌ $ext - MISSING"
    fi
done
echo ""

# Count tables
echo "📊 Checking tables..."
TABLE_COUNT=$($PSQL -c "SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public' AND tablename LIKE 'archon_%';" 2>/dev/null)
echo "  Total archon tables: $TABLE_COUNT"

# Check critical tables (using correct names from migrations)
CRITICAL_TABLES=("archon_projects" "archon_tasks" "archon_sources" "archon_settings" "archon_code_entities" "archon_git_commits" "archon_audit_findings" "archon_embeddings")
for table in "${CRITICAL_TABLES[@]}"; do
    exists=$($PSQL -c "SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = '$table';" 2>/dev/null)
    if [ -n "$exists" ]; then
        echo "  ✅ $table"
    else
        echo "  ❌ $table - MISSING"
    fi
done
echo ""

# Check settings
echo "⚙️  Checking archon_settings..."
SETTINGS=("MCP_TRANSPORT" "HOST" "PORT" "MODEL_CHOICE" "USE_HYBRID_SEARCH" "LLM_PROVIDER")
for setting in "${SETTINGS[@]}"; do
    result=$($PSQL -c "SELECT key FROM archon_settings WHERE key = '$setting';" 2>/dev/null)
    if [ -n "$result" ]; then
        echo "  ✅ $setting"
    else
        echo "  ⚠️  $setting - MISSING"
    fi
done
echo ""

echo "================================"
if [ "$TABLE_COUNT" -ge 30 ]; then
    echo "✅ Database appears to be properly configured"
    echo "   Tables: $TABLE_COUNT (expected ~36)"
    exit 0
elif [ "$TABLE_COUNT" -ge 10 ]; then
    echo "⚠️  Database partially configured"
    echo "   Tables: $TABLE_COUNT (expected ~36)"
    echo "   Some migrations may be missing"
    exit 1
else
    echo "❌ Database not properly configured"
    echo "   Tables: $TABLE_COUNT (expected ~36)"
    echo "   Run: ./scripts/db_setup.sh"
    exit 2
fi
