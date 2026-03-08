-- Migration: Add metadata column to archon_git_commits for semantic classification
-- Purpose: Store AI-generated commit classifications (intent, risk, breaking changes, etc.)
-- Use case: Enable semantic commit search, risk assessment, and regression detective features

-- Add metadata JSONB column
ALTER TABLE archon_git_commits
ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;

-- Add index for metadata queries
CREATE INDEX IF NOT EXISTS idx_git_commits_metadata ON archon_git_commits USING GIN (metadata);

-- Add comment explaining metadata structure
COMMENT ON COLUMN archon_git_commits.metadata IS
    'Semantic classification metadata from AI analysis. Expected structure:
    {
      "intent": "feature|bugfix|refactor|security-fix|performance|docs|test|chore",
      "risk_level": "high|medium|low",
      "api_breaking": boolean,
      "security_relevant": boolean,
      "performance_impact": "high|medium|low|none",
      "test_coverage": "full|partial|none",
      "classification_model": "claude-sonnet-4.5",
      "classification_timestamp": "2024-01-01T00:00:00Z",
      "confidence": 0.95
    }';
