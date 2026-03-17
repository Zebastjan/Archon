"""Tests for Semgrep Service

Priority 1 test coverage for the audit infrastructure.
"""

import json
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import UUID

import pytest

from src.server.services.semgrep_service import (
    SemgrepFinding,
    SemgrepService,
    get_semgrep_service,
)


class TestSemgrepFinding:
    """Test the SemgrepFinding dataclass."""
    
    def test_to_db_dict(self):
        """Test conversion to database dictionary."""
        finding = SemgrepFinding(
            check_id="test-check",
            path="src/test.py",
            line_start=10,
            line_end=15,
            message="Test message",
            severity="WARNING",
            code_snippet="test_code",
            metadata={"key": "value"},
            metavariables={"meta": "data"},
        )
        
        repo_id = UUID("12345678-1234-1234-1234-123456789abc")
        db_dict = finding.to_db_dict(repo_id)
        
        assert db_dict["repo_id"] == str(repo_id)
        assert db_dict["semgrep_check_id"] == "test-check"
        assert db_dict["file_path"] == "src/test.py"
        assert db_dict["line_start"] == 10
        assert db_dict["severity"] == "WARNING"
        assert json.loads(db_dict["metavariables"]) == {"meta": "data"}
        # data_flow comes from metadata.data_flow, not metadata directly
        assert json.loads(db_dict["data_flow"]) == {}


class TestSemgrepServiceRunAudit:
    """Test the run_audit method."""
    
    @patch("src.server.services.semgrep_service.subprocess.run")
    def test_run_audit_calls_semgrep_with_correct_args(self, mock_run):
        """Test that run_audit invokes Semgrep with correct arguments."""
        # Mock successful Semgrep run with no findings
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({"results": [], "errors": []}),
            stderr="",
        )
        
        service = SemgrepService()
        repo_path = "/tmp/test-repo"
        repo_id = UUID("12345678-1234-1234-1234-123456789abc")
        
        findings = service.run_audit(
            repo_path=repo_path,
            repo_id=repo_id,
            rulesets=["p/ci"],
            exclude_patterns=["tests/"],
        )
        
        # Verify subprocess was called
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        
        # Check command structure
        cmd = call_args[0][0]
        assert cmd[0] == "semgrep"
        assert "--config" in cmd
        assert "p/ci" in cmd
        assert "--json" in cmd
        assert "--quiet" in cmd
        assert "--exclude" in cmd
        assert "tests/" in cmd
        assert cmd[-1] == repo_path
        
        assert findings == []
    
    @patch("src.server.services.semgrep_service.subprocess.run")
    def test_run_audit_parses_json_output(self, mock_run):
        """Test that run_audit correctly parses Semgrep JSON output."""
        semgrep_output = {
            "results": [
                {
                    "check_id": "test.rule",
                    "path": "/tmp/test-repo/src/main.py",
                    "start": {"line": 10, "col": 5},
                    "end": {"line": 10, "col": 20},
                    "extra": {
                        "message": "Test finding",
                        "severity": "WARNING",
                        "lines": "problematic_code_here",
                        "metadata": {},
                        "metavars": {},
                    },
                }
            ],
            "errors": [],
        }
        
        mock_run.return_value = Mock(
            returncode=1,  # Semgrep returns 1 when findings exist
            stdout=json.dumps(semgrep_output),
            stderr="",
        )
        
        service = SemgrepService()
        findings = service.run_audit(
            repo_path="/tmp/test-repo",
            repo_id=UUID("12345678-1234-1234-1234-123456789abc"),
        )
        
        assert len(findings) == 1
        assert findings[0].check_id == "test.rule"
        assert findings[0].path == "src/main.py"  # Relative path
        assert findings[0].line_start == 10
        assert findings[0].message == "Test finding"
    
    @patch("src.server.services.semgrep_service.subprocess.run")
    def test_run_audit_handles_semgrep_failure(self, mock_run):
        """Test that run_audit handles Semgrep errors gracefully."""
        mock_run.return_value = Mock(
            returncode=2,  # Error code
            stdout="",
            stderr="Semgrep failed",
        )
        
        service = SemgrepService()
        findings = service.run_audit(
            repo_path="/tmp/test-repo",
            repo_id=UUID("12345678-1234-1234-1234-123456789abc"),
        )
        
        assert findings == []
    
    @patch("src.server.services.semgrep_service.subprocess.run")
    def test_run_audit_timeout(self, mock_run):
        """Test that run_audit handles timeout."""
        from subprocess import TimeoutExpired
        mock_run.side_effect = TimeoutExpired("semgrep", 300)
        
        service = SemgrepService()
        findings = service.run_audit(
            repo_path="/tmp/test-repo",
            repo_id=UUID("12345678-1234-1234-1234-123456789abc"),
        )
        
        assert findings == []


class TestSemgrepServiceTriage:
    """Test the triage_finding method."""
    
    @pytest.mark.asyncio
    @patch("src.server.services.semgrep_service.SemgrepService._store_triage_memory")
    @patch("src.server.services.semgrep_service.SemgrepService._execute_query")
    async def test_triage_finding_updates_status(self, mock_execute, mock_store_memory):
        """Test that triage_finding updates finding status correctly."""
        # Mock finding retrieval
        mock_execute.side_effect = [
            [{"id": "finding-123", "semgrep_check_id": "test.rule", "repo_id": "repo-123"}],
            None,  # Update call
            None,  # Rule quality metrics call
        ]
        
        service = SemgrepService()
        
        # Should not raise
        result = await service.triage_finding(
            finding_id=UUID("12345678-1234-1234-1234-123456789abc"),
            decision="confirmed_issue",
            rationale="Test rationale",
            reviewer="tester",
            store_in_memory=True,
        )
        
        assert result is True
        
        # Verify status update was called
        update_calls = [call for call in mock_execute.call_args_list if "UPDATE" in str(call)]
        assert len(update_calls) > 0
    
    @pytest.mark.asyncio
    @patch("src.server.services.semgrep_service.SemgrepService._store_triage_memory")
    @patch("src.server.services.semgrep_service.SemgrepService._execute_query")
    async def test_triage_finding_calls_store_triage_memory(self, mock_execute, mock_store_memory):
        """Test that triage_finding calls _store_triage_memory."""
        mock_execute.side_effect = [
            [{"id": "finding-123", "semgrep_check_id": "test.rule", "repo_id": "repo-123"}],
            None,
            None,
        ]
        
        service = SemgrepService()
        
        result = await service.triage_finding(
            finding_id=UUID("12345678-1234-1234-1234-123456789abc"),
            decision="intentional",
            rationale="Valid pattern",
            reviewer="tester",
            store_in_memory=True,
        )
        
        assert result is True
        mock_store_memory.assert_called_once()
    
    @pytest.mark.asyncio
    @patch("src.server.services.semgrep_service.SemgrepService._execute_query")
    async def test_triage_finding_skips_memory_when_store_false(self, mock_execute):
        """Test that triage_finding skips memory storage when store_in_memory=False."""
        mock_execute.side_effect = [
            [{"id": "finding-123", "semgrep_check_id": "test.rule", "repo_id": "repo-123"}],
            None,
            None,
        ]
        
        service = SemgrepService()
        
        with patch.object(service, '_store_triage_memory') as mock_store:
            result = await service.triage_finding(
                finding_id=UUID("12345678-1234-1234-1234-123456789abc"),
                decision="false_positive",
                rationale="Not applicable",
                reviewer="tester",
                store_in_memory=False,
            )
            
            assert result is True
            mock_store.assert_not_called()
    
    @pytest.mark.asyncio
    @patch("src.server.services.semgrep_service.SemgrepService._execute_query")
    async def test_triage_finding_finding_not_found(self, mock_execute):
        """Test that triage_finding handles missing finding."""
        mock_execute.return_value = []  # No finding found
        
        service = SemgrepService()
        
        result = await service.triage_finding(
            finding_id=UUID("12345678-1234-1234-1234-123456789abc"),
            decision="confirmed_issue",
            rationale="Test",
            reviewer="tester",
        )
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_triage_finding_invalid_decision(self):
        """Test that triage_finding validates decision values."""
        service = SemgrepService()
        
        with pytest.raises(ValueError, match="Invalid decision"):
            await service.triage_finding(
                finding_id=UUID("12345678-1234-1234-1234-123456789abc"),
                decision="invalid_decision",
                rationale="Test",
                reviewer="tester",
            )


class TestSemgrepServiceSuggestTriage:
    """Test the suggest_triage_decision method."""
    
    @pytest.mark.asyncio
    @patch("src.server.services.semgrep_service.SemgrepService._execute_query")
    async def test_suggest_triage_returns_empty_when_no_similar_patterns(self, mock_execute):
        """Test that suggest_triage_decision returns empty list when no similar patterns."""
        # Need 3 calls: finding details, semantic search (empty), fallback check match (empty)
        mock_execute.side_effect = [
            [{"id": "finding-123", "semgrep_check_id": "test.rule", "file_path": "test.py", "code_snippet": "def test(): pass"}],
            [],  # Semantic search returns empty
            [],  # Fallback check match also empty
        ]
        
        service = SemgrepService()
        
        # Mock embedding service
        with patch.object(service, '_get_embedding_service') as mock_get_emb:
            mock_emb = Mock()
            mock_emb.generate_for_code_entity = AsyncMock(return_value=[0.1] * 768)
            mock_get_emb.return_value = mock_emb
            
            result = await service.suggest_triage_decision(UUID("12345678-1234-1234-1234-123456789abc"))
        
        # Should return None when no similar patterns
        assert result is None
    
    @pytest.mark.asyncio
    @patch("src.server.services.semgrep_service.SemgrepService._execute_query")
    async def test_suggest_triage_returns_suggestion_when_similar_exist(self, mock_execute):
        """Test that suggest_triage_decision returns suggestion when similar patterns exist."""
        # First query: get finding details (with code_snippet to trigger semantic search)
        # Second query: semantic search returns results
        mock_execute.side_effect = [
            [{"id": "finding-123", "semgrep_check_id": "test.rule", "file_path": "test.py", "code_snippet": "def test(): pass"}],
            [
                {"decision": "intentional", "decision_rationale": "Valid", "confidence_score": 0.9, "similarity": 0.85},
                {"decision": "intentional", "decision_rationale": "OK", "confidence_score": 0.85, "similarity": 0.82},
            ],
        ]
        
        service = SemgrepService()
        
        with patch.object(service, '_get_embedding_service') as mock_get_emb:
            mock_emb = Mock()
            # Return a coroutine for async method
            mock_emb.generate_for_code_entity = AsyncMock(return_value=[0.1] * 768)
            mock_get_emb.return_value = mock_emb
            
            result = await service.suggest_triage_decision(UUID("12345678-1234-1234-1234-123456789abc"))
        
        assert result is not None
        assert result["suggested_decision"] == "intentional"
        assert result["similar_cases"] == 2


class TestSemgrepServiceSemanticDrift:
    """Test the check_semantic_drift stub method."""
    
    @pytest.mark.asyncio
    async def test_check_semantic_drift_returns_empty_list(self):
        """Test that check_semantic_drift returns empty list."""
        service = SemgrepService()
        
        result = await service.check_semantic_drift(
            repo_id="repo-123",
            entity_id="entity-456",
        )
        
        assert result == []
        assert isinstance(result, list)
    
    @pytest.mark.asyncio
    async def test_check_semantic_drift_does_not_raise(self):
        """Test that check_semantic_drift does not raise any exception."""
        service = SemgrepService()
        
        try:
            result = await service.check_semantic_drift(
                repo_id="repo-123",
                entity_id="entity-456",
            )
            assert result == []
        except Exception as e:
            pytest.fail(f"check_semantic_drift raised {e} unexpectedly!")


class TestGetSemgrepService:
    """Test the get_semgrep_service factory function."""
    
    def test_get_semgrep_service_returns_singleton(self):
        """Test that get_semgrep_service returns a singleton."""
        service1 = get_semgrep_service()
        service2 = get_semgrep_service()
        
        assert service1 is service2
    
    def test_get_semgrep_service_returns_semgrp_service_instance(self):
        """Test that get_semgrep_service returns SemgrepService instance."""
        service = get_semgrep_service()
        
        assert isinstance(service, SemgrepService)
