# Local PostgreSQL Setup Guide

This guide walks you through migrating from Supabase to local PostgreSQL for Archon.

## Why Local PostgreSQL?

- **Self-hosted**: No cloud dependency
- **Simpler**: Direct database connections without Supabase abstraction
- **Faster**: Local network latency vs internet round-trips
- **Privacy**: Data stays on your machine
- **Cost**: No monthly cloud fees

## Quick Start

### 1. Prerequisites

```bash
# Install Docker if not already installed
# macOS: brew install docker
# Ubuntu: sudo apt install docker.io
# Or download from https://docs.docker.com/get-docker/

# Verify Docker is running
docker ps
```

### 2. Setup Local PostgreSQL

```bash
# From the project root
cd /home/zebastjan/dev/archon
./scripts/setup_local_postgres.sh
```

This will:
- Pull PostgreSQL with pgvector Docker image
- Start container named `archon-postgres`
- Create database `archon` with user `archon`
- Enable extensions: vector, pgcrypto, pg_trgm
- Create persistent volume for data

### 3. Configure Environment

```bash
cd python

# Copy the example env file
cp ../.env.example .env

# Edit .env - use local database
# Comment out Supabase lines, uncomment ARCHON_DATABASE_URL:
ARCHON_DATABASE_URL=postgresql://archon:archon_local_dev@localhost:5432/archon
```

### 4. Run Migrations

```bash
# From project root
./scripts/run_migrations.sh
```

Or manually:
```bash
# If you have psql installed locally
psql postgresql://archon:archon_local_dev@localhost:5432/archon < migration/complete_setup.sql
psql postgresql://archon:archon_local_dev@localhost:5432/archon < migration/012_add_code_entities_and_relationships.sql
```

### 5. Install Dependencies

```bash
cd python
uv pip install -e ".[server]"
```

### 6. Test Connection

```bash
# Test database connection
python -c "
import asyncio
from src.server.services.database import get_database_connector

async def test():
    db = get_database_connector()
    await db.initialize()
    result = await db.fetch('SELECT version()')
    print('Connected to:', result[0]['version'])
    await db.close()

asyncio.run(test())
"
```

### 7. Start Archon Server

```bash
# Make sure you're in the python directory
cd python

# Start the server
uv run python -m src.server.main
```

## Management Commands

```bash
# Start PostgreSQL
docker start archon-postgres

# Stop PostgreSQL
docker stop archon-postgres

# View logs
docker logs -f archon-postgres

# Connect to database shell
docker exec -it archon-postgres psql -U archon -d archon

# Backup database
docker exec archon-postgres pg_dump -U archon archon > backup.sql

# Restore database
docker exec -i archon-postgres psql -U archon -d archon < backup.sql
```

## Switching Back to Supabase

If you need to switch back to Supabase temporarily:

```bash
# Edit python/.env
# Comment out: ARCHON_DATABASE_URL
# Uncomment: SUPABASE_URL and SUPABASE_SERVICE_KEY

# Restart server
```

## Troubleshooting

### "Connection refused"
- Make sure PostgreSQL container is running: `docker ps`
- Check port 5432 is not in use: `lsof -i :5432`
- Verify DATABASE_URL in .env is correct

### "database 'archon' does not exist"
- Container might not have initialized correctly
- Remove and recreate: `docker rm archon-postgres` then run setup script again

### "permission denied for table"
- Migrations might not have been applied
- Run migrations script again

### "asyncpg module not found"
- Install dependencies: `uv pip install asyncpg sqlalchemy`

## Architecture

```
┌─────────────────┐
│   Archon Server │
│   (Python)      │
└────────┬────────┘
         │
    ┌────▼────┐
    │ asyncpg │  (Async PostgreSQL driver)
    └────┬────┘
         │
    ┌────▼─────────────┐
    │ PostgreSQL +     │
    │ pgvector         │
    │ (Docker)         │
    └──────────────────┘
```

## Next Steps

Now that you have local PostgreSQL running, the services will automatically use it when `ARCHON_DATABASE_URL` is set. You can:

1. **Remove Supabase container** if you were using it locally
2. **Test the multi-language code intelligence** features
3. **Ingest the Archon repo** to dogfood the system

## Comparison: Supabase vs Local PostgreSQL

| Feature | Supabase | Local PostgreSQL |
|---------|----------|------------------|
| **Setup** | Cloud signup | Docker run |
| **Latency** | Network RTT | Localhost |
| **Data Control** | Cloud provider | Your machine |
| **Scaling** | Automatic | Manual |
| **Backups** | Managed | Self-managed |
| **Cost** | Monthly fee | Free |
| **Offline Use** | No | Yes |
| **RLS Policies** | Built-in | Manual implementation |

## Migration from Supabase Cloud

If you have data in Supabase cloud you want to migrate:

```bash
# Export from Supabase
pg_dump -h your-project.supabase.co -U postgres -d postgres > supabase_backup.sql

# Import to local
psql postgresql://archon:archon_local_dev@localhost:5432/archon < supabase_backup.sql
```

**Note**: You may need to disable RLS policies or set correct permissions during import.

---

**Questions?** Check the main README or file an issue.
