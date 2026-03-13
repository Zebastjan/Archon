#!/bin/bash
# Setup script for local PostgreSQL with pgvector for Archon

set -e

echo "🐘 Setting up local PostgreSQL for Archon..."

# Configuration
DB_NAME="${ARCHON_DB_NAME:-archon}"
DB_USER="${ARCHON_DB_USER:-archon}"
DB_PASSWORD="${ARCHON_DB_PASSWORD:-archon_local_dev}"
DB_PORT="${ARCHON_DB_PORT:-5432}"
CONTAINER_NAME="archon-postgres"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Stop and remove existing container if it exists
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "🛑 Stopping existing PostgreSQL container..."
    docker stop $CONTAINER_NAME >/dev/null 2>&1 || true
    echo "🗑️  Removing existing PostgreSQL container..."
    docker rm $CONTAINER_NAME >/dev/null 2>&1 || true
fi

echo "📦 Pulling PostgreSQL with pgvector image..."
docker pull ankane/pgvector:latest

echo "🚀 Starting PostgreSQL container..."
docker run -d \
    --name $CONTAINER_NAME \
    -e POSTGRES_USER=$DB_USER \
    -e POSTGRES_PASSWORD=$DB_PASSWORD \
    -e POSTGRES_DB=$DB_NAME \
    -p $DB_PORT:5432 \
    -v archon_postgres_data:/var/lib/postgresql/data \
    --restart unless-stopped \
    ankane/pgvector:latest

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL to be ready..."
sleep 5

MAX_RETRIES=30
RETRY_COUNT=0

while ! docker exec $CONTAINER_NAME pg_isready -U $DB_USER -d $DB_NAME >/dev/null 2>&1; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "❌ PostgreSQL failed to start after $MAX_RETRIES attempts"
        exit 1
    fi
    echo "  Waiting... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

echo "✅ PostgreSQL is ready!"

# Create extensions
echo "🔧 Creating PostgreSQL extensions..."
docker exec -i $CONTAINER_NAME psql -U $DB_USER -d $DB_NAME <<EOF
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
\dx
EOF

echo ""
echo "✅ Local PostgreSQL setup complete!"
echo ""
echo "📋 Connection Details:"
echo "  Host: localhost"
echo "  Port: $DB_PORT"
echo "  Database: $DB_NAME"
echo "  User: $DB_USER"
echo "  Password: $DB_PASSWORD"
echo ""
echo "🔌 Connection URL:"
echo "  postgresql://$DB_USER:$DB_PASSWORD@localhost:$DB_PORT/$DB_NAME"
echo ""
echo "📁 Data Volume: archon_postgres_data (persistent)"
echo ""
echo "🛠️  Useful Commands:"
echo "  Start: docker start $CONTAINER_NAME"
echo "  Stop:  docker stop $CONTAINER_NAME"
echo "  Logs:  docker logs -f $CONTAINER_NAME"
echo "  Shell: docker exec -it $CONTAINER_NAME psql -U $DB_USER -d $DB_NAME"
echo ""
echo "⚠️  Next Steps:"
echo "  1. Add to your .env file:"
echo "     ARCHON_DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@localhost:$DB_PORT/$DB_NAME"
echo ""
echo "  2. Run migrations:"
echo "     ./scripts/run_migrations.sh"
echo ""
