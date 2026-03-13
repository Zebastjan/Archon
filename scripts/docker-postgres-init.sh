#!/bin/bash
# PostgreSQL initialization script for Docker
# Runs automatically when postgres container starts for the first time

set -e

echo "🗄️  Archon PostgreSQL Initialization"
echo "===================================="

# Wait for PostgreSQL to be ready
until pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DATABASE"; do
  echo "⏳ Waiting for PostgreSQL to be ready..."
  sleep 1
done

echo "✅ PostgreSQL is ready"

# Create extensions
echo "🔧 Creating PostgreSQL extensions..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS vector;
    CREATE EXTENSION IF NOT EXISTS pgcrypto;
    CREATE EXTENSION IF NOT EXISTS pg_trgm;
    \dx
EOSQL

echo "✅ Extensions created"

# Run migrations if they exist in the mounted volume
MIGRATIONS_DIR="/docker-entrypoint-initdb.d/migrations"

if [ -d "$MIGRATIONS_DIR" ]; then
    echo "📂 Found migrations directory"
    
    # Run migrations in order
    for migration in "$MIGRATIONS_DIR"/*.sql; do
        if [ -f "$migration" ]; then
            echo "📄 Running migration: $(basename "$migration")"
            psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f "$migration"
            echo "   ✅ Completed"
        fi
    done
    
    echo "✅ All migrations completed"
else
    echo "⚠️  No migrations directory found at $MIGRATIONS_DIR"
fi

echo ""
echo "🎉 PostgreSQL initialization complete!"
echo "   Database: $POSTGRES_DB"
echo "   User: $POSTGRES_USER"
echo ""
