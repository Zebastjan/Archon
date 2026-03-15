"""Audit Workflow Service

Manages the human-in-the-loop workflow for reviewing and remediating audit findings.

Key Principles:
1. Findings are CANDIDATES for review, not automatic todos
2. Human review required before creating tasks
3. Support for marking as intentional/false positive
4. Progress tracking without blind execution

Workflow:
1. Queue findings for review (creates work items with status 'pending_review')
2. Human reviews each finding and marks as:
   - confirmed_issue → Create task and fix
   - intentional → Valid code, document why
   - false_positive → Pattern matched incorrectly
   - wont_fix → Accepted tech debt
3. Tasks only created for confirmed issues
4. Track progress and health score improvements
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg2
from psycopg2.extras import RealDictCursor

from src.server.config.logfire_config import get_logger

logger = get_logger(__name__)


@dataclass
class WorkItem:
    """A work item representing a finding queued for review."""
    id: UUID
    finding_id: UUID
    task_id: UUID | None
    project_id: UUID | None
    review_status: str  # pending_review, confirmed_issue, intentional, false_positive, fixed, wont_fix
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_notes: str | None
    file_context: str | None
    suggested_action: str | None
    estimated_effort_minutes: int | None
    created_at: datetime
    updated_at: datetime
    
    # Joined fields from finding/rule
    file_path: str = ""
    line_start: int = 0
    line_end: int = 0
    finding_message: str = ""
    severity: str = "warning"
    rule_id: str = ""
    rule_name: str = ""
    category: str = ""
    rationale: str = ""
    remediation_guidance: str = ""


@dataclass
class ReviewBatchResult:
    """Result of queuing findings for review."""
    work_items_created: int
    findings_skipped: int
    rule_breakdown: dict[str, int]
    
    
@dataclass
class ProgressSummary:
    """Summary of audit remediation progress."""
    total_findings: int
    pending_review: int
    confirmed_issue: int
    intentional: int
    false_positive: int
    fixed: int
    wont_fix: int
    
    # Health score tracking
    initial_health_score: int | None = None
    current_health_score: int | None = None
    
    # Effort estimates
    total_estimated_minutes: int = 0
    remaining_estimated_minutes: int = 0
    
    def percent_reviewed(self) -> float:
        """Percentage of findings that have been reviewed."""
        if self.total_findings == 0:
            return 0.0
        reviewed = self.confirmed_issue + self.intentional + self.false_positive + self.fixed + self.wont_fix
        return (reviewed / self.total_findings) * 100
    
    def percent_fixed(self) -> float:
        """Percentage of findings that are fixed."""
        if self.total_findings == 0:
            return 0.0
        return (self.fixed / self.total_findings) * 100


class AuditWorkflowService:
    """Service for managing audit finding review and remediation workflow."""
    
    def __init__(self, db_connection=None):
        """Initialize with optional database connection."""
        self._db = db_connection
        self._connection_string = "postgresql://archon:archon_local_dev@localhost:5434/archon"
    
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
    
    def queue_findings_for_review(
        self,
        repo_id: str | UUID,
        project_id: str | UUID | None = None,
        rule_filter: list[str] | None = None,
        max_findings: int = 100,
    ) -> ReviewBatchResult:
        """
        Queue findings for human review.
        
        This creates work items with status 'pending_review' - it does NOT
        automatically create tasks. Human review is required first.
        
        Args:
            repo_id: Repository to queue findings from
            project_id: Optional project to associate with
            rule_filter: Optional list of specific rules to queue (e.g., ['assert-mock-not-verified'])
            max_findings: Safety limit (default 100)
            
        Returns:
            ReviewBatchResult with counts and breakdown
        """
        logger.info(f"Queueing findings for review: repo={repo_id}, rules={rule_filter}")
        
        result = self._execute_query(
            "SELECT * FROM queue_findings_for_review(%s, %s, %s, %s)",
            (str(repo_id), str(project_id) if project_id else None, rule_filter, max_findings),
            commit=True
        )
        
        if result:
            row = result[0]
            return ReviewBatchResult(
                work_items_created=row.get('work_items_created', 0),
                findings_skipped=row.get('findings_skipped_already_queued', 0),
                rule_breakdown=dict(row.get('rule_breakdown', {})),
            )
        
        return ReviewBatchResult(0, 0, {})
    
    def get_pending_review_items(
        self,
        project_id: str | UUID | None = None,
        limit: int = 50,
    ) -> list[WorkItem]:
        """
        Get findings ready for human review.
        
        Returns items prioritized by severity (critical first).
        """
        query = """
            SELECT 
                aft.*,
                af.file_path,
                af.line_start,
                af.line_end,
                af.message as finding_message,
                af.severity,
                ar.rule_id,
                ar.name as rule_name,
                ar.category,
                ar.rationale,
                ar.remediation_guidance,
                aft.suggested_label,
                aft.suggested_rationale
            FROM archon_audit_finding_tasks aft
            JOIN archon_audit_findings af ON aft.finding_id = af.id
            JOIN archon_audit_rules ar ON af.rule_id = ar.id
            WHERE aft.review_status IN ('pending_review', 'auto_suggested')
        """
        params = []
        
        if project_id:
            query += " AND aft.project_id = %s"
            params.append(str(project_id))
        
        query += """
            ORDER BY 
                CASE af.severity 
                    WHEN 'critical' THEN 1 
                    WHEN 'error' THEN 2 
                    WHEN 'warning' THEN 3 
                    ELSE 4 
                END,
                aft.created_at
            LIMIT %s
        """
        params.append(limit)
        
        results = self._execute_query(query, tuple(params))
        return [self._row_to_work_item(row) for row in results]
    
    def review_finding(
        self,
        work_item_id: str | UUID,
        decision: str,  # confirmed_issue, intentional, false_positive, wont_fix
        reviewed_by: str,
        notes: str | None = None,
    ) -> bool:
        """
        Review a finding and mark with decision.
        
        Args:
            work_item_id: The work item to review
            decision: One of confirmed_issue, intentional, false_positive, wont_fix
            reviewed_by: Who made the review decision
            notes: Optional notes explaining the decision
            
        Returns:
            True if successful
        """
        if decision not in ('confirmed_issue', 'intentional', 'false_positive', 'wont_fix'):
            raise ValueError(f"Invalid decision: {decision}")
        
        logger.info(f"Reviewing finding {work_item_id}: {decision} by {reviewed_by}")
        
        result = self._execute_query(
            "SELECT review_finding(%s, %s, %s, %s)",
            (str(work_item_id), decision, reviewed_by, notes),
            commit=True
        )
        
        return bool(result and result[0].get('review_finding'))
    
    def create_task_from_finding(
        self,
        work_item_id: str | UUID,
        project_id: str | UUID,
        assignee: str = "User",
    ) -> UUID | None:
        """
        Create a task from a confirmed finding.
        
        Only works if the finding has been reviewed and marked as 'confirmed_issue'.
        """
        logger.info(f"Creating task from finding {work_item_id}")
        
        result = self._execute_query(
            "SELECT create_task_from_finding(%s, %s, %s)",
            (str(work_item_id), str(project_id), assignee),
            commit=True
        )
        
        if result and result[0].get('create_task_from_finding'):
            return UUID(result[0]['create_task_from_finding'])
        return None
    
    def get_progress_summary(
        self,
        project_id: str | UUID | None = None,
        repo_id: str | UUID | None = None,
    ) -> ProgressSummary:
        """Get summary of review and remediation progress."""
        
        # Build query based on filters
        if project_id:
            query = """
                SELECT 
                    review_status,
                    COUNT(*) as count,
                    SUM(estimated_effort_minutes) as total_minutes
                FROM archon_audit_finding_tasks
                WHERE project_id = %s
                GROUP BY review_status
            """
            params = (str(project_id),)
        elif repo_id:
            query = """
                SELECT 
                    aft.review_status,
                    COUNT(*) as count,
                    SUM(aft.estimated_effort_minutes) as total_minutes
                FROM archon_audit_finding_tasks aft
                JOIN archon_audit_findings af ON aft.finding_id = af.id
                WHERE af.repo_id = %s
                GROUP BY aft.review_status
            """
            params = (str(repo_id),)
        else:
            query = """
                SELECT 
                    review_status,
                    COUNT(*) as count,
                    SUM(estimated_effort_minutes) as total_minutes
                FROM archon_audit_finding_tasks
                GROUP BY review_status
            """
            params = ()
        
        results = self._execute_query(query, params)
        
        # Initialize counters
        summary = ProgressSummary(
            total_findings=0,
            pending_review=0,
            confirmed_issue=0,
            intentional=0,
            false_positive=0,
            fixed=0,
            wont_fix=0,
        )
        
        for row in results:
            status = row.get('review_status')
            count = row.get('count', 0)
            minutes = row.get('total_minutes') or 0
            
            summary.total_findings += count
            summary.total_estimated_minutes += minutes
            
            if status == 'pending_review':
                summary.pending_review = count
                summary.remaining_estimated_minutes += minutes
            elif status == 'confirmed_issue':
                summary.confirmed_issue = count
                summary.remaining_estimated_minutes += minutes
            elif status == 'intentional':
                summary.intentional = count
            elif status == 'false_positive':
                summary.false_positive = count
            elif status == 'fixed':
                summary.fixed = count
            elif status == 'wont_fix':
                summary.wont_fix = count
        
        return summary
    
    def get_review_statistics(self, repo_id: str | UUID | None = None) -> dict[str, Any]:
        """Get detailed review statistics."""
        
        # By rule
        rule_stats_query = """
            SELECT 
                ar.rule_id,
                ar.name as rule_name,
                aft.review_status,
                COUNT(*) as count
            FROM archon_audit_finding_tasks aft
            JOIN archon_audit_findings af ON aft.finding_id = af.id
            JOIN archon_audit_rules ar ON af.rule_id = ar.id
        """
        
        if repo_id:
            rule_stats_query += " WHERE af.repo_id = %s"
            params = (str(repo_id),)
        else:
            params = ()
        
        rule_stats_query += """
            GROUP BY ar.rule_id, ar.name, aft.review_status
            ORDER BY ar.rule_id, aft.review_status
        """
        
        rule_results = self._execute_query(rule_stats_query, params)
        
        # Organize by rule
        by_rule = {}
        for row in rule_results:
            rule_id = row['rule_id']
            if rule_id not in by_rule:
                by_rule[rule_id] = {
                    'name': row['rule_name'],
                    'statuses': {}
                }
            by_rule[rule_id]['statuses'][row['review_status']] = row['count']
        
        return {
            'by_rule': by_rule,
            'summary': self.get_progress_summary(repo_id=repo_id),
        }
    
    def _row_to_work_item(self, row: dict) -> WorkItem:
        """Convert database row to WorkItem dataclass."""
        return WorkItem(
            id=row.get('id'),
            finding_id=row.get('finding_id'),
            task_id=row.get('task_id'),
            project_id=row.get('project_id'),
            review_status=row.get('review_status'),
            reviewed_by=row.get('reviewed_by'),
            reviewed_at=row.get('reviewed_at'),
            review_notes=row.get('review_notes'),
            file_context=row.get('file_context'),
            suggested_action=row.get('suggested_action'),
            estimated_effort_minutes=row.get('estimated_effort_minutes'),
            created_at=row.get('created_at'),
            updated_at=row.get('updated_at'),
            file_path=row.get('file_path', ''),
            line_start=row.get('line_start', 0),
            line_end=row.get('line_end', 0),
            finding_message=row.get('finding_message', ''),
            severity=row.get('severity', 'warning'),
            rule_id=row.get('rule_id', ''),
            rule_name=row.get('rule_name', ''),
            category=row.get('category', ''),
            rationale=row.get('rationale', ''),
            remediation_guidance=row.get('remediation_guidance', ''),
            suggested_label=row.get('suggested_label'),
            suggested_rationale=row.get('suggested_rationale'),
        )


# Singleton instance
_audit_workflow_service: AuditWorkflowService | None = None


def get_audit_workflow_service(db_connection=None) -> AuditWorkflowService:
    """Get or create singleton workflow service."""
    global _audit_workflow_service
    if _audit_workflow_service is None:
        _audit_workflow_service = AuditWorkflowService(db_connection)
    return _audit_workflow_service
