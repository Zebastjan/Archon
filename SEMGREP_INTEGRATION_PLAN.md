# Semgrep Integration & Meta-Audit Implementation Plan

## Executive Summary

Replace the current rule-based audit system with Semgrep CE integration while building a "meta-audit" tracking system that learns from triage decisions to improve future audits.

**Key Goals:**
1. Swap regex-based rules for Semgrep's AST-aware pattern matching
2. Track all triage decisions to build a "triage memory" 
3. Detect when bugs slip past audits (false negatives)
4. Continuously improve rule quality based on outcomes

---

## Phase 1: Semgrep Integration Infrastructure

### 1.1 Database Schema Updates

**New Migration: `022_semgrep_integration.sql`**

```sql
-- =============================================================================
-- SEMGREP FINDINGS TABLE
-- Separate from archon_audit_findings to start fresh
-- =============================================================================

CREATE TABLE IF NOT EXISTS archon_semgrep_findings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Repository reference
    repo_id UUID REFERENCES archon_code_repos(id) ON DELETE CASCADE,
    
    -- Semgrep-specific fields
    semgrep_check_id TEXT NOT NULL,      -- e.g., "python.lang.security.audit.eval-detected"
    semgrep_rule_url TEXT,                -- Link to rule documentation
    
    -- Finding details
    message TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('INFO', 'WARNING', 'ERROR')),
    confidence TEXT DEFAULT 'medium',     -- Semgrep confidence level
    
    -- Location
    file_path TEXT NOT NULL,
    line_start INTEGER,
    line_end INTEGER,
    column_start INTEGER,
    column_end INTEGER,
    
    -- Code context
    code_snippet TEXT,
    
    -- Metavariables (captured pattern variables)
    metavariables JSONB DEFAULT '{}',
    
    -- Data flow info (for taint rules)
    data_flow JSONB DEFAULT '{}',
    
    -- Audit tracking
    status TEXT DEFAULT 'open' CHECK (status IN ('open', 'triaged', 'suppressed')),
    
    -- Run reference
    audit_run_id UUID REFERENCES archon_audit_runs(id) ON DELETE CASCADE,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_semgrep_findings_repo ON archon_semgrep_findings(repo_id);
CREATE INDEX idx_semgrep_findings_check_id ON archon_semgrep_findings(semgrep_check_id);
CREATE INDEX idx_semgrep_findings_status ON archon_semgrep_findings(status);
CREATE INDEX idx_semgrep_findings_file ON archon_semgrep_findings(file_path);
CREATE INDEX idx_semgrep_findings_run ON archon_semgrep_findings(audit_run_id);

-- =============================================================================
-- TRIAGE MEMORY: Store pattern -> decision mappings
-- This is the core of the "meta-audit" system
-- =============================================================================

CREATE TABLE IF NOT EXISTS archon_audit_triage_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- What triggered this triage
    check_id TEXT NOT NULL,              -- Semgrep check_id or rule_id
    repo_id UUID REFERENCES archon_code_repos(id) ON DELETE CASCADE,
    
    -- The pattern that was identified
    -- Store multiple ways to match:
    pattern_type TEXT NOT NULL CHECK (pattern_type IN (
        'exact_code',        -- Exact code match (rarely used)
        'ast_pattern',       -- Abstract syntax tree pattern
        'semantic_hash',     -- Embedding-based similarity
        'call_chain',        -- Function call pattern
        'file_pattern',      -- File path pattern
        'context_aware'      -- Complex context-dependent pattern
    )),
    
    pattern_value TEXT NOT NULL,         -- The actual pattern
    pattern_embedding VECTOR(1024),      -- For semantic similarity
    
    -- The decision made
    decision TEXT NOT NULL CHECK (decision IN (
        'confirmed_issue',   -- Real bug, needs fix
        'intentional',       -- Valid by design
        'false_positive',    -- Tool misfired
        'wont_fix'          -- Valid but accepted tech debt
    )),
    
    -- Why this decision was made
    decision_rationale TEXT NOT NULL,
    
    -- Context that informed the decision
    surrounding_code TEXT,               -- Code around the finding
    call_context TEXT,                   -- Who calls this code
    
    -- Confidence metrics
    confidence_score DECIMAL(3,2),       -- 0.0 to 1.0
    reviewer_experience TEXT,            -- Who reviewed it
    
    -- Link to the specific finding
    original_finding_id UUID,
    
    -- Hit tracking
    times_applied INTEGER DEFAULT 1,     -- How many times this pattern was matched
    last_applied_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Validation tracking (for meta-audit)
    was_validated BOOLEAN DEFAULT FALSE, -- Did we verify this was correct?
    validation_result TEXT CHECK (validation_result IN ('correct', 'incorrect', 'uncertain')),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_triage_memory_check_id ON archon_audit_triage_memory(check_id);
CREATE INDEX idx_triage_memory_pattern ON archon_audit_triage_memory(pattern_type, pattern_value);
CREATE INDEX idx_triage_memory_decision ON archon_audit_triage_memory(decision);
CREATE INDEX idx_triage_memory_embedding ON archon_audit_triage_memory 
    USING hnsw (pattern_embedding vector_cosine_ops);

-- =============================================================================
-- FALSE NEGATIVE LOG
-- Track bugs that slipped past the audit (meta-audit)
-- =============================================================================

CREATE TABLE IF NOT EXISTS archon_audit_false_negatives (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    repo_id UUID REFERENCES archon_code_repos(id) ON DELETE CASCADE,
    
    -- The bug that was missed
    bug_type TEXT NOT NULL,              -- e.g., "race_condition", "null_deref"
    bug_description TEXT NOT NULL,
    
    -- Where it occurred
    file_path TEXT NOT NULL,
    line_start INTEGER,
    line_end INTEGER,
    code_snippet TEXT,
    
    -- When it was discovered
    discovered_at TIMESTAMPTZ DEFAULT NOW(),
    discovered_by TEXT,                  -- Who found it
    discovery_method TEXT,               -- e.g., "production_bug", "manual_review", "other_tool"
    
    -- Link to fix
    fix_commit_sha TEXT,
    fix_pr_number INTEGER,
    
    -- Analysis: Why was this missed?
    root_cause TEXT,                     -- Human analysis of why audit missed it
    
    -- Could we have caught it?
    would_semgrep_catch BOOLEAN,         -- If we re-run semgrep now, does it flag?
    semgrep_rules_that_would_catch TEXT[], -- Which rules would have caught it?
    
    -- Action items
    action_taken TEXT,                   -- What we did about it
    new_rule_created BOOLEAN DEFAULT FALSE,
    new_rule_id TEXT,
    
    -- Tracking
    audit_run_at TIMESTAMPTZ,            -- When we last audited before the bug
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_false_negatives_repo ON archon_audit_false_negatives(repo_id);
CREATE INDEX idx_false_negatives_type ON archon_audit_false_negatives(bug_type);
CREATE INDEX idx_false_negatives_discovered ON archon_audit_false_negatives(discovered_at);

-- =============================================================================
-- RULE QUALITY METRICS
-- Track how well each rule/check is performing
-- =============================================================================

CREATE TABLE IF NOT EXISTS archon_audit_rule_quality (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    check_id TEXT NOT NULL UNIQUE,       -- Semgrep check_id
    
    -- Stats
    total_findings INTEGER DEFAULT 0,
    confirmed_issues INTEGER DEFAULT 0,
    false_positives INTEGER DEFAULT 0,
    intentional_count INTEGER DEFAULT 0,
    wont_fix_count INTEGER DEFAULT 0,
    
    -- Calculated metrics
    precision DECIMAL(5,4),              -- confirmed / total
    false_positive_rate DECIMAL(5,4),    -- fp / total
    
    -- Trending
    last_audit_at TIMESTAMPTZ,
    trend_direction TEXT CHECK (trend_direction IN ('improving', 'degrading', 'stable')),
    
    -- Recommendations
    should_disable BOOLEAN DEFAULT FALSE,
    disable_reason TEXT,
    
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- SEMGREP CONFIGURATION
-- Track which rulesets we use
-- =============================================================================

CREATE TABLE IF NOT EXISTS archon_semgrep_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    repo_id UUID REFERENCES archon_code_repos(id) ON DELETE CASCADE,
    
    -- Configuration
    rulesets TEXT[] DEFAULT ARRAY['p/security-audit', 'p/owasp-top-ten', 'p/cwe-top-25'],
    custom_rules_path TEXT,              -- Path to custom semgrep rules
    exclude_patterns TEXT[] DEFAULT ARRAY['tests/', 'test/', '*_test.py', '*.test.ts'],
    
    -- Suppression settings
    nosemgrep_ignored_rules TEXT[],      -- Rules we ignore via nosemgrep
    file_path_ignores TEXT[],            -- Files/paths to exclude
    
    -- Runtime settings
    max_file_size_kb INTEGER DEFAULT 1024,
    timeout_seconds INTEGER DEFAULT 300,
    
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- FUNCTIONS
-- =============================================================================

-- Function: Find similar triage decisions using semantic search
CREATE OR REPLACE FUNCTION find_similar_triage_decisions(
    p_check_id TEXT,
    p_code_embedding VECTOR(1024),
    p_similarity_threshold DECIMAL(3,2) DEFAULT 0.85
)
RETURNS TABLE (
    decision TEXT,
    decision_rationale TEXT,
    confidence_score DECIMAL(3,2),
    similarity DECIMAL(5,4)
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        tm.decision,
        tm.decision_rationale,
        tm.confidence_score,
        (1 - (tm.pattern_embedding <=> p_code_embedding))::DECIMAL(5,4) as similarity
    FROM archon_audit_triage_memory tm
    WHERE tm.check_id = p_check_id
    AND (1 - (tm.pattern_embedding <=> p_code_embedding)) >= p_similarity_threshold
    ORDER BY similarity DESC
    LIMIT 5;
END;
$$ LANGUAGE plpgsql;

-- Function: Record a false negative (bug that slipped past audit)
CREATE OR REPLACE FUNCTION record_false_negative(
    p_repo_id UUID,
    p_bug_type TEXT,
    p_bug_description TEXT,
    p_file_path TEXT,
    p_discovered_by TEXT DEFAULT 'manual',
    p_root_cause TEXT DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    v_id UUID;
BEGIN
    INSERT INTO archon_audit_false_negatives (
        repo_id,
        bug_type,
        bug_description,
        file_path,
        discovered_by,
        discovery_method,
        root_cause
    ) VALUES (
        p_repo_id,
        p_bug_type,
        p_bug_description,
        p_file_path,
        p_discovered_by,
        'manual_review',
        p_root_cause
    )
    RETURNING id INTO v_id;
    
    RETURN v_id;
END;
$$ LANGUAGE plpgsql;

-- Function: Update rule quality metrics
CREATE OR REPLACE FUNCTION update_rule_quality_metrics(
    p_check_id TEXT
)
RETURNS VOID AS $$
DECLARE
    v_total INTEGER;
    v_confirmed INTEGER;
    v_fp INTEGER;
    v_precision DECIMAL(5,4);
    v_fp_rate DECIMAL(5,4);
BEGIN
    -- Count findings from semgrep_findings joined with triage
    SELECT 
        COUNT(*),
        COUNT(*) FILTER (WHERE tm.decision = 'confirmed_issue'),
        COUNT(*) FILTER (WHERE tm.decision = 'false_positive')
    INTO v_total, v_confirmed, v_fp
    FROM archon_semgrep_findings sf
    LEFT JOIN archon_audit_triage_memory tm 
        ON sf.semgrep_check_id = tm.check_id
        AND sf.file_path = split_part(tm.surrounding_code, ':', 1)
    WHERE sf.semgrep_check_id = p_check_id;
    
    -- Calculate metrics
    IF v_total > 0 THEN
        v_precision := v_confirmed::DECIMAL / v_total;
        v_fp_rate := v_fp::DECIMAL / v_total;
    ELSE
        v_precision := 0;
        v_fp_rate := 0;
    END IF;
    
    -- Update or insert
    INSERT INTO archon_audit_rule_quality (
        check_id,
        total_findings,
        confirmed_issues,
        false_positives,
        precision,
        false_positive_rate,
        last_audit_at
    ) VALUES (
        p_check_id,
        v_total,
        v_confirmed,
        v_fp,
        v_precision,
        v_fp_rate,
        NOW()
    )
    ON CONFLICT (check_id) DO UPDATE SET
        total_findings = EXCLUDED.total_findings,
        confirmed_issues = EXCLUDED.confirmed_issues,
        false_positives = EXCLUDED.false_positives,
        precision = EXCLUDED.precision,
        false_positive_rate = EXCLUDED.false_positive_rate,
        last_audit_at = EXCLUDED.last_audit_at,
        updated_at = NOW();
END;
$$ LANGUAGE plpgsql;
```

### 1.2 Semgrep Service Implementation

**New File: `python/src/server/services/semgrep_service.py`**

```python
"""Semgrep Integration Service

Replaces regex-based audit rules with Semgrep's AST-aware pattern matching.
"""

import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg2
from psycopg2.extras import RealDictCursor

from src.server.config.logfire_config import get_logger
from src.server.services.embedding_service import get_embedding_service

logger = get_logger(__name__)


@dataclass
class SemgrepFinding:
    """A Semgrep finding parsed from JSON output."""
    
    # Identification
    check_id: str
    path: str
    line_start: int
    line_end: int
    column_start: int = 0
    column_end: int = 0
    
    # Content
    message: str
    severity: str = "WARNING"
    code_snippet: str = ""
    
    # Extra data
    metadata: dict[str, Any] = field(default_factory=dict)
    metavariables: dict[str, Any] = field(default_factory=dict)
    
    # URLs
    rule_url: str = ""
    
    def to_db_dict(self, repo_id: UUID, run_id: UUID | None = None) -> dict[str, Any]:
        """Convert to dict for database insertion."""
        return {
            "repo_id": str(repo_id),
            "audit_run_id": str(run_id) if run_id else None,
            "semgrep_check_id": self.check_id,
            "semgrep_rule_url": self.rule_url,
            "message": self.message,
            "severity": self.severity,
            "confidence": self.metadata.get("confidence", "medium"),
            "file_path": self.path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "column_start": self.column_start,
            "column_end": self.column_end,
            "code_snippet": self.code_snippet,
            "metavariables": json.dumps(self.metavariables),
            "data_flow": json.dumps(self.metadata.get("data_flow", {})),
        }


class SemgrepService:
    """Service for running Semgrep audits and managing findings."""
    
    # Default rulesets to use
    DEFAULT_RULESETS = [
        "p/security-audit",      # Security issues
        "p/owasp-top-ten",       # OWASP top 10
        "p/cwe-top-25",          # CWE top 25
        "p/python",              # Python best practices
        "p/typescript",          # TypeScript best practices
        "p/javascript",          # JavaScript best practices
    ]
    
    def __init__(self, db_connection=None):
        self._db = db_connection
        self._connection_string = "postgresql://archon:archon_local_dev@localhost:5434/archon"
        self._embedding_service = get_embedding_service()
    
    def _get_db(self):
        """Get database connection."""
        if self._db is None:
            self._db = psycopg2.connect(self._connection_string)
        return self._db
    
    def _execute_query(self, query: str, params: tuple = (), commit: bool = False) -> list[dict]:
        """Execute a query and return results."""
        conn = self._get_db()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            if cur.description:
                result = [dict(row) for row in cur.fetchall()]
                if commit:
                    conn.commit()
                return result
            if commit:
                conn.commit()
            return []
    
    def run_audit(
        self,
        repo_path: str | Path,
        repo_id: UUID,
        rulesets: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> list[SemgrepFinding]:
        """
        Run Semgrep audit on a repository.
        
        Args:
            repo_path: Path to the repository
            repo_id: Repository UUID for database storage
            rulesets: List of rulesets to use (defaults to DEFAULT_RULESETS)
            exclude_patterns: Patterns to exclude from scanning
            
        Returns:
            List of SemgrepFinding objects
        """
        repo_path = Path(repo_path)
        rulesets = rulesets or self.DEFAULT_RULESETS
        exclude_patterns = exclude_patterns or ["tests/", "test/", "*_test.py", "*.test.ts"]
        
        logger.info(f"Running Semgrep audit on {repo_path} with {len(rulesets)} rulesets")
        
        # Build command
        cmd = [
            "semgrep",
            "--config", ",".join(rulesets),
            "--json",
            "--output", "-",
        ]
        
        # Add excludes
        for pattern in exclude_patterns:
            cmd.extend(["--exclude", pattern])
        
        cmd.append(str(repo_path))
        
        # Run Semgrep
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )
            
            if result.returncode not in (0, 1):  # 0 = no findings, 1 = findings found
                logger.error(f"Semgrep failed: {result.stderr}")
                return []
            
            # Parse JSON output
            findings = self._parse_semgrep_output(result.stdout, repo_path)
            logger.info(f"Semgrep found {len(findings)} issues")
            
            return findings
            
        except subprocess.TimeoutExpired:
            logger.error("Semgrep timed out after 5 minutes")
            return []
        except FileNotFoundError:
            logger.error("Semgrep not installed. Run: pip install semgrep")
            return []
    
    def _parse_semgrep_output(self, json_output: str, repo_path: Path) -> list[SemgrepFinding]:
        """Parse Semgrep JSON output into SemgrepFinding objects."""
        findings = []
        
        try:
            data = json.loads(json_output)
        except json.JSONDecodeError:
            logger.error("Failed to parse Semgrep JSON output")
            return []
        
        for result in data.get("results", []):
            # Extract location info
            path = result.get("path", "")
            start = result.get("start", {})
            end = result.get("end", {})
            
            # Get code snippet
            extra = result.get("extra", {})
            lines = extra.get("lines", "")
            
            # Get metadata
            metadata = extra.get("metadata", {})
            
            finding = SemgrepFinding(
                check_id=result.get("check_id", ""),
                path=str(Path(path).relative_to(repo_path)) if path.startswith(str(repo_path)) else path,
                line_start=start.get("line", 0),
                line_end=end.get("line", 0),
                column_start=start.get("col", 0),
                column_end=end.get("col", 0),
                message=extra.get("message", ""),
                severity=extra.get("severity", "WARNING").upper(),
                code_snippet=lines,
                metadata=metadata,
                metavariables=extra.get("metavars", {}),
                rule_url=metadata.get("source", ""),
            )
            
            findings.append(finding)
        
        return findings
    
    def save_findings(
        self,
        findings: list[SemgrepFinding],
        repo_id: UUID,
        run_id: UUID | None = None,
    ) -> int:
        """Save findings to database."""
        if not findings:
            return 0
        
        conn = self._get_db()
        
        try:
            with conn.cursor() as cur:
                # Insert findings
                for finding in findings:
                    data = finding.to_db_dict(repo_id, run_id)
                    cur.execute("""
                        INSERT INTO archon_semgrep_findings (
                            repo_id, audit_run_id, semgrep_check_id, semgrep_rule_url,
                            message, severity, confidence, file_path,
                            line_start, line_end, column_start, column_end,
                            code_snippet, metavariables, data_flow
                        ) VALUES (
                            %(repo_id)s, %(audit_run_id)s, %(semgrep_check_id)s, %(semgrep_rule_url)s,
                            %(message)s, %(severity)s, %(confidence)s, %(file_path)s,
                            %(line_start)s, %(line_end)s, %(column_start)s, %(column_end)s,
                            %(code_snippet)s, %(metavariables)s, %(data_flow)s
                        )
                        ON CONFLICT DO NOTHING
                    """, data)
                
                conn.commit()
                logger.info(f"Saved {len(findings)} findings to database")
                return len(findings)
                
        except Exception as e:
            logger.exception(f"Failed to save findings: {e}")
            conn.rollback()
            return 0
    
    def get_findings_for_review(
        self,
        repo_id: UUID | None = None,
        status: str = "open",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get findings ready for review."""
        query = """
            SELECT 
                sf.*,
                repo.name as repo_name
            FROM archon_semgrep_findings sf
            JOIN archon_code_repos repo ON sf.repo_id = repo.id
            WHERE sf.status = %s
        """
        params = [status]
        
        if repo_id:
            query += " AND sf.repo_id = %s"
            params.append(str(repo_id))
        
        query += " ORDER BY sf.severity DESC, sf.created_at LIMIT %s"
        params.append(limit)
        
        return self._execute_query(query, tuple(params))
    
    def triage_finding(
        self,
        finding_id: UUID,
        decision: str,  # confirmed_issue, intentional, false_positive, wont_fix
        rationale: str,
        reviewer: str,
        store_in_memory: bool = True,
    ) -> bool:
        """
        Triage a finding and optionally store the decision in triage memory.
        
        This is the core of the "meta-audit" - learning from decisions.
        """
        if decision not in ("confirmed_issue", "intentional", "false_positive", "wont_fix"):
            raise ValueError(f"Invalid decision: {decision}")
        
        # Get finding details
        finding = self._execute_query(
            "SELECT * FROM archon_semgrep_findings WHERE id = %s",
            (str(finding_id),)
        )
        
        if not finding:
            logger.error(f"Finding {finding_id} not found")
            return False
        
        finding = finding[0]
        
        # Update finding status
        self._execute_query(
            "UPDATE archon_semgrep_findings SET status = 'triaged', updated_at = NOW() WHERE id = %s",
            (str(finding_id),),
            commit=True,
        )
        
        if store_in_memory:
            # Store in triage memory for future pattern matching
            self._store_triage_memory(finding, decision, rationale, reviewer)
        
        # Update rule quality metrics
        self._execute_query(
            "SELECT update_rule_quality_metrics(%s)",
            (finding["semgrep_check_id"],),
            commit=True,
        )
        
        logger.info(f"Triaged finding {finding_id}: {decision}")
        return True
    
    def _store_triage_memory(
        self,
        finding: dict[str, Any],
        decision: str,
        rationale: str,
        reviewer: str,
    ):
        """Store triage decision in memory for future pattern matching."""
        try:
            # Generate embedding for the code snippet
            embedding = self._embedding_service.generate_for_code_entity(
                name=f"{finding['semgrep_check_id']}:{finding['file_path']}",
                signature=None,
                docstring=None,
                source_code=finding.get("code_snippet", ""),
            )
            
            # Store in triage memory
            self._execute_query(
                """
                INSERT INTO archon_audit_triage_memory (
                    check_id,
                    repo_id,
                    pattern_type,
                    pattern_value,
                    pattern_embedding,
                    decision,
                    decision_rationale,
                    surrounding_code,
                    confidence_score,
                    reviewer_experience,
                    original_finding_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    finding["semgrep_check_id"],
                    finding["repo_id"],
                    "semantic_hash",  # Using semantic similarity
                    f"{finding['file_path']}:{finding['line_start']}",
                    embedding,
                    decision,
                    rationale,
                    finding.get("code_snippet", ""),
                    0.9 if decision == "false_positive" else 0.8,
                    reviewer,
                    finding["id"],
                ),
                commit=True,
            )
        except Exception as e:
            logger.warning(f"Failed to store triage memory: {e}")
    
    def suggest_triage_decision(
        self,
        finding_id: UUID,
    ) -> dict[str, Any] | None:
        """
        Suggest a triage decision based on similar past decisions.
        
        This is where the "meta-audit" magic happens - using past decisions
        to inform future ones.
        """
        # Get finding details
        finding = self._execute_query(
            "SELECT * FROM archon_semgrep_findings WHERE id = %s",
            (str(finding_id),)
        )
        
        if not finding:
            return None
        
        finding = finding[0]
        
        # Generate embedding for semantic search
        try:
            embedding = self._embedding_service.generate_for_code_entity(
                name=f"{finding['semgrep_check_id']}:{finding['file_path']}",
                signature=None,
                docstring=None,
                source_code=finding.get("code_snippet", ""),
            )
            
            # Find similar decisions
            similar = self._execute_query(
                """
                SELECT * FROM find_similar_triage_decisions(%s, %s, 0.80)
                LIMIT 3
                """,
                (finding["semgrep_check_id"], embedding),
            )
            
            if similar:
                # Return the most common decision among similar patterns
                decisions = [s["decision"] for s in similar]
                most_common = max(set(decisions), key=decisions.count)
                avg_confidence = sum(s["confidence_score"] for s in similar) / len(similar)
                
                return {
                    "suggested_decision": most_common,
                    "confidence": avg_confidence,
                    "similar_cases": len(similar),
                    "rationale": f"Based on {len(similar)} similar patterns previously triaged",
                }
        except Exception as e:
            logger.warning(f"Failed to suggest triage: {e}")
        
        return None
    
    def record_false_negative(
        self,
        repo_id: UUID,
        bug_type: str,
        bug_description: str,
        file_path: str,
        line_start: int | None = None,
        line_end: int | None = None,
        code_snippet: str = "",
        discovered_by: str = "manual",
        root_cause: str = "",
    ) -> UUID | None:
        """
        Record a bug that slipped past the audit.
        
        This is critical for the meta-audit - tracking what we missed.
        """
        result = self._execute_query(
            """
            INSERT INTO archon_audit_false_negatives (
                repo_id, bug_type, bug_description, file_path,
                line_start, line_end, code_snippet,
                discovered_by, discovery_method, root_cause
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                str(repo_id),
                bug_type,
                bug_description,
                file_path,
                line_start,
                line_end,
                code_snippet,
                discovered_by,
                "manual_review",
                root_cause,
            ),
            commit=True,
        )
        
        if result:
            fn_id = result[0]["id"]
            logger.info(f"Recorded false negative: {fn_id}")
            
            # TODO: Analyze if Semgrep would catch this now
            # This would require re-running Semgrep on the specific file
            
            return UUID(fn_id)
        
        return None
    
    def get_rule_quality_report(self) -> list[dict[str, Any]]:
        """Get quality metrics for all rules."""
        return self._execute_query(
            """
            SELECT 
                check_id,
                total_findings,
                confirmed_issues,
                false_positives,
                precision,
                false_positive_rate,
                should_disable,
                disable_reason
            FROM archon_audit_rule_quality
            ORDER BY false_positive_rate DESC
            """
        )
    
    def get_rules_to_disable(self, fp_threshold: float = 0.5) -> list[str]:
        """Get list of rules that should be disabled due to high false positive rate."""
        result = self._execute_query(
            """
            SELECT check_id
            FROM archon_audit_rule_quality
            WHERE false_positive_rate > %s
            AND total_findings > 10  -- Need enough data
            ORDER BY false_positive_rate DESC
            """,
            (fp_threshold,)
        )
        return [r["check_id"] for r in result]


# Singleton instance
_semgrep_service: SemgrepService | None = None


def get_semgrep_service(db_connection=None) -> SemgrepService:
    """Get or create singleton Semgrep service."""
    global _semgrep_service
    if _semgrep_service is None:
        _semgrep_service = SemgrepService(db_connection)
    return _semgrep_service
```

### 1.3 MCP Tools for Semgrep

**Update: `python/src/server/mcp_server/codebase_tools.py`** (add new methods)

```python
    async def code_audit_run_semgrep(
        self,
        repo_id: str,
        rulesets: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run Semgrep audit on a repository.
        
        Uses Semgrep's AST-aware pattern matching instead of regex.
        Stores findings for review and triage.
        
        Args:
            repo_id: Repository UUID
            rulesets: Optional list of Semgrep rulesets (defaults to security-audit, owasp-top-ten, etc.)
            
        Returns:
            Summary of findings stored
        """
        from src.server.services.semgrep_service import get_semgrep_service
        
        try:
            service = get_semgrep_service()
            
            # Get repo path from database
            db = await self._ensure_db()
            repo = await db.fetch_one(
                "SELECT local_path FROM archon_code_repos WHERE id = $1",
                repo_id
            )
            
            if not repo:
                return {"status": "error", "message": f"Repository {repo_id} not found"}
            
            # Run Semgrep
            findings = service.run_audit(
                repo_path=repo["local_path"],
                repo_id=repo_id,
                rulesets=rulesets,
            )
            
            # Save findings
            count = service.save_findings(findings, repo_id)
            
            return {
                "status": "success",
                "findings_count": count,
                "repo_id": repo_id,
                "rulesets_used": rulesets or service.DEFAULT_RULESETS,
                "message": f"Semgrep audit complete. {count} findings stored for review.",
            }
            
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def code_audit_get_findings(
        self,
        repo_id: str,
        status: str = "open",
        limit: int = 50,
    ) -> dict[str, Any]:
        """Get Semgrep findings ready for review."""
        from src.server.services.semgrep_service import get_semgrep_service
        
        try:
            service = get_semgrep_service()
            findings = service.get_findings_for_review(
                repo_id=repo_id,
                status=status,
                limit=limit,
            )
            
            return {
                "status": "success",
                "count": len(findings),
                "findings": findings,
            }
            
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def code_audit_triage_finding(
        self,
        finding_id: str,
        decision: str,  # confirmed_issue, intentional, false_positive, wont_fix
        rationale: str,
        reviewer: str = "user",
    ) -> dict[str, Any]:
        """Triage a Semgrep finding and store decision in triage memory."""
        from src.server.services.semgrep_service import get_semgrep_service
        
        try:
            service = get_semgrep_service()
            success = service.triage_finding(
                finding_id=finding_id,
                decision=decision,
                rationale=rationale,
                reviewer=reviewer,
                store_in_memory=True,
            )
            
            if success:
                return {
                    "status": "success",
                    "message": f"Finding triaged as {decision}",
                    "decision": decision,
                }
            else:
                return {
                    "status": "error",
                    "message": "Failed to triage finding",
                }
                
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def code_audit_record_false_negative(
        self,
        repo_id: str,
        bug_type: str,
        bug_description: str,
        file_path: str,
        root_cause: str = "",
    ) -> dict[str, Any]:
        """Record a bug that slipped past the audit (meta-audit tracking)."""
        from src.server.services.semgrep_service import get_semgrep_service
        
        try:
            service = get_semgrep_service()
            fn_id = service.record_false_negative(
                repo_id=repo_id,
                bug_type=bug_type,
                bug_description=bug_description,
                file_path=file_path,
                root_cause=root_cause,
            )
            
            if fn_id:
                return {
                    "status": "success",
                    "false_negative_id": str(fn_id),
                    "message": "False negative recorded for meta-audit analysis",
                }
            else:
                return {
                    "status": "error",
                    "message": "Failed to record false negative",
                }
                
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def code_audit_get_rule_quality(self) -> dict[str, Any]:
        """Get quality metrics for all audit rules."""
        from src.server.services.semgrep_service import get_semgrep_service
        
        try:
            service = get_semgrep_service()
            report = service.get_rule_quality_report()
            rules_to_disable = service.get_rules_to_disable(fp_threshold=0.5)
            
            return {
                "status": "success",
                "rules_analyzed": len(report),
                "rules_with_high_fp": len(rules_to_disable),
                "rules_to_disable": rules_to_disable,
                "report": report,
            }
            
        except Exception as e:
            return {"status": "error", "message": str(e)}
```

---

## Phase 2: Meta-Audit Tracking System

### 2.1 Core Meta-Audit Workflow

The meta-audit tracks three things:

1. **Triage Quality**: Are we making good decisions?
2. **Rule Quality**: Which rules are producing too many false positives?
3. **False Negatives**: What bugs slipped past our audits?

### 2.2 Triage Memory Pattern Matching

When triaging a finding, the system will:

1. Generate an embedding of the code snippet
2. Search triage_memory for similar patterns (same check_id, similar embedding)
3. If similar patterns were previously triaged, suggest the same decision
4. Store the new decision to improve future suggestions

### 2.3 False Negative Tracking

When a bug is discovered that the audit missed:

1. Record it in `archon_audit_false_negatives`
2. Analyze: Would Semgrep catch it now? (re-run on the code)
3. If not, consider creating a custom rule
4. Track patterns in missed bugs to identify blind spots

### 2.4 Rule Quality Monitoring

Weekly/Monthly automated analysis:

1. Calculate precision (confirmed / total) for each rule
2. Flag rules with >50% false positive rate for review
3. Suggest rules to disable or refine
4. Track trends over time (are we improving?)

---

## Phase 3: Implementation Steps

### Immediate (This Session)

1. **Create migration `022_semgrep_integration.sql`**
2. **Install Semgrep**: `pip install semgrep`
3. **Create `semgrep_service.py`** with basic run/save functionality

### Short-term (Next few sessions)

4. **Test Semgrep integration** on a small repo
5. **Build triage workflow UI/tools**
6. **Create the false negative recording workflow**
7. **Migrate away from old audit rules** (mark as deprecated)

### Medium-term (Ongoing)

8. **Build rule quality dashboard**
9. **Create custom Semgrep rules** for Archon-specific patterns
10. **Integrate with CI/CD** for automated audits on PRs

---

## Key Design Decisions

### Why Separate Tables?

- `archon_semgrep_findings` is separate from old `archon_audit_findings`
- Clean slate - don't inherit the 784 garbage findings
- Can migrate old confirmed issues if needed

### Why Semantic Search for Triage Memory?

- Exact code matching is too brittle
- Embeddings capture "similar code patterns"
- Same decision applies to similar code

### Why Track False Negatives?

- This is the hardest part of auditing
- You only know you missed something when it bites you
- Tracking reveals blind spots in our rules

### What About the Old System?

- Keep `archon_audit_findings` for historical reference
- Don't run the old rule-based audits anymore
- Eventually archive old findings after migration

---

## Usage Examples

### Run a New Audit

```python
# Run Semgrep audit
result = await code_audit_run_semgrep(
    repo_id="abc-123",
    rulesets=["p/security-audit", "p/python"]
)

# Review findings
findings = await code_audit_get_findings(
    repo_id="abc-123",
    status="open",
    limit=10
)
```

### Triage a Finding

```python
# Mark as intentional (valid by design)
await code_audit_triage_finding(
    finding_id="finding-uuid",
    decision="intentional",
    rationale="Broad except is used for top-level error routing in agent architecture",
    reviewer="zebastjan"
)
```

### Record a Missed Bug

```python
# We found a race condition the audit missed
await code_audit_record_false_negative(
    repo_id="abc-123",
    bug_type="race_condition",
    bug_description="Concurrent access to shared cache without synchronization",
    file_path="src/services/data_processor.py",
    root_cause="Semgrep doesn't have a rule for shared mutable state detection"
)
```

### Check Rule Quality

```python
# Get quality report
quality = await code_audit_get_rule_quality()

# See which rules are too noisy
for rule in quality["rules_to_disable"]:
    print(f"Consider disabling: {rule}")
```

---

## Success Metrics

**Week 1:**
- Semgrep runs successfully on Archon repo
- Findings stored in new table
- Triage workflow functional

**Week 4:**
- 50+ triage decisions in memory
- Suggestions working for similar patterns
- False positive rate tracked per rule

**Week 8:**
- First false negative recorded and analyzed
- Rule quality report identifies at least 1 rule to disable
- Precision >70% for active rules

**Month 6:**
- Triage memory correctly suggests decisions 80%+ of the time
- False negative rate tracked and improving
- Custom rules written for Archon-specific patterns

---

## Next Steps

Ready to implement Phase 1. Shall I:

1. Create the database migration?
2. Install Semgrep and create the service?
3. Both in parallel?

What would you like to tackle first?
