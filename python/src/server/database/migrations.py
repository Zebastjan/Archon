"""
Database Migration System for Archon

REQUIRES: pgvector extension
Vector dimensions: 1024 (BGE-Large)
"""

import logging
from typing import Any

from ..services.database import get_database_connector

logger = logging.getLogger(__name__)


class Migration:
    """Single migration."""

    def __init__(self, version: int, name: str, up_sql: str, down_sql: str = ""):
        self.version = version
        self.name = name
        self.up_sql = up_sql
        self.down_sql = down_sql

    async def apply(self) -> bool:
        """Apply this migration."""
        try:
            db = get_database_connector()
            await db.execute(self.up_sql)

            await db.execute(
                "INSERT INTO archon_migrations (version, name, applied_at) VALUES ($1, $2, NOW()) ON CONFLICT (version) DO UPDATE SET applied_at = NOW()",
                self.version,
                self.name,
            )

            logger.info(f"Applied migration {self.version}: {self.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to apply migration {self.version}: {e}")
            return False


MIGRATIONS = [
    Migration(
        version=1,
        name="create_core_tables",
        up_sql="""
        CREATE TABLE IF NOT EXISTS archon_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TIMESTAMP DEFAULT NOW()
        );
        
        CREATE TABLE IF NOT EXISTS archon_projects (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            title TEXT NOT NULL,
            description TEXT,
            github_repo TEXT,
            docs JSONB DEFAULT '[]',
            features JSONB DEFAULT '[]',
            data JSONB DEFAULT '[]',
            pinned BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
        
        CREATE TABLE IF NOT EXISTS archon_tasks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID REFERENCES archon_projects(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'todo',
            assignee TEXT DEFAULT 'User',
            task_order INTEGER DEFAULT 0,
            priority TEXT DEFAULT 'medium',
            feature TEXT,
            sources JSONB DEFAULT '[]',
            code_examples JSONB DEFAULT '[]',
            archived BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
        
        CREATE TABLE IF NOT EXISTS archon_sources (
            source_id TEXT PRIMARY KEY,
            name TEXT,
            url TEXT,
            description TEXT
        );
        
        CREATE TABLE IF NOT EXISTS archon_code_repos (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL,
            local_path TEXT,
            url TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
        """,
        down_sql="""
        DROP TABLE IF EXISTS archon_code_repos;
        DROP TABLE IF EXISTS archon_sources;
        DROP TABLE IF EXISTS archon_tasks;
        DROP TABLE IF EXISTS archon_projects;
        DROP TABLE IF EXISTS archon_migrations;
        """,
    ),
    Migration(
        version=2,
        name="create_audit_tables",
        up_sql="""
        CREATE TABLE IF NOT EXISTS archon_audit_rules (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            rule_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            category TEXT,
            severity TEXT DEFAULT 'warning',
            is_active BOOLEAN DEFAULT TRUE
        );
        
        CREATE TABLE IF NOT EXISTS archon_audit_findings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            rule_id UUID REFERENCES archon_audit_rules(id),
            repo_id UUID,
            severity TEXT DEFAULT 'warning',
            message TEXT,
            file_path TEXT,
            line_start INTEGER,
            status TEXT DEFAULT 'open',
            created_at TIMESTAMP DEFAULT NOW()
        );
        """,
        down_sql="""
        DROP TABLE IF EXISTS archon_audit_findings;
        DROP TABLE IF EXISTS archon_audit_rules;
        """,
    ),
    Migration(
        version=3,
        name="insert_default_audit_rules",
        up_sql="""
        INSERT INTO archon_audit_rules (rule_id, name, description, category, severity)
        VALUES
        ('complexity-high', 'High Cyclomatic Complexity', 'Function has high complexity', 'complexity', 'warning'),
        ('missing-docstring', 'Missing Docstring', 'Function lacks documentation', 'style', 'info'),
        ('broad-except', 'Broad Exception Handler', 'Catches all exceptions', 'security', 'error')
        ON CONFLICT (rule_id) DO NOTHING;
        """,
        down_sql="DELETE FROM archon_audit_rules WHERE rule_id IN ('complexity-high', 'missing-docstring', 'broad-except');",
    ),
    Migration(
        version=4,
        name="create_code_entities_table",
        up_sql="""
        CREATE TABLE IF NOT EXISTS archon_code_entities (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            repo_id UUID REFERENCES archon_code_repos(id) ON DELETE CASCADE,
            entity_type TEXT NOT NULL,
            name TEXT NOT NULL,
            file_path TEXT,
            line_start INTEGER,
            line_end INTEGER,
            source_code TEXT,
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMP DEFAULT NOW()
        );
        """,
        down_sql="DROP TABLE IF EXISTS archon_code_entities;",
    ),
    Migration(
        version=5,
        name="create_embedding_system",
        up_sql="""
        -- Create pgvector extension (will fail gracefully if not installed)
        CREATE EXTENSION IF NOT EXISTS vector;
        
        -- Embedding models registry
        CREATE TABLE IF NOT EXISTS archon_embedding_models (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            model_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            dimensions INTEGER NOT NULL,
            provider TEXT,
            is_default BOOLEAN DEFAULT FALSE,
            config JSONB DEFAULT '{}',
            created_at TIMESTAMP DEFAULT NOW()
        );
        
        -- Insert default BGE-Large model (1024 dimensions)
        INSERT INTO archon_embedding_models (model_id, name, dimensions, provider, is_default)
        VALUES ('bge-large', 'BGE-Large', 1024, 'ollama', TRUE)
        ON CONFLICT (model_id) DO NOTHING;
        
        -- Knowledge items
        CREATE TABLE IF NOT EXISTS archon_knowledge_items (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            url TEXT NOT NULL,
            knowledge_type TEXT,
            title TEXT,
            content TEXT,
            metadata JSONB DEFAULT '{}',
            source_id TEXT REFERENCES archon_sources(source_id),
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
        
        -- Embeddings table with VECTOR type
        CREATE TABLE IF NOT EXISTS archon_embeddings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            item_id UUID NOT NULL,
            item_type TEXT NOT NULL,
            model_id TEXT REFERENCES archon_embedding_models(model_id),
            embedding VECTOR(1024),  -- BGE-Large dimensions
            chunk_index INTEGER DEFAULT 0,
            total_chunks INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(item_id, model_id, chunk_index)
        );
        
        -- Indexes
        CREATE INDEX IF NOT EXISTS idx_embeddings_item ON archon_embeddings(item_id, item_type);
        CREATE INDEX IF NOT EXISTS idx_code_entities_repo ON archon_code_entities(repo_id);
        """,
        down_sql="""
        DROP TABLE IF EXISTS archon_embeddings;
        DROP TABLE IF EXISTS archon_knowledge_items;
        DROP TABLE IF EXISTS archon_embedding_models;
        """,
    ),
    Migration(
        version=6,
        name="add_version_scope_to_code_entities",
        up_sql="""
        -- Add columns for version-scoped search (ADR-007)
        ALTER TABLE archon_code_entities ADD COLUMN IF NOT EXISTS branch_name TEXT;
        ALTER TABLE archon_code_entities ADD COLUMN IF NOT EXISTS commit_sha TEXT;
        ALTER TABLE archon_code_entities ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE;
        ALTER TABLE archon_code_entities ADD COLUMN IF NOT EXISTS parent_commit_sha TEXT;
        ALTER TABLE archon_code_entities ADD COLUMN IF NOT EXISTS change_type TEXT;  -- added, modified, deleted
        ALTER TABLE archon_code_entities ADD COLUMN IF NOT EXISTS entity_identity TEXT;  -- stable ID across commits

        -- Create index for efficient branch filtering
        CREATE INDEX IF NOT EXISTS idx_code_entities_branch 
        ON archon_code_entities(repo_id, branch_name, is_deleted);

        CREATE INDEX IF NOT EXISTS idx_code_entities_identity 
        ON archon_code_entities(repo_id, entity_identity);

        CREATE INDEX IF NOT EXISTS idx_code_entities_commit 
        ON archon_code_entities(commit_sha);
        """,
        down_sql="""
        DROP INDEX IF EXISTS idx_code_entities_branch;
        DROP INDEX IF EXISTS idx_code_entities_identity;
        DROP INDEX IF EXISTS idx_code_entities_commit;
        ALTER TABLE archon_code_entities DROP COLUMN IF EXISTS branch_name;
        ALTER TABLE archon_code_entities DROP COLUMN IF EXISTS commit_sha;
        ALTER TABLE archon_code_entities DROP COLUMN IF EXISTS is_deleted;
        ALTER TABLE archon_code_entities DROP COLUMN IF EXISTS parent_commit_sha;
        ALTER TABLE archon_code_entities DROP COLUMN IF EXISTS change_type;
        ALTER TABLE archon_code_entities DROP COLUMN IF EXISTS entity_identity;
        """,
    ),
    Migration(
        version=7,
        name="add_audit_feedback_loop_tables",
        up_sql="""
        -- Extend archon_audit_findings with outcome tracking (ADR-011)
        ALTER TABLE archon_audit_findings ADD COLUMN IF NOT EXISTS resolution_note TEXT;
        ALTER TABLE archon_audit_findings ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMP;
        ALTER TABLE archon_audit_findings ADD COLUMN IF NOT EXISTS category TEXT;

        -- Audit outcomes table
        CREATE TABLE IF NOT EXISTS archon_audit_outcomes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            finding_id UUID REFERENCES archon_audit_findings(id) ON DELETE CASCADE,
            outcome_type TEXT NOT NULL,  -- bug_filed, bug_hit_production, validated_correct
            outcome_at TIMESTAMP DEFAULT NOW(),
            notes TEXT,
            related_issue_id TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );

        -- Learning events table
        CREATE TABLE IF NOT EXISTS archon_audit_learning_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            finding_id UUID REFERENCES archon_audit_findings(id) ON DELETE CASCADE,
            outcome_id UUID REFERENCES archon_audit_outcomes(id) ON DELETE SET NULL,
            event_type TEXT NOT NULL,  -- false_negative, dismissed_then_hit, correct_dismissal
            retrospective_task_id TEXT,
            correlation_data JSONB DEFAULT '{}',
            created_at TIMESTAMP DEFAULT NOW()
        );

        -- Indexes for efficient querying
        CREATE INDEX IF NOT EXISTS idx_audit_outcomes_finding 
        ON archon_audit_outcomes(finding_id);

        CREATE INDEX IF NOT EXISTS idx_audit_outcomes_type 
        ON archon_audit_outcomes(outcome_type);

        CREATE INDEX IF NOT EXISTS idx_learning_events_finding 
        ON archon_audit_learning_events(finding_id);

        CREATE INDEX IF NOT EXISTS idx_learning_events_type 
        ON archon_audit_learning_events(event_type);

        CREATE INDEX IF NOT EXISTS idx_audit_findings_category 
        ON archon_audit_findings(category);
        """,
        down_sql="""
        DROP INDEX IF EXISTS idx_audit_findings_category;
        DROP INDEX IF EXISTS idx_learning_events_type;
        DROP INDEX IF EXISTS idx_learning_events_finding;
        DROP INDEX IF EXISTS idx_audit_outcomes_type;
        DROP INDEX IF EXISTS idx_audit_outcomes_finding;
        DROP TABLE IF EXISTS archon_audit_learning_events;
        DROP TABLE IF EXISTS archon_audit_outcomes;
        ALTER TABLE archon_audit_findings DROP COLUMN IF EXISTS category;
        ALTER TABLE archon_audit_findings DROP COLUMN IF EXISTS resolved_at;
        ALTER TABLE archon_audit_findings DROP COLUMN IF EXISTS resolution_note;
        """,
    ),
    Migration(
        version=8,
        name="add_working_tree_indexing_support",
        up_sql="""
        -- Add source and commit_sha fields to archon_chunks (ADR-016)
        -- source: 'committed' or 'working_tree'
        -- commit_sha: SHA of the commit (NULL for working_tree source)
        ALTER TABLE archon_chunks ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'committed';
        ALTER TABLE archon_chunks ADD COLUMN IF NOT EXISTS commit_sha TEXT;
        ALTER TABLE archon_chunks ADD COLUMN IF NOT EXISTS file_path TEXT;
        ALTER TABLE archon_chunks ADD COLUMN IF NOT EXISTS repo_id UUID REFERENCES archon_code_repos(id) ON DELETE CASCADE;

        -- Index for efficient working_tree chunk queries
        CREATE INDEX IF NOT EXISTS idx_chunks_source ON archon_chunks(source);
        CREATE INDEX IF NOT EXISTS idx_chunks_file_path ON archon_chunks(file_path, repo_id);
        """,
        down_sql="""
        DROP INDEX IF EXISTS idx_chunks_file_path;
        DROP INDEX IF EXISTS idx_chunks_source;
        ALTER TABLE archon_chunks DROP COLUMN IF EXISTS repo_id;
        ALTER TABLE archon_chunks DROP COLUMN IF EXISTS file_path;
        ALTER TABLE archon_chunks DROP COLUMN IF EXISTS commit_sha;
        ALTER TABLE archon_chunks DROP COLUMN IF EXISTS source;
        """,
    ),
]


async def check_pgvector() -> bool:
    """Check if pgvector extension is available and working."""
    try:
        db = get_database_connector()
        # Try to create and use vector
        await db.execute("CREATE EXTENSION IF NOT EXISTS vector")
        result = await db.fetchval("SELECT '[1,2,3]'::vector(3)")
        return result is not None
    except Exception:
        return False


async def get_current_version() -> int:
    """Get current schema version."""
    try:
        db = get_database_connector()
        result = await db.fetchval("""
            SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'archon_migrations')
        """)
        if not result:
            return 0
        version = await db.fetchval("SELECT COALESCE(MAX(version), 0) FROM archon_migrations")
        return version or 0
    except Exception:
        return 0


async def migrate(target_version: int | None = None) -> bool:
    """Apply all pending migrations."""
    # First check pgvector
    if not await check_pgvector():
        logger.error("pgvector extension is not available!")
        logger.error("See PGVECTOR_INSTALL.md for installation instructions")
        return False

    current = await get_current_version()
    logger.info(f"Current schema version: {current}")

    if target_version is None:
        target_version = max(m.version for m in MIGRATIONS)

    if current >= target_version:
        logger.info(f"Already at version {current}")
        return True

    for migration in MIGRATIONS:
        if migration.version > current and migration.version <= target_version:
            print(f"Applying migration {migration.version}: {migration.name}...")
            success = await migration.apply()
            if not success:
                logger.error(f"Migration {migration.version} failed!")
                return False

    logger.info(f"Migrated to version {target_version}")
    return True


async def reset() -> bool:
    """Reset database."""
    print("WARNING: This will DELETE ALL DATA!")
    for migration in reversed(MIGRATIONS):
        if migration.down_sql:
            print(f"Rolling back migration {migration.version}...")
            try:
                db = get_database_connector()
                await db.execute(migration.down_sql)
            except Exception as e:
                logger.warning(f"Rollback issue: {e}")
    print("Database reset")
    return True


async def status():
    """Show migration status."""
    pgv = await check_pgvector()
    current = await get_current_version()
    latest = max(m.version for m in MIGRATIONS)

    print(f"pgvector available: {pgv}")
    print(f"Current version: {current}")
    print(f"Latest version: {latest}")
    print(f"Pending: {latest - current}")


async def main():
    """CLI for migrations."""
    import argparse
    import asyncio
    import sys

    parser = argparse.ArgumentParser(description="Database migrations")
    parser.add_argument("command", choices=["migrate", "reset", "status"])
    args = parser.parse_args()

    if args.command == "migrate":
        success = await migrate()
        sys.exit(0 if success else 1)
    elif args.command == "reset":
        await reset()
    elif args.command == "status":
        await status()


if __name__ == "__main__":
    import asyncio
    import sys

    asyncio.run(main())
