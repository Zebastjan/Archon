-- Migration: Add PostgreSQL function for upserting git commits with branch array merging
-- Issue: Supabase .upsert() replaces entire record, overwriting branches array
-- Solution: Use ON CONFLICT DO UPDATE with array concatenation to merge branches

-- Function to upsert git commits with branch array merging
-- FIXED: Now includes parent_shas parameter for merge commit tracking
CREATE OR REPLACE FUNCTION upsert_git_commit_with_branch_merge(
    p_repo_id UUID,
    p_commit_sha TEXT,
    p_author_name TEXT,
    p_author_email TEXT,
    p_commit_date TIMESTAMP WITH TIME ZONE,
    p_message TEXT,
    p_parent_shas TEXT[],
    p_branches TEXT[]
) RETURNS UUID AS $$
DECLARE
    v_commit_id UUID;
    v_existing_branches TEXT[];
BEGIN
    -- Check if commit already exists
    SELECT id, branches INTO v_commit_id, v_existing_branches
    FROM archon_git_commits
    WHERE repo_id = p_repo_id AND commit_sha = p_commit_sha;

    IF v_commit_id IS NOT NULL THEN
        -- Merge branches: combine existing + new, remove duplicates
        UPDATE archon_git_commits
        SET
            branches = ARRAY(
                SELECT DISTINCT unnest(
                    COALESCE(v_existing_branches, ARRAY[]::text[]) ||
                    p_branches
                )
            ),
            -- Only set parent_shas if not already set (they are immutable)
            parent_shas = COALESCE(parent_shas, p_parent_shas),
            -- Update other fields with latest values
            author_name = p_author_name,
            author_email = p_author_email,
            commit_date = p_commit_date,
            message = p_message,
            updated_at = NOW()
        WHERE id = v_commit_id;

        RETURN v_commit_id;
    ELSE
        -- Insert new commit with parent_shas
        INSERT INTO archon_git_commits (
            repo_id, commit_sha, author_name, author_email,
            commit_date, message, parent_shas, branches
        )
        VALUES (
            p_repo_id, p_commit_sha, p_author_name, p_author_email,
            p_commit_date, p_message, p_parent_shas, p_branches
        )
        RETURNING id INTO v_commit_id;

        RETURN v_commit_id;
    END IF;
END;
$$ LANGUAGE plpgsql;
