-- Add archon_code_repos table for repository tracking with GitHub linking

CREATE TABLE IF NOT EXISTS archon_code_repos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    local_path TEXT UNIQUE NOT NULL,
    github_owner TEXT,
    github_repo TEXT,
    github_url TEXT,
    branch TEXT DEFAULT 'main',
    last_commit_sha TEXT,
    last_synced TIMESTAMPTZ,
    auto_sync BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_archon_code_repos_github 
ON archon_code_repos(github_owner, github_repo);

CREATE INDEX IF NOT EXISTS idx_archon_code_repos_local_path 
ON archon_code_repos(local_path);

-- Auto-update timestamp trigger
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables 
               WHERE table_schema = 'public' 
               AND table_name = 'archon_code_repos') THEN
        -- Only create trigger if it doesn't exist
        IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_archon_code_repos_updated_at') THEN
            CREATE TRIGGER update_archon_code_repos_updated_at
                BEFORE UPDATE ON archon_code_repos
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();
        END IF;
    END IF;
END $$;

-- Add repo_id to archon_code_entities if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'archon_code_entities' 
        AND column_name = 'repo_id'
    ) THEN
        ALTER TABLE archon_code_entities ADD COLUMN repo_id UUID;
    END IF;
END $$;

-- Create foreign key constraint (optional, for data integrity)
-- ALTER TABLE archon_code_entities 
-- ADD CONSTRAINT fk_archon_code_entities_repo 
-- FOREIGN KEY (repo_id) REFERENCES archon_code_repos(id) ON DELETE CASCADE;
