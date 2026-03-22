# Installing pgvector (REQUIRED)

pgvector is **not optional** - it's core to Archon's architecture.

## Quick Install

### Arch Linux
```bash
yay -S pgvector
# Or from AUR:
git clone https://aur.archlinux.org/pgvector.git
cd pgvector
makepkg -si
```

### Ubuntu/Debian
```bash
sudo apt install postgresql-15-pgvector
```

### macOS
```bash
brew install pgvector
```

### From Source (any system)
```bash
git clone --branch v0.8.2 https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install
```

## Verify Installation

```bash
# Restart PostgreSQL
pg_ctl -D ~/.local/share/archon/postgres restart

# Test
psql -h 127.0.0.1 -p 5433 -U archon -d archon -c "CREATE EXTENSION vector; SELECT '[1,2,3]'::vector(3);"
```

Expected output:
```
 vector  
---------
 [1,2,3]
(1 row)
```

## Without Root Access

If you cannot install pgvector system-wide, you have these options:

### Option 1: Use System PostgreSQL (if pgvector installed)
```bash
# Use system postgres instead of local
sudo systemctl start postgresql
# Edit config.yaml to connect to system postgres
```

### Option 2: Conda/Miniconda (user-installable)
```bash
# Install conda
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh

# Install postgres with pgvector
conda install -c conda-forge postgresql pgvector
```

### Option 3: Docker (last resort)
While we want local-first, Docker ensures pgvector works:
```bash
docker run -d \
  -e POSTGRES_USER=archon \
  -e POSTGRES_PASSWORD=archon_local_dev \
  -e POSTGRES_DB=archon \
  -p 5433:5432 \
  ankane/pgvector:latest
```

## Vector Dimensions

Archon uses **1024 dimensions** for BGE-Large embeddings (not 1536 like OpenAI).

The schema supports multiple embedding models per document for A/B testing:
- Each embedding tagged with model name
- Can query across different models
- Can compare embedding quality

## Architecture Note

pgvector provides:
- Fast exact nearest neighbor search
- Approximate search with IVFFlat and HNSW indexes
- L2, inner product, and cosine distance
- Up to 16,000 dimensions

Without pgvector, we lose:
- Fast similarity search
- ANN indexes
- Proper vector distance calculations

This is why it's required, not optional.
