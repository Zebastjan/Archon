-- Migration: Git-Aware Knowledge Base Architecture
-- Purpose: Add native Git repository tracking with commit and file history support
--
-- Changes:
-- 1. Create archon_git_repositories table for Git sources
-- 2. Create archon_git_commits table for commit history
-- 3. Create archon_git_files table for file-level tracking
-- 4. Add necessary indexes and constraints

BEGIN;

-- ============================================
-- Git Repositories
-- ============================================

CREATE TABLE IF NOT EXISTS archon_git_repositories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id TEXT NOT NULL REFERENCES archon_sources(source_id) ON DELETE CASCADE,
    repo_url TEXT NOT NULL,
    repo_name TEXT NOT NULL,
    owner TEXT,
    default_branch TEXT NOT NULL DEFAULT 'main',
    current_head_sha TEXT,
    last_crawled_at TIMESTAMPTZ,
    crawl_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (crawl_status IN ('pending', 'crawling', 'completed', 'failed')),
    crawl_error JSONB,
    config JSONB DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(source_id)
);

CREATE INDEX IF NOT EXISTS idx_git_repos_source_id ON archon_git_repositories(source_id);
CREATE INDEX IF NOT EXISTS idx_git_repos_url ON archon_git_repositories(repo_url);
CREATE INDEX IF NOT EXISTS idx_git_repos_status ON archon_git_repositories(crawl_status);
CREATE INDEX IF NOT EXISTS idx_git_repos_owner_name ON archon_git_repositories(owner, repo_name);

-- ============================================
-- Git Commits
-- ============================================

CREATE TABLE IF NOT EXISTS archon_git_commits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repo_id UUID NOT NULL REFERENCES archon_git_repositories(id) ON DELETE CASCADE,
    commit_sha TEXT NOT NULL,
    parent_shas TEXT[] DEFAULT ARRAY[]::TEXT[],
    author_name TEXT,
    author_email TEXT,
    author_date TIMESTAMPTZ,
    committer_name TEXT,
    committer_email TEXT,
    commit_date TIMESTAMPTZ,
    message TEXT,
    branches TEXT[] DEFAULT ARRAY[]::TEXT[],
    tags TEXT[] DEFAULT ARRAY[]::TEXT[],
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(repo_id, commit_sha)
);

CREATE INDEX IF NOT EXISTS idx_git_commits_repo_id ON archon_git_commits(repo_id);
CREATE INDEX IF NOT EXISTS idx_git_commits_sha ON archon_git_commits(commit_sha);
CREATE INDEX IF NOT EXISTS idx_git_commits_date ON archon_git_commits(commit_date);
CREATE INDEX IF NOT EXISTS idx_git_commits_author ON archon_git_commits(author_email);
CREATE INDEX IF NOT EXISTS idx_git_commits_branches ON archon_git_commits USING GIN (branches);

-- ============================================
-- Git Files
-- ============================================

CREATE TABLE IF NOT EXISTS archon_git_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repo_id UUID NOT NULL REFERENCES archon_git_repositories(id) ON DELETE CASCADE,
    commit_id UUID NOT NULL REFERENCES archon_git_commits(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_extension TEXT,
    blob_sha TEXT NOT NULL,
    file_size INTEGER,
    language TEXT,
    is_binary BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(repo_id, commit_id, file_path)
);

CREATE INDEX IF NOT EXISTS idx_git_files_repo_id ON archon_git_files(repo_id);
CREATE INDEX IF NOT EXISTS idx_git_files_commit_id ON archon_git_files(commit_id);
CREATE INDEX IF NOT EXISTS idx_git_files_path ON archon_git_files(file_path);
CREATE INDEX IF NOT EXISTS idx_git_files_extension ON archon_git_files(file_extension);
CREATE INDEX IF NOT EXISTS idx_git_files_language ON archon_git_files(language);
CREATE INDEX IF NOT EXISTS idx_git_files_blob_sha ON archon_git_files(blob_sha);

-- ============================================
-- Comments for documentation
-- ============================================

COMMENT ON TABLE archon_git_repositories IS
    'Git repositories tracked as knowledge sources with crawl state';

COMMENT ON TABLE archon_git_commits IS
    'Git commit history with authorship and branch/tag information';

COMMENT ON TABLE archon_git_files IS
    'File-level tracking for each commit with language and binary detection';

COMMENT ON COLUMN archon_git_repositories.config IS
    'Repository configuration: {branch_filter: ["main", "develop"], file_patterns: ["**/*.md"], exclude_patterns: ["**/node_modules/**"], max_file_size: 1048576, max_commits: 1000, since_date: "2024-01-01", enable_history: true}';

COMMENT ON COLUMN archon_git_repositories.current_head_sha IS
    'SHA of the most recent commit crawled from the default branch';

COMMENT ON COLUMN archon_git_commits.parent_shas IS
    'Array of parent commit SHAs (empty for initial commit, 1+ for merges)';

COMMENT ON COLUMN archon_git_commits.branches IS
    'Array of branches containing this commit';

COMMENT ON COLUMN archon_git_commits.tags IS
    'Array of tags pointing to this commit';

COMMENT ON COLUMN archon_git_files.blob_sha IS
    'Git blob SHA for content deduplication and change detection';

COMMENT ON COLUMN archon_git_files.language IS
    'Programming language detected from file extension and content';

COMMENT ON COLUMN archon_git_files.is_binary IS
    'Whether the file is binary (skipped from text processing)';

-- Enable RLS on Git tables
ALTER TABLE archon_git_repositories ENABLE ROW LEVEL SECURITY;
ALTER TABLE archon_git_commits ENABLE ROW LEVEL SECURITY;
ALTER TABLE archon_git_files ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access to git_repositories" ON archon_git_repositories
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Service role full access to git_commits" ON archon_git_commits
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Service role full access to git_files" ON archon_git_files
    FOR ALL USING (true) WITH CHECK (true);

COMMIT;

-- Record migration application
INSERT INTO archon_migrations (version, migration_name)
VALUES ('0.1.0', '017_add_git_tables')
ON CONFLICT (version, migration_name) DO NOTHING;
