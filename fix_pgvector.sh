#!/bin/bash
# Fix pgvector installation for Archon

echo "============================================"
echo "Fixing pgvector Installation"
echo "============================================"
echo ""

# Option 1: Use yay-built package (if available)
if [ -f "$HOME/.cache/yay/pgvector/pgvector-0.8.2-1-x86_64.pkg.tar.zst" ]; then
    echo "Found yay-built pgvector package"
    echo "Installing with sudo..."
    sudo pacman -U "$HOME/.cache/yay/pgvector/pgvector-0.8.2-1-x86_64.pkg.tar.zst"
    
    if [ $? -eq 0 ]; then
        echo "✓ pgvector installed successfully"
        
        # Create extension in database
        echo "Creating extension in Archon database..."
        sudo -u postgres psql -c "CREATE EXTENSION IF NOT EXISTS vector;" archon 2>/dev/null || \
        psql -h 127.0.0.1 -p 5433 -U postgres -d archon -c "CREATE EXTENSION IF NOT EXISTS vector;"
        
        echo "✓ pgvector extension created"
        echo ""
        echo "Testing..."
        psql -h 127.0.0.1 -p 5433 -U archon -d archon -c "SELECT '[1,2,3]'::vector(3);"
        
        exit 0
    fi
fi

# Option 2: Try building from source
echo "Package not found, building from source..."
echo "This requires sudo for installation"
echo ""

TMP_DIR=$(mktemp -d)
cd "$TMP_DIR"

# Download and build
git clone --branch v0.8.2 https://github.com/pgvector/pgvector.git
cd pgvector
make

# Install
sudo make install

# Cleanup
cd /
rm -rf "$TMP_DIR"

# Create extension
echo "Creating extension..."
sudo -u postgres psql -c "CREATE EXTENSION IF NOT EXISTS vector;" archon 2>/dev/null || \
psql -h 127.0.0.1 -p 5433 -U postgres -d archon -c "CREATE EXTENSION IF NOT EXISTS vector;"

echo ""
echo "Testing..."
psql -h 127.0.0.1 -p 5433 -U archon -d archon -c "SELECT '[1,2,3]'::vector(3);"
