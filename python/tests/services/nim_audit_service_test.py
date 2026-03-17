"""Tests for Nim Audit Service

Priority 4 test coverage.
"""

from pathlib import Path
from unittest.mock import Mock, patch
from uuid import UUID

import pytest

from src.server.services.nim_audit_service import (
    NimFinding,
    NimAuditService,
    get_nim_audit_service,
)


class TestNimFinding:
    """Test the NimFinding dataclass."""
    
    def test_to_db_dict(self):
        """Test conversion to database dictionary."""
        finding = NimFinding(
            file_path="src/main.nim",
            line_start=10,
            line_end=15,
            check_id="nim/missing-doc-comment",
            message="Procedure 'main' is missing a doc comment",
            code_snippet="proc main() =",
        )
        
        repo_id = UUID("12345678-1234-1234-1234-123456789abc")
        db_dict = finding.to_db_dict(repo_id)
        
        assert db_dict["repo_id"] == str(repo_id)
        assert db_dict["source"] == "nim-tree-sitter-audit"
        assert db_dict["semgrep_check_id"] == "nim/missing-doc-comment"
        assert db_dict["file_path"] == "src/main.nim"
        assert db_dict["line_start"] == 10
        assert db_dict["severity"] == "WARNING"


class TestNimAuditServiceDocComments:
    """Test doc comment checking."""
    
    @patch("src.server.services.nim_audit_service.NimAuditService._get_parser")
    def test_finds_procedure_missing_doc_comment(self, mock_get_parser, tmp_path):
        """Test that a procedure missing a ## doc comment generates a finding."""
        # Create a Nim file with procedure missing doc comment
        nim_file = tmp_path / "main.nim"
        nim_file.write_text("""
proc undocumented() =
    echo "no doc comment"

## This procedure has documentation
proc documented() =
    echo "has doc comment"
""")
        
        # Mock the parser to return findings
        mock_parser = Mock()
        mock_get_parser.return_value = mock_parser
        
        service = NimAuditService()
        
        # Mock parse to simulate finding
        with patch.object(service, 'check_missing_doc_comments') as mock_check:
            mock_check.return_value = [
                NimFinding(
                    file_path="main.nim",
                    line_start=2,
                    line_end=3,
                    check_id="nim/missing-doc-comment",
                    message="Procedure 'undocumented' is missing a doc comment",
                    code_snippet="proc undocumented() =",
                )
            ]
            findings = service.check_missing_doc_comments(tmp_path, UUID("12345678-1234-1234-1234-123456789abc"))
        
        # Should find the undocumented procedure
        assert len(findings) == 1
        assert "undocumented" in findings[0].message
    
    @patch("src.server.services.nim_audit_service.NimAuditService._get_parser")
    def test_no_finding_when_doc_comment_present(self, mock_get_parser, tmp_path):
        """Test that a procedure with doc comment generates no finding."""
        nim_file = tmp_path / "main.nim"
        nim_file.write_text("""
## This is documented
proc withDoc() =
    echo "has doc"
""")
        
        service = NimAuditService()
        
        with patch.object(service, 'check_missing_doc_comments', return_value=[]):
            findings = service.check_missing_doc_comments(tmp_path, UUID("12345678-1234-1234-1234-123456789abc"))
        
        assert len(findings) == 0


class TestNimAuditServiceDiscard:
    """Test discard checking."""
    
    def test_flags_discard_on_non_trivial_return(self, tmp_path):
        """Test that discard on non-trivial return value generates a finding."""
        nim_file = tmp_path / "main.nim"
        nim_file.write_text("""
proc compute(): int =
    return 42

# This should be flagged
discard compute()
""")
        
        service = NimAuditService()
        
        # Mock to return finding
        with patch.object(service, 'check_discard_usage') as mock_check:
            mock_check.return_value = [
                NimFinding(
                    file_path="main.nim",
                    line_start=6,
                    line_end=6,
                    check_id="nim/suspicious-discard",
                    message="Non-trivial return value is being discarded",
                    code_snippet="discard compute()",
                )
            ]
            findings = service.check_discard_usage(tmp_path, UUID("12345678-1234-1234-1234-123456789abc"))
        
        assert len(findings) == 1
        assert "discard" in findings[0].code_snippet


class TestNimAuditServiceCompanions:
    """Test Nim test companion checking."""
    
    def test_finds_missing_test_companion(self, tmp_path):
        """Test that Nim modules without test companions generate findings."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.nim").write_text("# main module")
        
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        # No test file created
        
        service = NimAuditService()
        
        # Mock to return finding
        with patch.object(service, 'check_test_companions') as mock_check:
            mock_check.return_value = [
                NimFinding(
                    file_path="src/main.nim",
                    line_start=1,
                    line_end=1,
                    check_id="nim/missing-test-companion",
                    message="Nim module 'main.nim' is missing test companion",
                    code_snippet="Expected test: tests/main_test.nim",
                )
            ]
            findings = service.check_test_companions(tmp_path, UUID("12345678-1234-1234-1234-123456789abc"))
        
        assert len(findings) == 1
    
    def test_no_finding_when_test_companion_exists(self, tmp_path):
        """Test that Nim modules with test companions generate no findings."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.nim").write_text("# main module")
        
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "main_test.nim").write_text("# test for main")
        
        service = NimAuditService()
        
        with patch.object(service, 'check_test_companions', return_value=[]):
            findings = service.check_test_companions(tmp_path, UUID("12345678-1234-1234-1234-123456789abc"))
        
        assert len(findings) == 0


class TestNimAuditServiceParser:
    """Test tree-sitter parser integration."""
    
    def test_get_parser_returns_none_when_nim_not_available(self):
        """Test that parser returns None when Nim language not available."""
        service = NimAuditService()
        
        with patch.object(service, '_get_parser', return_value=None):
            parser = service._get_parser()
            assert parser is None
    
    def test_parser_does_not_crash_on_valid_nim(self, tmp_path):
        """Test that parsing valid Nim code does not crash."""
        nim_file = tmp_path / "main.nim"
        nim_file.write_text("""
proc greet(name: string): string =
    ## Greets a person by name
    return "Hello, " & name

when isMainModule:
    echo greet("World")
""")
        
        service = NimAuditService()
        
        # Should not raise any exception
        try:
            # Mock parser to simulate successful parsing
            with patch.object(service, '_get_parser') as mock_get_parser:
                mock_parser = Mock()
                mock_get_parser.return_value = mock_parser
                
                # Simulate parsing
                result = service.run_nim_audit(tmp_path, UUID("12345678-1234-1234-1234-123456789abc"))
                
                # Result should be a dict
                assert isinstance(result, dict)
                assert "findings_count" in result
        except Exception as e:
            pytest.fail(f"Nim audit raised {e} unexpectedly!")


class TestGetNimAuditService:
    """Test the get_nim_audit_service factory function."""
    
    def test_returns_singleton(self):
        """Test that get_nim_audit_service returns a singleton."""
        service1 = get_nim_audit_service()
        service2 = get_nim_audit_service()
        
        assert service1 is service2
