# Docker Compose Setup Guide

**The easiest way to run Archon with PostgreSQL**

---

## Quick Start (One Command)

```bash
cd /home/zebastjan/dev/archon

# Copy environment file
cp .env.example .env

# Start everything (PostgreSQL + Archon services)
docker compose up -d

# View logs
docker compose logs -f

# That's it! Archon is running at http://localhost:3737
```

---

## What Gets Started

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Compose Stack                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   postgres   │  │archon-server │  │  archon-mcp  │       │
│  │  (pgvector)  │◄─┤   (FastAPI)  │◄─┤  (MCP Server)│       │
│  │   :5432      │  │   :8181      │  │   :8051      │       │
│  └──────────────┘  └──────┬───────┘  └──────────────┘       │
│         ▲                 │                                  │
│         │                 ▼                                  │
│         │          ┌──────────────┐                         │
│         └──────────┤ archon-frontend│                        │
│                    │   (React)     │                        │
│                    │   :3737       │                        │
│                    └──────────────┘                         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

Services:
- **postgres**: PostgreSQL 15+ with pgvector extension
- **archon-server**: Main FastAPI backend
- **archon-mcp**: MCP server for Claude Code integration
- **archon-frontend**: React UI

---

## Commands

### Start Everything
```bash
docker compose up -d
```

### View Logs
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f archon-server
docker compose logs -f postgres
```

### Stop Everything
```bash
docker compose down
```

### Stop and Remove Data (⚠️ Destructive)
```bash
docker compose down -v  # Removes postgres data volume
```

### Restart a Service
```bash
docker compose restart archon-server
```

### Shell into Database
```bash
docker exec -it archon-postgres psql -U archon -d archon
```

---

## First Time Setup

### 1. Environment Variables

Edit `.env` file:
```bash
# Database (already set correctly for Docker)
ARCHON_DATABASE_URL=postgresql://archon:archon_local_dev@postgres:5432/archon

# Optional: Change default password
ARCHON_DB_PASSWORD=your_secure_password

# Required: API Keys (get from respective services)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GITHUB_PAT_TOKEN=ghp_...
```

### 2. Start Services
```bash
docker compose up -d
```

The first time you run this:
1. PostgreSQL container starts
2. Extensions (vector, pgcrypto, pg_trgm) are created
3. Migrations run automatically (`complete_setup.sql`, `012_add_code_entities...`)
4. Archon services start once database is ready

### 3. Verify Setup
```bash
# Check all services are healthy
docker compose ps

# Should show:
# NAME                STATUS
# archon-postgres     healthy
# archon-server       healthy
# archon-mcp          healthy
# archon-ui           healthy
```

### 4. Access Archon
- **UI**: http://localhost:3737
- **API**: http://localhost:8181
- **MCP**: http://localhost:8051

---

## Database Management

### Automatic Migrations
Migrations run automatically when the postgres container starts for the first time. No manual action needed.

### Manual Migrations
If you need to run migrations manually:
```bash
# Copy migration file to container
docker cp migration/012_add_code_entities_and_relationships.sql archon-postgres:/tmp/

# Run migration
docker exec -it archon-postgres psql -U archon -d archon -f /tmp/012_add_code_entities_and_relationships.sql
```

### Backup Database
```bash
docker exec archon-postgres pg_dump -U archon archon > backup_$(date +%Y%m%d).sql
```

### Restore Database
```bash
docker exec -i archon-postgres psql -U archon -d archon < backup_20240115.sql
```

### Reset Database (⚠️ Destructive)
```bash
# Stop and remove volume
docker compose down -v

# Start fresh (will re-run migrations)
docker compose up -d
```

---

## Optional Services

### Start with Agents
```bash
docker compose --profile agents up -d
```

### Start with Agent Work Orders
```bash
docker compose --profile work-orders up -d
```

### Start Everything
```bash
docker compose --profile agents --profile work-orders up -d
```

---

## Troubleshooting

### "Cannot connect to database"
```bash
# Check postgres is running
docker compose ps

# Check logs
docker compose logs postgres

# Restart
docker compose restart postgres
```

### "Migrations failed"
```bash
# Check if postgres is healthy first
docker compose ps

# View postgres logs
docker compose logs postgres

# Check if migrations ran
docker exec -it archon-postgres psql -U archon -d archon -c "\dt"
```

### "Service unhealthy"
```bash
# Restart specific service
docker compose restart archon-server

# View service logs
docker compose logs archon-server
```

### Port Already in Use
```bash
# Check what's using port 5432 (PostgreSQL)
lsof -i :5432

# Change port in .env
ARCHON_DB_PORT=5433

# Or stop the conflicting service
```

### Reset Everything
```bash
# Nuclear option - start completely fresh
docker compose down -v
docker compose up -d --build
```

---

## Configuration

### Change Database Password
Edit `.env`:
```bash
ARCHON_DB_PASSWORD=my_new_password
```

Then restart:
```bash
docker compose down -v  # Warning: destroys data
docker compose up -d
```

### Use External PostgreSQL
Edit `.env`:
```bash
ARCHON_DATABASE_URL=postgresql://user:pass@your-db-host:5432/archon
```

Then comment out the postgres service in docker-compose.yml or use:
```bash
docker compose up -d archon-server archon-mcp archon-frontend
```

### Switch Back to Supabase
Edit `.env`:
```bash
# Comment out ARCHON_DATABASE_URL
# ARCHON_DATABASE_URL=...

# Uncomment Supabase settings
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key
```

---

## Development

### Hot Reload
The docker-compose setup includes hot reload for development:
- `archon-server`: Reloads on Python changes
- `archon-frontend`: Reloads on React changes

### Mount Local Code
Already configured in docker-compose.yml:
```yaml
volumes:
  - ./python/src:/app/src
  - ./python/tests:/app/tests
```

### Run Tests in Docker
```bash
# Server tests
docker exec archon-server pytest tests/ -v

# Specific test
docker exec archon-server pytest tests/languages/test_language_support.py -v
```

---

## Architecture

```
Host Machine
    │
    ├── Port 3737 → archon-frontend (React UI)
    ├── Port 8181 → archon-server (FastAPI)
    ├── Port 8051 → archon-mcp (MCP Server)
    └── Port 5432 → postgres (PostgreSQL + pgvector)

Internal Docker Network (app-network)
    │
    ├── archon-server ↔ postgres (database)
    ├── archon-mcp ↔ archon-server (API calls)
    └── archon-frontend ↔ archon-server (API proxy in production)
```

---

## Data Persistence

PostgreSQL data is stored in a Docker volume:
```yaml
volumes:
  postgres_data:
    driver: local
```

This persists across container restarts but is lost if you run:
```bash
docker compose down -v  # ⚠️ Destroys data
```

To persist data permanently, consider:
1. Regular backups (see Backup section above)
2. Mounting a host directory instead of Docker volume

---

## Production Considerations

⚠️ **Default Docker setup is for development**

For production:
1. Change default passwords
2. Use SSL/TLS for database connections
3. Set up proper backups
4. Use environment-specific .env files
5. Consider external PostgreSQL (RDS, Cloud SQL, etc.)

---

## Summary

```bash
# Complete setup in 3 commands:
cd /home/zebastjan/dev/archon
cp .env.example .env
docker compose up -d

# Access at http://localhost:3737
```

PostgreSQL runs automatically, migrations apply on first start, and everything is configured to work together.
