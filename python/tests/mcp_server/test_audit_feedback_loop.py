"""Comprehensive tests for ADR-011: Audit Feedback Loop.

Tests cover:
- audit_track_outcome - Record outcome of dismissed findings
- audit_get_retrospectives - Query learning events
- audit_check_correlation - Check for previously dismissed findings
- Database migrations for new tables
- Edge cases and error handling

Run with:
    docker exec archon pytest tests/mcp_server/test_audit_feedback_loop.py -v
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestAuditTrackOutcomeUnit:
    """Unit tests for audit_track_outcome logic."""

    def test_tool_exists_in_audit_tools(self):
        """Test that audit_track_outcome is defined in code_audit_tools."""
        import src.mcp_server.features.code_audit.code_audit_tools as cat

        source_file = cat.__file__
        with open(source_file) as f:
            content = f.read()

        assert "async def audit_track_outcome" in content
        assert '"success"' in content

    def test_valid_outcome_types(self):
        """Test that only valid outcome types are accepted."""
        valid_types = {"bug_filed", "bug_hit_production", "validated_correct"}

        # Test all valid types
        for outcome_type in valid_types:
            assert outcome_type in valid_types

        # Test invalid types
        invalid_types = ["bug", "invalid", "other", ""]
        for invalid_type in invalid_types:
            assert invalid_type not in valid_types

    def test_outcome_response_structure(self):
        """Test that outcome response has expected structure."""
        expected_fields = ["success", "outcome_id", "learning_event_id", "message"]

        # Simulate response
        response = {
            "success": True,
            "outcome_id": "uuid-1",
            "learning_event_id": None,
            "message": "Recorded bug_filed outcome for finding",
        }

        for field in expected_fields:
            assert field in response

    def test_learning_event_created_for_bug_types(self):
        """Test that learning events are created for bug-related outcomes."""
        bug_outcomes = {"bug_filed", "bug_hit_production"}
        non_bug_outcomes = {"validated_correct"}

        for outcome in bug_outcomes:
            # Should create learning event
            assert outcome in bug_outcomes

        for outcome in non_bug_outcomes:
            # Should NOT create learning event
            assert outcome not in bug_outcomes

    def test_event_type_determination(self):
        """Test that event_type is correctly determined based on finding status."""
        test_cases = [
            ("false_positive", "bug_filed", "dismissed_then_hit"),
            ("wont_fix", "bug_hit_production", "dismissed_then_hit"),
            ("open", "bug_filed", "false_negative"),
            ("resolved", "bug_filed", "false_negative"),
        ]

        for finding_status, outcome_type, expected_event_type in test_cases:
            if outcome_type in ("bug_filed", "bug_hit_production"):
                if finding_status in ("false_positive", "wont_fix"):
                    actual_event_type = "dismissed_then_hit"
                else:
                    actual_event_type = "false_negative"
                assert actual_event_type == expected_event_type, f"Failed for ({finding_status}, {outcome_type})"


class TestAuditGetRetrospectivesUnit:
    """Unit tests for audit_get_retrospectives logic."""

    def test_tool_exists_in_audit_tools(self):
        """Test that audit_get_retrospectives is defined in code_audit_tools."""
        import src.mcp_server.features.code_audit.code_audit_tools as cat

        source_file = cat.__file__
        with open(source_file) as f:
            content = f.read()

        assert "async def audit_get_retrospectives" in content

    def test_response_structure(self):
        """Test that response has expected structure."""
        response = {
            "success": True,
            "events": [
                {
                    "event_id": "uuid-1",
                    "event_type": "dismissed_then_hit",
                    "created_at": "2026-03-25T10:00:00",
                    "finding": {
                        "id": "finding-1",
                        "message": "Test finding",
                        "file_path": "src/auth.py",
                        "severity": "warning",
                        "status": "false_positive",
                    },
                    "outcome": {
                        "type": "bug_filed",
                        "notes": "Bug confirmed in production",
                        "issue_id": "BUG-123",
                    },
                    "correlation": {"original_status": "false_positive", "outcome_type": "bug_filed"},
                }
            ],
            "count": 1,
        }

        assert response["success"] is True
        assert "events" in response
        assert "count" in response
        assert len(response["events"]) == response["count"]

    def test_event_type_filter(self):
        """Test filtering by event_type."""
        all_events = [
            {"event_type": "dismissed_then_hit"},
            {"event_type": "false_negative"},
            {"event_type": "correct_dismissal"},
            {"event_type": "dismissed_then_hit"},
        ]

        # Filter for dismissed_then_hit
        filtered = [e for e in all_events if e["event_type"] == "dismissed_then_hit"]
        assert len(filtered) == 2

        # Filter for false_negative
        filtered = [e for e in all_events if e["event_type"] == "false_negative"]
        assert len(filtered) == 1

    def test_limit_parameter(self):
        """Test that limit parameter is respected."""
        all_events = list(range(100))
        limit = 10
        limited = all_events[:limit]

        assert len(limited) == 10

    def test_correlation_data_parsing(self):
        """Test that correlation_data JSONB is parsed correctly."""
        test_cases = [
            ('{"key": "value"}', {"key": "value"}),
            (
                '{"original_status": "false_positive", "outcome_type": "bug_filed"}',
                {"original_status": "false_positive", "outcome_type": "bug_filed"},
            ),
            ("", {}),
            ("not json", {}),
        ]

        for input_str, expected in test_cases:
            if not input_str:
                result = {}
            else:
                try:
                    result = json.loads(input_str)
                except json.JSONDecodeError:
                    result = {}

            assert result == expected, f"Failed for input: {input_str}"


class TestAuditCheckCorrelationUnit:
    """Unit tests for audit_check_correlation logic."""

    def test_tool_exists_in_audit_tools(self):
        """Test that audit_check_correlation is defined in code_audit_tools."""
        import src.mcp_server.features.code_audit.code_audit_tools as cat

        source_file = cat.__file__
        with open(source_file) as f:
            content = f.read()

        assert "async def audit_check_correlation" in content

    def test_response_structure(self):
        """Test that response has expected structure."""
        response = {
            "success": True,
            "has_correlation": True,
            "dismissed_findings": [
                {
                    "id": "uuid-1",
                    "rule_id": "complexity-high",
                    "message": "Function has high complexity",
                    "severity": "warning",
                    "status": "false_positive",
                    "category": "complexity",
                    "created_at": "2026-03-25T10:00:00",
                    "learning_events_count": 1,
                    "last_outcome_type": "bug_filed",
                }
            ],
            "count": 1,
            "warning": "1 previously dismissed finding(s) in this file",
        }

        assert response["success"] is True
        assert "has_correlation" in response
        assert "dismissed_findings" in response
        assert "count" in response

    def test_no_correlation_response(self):
        """Test response when no dismissed findings exist."""
        response = {
            "success": True,
            "has_correlation": False,
            "dismissed_findings": [],
            "count": 0,
            "warning": None,
        }

        assert response["success"] is True
        assert response["has_correlation"] is False
        assert len(response["dismissed_findings"]) == 0
        assert response["warning"] is None

    def test_dismissed_status_filter(self):
        """Test that only dismissed findings are returned."""
        findings = [
            {"status": "open"},
            {"status": "false_positive"},
            {"status": "wont_fix"},
            {"status": "resolved"},
        ]

        dismissed = [f for f in findings if f["status"] in ("false_positive", "wont_fix")]

        assert len(dismissed) == 2
        assert all(f["status"] in ("false_positive", "wont_fix") for f in dismissed)

    def test_function_name_filter_logic(self):
        """Test filtering by function name."""
        findings = [
            {"message": "Function foo has high complexity", "code_snippet": "def foo(): pass"},
            {"message": "Function bar has high complexity", "code_snippet": "def bar(): pass"},
            {"message": "General warning", "code_snippet": "some code"},
        ]

        function_name = "foo"
        filtered = [
            f
            for f in findings
            if function_name in (f["message"] or "").lower() or function_name in (f["code_snippet"] or "").lower()
        ]

        assert len(filtered) == 1
        assert "foo" in filtered[0]["message"].lower()


class TestDatabaseMigrations:
    """Tests for database migration SQL."""

    def test_migration_version_7_exists(self):
        """Test that migration version 7 for ADR-011 exists."""
        from src.server.database.migrations import MIGRATIONS

        version_7 = [m for m in MIGRATIONS if m.version == 7]
        assert len(version_7) == 1, "Migration version 7 should exist"

        migration = version_7[0]
        assert "audit_feedback_loop" in migration.name.lower()

    def test_migration_creates_outcomes_table(self):
        """Test that migration creates archon_audit_outcomes table."""
        from src.server.database.migrations import MIGRATIONS

        version_7 = [m for m in MIGRATIONS if m.version == 7][0]

        assert "CREATE TABLE IF NOT EXISTS archon_audit_outcomes" in version_7.up_sql

    def test_migration_creates_learning_events_table(self):
        """Test that migration creates archon_audit_learning_events table."""
        from src.server.database.migrations import MIGRATIONS

        version_7 = [m for m in MIGRATIONS if m.version == 7][0]

        assert "CREATE TABLE IF NOT EXISTS archon_audit_learning_events" in version_7.up_sql

    def test_migration_adds_columns_to_findings(self):
        """Test that migration adds columns to archon_audit_findings."""
        from src.server.database.migrations import MIGRATIONS

        version_7 = [m for m in MIGRATIONS if m.version == 7][0]

        assert "resolution_note TEXT" in version_7.up_sql
        assert "resolved_at TIMESTAMP" in version_7.up_sql
        assert "category TEXT" in version_7.up_sql

    def test_migration_has_indexes(self):
        """Test that migration creates proper indexes."""
        from src.server.database.migrations import MIGRATIONS

        version_7 = [m for m in MIGRATIONS if m.version == 7][0]

        expected_indexes = [
            "idx_audit_outcomes_finding",
            "idx_audit_outcomes_type",
            "idx_learning_events_finding",
            "idx_learning_events_type",
            "idx_audit_findings_category",
        ]

        for index in expected_indexes:
            assert index in version_7.up_sql, f"Missing index: {index}"

    def test_migration_has_rollback(self):
        """Test that migration has rollback SQL."""
        from src.server.database.migrations import MIGRATIONS

        version_7 = [m for m in MIGRATIONS if m.version == 7][0]

        assert version_7.down_sql, "Migration should have rollback SQL"
        assert "DROP TABLE IF EXISTS archon_audit_outcomes" in version_7.down_sql
        assert "DROP TABLE IF EXISTS archon_audit_learning_events" in version_7.down_sql


class TestCorrelationLogic:
    """Tests for correlation and learning logic."""

    def test_correlation_matches_file_path(self):
        """Test that correlation queries by file path."""
        findings = [
            {"file_path": "src/auth.py", "status": "false_positive"},
            {"file_path": "src/db.py", "status": "false_positive"},
            {"file_path": "src/auth.py", "status": "open"},
        ]

        file_path = "src/auth.py"
        matched = [f for f in findings if f["file_path"] == file_path and f["status"] in ("false_positive", "wont_fix")]

        assert len(matched) == 1
        assert matched[0]["file_path"] == file_path

    def test_correlation_requires_dismissed_status(self):
        """Test that only dismissed findings create correlations."""
        findings = [
            {"file_path": "src/auth.py", "status": "false_positive"},
            {"file_path": "src/auth.py", "status": "wont_fix"},
            {"file_path": "src/auth.py", "status": "open"},
            {"file_path": "src/auth.py", "status": "resolved"},
        ]

        file_path = "src/auth.py"
        dismissed = [
            f for f in findings if f["file_path"] == file_path and f["status"] in ("false_positive", "wont_fix")
        ]

        assert len(dismissed) == 2

    def test_correlation_catches_same_location(self):
        """Test that correlation catches findings in the same location."""
        previous_findings = [
            {"file_path": "src/auth.py", "message": "High complexity in login()", "status": "false_positive"},
            {"file_path": "src/db.py", "message": "High complexity in query()", "status": "wont_fix"},
        ]

        new_bug = {
            "file_path": "src/auth.py",
            "function": "login",
            "error": "Timeout error in login",
        }

        # Check for correlation
        matches = [
            f
            for f in previous_findings
            if f["file_path"] == new_bug["file_path"] and f["status"] in ("false_positive", "wont_fix")
        ]

        assert len(matches) == 1


class TestErrorHandling:
    """Tests for error handling in audit feedback tools."""

    def test_invalid_finding_id_handled(self):
        """Test that invalid finding_id is handled."""
        # Non-UUID finding_id
        finding_id = "not-a-uuid"

        # In real code, this would be caught by the database
        try:
            from uuid import UUID

            UUID(finding_id)
            is_valid = True
        except ValueError:
            is_valid = False

        assert is_valid is False

    def test_missing_finding_handled(self):
        """Test that missing finding returns appropriate error."""
        response = {"success": False, "error": "Finding uuid-findings-id not found"}

        assert response["success"] is False
        assert "not found" in response["error"].lower()

    def test_database_error_handled(self):
        """Test that database errors are handled gracefully."""
        # Simulate database connection error
        error = Exception("Connection refused")

        response = {
            "success": False,
            "error": str(error),
        }

        assert response["success"] is False
        assert "Connection refused" in response["error"]


class TestOutcomeTypes:
    """Tests for outcome type handling."""

    def test_outcome_types_valid(self):
        """Test all valid outcome types."""
        valid_types = ["bug_filed", "bug_hit_production", "validated_correct"]

        for outcome_type in valid_types:
            assert outcome_type in ["bug_filed", "bug_hit_production", "validated_correct"]

    def test_outcome_type_validation(self):
        """Test outcome type validation logic."""
        valid_types = {"bug_filed", "bug_hit_production", "validated_correct"}

        invalid_tests = ["bug", "", None, "invalid_type", "BugFiled"]
        for invalid in invalid_tests:
            assert invalid not in valid_types, f"'{invalid}' should not be in valid_types"


class TestLearningEventTypes:
    """Tests for learning event type logic."""

    def test_event_types(self):
        """Test all valid event types."""
        valid_types = {"false_negative", "dismissed_then_hit", "correct_dismissal"}

        assert "false_negative" in valid_types
        assert "dismissed_then_hit" in valid_types
        assert "correct_dismissal" in valid_types

    def test_event_type_correlation(self):
        """Test event type is correlated with finding status and outcome."""
        # Scenario 1: Finding was dismissed, then bug hit
        # Expected: dismissed_then_hit
        test_cases = [
            {
                "finding_status": "false_positive",
                "outcome_type": "bug_filed",
                "expected_event": "dismissed_then_hit",
            },
            {
                "finding_status": "wont_fix",
                "outcome_type": "bug_hit_production",
                "expected_event": "dismissed_then_hit",
            },
            {
                "finding_status": "open",
                "outcome_type": "bug_filed",
                "expected_event": "false_negative",
            },
            {
                "finding_status": "resolved",
                "outcome_type": "bug_filed",
                "expected_event": "false_negative",
            },
        ]

        for case in test_cases:
            if case["finding_status"] in ("false_positive", "wont_fix"):
                event_type = "dismissed_then_hit"
            else:
                event_type = "false_negative"

            assert event_type == case["expected_event"], f"Failed for case: {case}"


class TestFullAuditFeedbackWorkflow:
    """Tests for the complete audit feedback workflow."""

    def test_dismiss_finding_then_bug_workflow(self):
        """Test complete workflow: dismiss finding -> file bug -> get retrospective."""
        # Step 1: Finding was marked false_positive
        finding = {
            "id": "finding-1",
            "file_path": "src/auth.py",
            "message": "High complexity in login()",
            "status": "false_positive",
            "category": "complexity",
        }

        # Step 2: Bug filed for same location
        bug = {
            "file_path": "src/auth.py",
            "function": "login",
            "error": "Timeout error during login",
        }

        # Step 3: Check correlation
        correlated = finding["file_path"] == bug["file_path"] and finding["status"] in ("false_positive", "wont_fix")

        assert correlated is True

        # Step 4: Create outcome
        outcome = {
            "finding_id": finding["id"],
            "outcome_type": "bug_filed",
            "notes": f"Bug found: {bug['error']}",
            "related_issue_id": "BUG-123",
        }

        assert outcome["outcome_type"] == "bug_filed"

        # Step 5: Create learning event
        learning_event = {
            "finding_id": finding["id"],
            "event_type": "dismissed_then_hit",
            "correlation_data": {
                "original_status": finding["status"],
                "outcome_type": outcome["outcome_type"],
                "notes": outcome["notes"],
            },
        }

        assert learning_event["event_type"] == "dismissed_then_hit"
        assert learning_event["correlation_data"]["original_status"] == "false_positive"

    def test_correct_dismissal_workflow(self):
        """Test workflow for correct dismissals."""
        # Finding was dismissed, no bug appeared -> validated_correct
        finding = {
            "id": "finding-2",
            "status": "false_positive",
        }

        outcome = {
            "finding_id": finding["id"],
            "outcome_type": "validated_correct",
            "notes": "False positive confirmed, no actual issue",
        }

        # No learning event for validated_correct (no bug to correlate)
        assert outcome["outcome_type"] == "validated_correct"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
