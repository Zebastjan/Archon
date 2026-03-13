#!/bin/bash
# Run all database migrations on local PostgreSQL

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load environment variables if .env exists
if [ -f "$PROJECT_ROOT/python/.env" ]; then
    export $(grep -v '^#' "$PROJECT_ROOT/python/.env" | xargs)
fi

# Database URL priority: env var > default
DB_URL="${ARCHON_DATABASE_URL:-postgresql://archon:archon_local_dev@localhost:5432/archon}"

echo "🗄️  Running Archon database migrations..."
echo "   Database: $DB_URL"
echo ""

# Check if psql is available
if ! command -v psql &> /dev/null; then
    echo "⚠️  psql not found locally. Using Docker..."
    
    # Check if container is running
    if ! docker ps --format '{{.Names}}' | grep -q "^archon-postgres$"; then
        echo "❌ PostgreSQL container is not running. Start it with:"
        echo "   docker start archon-postgres"
        exit 1
    fi
    
    # Use docker to run migrations
    RUN_MIGRATION() {
        docker exec -i archon-postgres psql "$DB_URL" < "$1"
    }
else
    # Use local psql
    RUN_MIGRATION() {
        psql "$DB_URL" < "$1"
    }
fi

# List of migrations in order
MIGRATIONS=(
    "$PROJECT_ROOT/migration/complete_setup.sql"
    "$PROJECT_ROOT/migration/012_add_code_entities_and_relationships.sql"
)

for migration in "${MIGRATIONS[@]}"; do
    if [ -f "$migration" ]; then
        echo "📄 Running: $(basename "$migration")"
        if RUN_MIGRATION "$migration"; then
            echo "   ✅ Success"
        else
            echo "   ❌ Failed"
            exit 1
        fi
    else
        echo "⚠️  Migration not found: $migration"
    fi
done

echo ""
echo "✅ All migrations completed successfully!"
echo ""
