-- Migration: Add chunking metadata and versioning support
-- Purpose: Enable rich metadata on chunks and support for re-chunking/A-B testing
--
-- Changes:
-- 1. Add hybrid schema columns to archon_chunks (section_path, page_number, element_type, order_index, metadata)
-- 2. Create archon_chunking_runs table for versioned chunking
-- 3. Add chunking_run_id foreign key to archon_chunks

BEGIN;

-- ============================================
-- Add hybrid schema columns to chunks
-- ============================================

-- Section hierarchy: ['Guide', 'Installation', 'Linux']
ALTER TABLE archon_chunks 
ADD COLUMN IF NOT EXISTS section_path TEXT[];

-- Title of the current section/heading
ALTER TABLE archon_chunks 
ADD COLUMN IF NOT EXISTS section_title TEXT;

-- Page number (for PDF/DOCX sources)
ALTER TABLE archon_chunks 
ADD COLUMN IF NOT EXISTS page_number INTEGER;

-- Element type: paragraph, heading, table, figure, code, list, etc.
ALTER TABLE archon_chunks 
ADD COLUMN IF NOT EXISTS element_type TEXT DEFAULT 'paragraph';

-- Order index for global ordering within a document (survives re-chunking)
ALTER TABLE archon_chunks 
ADD COLUMN IF NOT EXISTS order_index INTEGER;

-- Extra metadata as JSONB for extensibility
ALTER TABLE archon_chunks 
ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';

-- ============================================
-- Chunking runs table for versioning/A-B testing
-- ============================================

CREATE TABLE IF NOT EXISTS archon_chunking_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    blob_id UUID NOT NULL REFERENCES archon_document_blobs(id) ON DELETE CASCADE,
    strategy TEXT NOT NULL,  -- 'basic', 'token_aware', 'markdown_aware', 'code_aware', 'docling_hierarchical', 'docling_hybrid'
    config JSONB DEFAULT '{}',  -- {max_tokens: 512, overlap: 50, ...}
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(blob_id, strategy, (config->>'max_tokens'))
);

CREATE INDEX IF NOT EXISTS idx_chunking_runs_blob_id ON archon_chunking_runs(blob_id);
CREATE INDEX IF NOT EXISTS idx_chunking_runs_active ON archon_chunking_runs(blob_id, is_active) WHERE is_active = TRUE;

-- Add foreign key to chunks
ALTER TABLE archon_chunks 
ADD COLUMN IF NOT EXISTS chunking_run_id UUID REFERENCES archon_chunking_runs(id) ON DELETE SET NULL;

-- Update unique constraint to include chunking_run_id
ALTER TABLE archon_chunks DROP CONSTRAINT IF EXISTS archon_chunks_blob_id_chunk_index_key;
ALTER TABLE archon_chunks ADD UNIQUE(blob_id, chunking_run_id, chunk_index);

-- ============================================
-- Comments for documentation
-- ============================================

COMMENT ON TABLE archon_chunks IS 
    'Chunked content derived from document blobs (supports versioning via chunking_run_id)';

COMMENT ON COLUMN archon_chunks.section_path IS 
    'Hierarchical path of headings, e.g. ARRAY[''Guide'', ''Installation'', ''Linux'']';

COMMENT ON COLUMN archon_chunks.section_title IS 
    'Title of the current section or heading';

COMMENT ON COLUMN archon_chunks.page_number IS 
    'Page number for PDF/DOCX sources';

COMMENT ON COLUMN archon_chunks.element_type IS 
    'Type of content: paragraph, heading, table, figure, code, list, etc.';

COMMENT ON COLUMN archon_chunks.order_index IS 
    'Global ordering index within document (survives re-chunking)';

COMMENT ON COLUMN archon_chunks.metadata IS 
    'Extra metadata JSONB: figure_ids, table_ids, footnotes, Docling node IDs, etc.';

COMMENT ON TABLE archon_chunking_runs IS 
    'Tracks chunking runs for versioning and A-B testing';

COMMENT ON COLUMN archon_chunking_runs.strategy IS 
    'Chunking strategy: basic, token_aware, markdown_aware, code_aware, docling_hierarchical, docling_hybrid';

COMMENT ON COLUMN archon_chunking_runs.config IS 
    'Chunking configuration: {max_tokens, overlap, min_chunk_size, ...}';

COMMENT ON COLUMN archon_chunking_runs.is_active IS 
    'Whether this chunk set is currently used for retrieval';

-- Enable RLS on chunking_runs
ALTER TABLE archon_chunking_runs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access to chunking_runs" ON archon_chunking_runs
    FOR ALL USING (true) WITH CHECK (true);

COMMIT;

-- Record migration application
INSERT INTO archon_migrations (version, migration_name)
VALUES ('0.1.0', '016_add_chunking_metadata')
ON CONFLICT (version, migration_name) DO NOTHING;
