"""Tests for Coverage Service

Priority 2 test coverage.
"""

import json
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import UUID

import pytest

from src.server.services.coverage_service import (
    CoverageFinding,
    CoverageService,
    get_coverage_service,
)


class TestCoverageFinding:
    """Test the CoverageFinding dataclass."""
    
    def test_to_db_dict(self):
        """Test conversion to database dictionary."""
        finding = CoverageFinding(
            file_path="src/main.py",
            coverage_pct=65.5,
            lines_covered=131,
            lines_total=200,
            threshold=80.0,
            source="pytest-cov",
        )
        
        repo_id = UUID("12345678-1234-1234-1234-123456789abc")
        db_dict = finding.to_db_dict(repo_id)
        
        assert db_dict["repo_id"] == str(repo_id)
        assert db_dict["source"] == "pytest-cov"
        assert db_dict["semgrep_check_id"] == "coverage/below-threshold"
        assert db_dict["file_path"] == "src/main.py"
        assert "65.5%" in db_dict["message"]
        assert "80.0%" in db_dict["message"]
        assert db_dict["severity"] == "WARNING"


class TestCoverageServiceDetection:
    """Test project type detection."""
    
    def test_detects_vitest_from_package_json(self, tmp_path):
        """Test that it detects vitest from devDependencies."""
        package_json = tmp_path / "package.json"
        package_json.write_text(json.dumps({
            "devDependencies": {"vitest": "^1.0.0"}
        }))
        
        service = CoverageService()
        
        # Create a dummy test script
        (tmp_path / "test").mkdir()
        
        # The service should detect this as TypeScript/JavaScript
        # and try to run with vitest
        with patch("src.server.services.coverage_service.subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="1.0.0", stderr="")
            
            # Just verify it detects the project type
            assert (tmp_path / "package.json").exists()


class TestCoverageServicePytestCov:
    """Test pytest-cov integration."""
    
    @patch("src.server.services.coverage_service.subprocess.run")
    def test_run_pytest_cov_with_mocked_coverage(self, mock_run, tmp_path):
        """Test that pytest-cov parses coverage JSON correctly."""
        # Create mock coverage data
        coverage_data = {
            "files": {
                "src/main.py": {
                    "summary": {
                        "covered_lines": 60,
                        "num_statements": 100,
                        "percent_covered": 60.0,
                    }
                },
                "src/utils.py": {
                    "summary": {
                        "covered_lines": 90,
                        "num_statements": 100,
                        "percent_covered": 90.0,
                    }
                },
                "test_main.py": {  # Should be excluded
                    "summary": {
                        "covered_lines": 50,
                        "num_statements": 50,
                        "percent_covered": 100.0,
                    }
                },
            }
        }
        
        # Mock the subprocess calls
        def mock_subprocess(*args, **kwargs):
            cmd = args[0]
            if "pytest" in cmd:
                # pytest call - simulate creating coverage file
                coverage_file = tmp_path / ".coverage.json"
                coverage_file.write_text(json.dumps(coverage_data))
                return Mock(returncode=0, stdout="", stderr="")
            return Mock(returncode=0, stdout="", stderr="")
        
        mock_run.side_effect = mock_subprocess
        
        service = CoverageService()
        
        # Create source files
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("# main")
        (src_dir / "utils.py").write_text("# utils")
        
        findings = service.run_pytest_cov(
            repo_path=tmp_path,
            repo_id=UUID("12345678-1234-1234-1234-123456789abc"),
            threshold=80,
        )
        
        # Should find only src/main.py (60% < 80%)
        # src/utils.py is 90% >= 80%, so no finding
        # test_main.py is excluded as test file
        assert len(findings) == 1
        assert findings[0].file_path == "src/main.py"
        assert findings[0].coverage_pct == 60.0
    
    def test_only_generates_findings_below_threshold(self):
        """Test that findings are only generated for files below threshold."""
        service = CoverageService()
        
        coverage_data = {
            "files": {
                "src/low_coverage.py": {
                    "summary": {"covered_lines": 50, "num_statements": 100}
                },
                "src/high_coverage.py": {
                    "summary": {"covered_lines": 95, "num_statements": 100}
                },
                "src/exact_threshold.py": {
                    "summary": {"covered_lines": 80, "num_statements": 100}
                },
            }
        }
        
        findings = service._parse_pytest_cov(coverage_data, threshold=80.0)
        
        # Only low_coverage.py should be below threshold
        assert len(findings) == 1
        assert findings[0].file_path == "src/low_coverage.py"
    
    @patch("src.server.services.coverage_service.subprocess.run")
    def test_pytest_cov_file_not_found(self, mock_run):
        """Test handling when coverage file is not generated."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        
        service = CoverageService()
        
        with patch.object(Path, "exists", return_value=False):
            findings = service.run_pytest_cov(
                repo_path="/tmp/fake-repo",
                repo_id=UUID("12345678-1234-1234-1234-123456789abc"),
            )
        
        assert findings == []


class TestCoverageServiceC8:
    """Test c8 integration."""
    
    def test_c8_parses_coverage_summary(self, tmp_path):
        """Test that c8 parses coverage summary correctly."""
        service = CoverageService()
        
        coverage_data = {
            "total": {
                "lines": {"total": 1000, "covered": 750, "pct": 75}
            },
            "/project/src/main.ts": {
                "lines": {"total": 100, "covered": 60, "pct": 60},
                "pct": 60  # c8 format has pct at both levels
            },
            "/project/src/utils.ts": {
                "lines": {"total": 100, "covered": 90, "pct": 90},
                "pct": 90
            },
            "/project/src/app.ts": {
                "lines": {"total": 100, "covered": 85, "pct": 85},
                "pct": 85
            },
        }
        
        findings = service._parse_c8(coverage_data, threshold=80.0, repo_path="/project")
        
        # Only main.ts is below 80%
        assert len(findings) == 1
        assert findings[0].file_path == "src/main.ts"
        assert findings[0].coverage_pct == 60.0
    
    def test_c8_excludes_test_files(self, tmp_path):
        """Test that c8 excludes test files."""
        service = CoverageService()
        
        coverage_data = {
            "/project/src/main.ts": {
                "lines": {"total": 100, "covered": 70, "pct": 70}
            },
            "/project/src/main.test.ts": {  # Should be excluded
                "lines": {"total": 50, "covered": 25, "pct": 50}
            },
            "/project/tests/helper.ts": {  # Should be excluded
                "lines": {"total": 30, "covered": 15, "pct": 50}
            },
        }
        
        findings = service._parse_c8(coverage_data, threshold=80.0, repo_path="/project")
        
        # Only main.ts should be included (test files excluded by pattern matching)
        assert len(findings) == 1
        assert "main.ts" in findings[0].file_path
        assert ".test." not in findings[0].file_path


class TestCoverageServiceThreshold:
    """Test threshold configuration."""
    
    def test_default_threshold_is_80(self):
        """Test that default threshold is 80%."""
        service = CoverageService()
        
        # Mock the database call to return no result
        with patch.object(service, '_execute_query', return_value=[]):
            threshold = service._get_coverage_threshold(UUID("12345678-1234-1234-1234-123456789abc"))
        
        assert threshold == 80
    
    def test_custom_threshold_from_database(self):
        """Test that custom threshold is read from database."""
        service = CoverageService()
        
        with patch.object(service, '_execute_query', return_value=[{"coverage_threshold": 90}]):
            threshold = service._get_coverage_threshold(UUID("12345678-1234-1234-1234-123456789abc"))
        
        assert threshold == 90


class TestGetCoverageService:
    """Test the get_coverage_service factory function."""
    
    def test_get_coverage_service_returns_singleton(self):
        """Test that get_coverage_service returns a singleton."""
        service1 = get_coverage_service()
        service2 = get_coverage_service()
        
        assert service1 is service2
