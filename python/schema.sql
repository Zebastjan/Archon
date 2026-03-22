-- Archon Database Schema v2.0
-- 
-- REQUIRED: pgvector extension
-- Vector dimensions: 1024 (BGE-Large)
-- Supports multiple embeddings per document for A/B testing

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- Migration tracking
CREATE TABLE IF NOT EXISTS archon_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TIMESTAMP DEFAULT NOW()
);

-- Projects
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

-- Tasks
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

-- Sources for RAG
CREATE TABLE IF NOT EXISTS archon_sources (
    source_id TEXT PRIMARY KEY,
    name TEXT,
    url TEXT,
    description TEXT
);

-- Embedding models registry
-- Supports multiple models for A/B testing
CREATE TABLE IF NOT EXISTS archon_embedding_models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id TEXT UNIQUE NOT NULL,  -- e.g., 'bge-large', 'text-embedding-3-small'
    name TEXT NOT NULL,
    dimensions INTEGER NOT NULL,      -- e.g., 1024 for BGE-Large
    provider TEXT,                    -- 'ollama', 'openai', 'local'
    is_default BOOLEAN DEFAULT FALSE,
    config JSONB DEFAULT '{}',        -- Provider-specific config
    created_at TIMESTAMP DEFAULT NOW()
);

-- Knowledge items with multiple embeddings support
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

-- Embeddings table (supports multiple embeddings per item)
CREATE TABLE IF NOT EXISTS archon_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id UUID NOT NULL,              -- References knowledge_items or code_entities
    item_type TEXT NOT NULL,            -- 'knowledge' or 'code'
    model_id TEXT REFERENCES archon_embedding_models(model_id),
    embedding VECTOR(1024),             -- BGE-Large dimensions
    chunk_index INTEGER DEFAULT 0,      -- For chunked documents
    total_chunks INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Index for fast similarity search
CREATE INDEX IF NOT EXISTS idx_embeddings_item 
ON archon_embeddings(item_id, item_type);

-- Create IVFFlat index for approximate search
-- Note: Run this after inserting some data for better performance:
-- CREATE INDEX ON archon_embeddings USING ivfflat (embedding vector_cosine_ops);

-- Code repositories
CREATE TABLE IF NOT EXISTS archon_code_repos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    local_path TEXT,
    url TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Code entities
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

-- Audit rules
CREATE TABLE IF NOT EXISTS archon_audit_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT,
    severity TEXT DEFAULT 'warning',
    is_active BOOLEAN DEFAULT TRUE
);

-- Audit findings
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

-- Insert default embedding model (BGE-Large)
INSERT INTO archon_embedding_models (model_id, name, dimensions, provider, is_default)
VALUES ('bge-large', 'BGE-Large', 1024, 'ollama', TRUE)
ON CONFLICT (model_id) DO NOTHING;

-- Insert default audit rules
INSERT INTO archon_audit_rules (rule_id, name, description, category, severity)
VALUES
('complexity-high', 'High Cyclomatic Complexity', 'Function has high complexity', 'complexity', 'warning'),
('missing-docstring', 'Missing Docstring', 'Function lacks documentation', 'style', 'info'),
('broad-except', 'Broad Exception Handler', 'Catches all exceptions', 'security', 'error')
ON CONFLICT (rule_id) DO NOTHING;

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_tasks_project_id ON archon_tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON archon_tasks(status);
CREATE INDEX IF NOT EXISTS idx_findings_repo_id ON archon_audit_findings(repo_id);
CREATE INDEX IF NOT EXISTS idx_findings_status ON archon_audit_findings(status);
CREATE INDEX IF NOT EXISTS idx_code_entities_repo ON archon_code_entities(repo_id);

-- Create IVFFlat index for vector search (creates 100 lists)
-- Higher values = more accurate but slower
-- Run after inserting ~10k vectors for best results
-- CREATE INDEX IF NOT EXISTS idx_embeddings_vector ON archon_embeddings 
-- USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Record schema version
INSERT INTO archon_migrations (version, name, applied_at)
VALUES (5, 'schema_v2_pgvector', NOW())
ON CONFLICT (version) DO NOTHING;
