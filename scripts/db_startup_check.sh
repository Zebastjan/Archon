#!/bin/bash
# Database Startup Check - Run this before starting Archon services
# Add to docker-compose or systemd service to ensure DB is ready

set -e

DB_HOST="${ARCHON_DB_HOST:-localhost}"
DB_PORT="${ARCHON_DB_PORT:-5432}"
DB_NAME="${ARCHON_DB_NAME:-archon}"
DB_USER="${ARCHON_DB_USER:-archon}"
DB_PASS="${ARCHON_DB_PASSWORD:-archon}"

export PGPASSWORD="$DB_PASS"

PSQL="psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t -A"

echo "🚀 Archon Database Startup Check"
echo "================================="
echo ""

# Wait for database to be ready (with timeout)
MAX_RETRIES=30
RETRY_COUNT=0

echo "⏳ Waiting for database to be ready..."
while ! $PSQL -c "SELECT 1;" > /dev/null 2>&1; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "❌ Database not ready after $MAX_RETRIES attempts"
        echo "   Check: docker ps | grep postgres"
        exit 1
    fi
    echo "  Attempt $RETRY_COUNT/$MAX_RETRIES..."
    sleep 2
done
echo "✅ Database is ready"
echo ""

# Check if we have enough tables
TABLE_COUNT=$($PSQL -c "SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public' AND tablename LIKE 'archon_%';" 2>/dev/null | tr -d ' ')

echo "📊 Found $TABLE_COUNT archon tables"
echo ""

if [ -z "$TABLE_COUNT" ] || [ "$TABLE_COUNT" -lt 30 ]; then
    echo "⚠️  Database schema incomplete ($TABLE_COUNT tables)"
    echo "   Running automatic database setup..."
    echo ""
    
    # Run setup script
    if [ -f "/home/zebastjan/dev/archon/scripts/db_setup.sh" ]; then
        /home/zebastjan/dev/archon/scripts/db_setup.sh
        exit_code=$?
        
        if [ $exit_code -eq 0 ]; then
            echo ""
            echo "✅ Database setup complete"
            exit 0
        else
            echo ""
            echo "❌ Database setup failed"
            exit 1
        fi
    else
        echo "❌ Setup script not found at /home/zebastjan/dev/archon/scripts/db_setup.sh"
        exit 1
    fi
else
    echo "✅ Database schema is complete ($TABLE_COUNT tables)"
    
    # Quick verification of critical components
    echo ""
    echo "🔍 Quick verification..."
    
    # Check pgvector
    vector_exists=$($PSQL -c "SELECT 1 FROM pg_extension WHERE extname = 'vector';" 2>/dev/null)
    if [ -n "$vector_exists" ]; then
        echo "  ✅ pgvector extension"
    else
        echo "  ❌ pgvector missing - embeddings will not work!"
    fi
    
    # Check settings
    settings_count=$($PSQL -c "SELECT COUNT(*) FROM archon_settings;" 2>/dev/null | tr -d ' ')
    if [ -n "$settings_count" ] && [ "$settings_count" -gt 0 ]; then
        echo "  ✅ Settings table ($settings_count settings)"
    else
        echo "  ⚠️  Settings table empty"
    fi
    
    echo ""
    echo "✅ Database is ready for Archon"
    exit 0
fi
