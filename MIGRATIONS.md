# Database Migrations

Archon uses a simple Python-based migration system.

## Quick Start

Migrations run automatically when you start the server:
```bash
python start.py
```

## Manual Migration Commands

### Check current version
```bash
cd python
python -m src.server.database.migrations status
```

### Run migrations
```bash
cd python
python -m src.server.database.migrations migrate
```

### Reset database (DANGER: deletes all data!)
```bash
cd python
python -m src.server.database.migrations reset
```

## Migration Files

Migrations are defined in `python/src/server/database/migrations.py`.

Each migration has:
- `version`: Integer version number
- `name`: Human-readable name
- `up_sql`: SQL to apply the migration
- `down_sql`: SQL to rollback (optional)

## Current Schema

### Version 1: Core Tables
- `archon_projects` - Projects
- `archon_tasks` - Tasks
- `archon_sources` - Knowledge sources
- `archon_code_repos` - Code repositories

### Version 2: Audit Tables
- `archon_audit_rules` - Audit rule definitions
- `archon_audit_findings` - Audit findings

### Version 3: Default Data
- Inserts default audit rules

### Version 4: Knowledge Tables
- `archon_knowledge_items` - Documents with embeddings
- `archon_code_entities` - Code entities with embeddings

## pgvector Support

The schema works with or without pgvector:

**With pgvector:**
```sql
CREATE EXTENSION vector;
-- Embeddings stored as VECTOR(1536)
```

**Without pgvector:**
```sql
-- Embeddings stored as JSONB arrays [0.1, 0.2, ...]
```

The application handles both transparently.

## Schema SQL

For reference, see `python/schema.sql` - a complete schema dump that can be used with `psql` directly if needed.
