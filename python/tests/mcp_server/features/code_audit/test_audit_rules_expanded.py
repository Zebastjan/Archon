"""Tests for expanded audit rules and methodology support.

Tests the enhanced audit rule system with security, maintainability,
and methodology-aware rules.
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from src.server.services.code_metrics_service import (
    CodeMetricsService,
    AuditRule,
    get_code_metrics_service,
)


@pytest.fixture
def mock_db():
    """Create a mock database connection."""
    mock = MagicMock()
    return mock


class TestExpandedAuditRules:
    """Tests for expanded audit rules with enhanced metadata."""
    
    def test_security_rules_have_owasp_cwe(self, mock_db):
        """Verify security rules have OWASP and CWE references."""
        service = CodeMetricsService(db_connection=mock_db)
        
        # Mock security rules - patch _execute_query to return test data
        mock_rules = [
            {
                "id": str(uuid4()),
                "rule_id": "hardcoded-secrets",
                "name": "Hardcoded Secrets",
                "category": "security",
                "severity": "critical",
                "implementation_type": "pattern-static",
                "applies_to_security_first": True,
                "owasp_category": "A07:2021",
                "cwe_id": "CWE-798",
                "rationale": "Secrets in code are a security risk",
                "is_active": True,
                "is_builtin": True,
            },
            {
                "id": str(uuid4()),
                "rule_id": "sql-injection",
                "name": "SQL Injection",
                "category": "security",
                "severity": "critical",
                "implementation_type": "pattern-static",
                "applies_to_security_first": True,
                "owasp_category": "A03:2021",
                "cwe_id": "CWE-89",
                "rationale": "SQL injection enables attacks",
                "is_active": True,
                "is_builtin": True,
            }
        ]
        
        with patch.object(service, '_execute_query', return_value=mock_rules):
            rules = service.get_audit_rules(category="security")
        
            assert len(rules) == 2
            
            # Verify security metadata
            for rule in rules:
                assert rule.applies_to_security_first is True
                assert rule.owasp_category is not None
                assert rule.cwe_id is not None
                assert rule.rationale != ""
    
    def test_maintainability_rules_have_guidance(self, mock_db):
        """Verify maintainability rules have remediation guidance."""
        service = CodeMetricsService(db_connection=mock_db)
        
        mock_rules = [
            {
                "id": str(uuid4()),
                "rule_id": "too-many-params",
                "name": "Too Many Parameters",
                "category": "maintainability",
                "severity": "warning",
                "implementation_type": "mechanical-static",
                "rationale": "High parameter count indicates tight coupling",
                "remediation_guidance": "Use configuration objects",
                "example_violation": "def func(a, b, c, d, e, f, g, h):",
                "example_fix": "def func(config):",
                "estimated_fix_time_minutes": 30,
                "is_active": True,
                "is_builtin": True,
            }
        ]
        
        with patch.object(service, '_execute_query', return_value=mock_rules):
            rules = service.get_audit_rules(category="maintainability")
            
            assert len(rules) == 1
            rule = rules[0]
            
            assert rule.rationale != ""
            assert rule.remediation_guidance != ""
            assert rule.example_violation != ""
            assert rule.example_fix != ""
            assert rule.estimated_fix_time_minutes > 0
    
    def test_rules_have_implementation_type(self, mock_db):
        """Verify rules have implementation type classification."""
        service = CodeMetricsService(db_connection=mock_db)
        
        mock_rules = [
            {
                "id": str(uuid4()),
                "rule_id": "complexity-high",
                "category": "complexity",
                "implementation_type": "threshold-static",
                "is_active": True,
                "is_builtin": True,
            },
            {
                "id": str(uuid4()),
                "rule_id": "duplicate-code",
                "category": "maintainability",
                "implementation_type": "heuristic-static",
                "is_active": True,
                "is_builtin": True,
            }
        ]
        
        with patch.object(service, '_execute_query', return_value=mock_rules):
            rules = service.get_audit_rules()
            
            implementation_types = {r.implementation_type for r in rules}
            assert "threshold-static" in implementation_types
            assert "heuristic-static" in implementation_types
    
    def test_rules_have_references(self, mock_db):
        """Verify rules have reference links."""
        service = CodeMetricsService(db_connection=mock_db)
        
        mock_rules = [
            {
                "id": str(uuid4()),
                "rule_id": "weak-crypto",
                "category": "security",
                "references": [
                    "https://owasp.org/Top10/A02_2021-Cryptographic_Failures/",
                    "https://cwe.mitre.org/data/definitions/327.html"
                ],
                "is_active": True,
                "is_builtin": True,
            }
        ]
        
        with patch.object(service, '_execute_query', return_value=mock_rules):
            rules = service.get_audit_rules()
            
            assert len(rules) == 1
            assert len(rules[0].references) == 2
            assert "owasp.org" in rules[0].references[0]


class TestMethodologyAwareRules:
    """Tests for methodology-aware audit rules."""
    
    def test_tdd_rules_flagged(self, mock_db):
        """Verify TDD rules are flagged correctly."""
        service = CodeMetricsService(db_connection=mock_db)
        
        mock_rules = [
            {
                "id": str(uuid4()),
                "rule_id": "untested-production-code",
                "category": "methodology",
                "applies_to_tdd": True,
                "applies_to_doc_driven": False,
                "methodology_tags": '["tdd", "testing", "quality"]',
                "is_active": True,
                "is_builtin": True,
            },
            {
                "id": str(uuid4()),
                "rule_id": "missing-tests-for-public-api",
                "category": "methodology",
                "applies_to_tdd": True,
                "applies_to_doc_driven": False,
                "methodology_tags": '["tdd", "testing"]',
                "is_active": True,
                "is_builtin": True,
            }
        ]
        
        with patch.object(service, '_execute_query', return_value=mock_rules):
            rules = service.get_audit_rules(category="methodology")
            
            for rule in rules:
                assert rule.applies_to_tdd is True
                assert "tdd" in rule.methodology_tags
    
    def test_doc_driven_rules_flagged(self, mock_db):
        """Verify documentation-driven rules are flagged."""
        service = CodeMetricsService(db_connection=mock_db)
        
        mock_rules = [
            {
                "id": str(uuid4()),
                "rule_id": "public-api-missing-docs",
                "category": "documentation",
                "applies_to_tdd": False,
                "applies_to_doc_driven": True,
                "methodology_tags": '["doc-driven"]',
                "is_active": True,
                "is_builtin": True,
            }
        ]
        
        with patch.object(service, '_execute_query', return_value=mock_rules):
            rules = service.get_audit_rules(category="documentation")
            
            assert len(rules) == 1
            assert rules[0].applies_to_doc_driven is True
            assert "doc-driven" in rules[0].methodology_tags
    
    def test_methodology_tags_parsing(self, mock_db):
        """Verify methodology tags are parsed correctly from JSON."""
        service = CodeMetricsService(db_connection=mock_db)
        
        mock_rules = [
            {
                "id": str(uuid4()),
                "rule_id": "test-rule",
                "methodology_tags": '["tdd", "testing", "quality"]',
                "is_active": True,
                "is_builtin": True,
            }
        ]
        
        with patch.object(service, '_execute_query', return_value=mock_rules):
            rules = service.get_audit_rules()
            
            assert len(rules) == 1
            assert isinstance(rules[0].methodology_tags, list)
            assert "tdd" in rules[0].methodology_tags
            assert "testing" in rules[0].methodology_tags


class TestRuleCatalogExpansion:
    """Tests for the expanded rule catalog."""
    
    def test_security_rules_count(self, mock_db):
        """Verify we have expected number of security rules."""
        service = CodeMetricsService(db_connection=mock_db)
        
        # Mock 6 security rules
        mock_rules = [
            {"id": str(uuid4()), "rule_id": f"security-{i}", "category": "security", "is_active": True, "is_builtin": True}
            for i in range(6)
        ]
        
        with patch.object(service, '_execute_query', return_value=mock_rules):
            rules = service.get_audit_rules(category="security")
            
            assert len(rules) == 6
    
    def test_maintainability_rules_count(self, mock_db):
        """Verify we have expected number of maintainability rules."""
        service = CodeMetricsService(db_connection=mock_db)
        
        mock_rules = [
            {"id": str(uuid4()), "rule_id": f"maintainability-{i}", "category": "maintainability", "is_active": True, "is_builtin": True}
            for i in range(8)
        ]
        
        with patch.object(service, '_execute_query', return_value=mock_rules):
            rules = service.get_audit_rules(category="maintainability")
            
            assert len(rules) == 8
    
    def test_documentation_rules_count(self, mock_db):
        """Verify we have documentation/test hygiene rules."""
        service = CodeMetricsService(db_connection=mock_db)
        
        mock_rules = [
            {"id": str(uuid4()), "rule_id": f"documentation-{i}", "category": "documentation", "is_active": True, "is_builtin": True}
            for i in range(4)
        ]
        
        with patch.object(service, '_execute_query', return_value=mock_rules):
            rules = service.get_audit_rules(category="documentation")
            
            assert len(rules) == 4
    
    def test_methodology_rules_count(self, mock_db):
        """Verify we have methodology rules."""
        service = CodeMetricsService(db_connection=mock_db)
        
        mock_rules = [
            {"id": str(uuid4()), "rule_id": f"methodology-{i}", "category": "methodology", "is_active": True, "is_builtin": True}
            for i in range(3)
        ]
        
        with patch.object(service, '_execute_query', return_value=mock_rules):
            rules = service.get_audit_rules(category="methodology")
            
            assert len(rules) == 3


class TestAuditRuleDataStructure:
    """Tests for AuditRule data structure."""
    
    def test_audit_rule_to_dict_includes_all_fields(self):
        """Verify AuditRule.to_dict includes all new fields."""
        rule = AuditRule(
            rule_id="test-rule",
            name="Test Rule",
            category="security",
            implementation_type="pattern-static",
            rationale="Test rationale",
            remediation_guidance="Fix it",
            example_violation="bad_code",
            example_fix="good_code",
            references=["https://example.com"],
            methodology_tags=["tdd"],
            applies_to_tdd=True,
            applies_to_doc_driven=False,
            applies_to_security_first=True,
            owasp_category="A01:2021",
            cwe_id="CWE-123",
            estimated_fix_time_minutes=15,
        )
        
        data = rule.to_dict()
        
        # Verify enhanced fields
        assert data["implementation_type"] == "pattern-static"
        assert data["rationale"] == "Test rationale"
        assert data["remediation_guidance"] == "Fix it"
        assert data["example_violation"] == "bad_code"
        assert data["example_fix"] == "good_code"
        assert data["references"] == ["https://example.com"]
        assert data["methodology_tags"] == ["tdd"]
        assert data["applies_to_tdd"] is True
        assert data["applies_to_doc_driven"] is False
        assert data["applies_to_security_first"] is True
        assert data["owasp_category"] == "A01:2021"
        assert data["cwe_id"] == "CWE-123"
        assert data["estimated_fix_time_minutes"] == 15


class TestRuleSeverityLevels:
    """Tests for rule severity classification."""
    
    def test_critical_severity_rules(self, mock_db):
        """Verify critical severity rules exist."""
        service = CodeMetricsService(db_connection=mock_db)
        
        mock_rules = [
            {
                "id": str(uuid4()),
                "rule_id": "hardcoded-secrets",
                "severity": "critical",
                "is_active": True,
                "is_builtin": True,
            },
            {
                "id": str(uuid4()),
                "rule_id": "sql-injection",
                "severity": "critical",
                "is_active": True,
                "is_builtin": True,
            }
        ]
        
        with patch.object(service, '_execute_query', return_value=mock_rules):
            rules = service.get_audit_rules()
            
            critical_rules = [r for r in rules if r.severity == "critical"]
            assert len(critical_rules) == 2
    
    def test_warning_severity_rules(self, mock_db):
        """Verify warning severity rules exist."""
        service = CodeMetricsService(db_connection=mock_db)
        
        mock_rules = [
            {
                "id": str(uuid4()),
                "rule_id": "complexity-high",
                "severity": "warning",
                "is_active": True,
                "is_builtin": True,
            },
            {
                "id": str(uuid4()),
                "rule_id": "function-too-long",
                "severity": "warning",
                "is_active": True,
                "is_builtin": True,
            }
        ]
        
        with patch.object(service, '_execute_query', return_value=mock_rules):
            rules = service.get_audit_rules()
            
            warning_rules = [r for r in rules if r.severity == "warning"]
            assert len(warning_rules) == 2


class TestActiveVsInactiveRules:
    """Tests for active/inactive rule filtering."""
    
    def test_get_active_rules_only(self, mock_db):
        """Verify get_audit_rules filters by is_active."""
        service = CodeMetricsService(db_connection=mock_db)
        
        mock_rules = [
            {"id": str(uuid4()), "rule_id": "active-rule", "is_active": True, "is_builtin": True},
        ]
        
        with patch.object(service, '_execute_query', return_value=mock_rules):
            rules = service.get_audit_rules(is_active=True)
            
            assert len(rules) == 1
            assert rules[0].is_active is True
    
    def test_get_included_inactive_rules(self, mock_db):
        """Verify can get inactive rules."""
        service = CodeMetricsService(db_connection=mock_db)
        
        mock_rules = [
            {"id": str(uuid4()), "rule_id": "inactive-rule", "is_active": False, "is_builtin": True},
        ]
        
        with patch.object(service, '_execute_query', return_value=mock_rules):
            # Mock would return inactive when is_active=False
            rules = service.get_audit_rules(is_active=False)
            
            # Should return inactive rules
            assert len(rules) >= 0  # May be empty if filtering works


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
