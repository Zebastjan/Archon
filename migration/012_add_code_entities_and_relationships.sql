-- =====================================================
-- Migration: Add Code Entities and Relationships Tables
-- Phase 1: Multi-Language Code Intelligence
-- =====================================================
-- Creates tables for storing extracted code entities (functions, classes, etc.)
-- and their relationships (calls, inherits, imports) parsed via Tree-sitter.
-- Supports multi-dimensional embeddings (384, 768, 1024, 1536, 3072)
-- following the existing Archon pattern.
--
-- Run this in your PostgreSQL/Supabase SQL Editor
-- =====================================================

-- =====================================================
-- SECTION 0: UTILITY FUNCTIONS
-- =====================================================

-- Create update_updated_at_column function if it doesn't exist
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $func$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$func$ LANGUAGE plpgsql;

-- =====================================================
-- SECTION 1: CODE ENTITIES TABLE
-- =====================================================

CREATE TABLE IF NOT EXISTS archon_code_entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repo_id UUID,
    
    -- Location
    file_path TEXT NOT NULL,
    line_start INT NOT NULL,
    line_end INT NOT NULL,
    
    -- Entity metadata
    entity_type TEXT NOT NULL CHECK (entity_type IN (
        'function', 'method', 'class', 'interface', 
        'module', 'variable', 'constant', 'import', 'decorator'
    )),
    name TEXT NOT NULL,
    signature TEXT,
    docstring TEXT,
    source_code TEXT,
    
    -- Multi-dimensional embeddings (following existing Archon pattern)
    embedding_384 VECTOR(384),   -- Small models (all-MiniLM-L6-v2)
    embedding_768 VECTOR(768),   -- BGE-small
    embedding_1024 VECTOR(1024), -- BGE-base, Ollama models  
    embedding_1536 VECTOR(1536), -- OpenAI text-embedding-3-small
    embedding_3072 VECTOR(3072), -- OpenAI text-embedding-3-large
    
    -- Model tracking
    embedding_model TEXT,
    embedding_dimension INT,
    
    -- Language
    language TEXT NOT NULL,
    
    -- Git tracking
    commit_sha TEXT NOT NULL,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- SECTION 2: CODE RELATIONSHIPS TABLE (Graph Edges)
-- =====================================================

CREATE TABLE IF NOT EXISTS archon_code_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    source_entity_id UUID NOT NULL REFERENCES archon_code_entities(id) ON DELETE CASCADE,
    target_entity_id UUID NOT NULL REFERENCES archon_code_entities(id) ON DELETE CASCADE,
    
    relationship_type TEXT NOT NULL CHECK (relationship_type IN (
        'CALLS', 'INHERITS', 'IMPORTS', 'DEFINES', 'USES', 
        'DECORATES', 'RETURNS', 'ACCEPTS', 'RAISES', 'IMPLEMENTS'
    )),
    
    -- Optional metadata (line number, confidence, etc.)
    metadata JSONB DEFAULT '{}',
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- SECTION 3: INDEXES
-- =====================================================

-- Entity indexes
CREATE INDEX IF NOT EXISTS idx_code_entities_repo ON archon_code_entities(repo_id);
CREATE INDEX IF NOT EXISTS idx_code_entities_file ON archon_code_entities(file_path);
CREATE INDEX IF NOT EXISTS idx_code_entities_type ON archon_code_entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_code_entities_language ON archon_code_entities(language);
CREATE INDEX IF NOT EXISTS idx_code_entities_commit ON archon_code_entities(commit_sha);
CREATE INDEX IF NOT EXISTS idx_code_entities_name ON archon_code_entities(name);

-- Multi-dimensional embedding indexes (ivfflat for ANN search)
CREATE INDEX IF NOT EXISTS idx_code_entities_embedding_384 ON archon_code_entities 
    USING ivfflat (embedding_384 vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_code_entities_embedding_768 ON archon_code_entities 
    USING ivfflat (embedding_768 vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_code_entities_embedding_1024 ON archon_code_entities 
    USING ivfflat (embedding_1024 vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_code_entities_embedding_1536 ON archon_code_entities 
    USING ivfflat (embedding_1536 vector_cosine_ops) WITH (lists = 100);
-- Note: 3072-dimensional embeddings cannot have vector indexes due to pgvector 2000 dim limit

-- Relationship indexes
CREATE INDEX IF NOT EXISTS idx_code_relationships_source ON archon_code_relationships(source_entity_id);
CREATE INDEX IF NOT EXISTS idx_code_relationships_target ON archon_code_relationships(target_entity_id);
CREATE INDEX IF NOT EXISTS idx_code_relationships_type ON archon_code_relationships(relationship_type);

-- Composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_code_entities_repo_language ON archon_code_entities(repo_id, language);
CREATE INDEX IF NOT EXISTS idx_code_entities_repo_type ON archon_code_entities(repo_id, entity_type);

-- =====================================================
-- SECTION 4: TRIGGERS
-- =====================================================

-- Auto-update timestamp trigger
CREATE OR REPLACE TRIGGER update_code_entities_updated_at
    BEFORE UPDATE ON archon_code_entities
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- SECTION 5: ROW LEVEL SECURITY (Supabase only)
-- =====================================================

-- Only enable RLS if auth schema exists (Supabase)
DO $rls_block$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'auth') THEN
        ALTER TABLE archon_code_entities ENABLE ROW LEVEL SECURITY;
        ALTER TABLE archon_code_relationships ENABLE ROW LEVEL SECURITY;
        
        -- Service role policies
        CREATE POLICY "Allow service role full access to archon_code_entities" ON archon_code_entities
            FOR ALL USING (auth.role() = 'service_role');

        CREATE POLICY "Allow service role full access to archon_code_relationships" ON archon_code_relationships
            FOR ALL USING (auth.role() = 'service_role');

        -- Authenticated user policies (read-only for entities)
        CREATE POLICY "Allow authenticated users to read archon_code_entities" ON archon_code_entities
            FOR SELECT TO authenticated
            USING (true);

        CREATE POLICY "Allow authenticated users to read archon_code_relationships" ON archon_code_relationships
            FOR SELECT TO authenticated
            USING (true);
    END IF;
END $rls_block$;

-- =====================================================
-- SECTION 6: SEARCH FUNCTIONS
-- =====================================================

-- Multi-dimensional function to search for code entities by embedding
CREATE OR REPLACE FUNCTION match_archon_code_entities_multi (
  query_embedding VECTOR,
  embedding_dimension INTEGER,
  match_count INT DEFAULT 10,
  filter JSONB DEFAULT '{}'::jsonb,
  repo_filter UUID DEFAULT NULL
) RETURNS TABLE (
  id UUID,
  repo_id UUID,
  file_path TEXT,
  entity_type TEXT,
  name TEXT,
  signature TEXT,
  docstring TEXT,
  source_code TEXT,
  language TEXT,
  commit_sha TEXT,
  similarity FLOAT
)
LANGUAGE plpgsql
AS $$
#variable_conflict use_column
DECLARE
  sql_query TEXT;
  embedding_column TEXT;
BEGIN
  -- Determine which embedding column to use based on dimension
  CASE embedding_dimension
    WHEN 384 THEN embedding_column := 'embedding_384';
    WHEN 768 THEN embedding_column := 'embedding_768';
    WHEN 1024 THEN embedding_column := 'embedding_1024';
    WHEN 1536 THEN embedding_column := 'embedding_1536';
    WHEN 3072 THEN embedding_column := 'embedding_3072';
    ELSE RAISE EXCEPTION 'Unsupported embedding dimension: %', embedding_dimension;
  END CASE;

  -- Build dynamic query
  sql_query := format('
    SELECT id, repo_id, file_path, entity_type, name, signature, docstring, source_code, language, commit_sha,
           1 - (%I <=> $1) AS similarity
    FROM archon_code_entities
    WHERE (%I IS NOT NULL)
      AND metadata @> $3
      AND ($4 IS NULL OR repo_id = $4)
    ORDER BY %I <=> $1
    LIMIT $2',
    embedding_column, embedding_column, embedding_column);

  -- Execute dynamic query
  RETURN QUERY EXECUTE sql_query USING query_embedding, match_count, filter, repo_filter;
END;
$$;

-- Legacy compatibility function (defaults to 1536D)
CREATE OR REPLACE FUNCTION match_archon_code_entities (
  query_embedding VECTOR(1536),
  match_count INT DEFAULT 10,
  filter JSONB DEFAULT '{}'::jsonb,
  repo_filter UUID DEFAULT NULL
) RETURNS TABLE (
  id UUID,
  repo_id UUID,
  file_path TEXT,
  entity_type TEXT,
  name TEXT,
  signature TEXT,
  docstring TEXT,
  source_code TEXT,
  language TEXT,
  commit_sha TEXT,
  similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY SELECT * FROM match_archon_code_entities_multi(query_embedding, 1536, match_count, filter, repo_filter);
END;
$$;

-- Function to get entity relationships with traversal
CREATE OR REPLACE FUNCTION get_entity_relationships (
  entity_id UUID,
  relationship_types TEXT[] DEFAULT NULL,
  direction TEXT DEFAULT 'both' -- 'incoming', 'outgoing', 'both'
) RETURNS TABLE (
  relationship_id UUID,
  related_entity_id UUID,
  relationship_type TEXT,
  entity_name TEXT,
  entity_type TEXT,
  file_path TEXT,
  metadata JSONB
)
LANGUAGE plpgsql
AS $$
BEGIN
  -- Outgoing relationships
  IF direction IN ('outgoing', 'both') THEN
    RETURN QUERY
    SELECT 
      cr.id,
      cr.target_entity_id,
      cr.relationship_type,
      ce.name,
      ce.entity_type,
      ce.file_path,
      cr.metadata
    FROM archon_code_relationships cr
    JOIN archon_code_entities ce ON ce.id = cr.target_entity_id
    WHERE cr.source_entity_id = entity_id
      AND (relationship_types IS NULL OR cr.relationship_type = ANY(relationship_types));
  END IF;
  
  -- Incoming relationships
  IF direction IN ('incoming', 'both') THEN
    RETURN QUERY
    SELECT 
      cr.id,
      cr.source_entity_id,
      cr.relationship_type,
      ce.name,
      ce.entity_type,
      ce.file_path,
      cr.metadata
    FROM archon_code_relationships cr
    JOIN archon_code_entities ce ON ce.id = cr.source_entity_id
    WHERE cr.target_entity_id = entity_id
      AND (relationship_types IS NULL OR cr.relationship_type = ANY(relationship_types));
  END IF;
END;
$$;

-- Function to find path between entities (simple 2-hop)
CREATE OR REPLACE FUNCTION find_entity_path (
  source_entity_id UUID,
  target_entity_id UUID,
  max_depth INT DEFAULT 2
) RETURNS TABLE (
  path TEXT[],
  depth INT
)
LANGUAGE plpgsql
AS $$
BEGIN
  -- Direct relationship (depth 1)
  RETURN QUERY
  SELECT 
    ARRAY[se.name, te.name],
    1
  FROM archon_code_relationships cr
  JOIN archon_code_entities se ON se.id = cr.source_entity_id
  JOIN archon_code_entities te ON te.id = cr.target_entity_id
  WHERE cr.source_entity_id = source_entity_id 
    AND cr.target_entity_id = target_entity_id;
  
  -- 2-hop paths (depth 2)
  RETURN QUERY
  SELECT 
    ARRAY[s.name, i.name, t.name],
    2
  FROM archon_code_relationships cr1
  JOIN archon_code_relationships cr2 ON cr1.target_entity_id = cr2.source_entity_id
  JOIN archon_code_entities s ON s.id = cr1.source_entity_id
  JOIN archon_code_entities i ON i.id = cr1.target_entity_id
  JOIN archon_code_entities t ON t.id = cr2.target_entity_id
  WHERE cr1.source_entity_id = source_entity_id 
    AND cr2.target_entity_id = target_entity_id;
END;
$$;

-- =====================================================
-- SECTION 7: TABLE COMMENTS
-- =====================================================

COMMENT ON TABLE archon_code_entities IS 
    'Stores extracted code entities (functions, classes, etc.) parsed via Tree-sitter with multi-dimensional embeddings';

COMMENT ON COLUMN archon_code_entities.entity_type IS 
    'Type of code entity: function, method, class, interface, module, variable, constant, import, decorator';

COMMENT ON COLUMN archon_code_entities.signature IS 
    'Function signature or class definition line for quick reference';

COMMENT ON COLUMN archon_code_entities.embedding_model IS 
    'Name of the embedding model used (e.g., text-embedding-3-small, BGE-small)';

COMMENT ON TABLE archon_code_relationships IS 
    'Stores relationships between code entities (CALLS, INHERITS, IMPORTS, etc.) enabling graph queries';

COMMENT ON COLUMN archon_code_relationships.relationship_type IS 
    'Type of relationship: CALLS, INHERITS, IMPORTS, DEFINES, USES, DECORATES, RETURNS, ACCEPTS, RAISES, IMPLEMENTS';

COMMENT ON FUNCTION match_archon_code_entities_multi IS 
    'Multi-dimensional semantic search over code entities with configurable embedding dimensions';

COMMENT ON FUNCTION get_entity_relationships IS 
    'Get all relationships for a code entity with optional filtering by type and direction';

COMMENT ON FUNCTION find_entity_path IS 
    'Find paths between two code entities (up to 2 hops)';

-- =====================================================
-- SECTION 8: MIGRATION TRACKING
-- =====================================================

-- Only track migration if archon_migrations table exists
DO $migrate_block$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'archon_migrations'
    ) THEN
        INSERT INTO archon_migrations (version, migration_name)
        VALUES ('0.1.0', '012_add_code_entities_and_relationships')
        ON CONFLICT (version, migration_name) DO NOTHING;
    END IF;
END $migrate_block$;

-- =====================================================
-- SECTION 9: VERIFICATION
-- =====================================================

-- Verify table creation
DO $verify_block$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name = 'archon_code_entities'
    ) THEN
        RAISE NOTICE 'Table archon_code_entities created successfully';
    ELSE
        RAISE EXCEPTION 'Table archon_code_entities was not created';
    END IF;
    
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name = 'archon_code_relationships'
    ) THEN
        RAISE NOTICE 'Table archon_code_relationships created successfully';
    ELSE
        RAISE EXCEPTION 'Table archon_code_relationships was not created';
    END IF;
END $verify_block$;

-- =====================================================
-- MIGRATION COMPLETE
-- =====================================================
-- Next steps:
-- 1. Install tree-sitter Python dependencies
-- 2. Run code entity extraction on existing repositories
-- 3. Test MCP tools for code search
-- =====================================================
