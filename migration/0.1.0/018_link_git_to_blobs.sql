-- Migration: Link Git to Document Blobs
-- Purpose: Connect Git file tracking to the document blob and source tables
--
-- Changes:
-- 1. Add git_file_id and git_commit_id columns to archon_document_blobs
-- 2. Add repo_id column to archon_sources
-- 3. Create indexes for new foreign key relationships

BEGIN;

-- ============================================
-- Add Git columns to document blobs
-- ============================================

ALTER TABLE archon_document_blobs
ADD COLUMN IF NOT EXISTS git_file_id UUID REFERENCES archon_git_files(id) ON DELETE SET NULL;

ALTER TABLE archon_document_blobs
ADD COLUMN IF NOT EXISTS git_commit_id UUID REFERENCES archon_git_commits(id) ON DELETE SET NULL;

-- ============================================
-- Add repo_id to sources for Git sources
-- ============================================

ALTER TABLE archon_sources
ADD COLUMN IF NOT EXISTS repo_id UUID REFERENCES archon_git_repositories(id) ON DELETE SET NULL;

-- ============================================
-- Create indexes for Git relationships
-- ============================================

CREATE INDEX IF NOT EXISTS idx_document_blobs_git_file_id ON archon_document_blobs(git_file_id);
CREATE INDEX IF NOT EXISTS idx_document_blobs_git_commit_id ON archon_document_blobs(git_commit_id);
CREATE INDEX IF NOT EXISTS idx_sources_repo_id ON archon_sources(repo_id);

-- Combined index for Git-specific blob queries
CREATE INDEX IF NOT EXISTS idx_document_blobs_git_lookup
    ON archon_document_blobs(git_file_id, git_commit_id)
    WHERE git_file_id IS NOT NULL;

-- ============================================
-- Comments for documentation
-- ============================================

COMMENT ON COLUMN archon_document_blobs.git_file_id IS
    'Reference to Git file entry if this blob is from a Git repository';

COMMENT ON COLUMN archon_document_blobs.git_commit_id IS
    'Reference to Git commit where this file version was captured';

COMMENT ON COLUMN archon_sources.repo_id IS
    'Reference to Git repository if this source is a Git-based knowledge source';

-- Record migration application
INSERT INTO archon_migrations (version, migration_name)
VALUES ('0.1.0', '018_link_git_to_blobs')
ON CONFLICT (version, migration_name) DO NOTHING;

COMMIT;
