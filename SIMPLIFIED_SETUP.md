# Archon - Local-First Setup

## Philosophy

- **Local-only**: Everything runs on your machine, no external services
- **No Docker**: PostgreSQL runs as a local process, not a container
- **Unified**: Single Python application, not microservices
- **Strict Config**: Validated YAML, no foot-guns allowed

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Archon Application (Single Python Process)                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ FastAPI     │  │ MCP Tools   │  │ Services            │  │
│  │ Routes      │  │ (Direct)    │  │ (Unified)           │  │
│  │ /api/*      │  │ /mcp        │  │                     │  │
│  └──────┬──────┘  └─────────────┘  └─────────────────────┘  │
│         │                        │                          │
│         │                        ▼ Direct imports            │
│         │              ┌─────────────────────┐               │
│         │              │   PostgreSQL        │               │
│         │              │   (Local Process)   │               │
│         │              │   ~/.local/share/   │               │
│         │              │     archon/postgres │               │
│         │              └─────────────────────┘               │
│         │                        ▲                          │
│         └────────────────────────┘                          │
│              SQL via asyncpg                                │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

### 1. Install PostgreSQL

**Ubuntu/Debian:**
```bash
sudo apt install postgresql postgresql-contrib pgvector
sudo systemctl stop postgresql      # We manage it ourselves
sudo systemctl disable postgresql
```

**macOS:**
```bash
brew install postgresql@15
brew services stop postgresql       # We manage it ourselves
```

**Arch:**
```bash
sudo pacman -S postgresql postgresql-libs
sudo systemctl stop postgresql
sudo systemctl disable postgresql
```

**Note:** pgvector is optional but recommended for vector search. Without it, embeddings are stored as JSONB arrays (works fine, just slower for similarity search).

### 2. Verify Installation

```bash
which initdb   # Should show path
which pg_ctl   # Should show path
```

## Configuration

Edit `python/config.yaml`:

```yaml
server:
  host: "127.0.0.1"        # Localhost only
  port: 8181               # Must be 1024-65535
  reload: true             # Auto-reload in dev
  log_level: "INFO"

database:
  # Local PostgreSQL (NOT Docker!)
  user: "archon"           # Your username or 'archon'
  name: "archon"           # Database name
  password: null           # null = use peer auth (socket)
  port: 5432               # Standard Postgres port
  data_dir: "~/.local/share/archon/postgres"
  
  # Socket auth is preferred (no password needed)
  # Falls back to TCP if socket not available

features:
  code_intelligence:
    enabled: true
    languages: ["python", "typescript", "javascript", "nim"]
```

## Usage

### Start Everything

```bash
python start.py
```

This will:
1. Check PostgreSQL is installed
2. Initialize data directory if needed (`~/.local/share/archon/postgres`)
3. Start PostgreSQL on port 5432
4. Create user and database if needed
5. Run migrations
6. Start Archon server on port 8181

### Manual PostgreSQL Management

```bash
# Start just PostgreSQL
cd python && python -m src.local_postgres start

# Stop PostgreSQL
cd python && python -m src.local_postgres stop

# Check status
cd python && python -m src.local_postgres status

# Connect with psql
cd python && python -m src.local_postgres psql
```

### Development

```bash
cd python
python -m uvicorn src.unified_main:app --reload --port 8181
```

## Data Location

Everything is stored locally in your home directory:

```
~/.local/share/archon/
├── postgres/          # PostgreSQL data files
│   ├── PG_VERSION
│   ├── base/
│   └── postmaster.pid
├── repos/             # Cloned/indexed repositories
└── logs/              # Application logs
    ├── archon.log
    └── postgres.log

~/.cache/archon/       # Temporary/cache files
```

## MCP Client Configuration

```json
{
  "mcpServers": {
    "archon": {
      "command": "http://localhost:8181/mcp",
      "type": "sse"
    }
  }
}
```

## Why This Design?

### vs SQLite
- **Better concurrency**: SQLite locks on writes, Postgres handles multiple connections
- **Full SQL support**: Window functions, CTEs, complex queries
- **pgvector**: Vector embeddings for RAG
- **Robustness**: Better crash recovery, transactions

### vs Docker Postgres
- **No container overhead**: Direct process management
- **Native filesystem**: Easy to inspect, backup, migrate
- **Socket auth**: More secure (no password in config)
- **Familiar tooling**: Use standard psql, pg_dump, etc.

### vs Microservices
- **Single process**: No HTTP overhead between components
- **Direct imports**: Full type safety, no serialization
- **Easier debugging**: One stack trace, one log stream
- **Simpler deployment**: Just Python, no Docker

## Troubleshooting

### "PostgreSQL not installed"
Install PostgreSQL for your OS (see Prerequisites)

### "Port 5432 already in use"
Another Postgres is running. Either:
- Stop system Postgres: `sudo systemctl stop postgresql`
- Change port in config.yaml: `port: 5433`

### "Permission denied"
Ensure your user can write to `~/.local/share/archon`:
```bash
mkdir -p ~/.local/share/archon
chmod 755 ~/.local/share/archon
```

### Reset Everything
```bash
# Stop postgres
python -m src.local_postgres stop

# Delete data (WARNING: loses all data!)
rm -rf ~/.local/share/archon/postgres

# Re-initialize
python start.py
```

## Migration from Docker Setup

Old Docker Compose had: postgres, server, mcp, frontend containers

New setup has:
- PostgreSQL running locally (managed by Archon)
- Single Python process (server + MCP combined)
- Frontend can be served by FastAPI static files or run separately

Update your workflow:
- `docker compose up` → `python start.py`
- `docker compose down` → Ctrl+C (stops gracefully)
- `docker logs` → `tail ~/.local/share/archon/logs/archon.log`
