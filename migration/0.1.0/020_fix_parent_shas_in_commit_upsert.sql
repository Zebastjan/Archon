-- Migration: Fix parent_shas not being stored in commit upsert function
-- Issue: parent_shas parameter was missing from upsert_git_commit_with_branch_merge
-- Impact: Merge commits cannot be properly identified or tracked
-- Fix: Add p_parent_shas parameter and include in INSERT/UPDATE

-- Drop old function
DROP FUNCTION IF EXISTS upsert_git_commit_with_branch_merge(
    UUID, TEXT, TEXT, TEXT, TIMESTAMP WITH TIME ZONE, TEXT, TEXT[]
);

-- Recreate function with parent_shas support
CREATE OR REPLACE FUNCTION upsert_git_commit_with_branch_merge(
    p_repo_id UUID,
    p_commit_sha TEXT,
    p_author_name TEXT,
    p_author_email TEXT,
    p_commit_date TIMESTAMP WITH TIME ZONE,
    p_message TEXT,
    p_parent_shas TEXT[],
    p_branches TEXT[]
) RETURNS VOID AS $$
BEGIN
    INSERT INTO archon_git_commits (
        repo_id, commit_sha, author_name, author_email,
        commit_date, message, parent_shas, branches
    )
    VALUES (
        p_repo_id, p_commit_sha, p_author_name, p_author_email,
        p_commit_date, p_message, p_parent_shas, p_branches
    )
    ON CONFLICT (repo_id, commit_sha)
    DO UPDATE SET
        -- Merge branches array: combine existing + new, remove duplicates
        branches = ARRAY(
            SELECT DISTINCT unnest(
                COALESCE(archon_git_commits.branches, ARRAY[]::text[]) ||
                EXCLUDED.branches
            )
        ),
        -- Update other fields with latest values
        author_name = EXCLUDED.author_name,
        author_email = EXCLUDED.author_email,
        commit_date = EXCLUDED.commit_date,
        message = EXCLUDED.message,
        -- Set parent_shas if not already set (parent_shas are immutable)
        parent_shas = COALESCE(archon_git_commits.parent_shas, EXCLUDED.parent_shas);
END;
$$ LANGUAGE plpgsql;

-- Add comment explaining the fix
COMMENT ON FUNCTION upsert_git_commit_with_branch_merge IS
    'Upserts git commits with branch array merging and parent SHA tracking. '
    'Fixed in migration 020 to include parent_shas parameter for merge commit support.';
