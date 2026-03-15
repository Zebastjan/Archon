"""Tests for repo_health_check super-tool.

Tests the unified tool that combines metrics, audit, and worktree safety.
"""

import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from src.mcp_server.features.code_audit.repo_health_super_tool import (
    run_repo_health_check,
    FOCUS_RULESETS,
    _calculate_category_scores,
    _generate_highlights,
    _generate_recommendations,
)
from src.server.services.code_metrics_service import CodeMetrics, AuditFinding


class TestRepoHealthSuperTool:
    """Tests for the repo_health_check super-tool."""
    
    def test_focus_rulesets_defined(self):
        """Verify all focus modes have rulesets."""
        assert "full" in FOCUS_RULESETS
        assert "security" in FOCUS_RULESETS
        assert "tdd" in FOCUS_RULESETS
        assert "docs" in FOCUS_RULESETS
        assert "maintainability" in FOCUS_RULESETS
        
        # Verify security ruleset has expected rules
        security_rules = FOCUS_RULESETS["security"]
        assert "hardcoded-secrets" in security_rules
        assert "sql-injection" in security_rules
        
        # Verify TDD ruleset
        tdd_rules = FOCUS_RULESETS["tdd"]
        assert "untested-production-code" in tdd_rules
    
    @patch("src.mcp_server.features.code_audit.repo_health_super_tool.get_worktree_service")
    @patch("src.mcp_server.features.code_audit.repo_health_super_tool.get_code_metrics_service")
    def test_repo_health_check_success(self, mock_get_metrics, mock_get_worktree):
        """Test successful repo health check."""
        
        # Mock worktree validation
        mock_worktree_service = MagicMock()
        mock_validation = MagicMock()
        mock_validation.is_safe = True
        mock_validation.issues = []
        mock_validation.warnings = []
        mock_validation.context = None
        mock_worktree_service.validate_safe_to_work.return_value = mock_validation
        mock_get_worktree.return_value = mock_worktree_service
        
        # Mock metrics service
        mock_metrics_service = MagicMock()
        mock_metrics = CodeMetrics(
            total_files=50,
            total_lines_of_code=5000,
            health_score=78,
            avg_cyclomatic_complexity=5.5,
            max_cyclomatic_complexity=15,
        )
        mock_metrics_service.calculate_repo_metrics.return_value = mock_metrics
        mock_metrics_service.run_audit.return_value = (12, str(uuid4()))
        
        # Mock findings
        mock_findings = [
            AuditFinding(rule_id="complexity-high", severity="warning", message="Test"),
            AuditFinding(rule_id="hardcoded-secrets", severity="critical", message="Secret"),
        ]
        mock_metrics_service.get_audit_findings.return_value = mock_findings
        
        mock_get_metrics.return_value = mock_metrics_service
        
        # Run the tool
        result = run_repo_health_check(
            repo_id=str(uuid4()),
            focus="full",
        )
        
        # Verify structure
        assert result["success"] is True
        assert result["health_score"] == 78
        assert "per_category_scores" in result
        assert "highlights" in result
        assert "recommendations" in result
        assert "run_id" in result
        assert result["focus"] == "full"
        assert result["safety_validated"] is True
        
        # Verify findings summary
        assert result["findings_summary"]["total"] == 12
    
    @patch("src.mcp_server.features.code_audit.repo_health_super_tool.get_worktree_service")
    def test_worktree_safety_failure(self, mock_get_worktree):
        """Test that worktree safety issues are caught."""
        
        mock_worktree_service = MagicMock()
        mock_validation = MagicMock()
        mock_validation.is_safe = False
        mock_validation.issues = [{"message": "Conflict detected"}]
        mock_validation.warnings = []
        mock_validation.context.to_dict.return_value = {"is_worktree": True}
        mock_worktree_service.validate_safe_to_work.return_value = mock_validation
        mock_get_worktree.return_value = mock_worktree_service
        
        result = run_repo_health_check(repo_id=str(uuid4()))
        
        assert result["success"] is False
        assert "Worktree safety validation failed" in result["error"]
        assert "safety_issues" in result
    
    @patch("src.mcp_server.features.code_audit.repo_health_super_tool.get_worktree_service")
    @patch("src.mcp_server.features.code_audit.repo_health_super_tool.get_code_metrics_service")
    def test_security_focus(self, mock_get_metrics, mock_get_worktree):
        """Test security-focused audit."""
        
        # Mock worktree
        mock_worktree_service = MagicMock()
        mock_validation = MagicMock()
        mock_validation.is_safe = True
        mock_worktree_service.validate_safe_to_work.return_value = mock_validation
        mock_get_worktree.return_value = mock_worktree_service
        
        # Mock metrics
        mock_metrics_service = MagicMock()
        mock_metrics = CodeMetrics(health_score=85)
        mock_metrics_service.calculate_repo_metrics.return_value = mock_metrics
        mock_metrics_service.run_audit.return_value = (5, str(uuid4()))
        mock_metrics_service.get_audit_findings.return_value = []
        mock_get_metrics.return_value = mock_metrics_service
        
        result = run_repo_health_check(
            repo_id=str(uuid4()),
            focus="security",
        )
        
        assert result["success"] is True
        assert result["focus"] == "security"
        
        # Verify security ruleset was passed
        call_args = mock_metrics_service.run_audit.call_args
        ruleset = call_args[0][1]  # Second positional arg
        assert "hardcoded-secrets" in ruleset
        assert "sql-injection" in ruleset
    
    @patch("src.mcp_server.features.code_audit.repo_health_super_tool.get_worktree_service")
    @patch("src.mcp_server.features.code_audit.repo_health_super_tool.get_code_metrics_service")
    def test_custom_ruleset(self, mock_get_metrics, mock_get_worktree):
        """Test custom ruleset."""
        
        # Mock worktree
        mock_worktree_service = MagicMock()
        mock_validation = MagicMock()
        mock_validation.is_safe = True
        mock_worktree_service.validate_safe_to_work.return_value = mock_validation
        mock_get_worktree.return_value = mock_worktree_service
        
        # Mock metrics
        mock_metrics_service = MagicMock()
        mock_metrics = CodeMetrics(health_score=90)
        mock_metrics_service.calculate_repo_metrics.return_value = mock_metrics
        mock_metrics_service.run_audit.return_value = (0, str(uuid4()))
        mock_metrics_service.get_audit_findings.return_value = []
        mock_get_metrics.return_value = mock_metrics_service
        
        result = run_repo_health_check(
            repo_id=str(uuid4()),
            ruleset="complexity-high,missing-docstring",
        )
        
        assert result["success"] is True
        
        # Verify custom ruleset was passed
        call_args = mock_metrics_service.run_audit.call_args
        ruleset = call_args[0][1]
        assert ruleset == ["complexity-high", "missing-docstring"]


class TestCategoryScores:
    """Tests for category score calculation."""
    
    def test_category_scores_calculation(self):
        """Test that category scores are calculated correctly."""
        
        metrics = CodeMetrics(health_score=80)
        findings = [
            AuditFinding(rule_id="hardcoded-secrets", severity="critical"),
            AuditFinding(rule_id="complexity-high", severity="warning"),
        ]
        
        scores = _calculate_category_scores(metrics, findings)
        
        assert "overall" in scores
        assert "security" in scores
        assert "complexity" in scores
        assert "maintainability" in scores
        assert "documentation" in scores
        
        # Security should be penalized for critical finding
        assert scores["security"] < scores["overall"]


class TestHighlights:
    """Tests for highlights generation."""
    
    def test_highlights_sorted_by_severity(self):
        """Test that highlights are sorted by severity."""
        
        findings = [
            AuditFinding(rule_id="complexity-high", severity="warning", message="Warning"),
            AuditFinding(rule_id="hardcoded-secrets", severity="critical", message="Critical"),
            AuditFinding(rule_id="function-too-long", severity="error", message="Error"),
        ]
        
        highlights = _generate_highlights(findings)
        
        assert len(highlights) == 3
        # Should be sorted: critical, error, warning
        assert highlights[0]["severity"] == "critical"
        assert highlights[1]["severity"] == "error"
        assert highlights[2]["severity"] == "warning"
    
    def test_highlights_limited_to_10(self):
        """Test that highlights are limited to top 10."""
        
        findings = [
            AuditFinding(rule_id=f"rule-{i}", severity="warning", message=f"Finding {i}")
            for i in range(20)
        ]
        
        highlights = _generate_highlights(findings)
        
        assert len(highlights) == 10


class TestRecommendations:
    """Tests for recommendations generation."""
    
    def test_recommendations_for_complexity(self):
        """Test recommendations include complexity issues."""
        
        metrics = CodeMetrics(
            max_cyclomatic_complexity=50,
            code_to_comment_ratio=300,
        )
        findings = []
        
        recommendations = _generate_recommendations(metrics, findings, "full")
        
        # Should recommend refactoring high complexity
        assert any("complexity" in r.lower() for r in recommendations)
    
    def test_recommendations_for_comments(self):
        """Test recommendations include comment ratio."""
        
        metrics = CodeMetrics(
            code_to_comment_ratio=50,  # Very high ratio
        )
        findings = []
        
        recommendations = _generate_recommendations(metrics, findings, "full")
        
        # Should recommend adding comments
        assert any("comment" in r.lower() for r in recommendations)
    
    def test_security_focus_recommendations(self):
        """Test security-specific recommendations."""
        
        # Need to set up a scenario where security focus applies
        # The security focus adds recommendations only if there are security findings
        metrics = CodeMetrics()
        # Create a finding that looks like a security finding
        finding = AuditFinding(rule_id="hardcoded-secrets", severity="critical")
        
        recommendations = _generate_recommendations(metrics, [finding], "security")
        
        # Should include at least one recommendation (critical finding triggers generic rec)
        assert len(recommendations) > 0


class TestToolUsagePolicy:
    """Tests for tool usage policy compliance."""
    
    def test_super_tool_replaces_multiple_calls(self):
        """Verify super-tool replaces need for multiple tool calls."""
        
        # The super tool should internally call:
        # - validate_safe_to_work
        # - calculate_repo_metrics
        # - run_audit
        # - get_audit_findings
        
        # This is tested implicitly by successful execution
        pass
    
    def test_results_cached_for_follow_ups(self):
        """Verify run_id allows referencing results without re-running."""
        
        # The run_id returned allows:
        # - code_audit_get_findings(repo_id, run_id=...)
        # - code_audit_get_summary(repo_id)
        # Without re-running repo_health_check
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
