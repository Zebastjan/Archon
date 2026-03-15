-- =====================================================
-- Migration: Add Worktree Safety Columns to Tasks
-- Phase 5: Worktree Safety & Branch Isolation
-- =====================================================
-- Adds columns for tracking task worktree context to prevent
-- conflicts when multiple instances work on different branches
-- =====================================================

-- =====================================================
-- SECTION 1: ADD WORKTREE COLUMNS
-- =====================================================

-- Add worktree tracking columns to archon_tasks
ALTER TABLE archon_tasks
    ADD COLUMN IF NOT EXISTS worktree_id UUID DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS branch_name TEXT DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS repo_path TEXT DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS base_branch TEXT DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS is_isolated BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS parent_worktree_id UUID DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS merge_conflicts_expected JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS worktree_created_at TIMESTAMPTZ DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS worktree_status TEXT DEFAULT 'active' CHECK (worktree_status IN ('active', 'locked', 'conflict', 'clean')),
    ADD COLUMN IF NOT EXISTS entities_affected JSONB DEFAULT '[]'::jsonb; -- Track which entities this task touches

-- =====================================================
-- SECTION 2: CREATE INDEXES
-- =====================================================

-- Indexes for worktree queries
CREATE INDEX IF NOT EXISTS idx_archon_tasks_worktree_id ON archon_tasks(worktree_id);
CREATE INDEX IF NOT EXISTS idx_archon_tasks_branch_name ON archon_tasks(branch_name);
CREATE INDEX IF NOT EXISTS idx_archon_tasks_repo_path ON archon_tasks(repo_path);
CREATE INDEX IF NOT EXISTS idx_archon_tasks_worktree_status ON archon_tasks(worktree_status);
CREATE INDEX IF NOT EXISTS idx_archon_tasks_parent_worktree ON archon_tasks(parent_worktree_id);

-- Composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_archon_tasks_project_worktree ON archon_tasks(project_id, worktree_id);
CREATE INDEX IF NOT EXISTS idx_archon_tasks_branch_status ON archon_tasks(branch_name, worktree_status);

-- GIN index for JSONB arrays
CREATE INDEX IF NOT EXISTS idx_archon_tasks_entities_affected ON archon_tasks USING GIN(entities_affected);
CREATE INDEX IF NOT EXISTS idx_archon_tasks_merge_conflicts ON archon_tasks USING GIN(merge_conflicts_expected);

-- =====================================================
-- SECTION 3: CREATE WORKTREE CONFLICT DETECTION FUNCTION
-- =====================================================

-- Function to detect potential conflicts between tasks in different worktrees
CREATE OR REPLACE FUNCTION detect_worktree_conflicts(
    p_worktree_id UUID,
    p_entities JSONB DEFAULT NULL
)
RETURNS TABLE (
    conflicting_task_id UUID,
    conflicting_worktree_id UUID,
    conflicting_branch TEXT,
    conflict_type TEXT, -- 'file', 'entity', 'branch'
    conflict_severity TEXT, -- 'critical', 'warning', 'info'
    details JSONB
) AS $$
BEGIN
    -- Find tasks in other worktrees that affect the same entities/files
    RETURN QUERY
    SELECT 
        t.id AS conflicting_task_id,
        t.worktree_id AS conflicting_worktree_id,
        t.branch_name AS conflicting_branch,
        CASE 
            WHEN t.entities_affected && p_entities THEN 'entity'
            WHEN t.merge_conflicts_expected && p_entities THEN 'file'
            ELSE 'branch'
        END AS conflict_type,
        CASE 
            WHEN t.status IN ('doing', 'review') THEN 'critical'
            WHEN t.status = 'todo' THEN 'warning'
            ELSE 'info'
        END AS conflict_severity,
        jsonb_build_object(
            'task_title', t.title,
            'task_status', t.status,
            'task_assignee', t.assignee,
            'shared_entities', t.entities_affected * p_entities
        ) AS details
    FROM archon_tasks t
    WHERE t.worktree_id IS NOT NULL
        AND t.worktree_id != p_worktree_id
        AND t.archived = FALSE
        AND t.status IN ('todo', 'doing', 'review') -- Only check active tasks
        AND (
            -- Check for entity overlaps
            (p_entities IS NOT NULL AND t.entities_affected && p_entities)
            OR 
            -- Check for file path overlaps
            (p_entities IS NOT NULL AND t.merge_conflicts_expected && p_entities)
        );
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- SECTION 4: CREATE WORKTREE VALIDATION FUNCTION
-- =====================================================

-- Function to validate if it's safe to create/update a task in a worktree
CREATE OR REPLACE FUNCTION validate_worktree_safe(
    p_worktree_id UUID,
    p_branch_name TEXT,
    p_repo_path TEXT,
    p_task_id UUID DEFAULT NULL,
    p_entities JSONB DEFAULT '[]'::jsonb
)
RETURNS TABLE (
    is_safe BOOLEAN,
    issues JSONB,
    warnings JSONB
) AS $$
DECLARE
    v_is_safe BOOLEAN := TRUE;
    v_issues JSONB := '[]'::jsonb;
    v_warnings JSONB := '[]'::jsonb;
    v_existing_task RECORD;
    v_worktree_exists BOOLEAN;
    v_branch_matches BOOLEAN;
    v_lock_status TEXT;
BEGIN
    -- Check 1: Does worktree exist in tasks?
    SELECT EXISTS(
        SELECT 1 FROM archon_tasks 
        WHERE worktree_id = p_worktree_id
    ) INTO v_worktree_exists;
    
    IF NOT v_worktree_exists AND p_worktree_id IS NOT NULL THEN
        -- New worktree - check if path is valid
        v_warnings := v_warnings || jsonb_build_object(
            'type', 'new_worktree',
            'message', 'Creating task in new worktree: ' || p_worktree_id::text,
            'severity', 'info'
        );
    END IF;
    
    -- Check 2: Branch name matches worktree
    IF p_worktree_id IS NOT NULL THEN
        SELECT branch_name = p_branch_name
        INTO v_branch_matches
        FROM archon_tasks
        WHERE worktree_id = p_worktree_id
        LIMIT 1;
        
        IF NOT v_branch_matches THEN
            v_issues := v_issues || jsonb_build_object(
                'type', 'branch_mismatch',
                'message', 'Branch name mismatch with worktree',
                'severity', 'error',
                'expected_branch', p_branch_name
            );
            v_is_safe := FALSE;
        END IF;
    END IF;
    
    -- Check 3: Worktree not locked
    SELECT worktree_status INTO v_lock_status
    FROM archon_tasks
    WHERE worktree_id = p_worktree_id
    LIMIT 1;
    
    IF v_lock_status = 'locked' THEN
        v_issues := v_issues || jsonb_build_object(
            'type', 'worktree_locked',
            'message', 'Worktree is locked by another process',
            'severity', 'error'
        );
        v_is_safe := FALSE;
    END IF;
    
    -- Check 4: Task not already active in another worktree
    IF p_task_id IS NOT NULL THEN
        SELECT worktree_id, branch_name INTO v_existing_task
        FROM archon_tasks
        WHERE id = p_task_id
            AND worktree_id IS NOT NULL
            AND worktree_id != p_worktree_id
            AND status IN ('doing', 'review');
        
        IF FOUND THEN
            v_issues := v_issues || jsonb_build_object(
                'type', 'task_in_other_worktree',
                'message', 'Task is active in another worktree',
                'severity', 'error',
                'other_worktree_id', v_existing_task.worktree_id,
                'other_branch', v_existing_task.branch_name
            );
            v_is_safe := FALSE;
        END IF;
    END IF;
    
    -- Check 5: No conflicting tasks on same entities
    IF jsonb_array_length(p_entities) > 0 THEN
        FOR v_existing_task IN
            SELECT * FROM detect_worktree_conflicts(p_worktree_id, p_entities)
            WHERE conflict_severity IN ('critical', 'warning')
        LOOP
            IF v_existing_task.conflict_severity = 'critical' THEN
                v_issues := v_issues || jsonb_build_object(
                    'type', 'concurrent_modification',
                    'message', 'Another task is modifying the same entities',
                    'severity', 'error',
                    'conflicting_task_id', v_existing_task.conflicting_task_id,
                    'conflicting_worktree', v_existing_task.conflicting_worktree_id,
                    'conflict_type', v_existing_task.conflict_type
                );
                v_is_safe := FALSE;
            ELSE
                v_warnings := v_warnings || jsonb_build_object(
                    'type', 'potential_conflict',
                    'message', 'Another task may affect the same entities',
                    'severity', 'warning',
                    'conflicting_task_id', v_existing_task.conflicting_task_id,
                    'details', v_existing_task.details
                );
            END IF;
        END LOOP;
    END IF;
    
    -- Check 6: Warn if entities list is empty
    IF jsonb_array_length(p_entities) = 0 THEN
        v_warnings := v_warnings || jsonb_build_object(
            'type', 'no_entities_tracked',
            'message', 'Task has no tracked entities - conflicts cannot be detected',
            'severity', 'warning'
        );
    END IF;
    
    RETURN QUERY SELECT v_is_safe, v_issues, v_warnings;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- SECTION 5: CREATE TRIGGER FOR WORKTREE SAFETY
-- =====================================================

-- Trigger function to validate worktree safety before task operations
CREATE OR REPLACE FUNCTION worktree_safety_trigger()
RETURNS TRIGGER AS $$
DECLARE
    v_validation RECORD;
BEGIN
    -- Only validate if worktree_id is being set/changed
    IF NEW.worktree_id IS NULL THEN
        RETURN NEW; -- No worktree context, skip validation
    END IF;
    
    -- Run validation
    SELECT * INTO v_validation
    FROM validate_worktree_safe(
        NEW.worktree_id,
        NEW.branch_name,
        NEW.repo_path,
        NEW.id,
        COALESCE(NEW.entities_affected, '[]'::jsonb)
    );
    
    -- If not safe, raise exception
    IF NOT v_validation.is_safe THEN
        RAISE EXCEPTION 'Worktree safety violation: %', v_validation.issues
            USING ERRCODE = 'P0001',
                  DETAIL = jsonb_pretty(v_validation.issues);
    END IF;
    
    -- Set worktree creation timestamp if new
    IF TG_OP = 'INSERT' AND NEW.worktree_created_at IS NULL THEN
        NEW.worktree_created_at := NOW();
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create the trigger (disabled by default, can be enabled when strict mode needed)
DROP TRIGGER IF EXISTS worktree_safety_check ON archon_tasks;
CREATE TRIGGER worktree_safety_check
    BEFORE INSERT OR UPDATE ON archon_tasks
    FOR EACH ROW
    EXECUTE FUNCTION worktree_safety_trigger();

-- Disable trigger by default (can be enabled when strict worktree safety is needed)
-- ALTER TABLE archon_tasks DISABLE TRIGGER worktree_safety_check;

-- =====================================================
-- SECTION 6: CREATE WORKTREE MANAGEMENT VIEW
-- =====================================================

-- View for getting worktree summary information
CREATE OR REPLACE VIEW archon_worktree_summary AS
SELECT 
    t.worktree_id,
    t.branch_name,
    t.repo_path,
    t.base_branch,
    t.parent_worktree_id,
    t.is_isolated,
    COUNT(*) FILTER (WHERE t.archived = FALSE) as active_task_count,
    COUNT(*) FILTER (WHERE t.status = 'todo' AND t.archived = FALSE) as todo_count,
    COUNT(*) FILTER (WHERE t.status = 'doing' AND t.archived = FALSE) as doing_count,
    COUNT(*) FILTER (WHERE t.status = 'review' AND t.archived = FALSE) as review_count,
    COUNT(*) FILTER (WHERE t.status = 'done' AND t.archived = FALSE) as done_count,
    MIN(t.worktree_created_at) as created_at,
    MAX(t.updated_at) as last_activity,
    t.worktree_status
FROM archon_tasks t
WHERE t.worktree_id IS NOT NULL
GROUP BY t.worktree_id, t.branch_name, t.repo_path, t.base_branch, 
         t.parent_worktree_id, t.is_isolated, t.worktree_status;

-- =====================================================
-- SECTION 7: ADD COMMENTS
-- =====================================================

COMMENT ON COLUMN archon_tasks.worktree_id IS 'Unique identifier for the git worktree this task belongs to';
COMMENT ON COLUMN archon_tasks.branch_name IS 'Git branch name for this worktree (e.g., feature/new-auth)';
COMMENT ON COLUMN archon_tasks.repo_path IS 'Absolute path to the worktree directory';
COMMENT ON COLUMN archon_tasks.base_branch IS 'The branch this worktree was created from';
COMMENT ON COLUMN archon_tasks.is_isolated IS 'Whether this worktree is fully isolated from others';
COMMENT ON COLUMN archon_tasks.parent_worktree_id IS 'For nested worktrees, the parent worktree ID';
COMMENT ON COLUMN archon_tasks.merge_conflicts_expected IS 'JSON array of file paths expected to conflict during merge';
COMMENT ON COLUMN archon_tasks.worktree_created_at IS 'When the worktree was first used for tasks';
COMMENT ON COLUMN archon_tasks.worktree_status IS 'Status: active, locked (by another process), conflict, clean';
COMMENT ON COLUMN archon_tasks.entities_affected IS 'JSON array of entity IDs this task modifies';

COMMENT ON FUNCTION detect_worktree_conflicts IS 'Detects potential conflicts between tasks in different worktrees';
COMMENT ON FUNCTION validate_worktree_safe IS 'Validates if it is safe to create/update a task in a worktree';
COMMENT ON VIEW archon_worktree_summary IS 'Summary view of all worktrees and their task counts';

-- =====================================================
-- SECTION 8: MIGRATION TRACKING
-- =====================================================

INSERT INTO archon_migrations (version, migration_name)
VALUES ('0.1.0', '014_add_worktree_safety_to_tasks')
ON CONFLICT (version, migration_name) DO NOTHING;

-- =====================================================
-- MIGRATION COMPLETE
-- =====================================================
-- Worktree safety columns and functions are now available
-- 
-- Usage:
--   SELECT * FROM validate_worktree_safe('worktree-uuid', 'branch', '/path');
--   SELECT * FROM detect_worktree_conflicts('worktree-uuid');
--   SELECT * FROM archon_worktree_summary;
-- =====================================================
