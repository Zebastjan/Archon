-- Stage 3: Knowledge Graph Schema Migration
-- This MUST run before LFM2-8B summarization (Stage 5)
-- Run: docker exec archon psql -U archon -d archon -f /docker-entrypoint-initdb.d/migrations/013_knowledge_graph_schema.sql

-- =====================================================
-- SECTION 1: Add entity identity for cross-commit tracking
-- =====================================================

-- Add entity_identity column
ALTER TABLE archon_code_entities 
ADD COLUMN IF NOT EXISTS entity_identity TEXT;

-- Add branch_name
ALTER TABLE archon_code_entities 
ADD COLUMN IF NOT EXISTS branch_name TEXT;

-- Add parent_commit_sha
ALTER TABLE archon_code_entities 
ADD COLUMN IF NOT EXISTS parent_commit_sha TEXT;

-- Add change_type
ALTER TABLE archon_code_entities 
ADD COLUMN IF NOT EXISTS change_type TEXT;

ALTER TABLE archon_code_entities 
ADD CONSTRAINT change_type_check 
CHECK (change_type IN ('added', 'modified', 'deleted', 'unchanged'));

-- Add summary column (for LFM2-8B)
ALTER TABLE archon_code_entities 
ADD COLUMN IF NOT EXISTS summary TEXT;

-- =====================================================
-- SECTION 2: Backfill entity_identity
-- =====================================================

-- Create temporary function
CREATE OR REPLACE FUNCTION compute_entity_identity()
RETURNS void AS $$
BEGIN
    UPDATE archon_code_entities 
    SET entity_identity = md5(
       _COALESCE(repo_id::text, '') || 
        _COALESCE(file_path, '') || 
        _COALESCE(name, '') || 
        _COALESCE(entity_type, '')
    )
    WHERE entity_identity IS NULL;
END;
$$ LANGUAGE plpgsql;

-- Run the backfill
SELECT compute_entity_identity();

-- =====================================================
-- SECTION 3: Create indexes for cross-commit queries
-- =====================================================

-- Entity identity index (for finding same entity across commits)
CREATE INDEX IF NOT EXISTS idx_entity_identity 
ON archon_code_entities(entity_identity);

-- Commit index
CREATE INDEX IF NOT EXISTS idx_entity_commit 
ON archon_code_entities(repo_id, commit_sha);

-- Branch index  
CREATE INDEX IF NOT EXISTS idx_entity_branch 
ON archon_code_entities(repo_id, branch_name);

-- File path index
CREATE INDEX IF NOT EXISTS idx_entity_file 
ON archon_code_entities(repo_id, file_path);

-- =====================================================
-- SECTION 4: Add entity_identity NOT NULL (after backfill)
-- =====================================================

ALTER TABLE archon_code_entities 
ALTER COLUMN entity_identity SET NOT NULL;

-- =====================================================
-- SECTION 5: Create documents table for documentation
-- =====================================================

CREATE TABLE IF NOT EXISTS archon_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repo_id UUID REFERENCES archon_code_repos(id),
    
    -- Location
    file_path TEXT NOT NULL,
    chunk_index INT DEFAULT 0,
    
    -- Content
    title TEXT,
    content TEXT NOT NULL,
    content_type TEXT,  -- 'section', 'heading', 'paragraph', 'code_block', 'list'
    
    -- Classification
    doc_type TEXT,  -- 'readme', 'adr', 'design', 'api', 'guide', 'other'
    language TEXT,  -- For code blocks: 'python', 'nim', etc.
    
    -- Semantic metadata
    heading_path TEXT,
    parent_headings JSONB DEFAULT '[]'::jsonb,
    
    -- AI
    embedding_1024 VECTOR(1024),
    summary TEXT,
    embedding_model TEXT,
    embedding_dimension INT,
    
    -- Git
    commit_sha TEXT,
    branch_name TEXT,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for documents
CREATE INDEX IF NOT EXISTS idx_doc_repo ON archon_documents(repo_id);
CREATE INDEX IF NOT EXISTS idx_doc_type ON archon_documents(doc_type);
CREATE INDEX IF NOT EXISTS idx_doc_file ON archon_documents(file_path);
CREATE INDEX IF NOT EXISTS idx_doc_embedding ON archon_documents USING ivfflat(embedding_1024 vector_cosine_ops);

-- =====================================================
-- SECTION 6: Expand relationship types
-- =====================================================

-- Check current constraint
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conname = 'archon_code_relationships_relationship_type_check';

-- Drop and recreate with more types
ALTER TABLE archon_code_relationships 
DROP CONSTRAINT IF EXISTS archon_code_relationships_relationship_type_check;

ALTER TABLE archon_code_relationships 
ADD CONSTRAINT archon_code_relationships_relationship_type_check 
CHECK (relationship_type IN (
    'DEFINES',
    'CALLS', 
    'INHERITS',
    'IMPLEMENTS',  -- class implements interface
    'USES',        -- uses/imports another entity
    'ANNOTATES',   -- decorator/macro applied
    'RETURNS',     -- returns type
    'ACCEPTS',     -- parameter types
    'DECORATES',   -- decorator on function
    'CONTAINS',    -- file contains entity
    'INSTANCE_OF', -- object instance type
    'RELATED_TO'   -- general relationship
));

-- =====================================================
-- VERIFICATION
-- =====================================================

DO $$
BEGIN
    RAISE NOTICE 'Knowledge Graph Schema Migration Complete!';
    
    -- Verify entity types
    RAISE NOTICE 'Entity types available:';
    BEGIN
        SELECT string_agg(unnorm, ', ')
        INTO STRICT e.types
        FROM unnest(ARRAY['function', 'method', 'class', 'interface', 'module', 'variable', 'constant', 'import', 'decorator', 'proc', 'func', 'iterator', 'template', 'macro', 'type', 'unknown'])
        AS unnorm;
        RAISE NOTICE '  Entity types: %', e.types
        FROM (SELECT 1) AS t;
    END;
    
    -- Verify relationship types
    RAISE NOTICE 'Relationship types available:';
    PERFORM 1;
END;
$$;

-- Show final table structure
SELECT column_name, data_type, is_nullable
FROM information_schema.columns 
WHERE table_name IN ('archon_code_entities', 'archon_documents', 'archon_code_relationships')
ORDER BY table_name, ordinal_position;