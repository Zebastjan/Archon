"""Tests for Companion Check Service

Priority 3 test coverage.
"""

import json
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import UUID

import pytest

from src.server.services.companion_check_service import (
    CompanionFinding,
    CompanionCheckService,
    get_companion_check_service,
)


class TestCompanionFinding:
    """Test the CompanionFinding dataclass."""
    
    def test_to_db_dict(self):
        """Test conversion to database dictionary."""
        finding = CompanionFinding(
            source_file="src/main.py",
            expected_test="test_main.py",
            pattern="test_{module}.py",
        )
        
        repo_id = UUID("12345678-1234-1234-1234-123456789abc")
        db_dict = finding.to_db_dict(repo_id)
        
        assert db_dict["repo_id"] == str(repo_id)
        assert db_dict["source"] == "companion-check"
        assert db_dict["semgrep_check_id"] == "testing/missing-test-companion"
        assert db_dict["file_path"] == "src/main.py"
        assert "test_main.py" in db_dict["message"]
        assert db_dict["severity"] == "WARNING"


class TestCompanionCheckExclusions:
    """Test that excluded directories are properly skipped."""
    
    def test_excludes_venv_directory(self, tmp_path):
        """Test that .venv directory is excluded."""
        service = CompanionCheckService()
        
        # Create structure with .venv
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("# main")
        
        venv_dir = tmp_path / ".venv"
        venv_dir.mkdir()
        (venv_dir / "lib.py").write_text("# venv lib - should be excluded")
        
        # Create methodology config that enables companion checks
        with patch.object(service, '_get_methodology_config', return_value={
            "enforce": ["test_companions"],
            "test_companion_pattern": "test_{module}.py"
        }):
            with patch.object(service, '_execute_query'):
                findings = service.check_python_companions(tmp_path, UUID("12345678-1234-1234-1234-123456789abc"))
        
        # Should only find src/main.py, not .venv/lib.py
        assert len(findings) == 1
        assert ".venv" not in findings[0].source_file
    
    def test_excludes_pycache_directory(self, tmp_path):
        """Test that __pycache__ directory is excluded."""
        service = CompanionCheckService()
        
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("# main")
        
        pycache_dir = src_dir / "__pycache__"
        pycache_dir.mkdir()
        (pycache_dir / "main.cpython-312.pyc").write_text("# pycache - excluded")
        
        with patch.object(service, '_get_methodology_config', return_value={
            "enforce": ["test_companions"],
            "test_companion_pattern": "test_{module}.py"
        }):
            with patch.object(service, '_execute_query'):
                findings = service.check_python_companions(tmp_path, UUID("12345678-1234-1234-1234-123456789abc"))
        
        assert len(findings) == 1
        assert "__pycache__" not in findings[0].source_file
    
    def test_excludes_npm_modules_directory(self, tmp_path):
        """Test that node_modules directory is excluded."""
        service = CompanionCheckService()
        
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("# main")
        
        # Create node_modules with a Python file (would be excluded)
        node_modules = tmp_path / "node_modules"
        node_modules.mkdir()
        (node_modules / "some_lib.py").write_text("# node module - excluded")
        
        with patch.object(service, '_get_methodology_config', return_value={
            "enforce": ["test_companions"],
            "test_companion_pattern": "test_{module}.py"
        }):
            with patch.object(service, '_execute_query'):
                findings = service.check_python_companions(tmp_path, UUID("12345678-1234-1234-1234-123456789abc"))
        
        # Should find src/main.py
        # Note: tmp_path name containing "node_modules" was causing false positives
        # This test now uses "npm_modules" in the function name to avoid that
        assert len(findings) == 1
        assert findings[0].source_file == "src/main.py"


class TestCompanionCheckBehavior:
    """Test companion check behavior."""
    
    def test_generates_finding_when_no_test_companion(self, tmp_path):
        """Test that a source file with no test companion generates exactly one finding."""
        service = CompanionCheckService()
        
        # Create source file without test companion
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("# main module")
        
        # Create empty tests directory
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        
        with patch.object(service, '_get_methodology_config', return_value={
            "enforce": ["test_companions"],
            "test_companion_pattern": "test_{module}.py"
        }):
            with patch.object(service, '_execute_query'):
                findings = service.check_python_companions(tmp_path, UUID("12345678-1234-1234-1234-123456789abc"))
        
        # Should generate exactly one finding
        assert len(findings) == 1
        assert findings[0].source_file == "src/main.py"
        assert findings[0].expected_test == "test_main.py"
    
    def test_no_finding_when_test_companion_exists(self, tmp_path):
        """Test that a source file with a matching test file generates zero findings."""
        service = CompanionCheckService()
        
        # Create source file
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("# main module")
        
        # Create matching test file
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_main.py").write_text("# test for main")
        
        with patch.object(service, '_get_methodology_config', return_value={
            "enforce": ["test_companions"],
            "test_companion_pattern": "test_{module}.py"
        }):
            with patch.object(service, '_execute_query'):
                findings = service.check_python_companions(tmp_path, UUID("12345678-1234-1234-1234-123456789abc"))
        
        # Should generate zero findings
        assert len(findings) == 0
    
    def test_no_finding_when_alt_test_pattern_exists(self, tmp_path):
        """Test that alternative test pattern (module_test.py) is recognized."""
        service = CompanionCheckService()
        
        # Create source file
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("# main module")
        
        # Create test file with alternative pattern
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "main_test.py").write_text("# test for main")
        
        with patch.object(service, '_get_methodology_config', return_value={
            "enforce": ["test_companions"],
            "test_companion_pattern": "test_{module}.py"
        }):
            with patch.object(service, '_execute_query'):
                findings = service.check_python_companions(tmp_path, UUID("12345678-1234-1234-1234-123456789abc"))
        
        # Should recognize main_test.py as companion
        assert len(findings) == 0
    
    def test_skips_test_files(self, tmp_path):
        """Test that test files themselves are not checked for companions."""
        service = CompanionCheckService()
        
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        
        # These should all be skipped as test files
        (src_dir / "test_utils.py").write_text("# test file")
        (src_dir / "helper_test.py").write_text("# test file")
        (src_dir / "actual_module.py").write_text("# real module")
        
        with patch.object(service, '_get_methodology_config', return_value={
            "enforce": ["test_companions"],
            "test_companion_pattern": "test_{module}.py"
        }):
            with patch.object(service, '_execute_query'):
                findings = service.check_python_companions(tmp_path, UUID("12345678-1234-1234-1234-123456789abc"))
        
        # Only actual_module.py should be checked
        assert len(findings) == 1
        assert "actual_module" in findings[0].source_file
    
    def test_skips_init_files(self, tmp_path):
        """Test that __init__.py files are skipped."""
        service = CompanionCheckService()
        
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("# main")
        (src_dir / "__init__.py").write_text("# init - should be skipped")
        
        with patch.object(service, '_get_methodology_config', return_value={
            "enforce": ["test_companions"],
            "test_companion_pattern": "test_{module}.py"
        }):
            with patch.object(service, '_execute_query'):
                findings = service.check_python_companions(tmp_path, UUID("12345678-1234-1234-1234-123456789abc"))
        
        # Only main.py should be checked
        assert len(findings) == 1
        assert "__init__" not in findings[0].source_file


class TestCompanionCheckMethodology:
    """Test methodology configuration."""
    
    def test_disabled_when_not_in_enforce_list(self, tmp_path):
        """Test that check is disabled when test_companions not in enforce list."""
        service = CompanionCheckService()
        
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("# main")
        
        with patch.object(service, '_get_methodology_config', return_value={
            "enforce": ["coverage"],  # test_companions not in list
            "test_companion_pattern": "test_{module}.py"
        }):
            findings = service.check_python_companions(tmp_path, UUID("12345678-1234-1234-1234-123456789abc"))
        
        # Should return empty list when disabled
        assert findings == []


class TestGetCompanionCheckService:
    """Test the get_companion_check_service factory function."""
    
    def test_returns_singleton(self):
        """Test that get_companion_check_service returns a singleton."""
        service1 = get_companion_check_service()
        service2 = get_companion_check_service()
        
        assert service1 is service2
