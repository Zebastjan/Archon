-- Test Database Setup Script
-- Sets up minimal schema for integration testing

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create test schema
CREATE SCHEMA IF NOT EXISTS public;

-- Git repositories table
CREATE TABLE IF NOT EXISTS archon_git_repositories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_path_normalized TEXT NOT NULL,
    repository_url TEXT,
    last_synced TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Git commits table
CREATE TABLE IF NOT EXISTS archon_git_commits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repo_id UUID NOT NULL REFERENCES archon_git_repositories(id) ON DELETE CASCADE,
    commit_sha TEXT NOT NULL,
    message TEXT,
    author_name TEXT,
    author_email TEXT,
    commit_date TIMESTAMP WITH TIME ZONE,
    parent_shas TEXT[],
    branches TEXT[] DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    embedding_768 vector(768),
    embedding_1024 vector(1024),
    embedding_1536 vector(1536),
    embedding_model TEXT,
    embedding_timestamp TIMESTAMP WITH TIME ZONE,
    embedding_source TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    UNIQUE(repo_id, commit_sha)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_git_commits_repo_id ON archon_git_commits(repo_id);
CREATE INDEX IF NOT EXISTS idx_git_commits_sha ON archon_git_commits(commit_sha);
CREATE INDEX IF NOT EXISTS idx_git_commits_branches ON archon_git_commits USING GIN(branches);
CREATE INDEX IF NOT EXISTS idx_git_commits_metadata ON archon_git_commits USING GIN(metadata);

-- Vector similarity search indexes (using HNSW for performance)
CREATE INDEX IF NOT EXISTS idx_git_commits_embedding_768_hnsw
    ON archon_git_commits
    USING hnsw (embedding_768 vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_git_commits_embedding_1536_hnsw
    ON archon_git_commits
    USING hnsw (embedding_1536 vector_cosine_ops);

-- Git files table
CREATE TABLE IF NOT EXISTS archon_git_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repo_id UUID NOT NULL REFERENCES archon_git_repositories(id) ON DELETE CASCADE,
    commit_id UUID NOT NULL REFERENCES archon_git_commits(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    blob_sha TEXT NOT NULL,
    is_binary BOOLEAN DEFAULT false,
    file_size BIGINT,
    language TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_git_files_repo_commit ON archon_git_files(repo_id, commit_id);
CREATE INDEX IF NOT EXISTS idx_git_files_path ON archon_git_files(file_path);

-- RPC function for commit upserting with branch merge
CREATE OR REPLACE FUNCTION upsert_git_commit_with_branch_merge(
    p_repo_id UUID,
    p_commit_sha TEXT,
    p_message TEXT,
    p_author_name TEXT,
    p_author_email TEXT,
    p_commit_date TIMESTAMP WITH TIME ZONE,
    p_parent_shas TEXT[],
    p_branches TEXT[],
    p_metadata JSONB DEFAULT '{}'::jsonb
) RETURNS UUID AS $$
DECLARE
    v_commit_id UUID;
    v_existing_branches TEXT[];
BEGIN
    -- Check if commit exists
    SELECT id, branches INTO v_commit_id, v_existing_branches
    FROM archon_git_commits
    WHERE repo_id = p_repo_id AND commit_sha = p_commit_sha;

    IF v_commit_id IS NOT NULL THEN
        -- Merge branches (union of existing and new)
        UPDATE archon_git_commits
        SET
            branches = ARRAY(SELECT DISTINCT unnest(COALESCE(v_existing_branches, '{}') || p_branches)),
            updated_at = now()
        WHERE id = v_commit_id;
    ELSE
        -- Insert new commit
        INSERT INTO archon_git_commits (
            repo_id, commit_sha, message, author_name, author_email,
            commit_date, parent_shas, branches, metadata
        ) VALUES (
            p_repo_id, p_commit_sha, p_message, p_author_name, p_author_email,
            p_commit_date, p_parent_shas, p_branches, p_metadata
        )
        RETURNING id INTO v_commit_id;
    END IF;

    RETURN v_commit_id;
END;
$$ LANGUAGE plpgsql;

-- RPC function for semantic commit search
CREATE OR REPLACE FUNCTION search_commits_by_embedding(
    query_embedding vector(1536),
    match_count INT DEFAULT 10,
    min_similarity FLOAT DEFAULT 0.0,
    filter_repo_id UUID DEFAULT NULL,
    filter_branch TEXT DEFAULT NULL,
    filter_since TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    filter_until TIMESTAMP WITH TIME ZONE DEFAULT NULL
) RETURNS TABLE (
    id UUID,
    commit_sha TEXT,
    repo_id UUID,
    message TEXT,
    author_name TEXT,
    author_email TEXT,
    commit_date TIMESTAMP WITH TIME ZONE,
    branches TEXT[],
    metadata JSONB,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.commit_sha,
        c.repo_id,
        c.message,
        c.author_name,
        c.author_email,
        c.commit_date,
        c.branches,
        c.metadata,
        1 - (c.embedding_1536 <=> query_embedding) AS similarity
    FROM archon_git_commits c
    WHERE
        c.embedding_1536 IS NOT NULL
        AND (filter_repo_id IS NULL OR c.repo_id = filter_repo_id)
        AND (filter_branch IS NULL OR filter_branch = ANY(c.branches))
        AND (filter_since IS NULL OR c.commit_date >= filter_since)
        AND (filter_until IS NULL OR c.commit_date <= filter_until)
        AND (1 - (c.embedding_1536 <=> query_embedding)) >= min_similarity
    ORDER BY c.embedding_1536 <=> query_embedding
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions
GRANT ALL ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA public TO postgres;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO postgres;
