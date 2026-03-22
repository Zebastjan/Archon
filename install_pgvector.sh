#!/bin/bash
# Install pgvector extension locally for Archon's PostgreSQL

set -e

PGVECTOR_VERSION="0.8.0"
POSTGRES_VERSION="18"
DATA_DIR="$HOME/.local/share/archon/postgres"

echo "Installing pgvector ${PGVECTOR_VERSION} for PostgreSQL ${POSTGRES_VERSION}..."

# Create temp directory
TMP_DIR=$(mktemp -d)
cd "$TMP_DIR"

# Download pgvector
echo "Downloading pgvector..."
curl -L -o pgvector.tar.gz "https://github.com/pgvector/pgvector/archive/refs/tags/v${PGVECTOR_VERSION}.tar.gz"
tar xzf pgvector.tar.gz
cd "pgvector-${PGVECTOR_VERSION}"

# Build pgvector
echo "Building pgvector..."
make USE_PGXS=1 PG_CONFIG=$(which pg_config)

# Install to data directory
echo "Installing pgvector..."
# Get extension directory
EXT_DIR=$(pg_config --sharedir)/extension

# Copy extension files to user's postgres data dir for local install
mkdir -p "$DATA_DIR/extensions"
cp vector.control "$DATA_DIR/extensions/"
cp sql/vector--*.sql "$DATA_DIR/extensions/"

# Copy shared library
LIB_DIR=$(pg_config --pkglibdir)
mkdir -p "$DATA_DIR/lib"

# Find the compiled library
if [ -f "vector.so" ]; then
    cp vector.so "$DATA_DIR/lib/"
elif [ -f "./vector.so" ]; then
    cp ./vector.so "$DATA_DIR/lib/"
else
    echo "Looking for vector.so..."
    find . -name "vector.so" -exec cp {} "$DATA_DIR/lib/" \;
fi

# Clean up
cd ..
rm -rf "$TMP_DIR"

echo "pgvector installed to $DATA_DIR/extensions/"
echo ""
echo "Add to postgresql.conf:"
echo "  shared_preload_libraries = 'vector'"
echo ""
echo "Or start postgres with:"
echo "  pg_ctl -D $DATA_DIR start"
