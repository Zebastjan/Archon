-- Migration: Add PostgreSQL function for upserting git commits with branch array merging
-- Issue: Supabase .upsert() replaces entire record, overwriting branches array
-- Solution: Use ON CONFLICT DO UPDATE with array concatenation to merge branches

-- Function to upsert git commits with branch array merging
CREATE OR REPLACE FUNCTION upsert_git_commit_with_branch_merge(
    p_repo_id UUID,
    p_commit_sha TEXT,
    p_author_name TEXT,
    p_author_email TEXT,
    p_commit_date TIMESTAMP WITH TIME ZONE,
    p_message TEXT,
    p_branches TEXT[]
) RETURNS VOID AS $$
BEGIN
    INSERT INTO archon_git_commits (
        repo_id, commit_sha, author_name, author_email,
        commit_date, message, branches
    )
    VALUES (
        p_repo_id, p_commit_sha, p_author_name, p_author_email,
        p_commit_date, p_message, p_branches
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
        message = EXCLUDED.message;
END;
$$ LANGUAGE plpgsql;
