"""Integration tests for code audit and metrics system.

Tests the code metrics calculation and audit rule enforcement.
"""

import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4

pytestmark = pytest.mark.integration

from src.mcp_server.features.code_audit.code_audit_tools import register_code_audit_tools
from src.server.services.code_metrics_service import (
    CodeMetricsService,
    CodeMetrics,
    AuditFinding,
)


@pytest.fixture
def mock_supabase():
    """Create a mock Supabase client."""
    mock = MagicMock()
    mock.table = MagicMock(return_value=mock)
    mock.select = MagicMock(return_value=mock)
    mock.eq = MagicMock(return_value=mock)
    mock.execute = MagicMock(return_value=MagicMock(data=[]))
    mock.rpc = MagicMock(return_value=mock)
    return mock


@pytest.fixture
def mock_mcp():
    """Create a mock MCP server."""
    mock = MagicMock()
    mock._tools = {}
    
    def tool_decorator():
        def decorator(func):
            mock._tools[func.__name__] = func
            return func
        return decorator
    
    mock.tool = tool_decorator
    return mock


class TestCodeAuditToolsRegistration:
    """Tests for code audit tool registration."""
    
    def test_all_code_audit_tools_registered(self, mock_mcp):
        """Verify all code audit tools are registered."""
        register_code_audit_tools(mock_mcp)
        
        expected_tools = [
            "code_audit_calculate_metrics",
            "code_audit_run",
            "code_audit_get_findings",
            "code_audit_get_summary",
            "code_audit_get_rules",
            "code_audit_acknowledge_finding",
            "code_audit_analyze_entity",
        ]
        
        for tool_name in expected_tools:
            assert tool_name in mock_mcp._tools, f"Tool {tool_name} not registered"
    
    def test_tools_are_callable(self, mock_mcp):
        """Verify registered tools are callable."""
        register_code_audit_tools(mock_mcp)
        
        for tool_name, tool_func in mock_mcp._tools.items():
            assert callable(tool_func), f"Tool {tool_name} is not callable"


class TestCodeMetricsCalculation:
    """Tests for code metrics calculation."""
    
    def test_cyclomatic_complexity_calculation(self):
        """Test cyclomatic complexity calculation."""
        service = CodeMetricsService()
        
        # Simple function - complexity should be 1
        simple_code = "def simple():\n    return 1"
        complexity = service.calculate_cyclomatic_complexity(simple_code, "python")
        assert complexity >= 1
        
        # Function with one if - complexity should be at least 2
        if_code = "def with_if(x):\n    if x:\n        return 1\n    return 0"
        complexity = service.calculate_cyclomatic_complexity(if_code, "python")
        assert complexity >= 2
        
        # Function with multiple branches - higher complexity
        complex_code = """
def complex_func(x, y):
    if x > 0:
        if y > 0:
            return 1
        else:
            return 2
    elif x < 0:
        return 3
    else:
        return 4
"""
        complexity = service.calculate_cyclomatic_complexity(complex_code, "python")
        assert complexity > 3
    
    def test_line_counting(self):
        """Test line counting functionality."""
        service = CodeMetricsService()
        
        code = """def example():
    # This is a comment
    x = 1  # inline comment
    
    if x:
        return x
"""
        code_lines, comment_lines, blank_lines = service.count_lines(code)
        
        assert code_lines > 0
        assert comment_lines >= 1
        assert blank_lines >= 1
    
    def test_todo_fixme_counting(self):
        """Test TODO/FIXME counting."""
        service = CodeMetricsService()
        
        code = """
# TODO: Fix this
# FIXME: Refactor needed
def example():
    pass
"""
        todos, fixmes = service.count_todos_and_fixmes(code)
        
        assert todos >= 1
        assert fixmes >= 1
    
    def test_health_score_calculation(self):
        """Test health score calculation."""
        service = CodeMetricsService()
        
        # Good code metrics
        good_metrics = CodeMetrics(
            avg_cyclomatic_complexity=5,
            avg_function_length=20,
            code_to_comment_ratio=5,
            todo_count=0,
            fixme_count=0,
            max_cyclomatic_complexity=10,
        )
        good_score = service._calculate_health_score(good_metrics)
        assert good_score >= 70
        
        # Bad code metrics
        bad_metrics = CodeMetrics(
            avg_cyclomatic_complexity=20,
            avg_function_length=100,
            code_to_comment_ratio=50,
            todo_count=10,
            fixme_count=5,
            max_cyclomatic_complexity=50,
        )
        bad_score = service._calculate_health_score(bad_metrics)
        assert bad_score < 50
    
    def test_language_detection(self):
        """Test language detection from file paths."""
        service = CodeMetricsService()
        
        assert service._detect_language("test.py") == "python"
        assert service._detect_language("test.js") == "javascript"
        assert service._detect_language("test.ts") == "typescript"
        assert service._detect_language("test.tsx") == "typescript"
        assert service._detect_language("test.go") == "go"
        assert service._detect_language("test.rs") == "rust"
        assert service._detect_language("README.md") == "unknown"


class TestCodeMetricsIntegration:
    """Integration tests for metrics calculation."""
    
    @pytest.mark.asyncio
    async def test_calculate_metrics_tool(self, mock_mcp, mock_supabase):
        """Test the calculate metrics MCP tool."""
        register_code_audit_tools(mock_mcp)
        
        with patch("src.mcp_server.features.code_audit.code_audit_tools.get_code_metrics_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.calculate_repo_metrics = MagicMock(return_value=CodeMetrics(
                total_files=10,
                total_lines_of_code=1000,
                health_score=85,
            ))
            mock_get_service.return_value = mock_service
            
            tool = mock_mcp._tools.get("code_audit_calculate_metrics")
            result = await tool(repo_id=str(uuid4()))
            
            assert result["success"] is True
            assert result["metrics"]["total_files"] == 10
            assert result["metrics"]["health_score"] == 85
    
    @pytest.mark.asyncio
    async def test_run_audit_tool(self, mock_mcp, mock_supabase):
        """Test the run audit MCP tool."""
        register_code_audit_tools(mock_mcp)
        
        with patch("src.mcp_server.features.code_audit.code_audit_tools.get_code_metrics_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.run_audit = MagicMock(return_value=(5, uuid4()))
            mock_get_service.return_value = mock_service
            
            tool = mock_mcp._tools.get("code_audit_run")
            result = await tool(repo_id=str(uuid4()))
            
            assert result["success"] is True
            assert result["findings_count"] == 5
            assert result["audit_run_id"] is not None
    
    @pytest.mark.asyncio
    async def test_get_findings_tool(self, mock_mcp, mock_supabase):
        """Test the get findings MCP tool."""
        register_code_audit_tools(mock_mcp)
        
        with patch("src.mcp_server.features.code_audit.code_audit_tools.get_code_metrics_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_audit_findings = MagicMock(return_value=[
                AuditFinding(
                    rule_id="complexity-high",
                    severity="warning",
                    message="Function too complex",
                    file_path="src/test.py",
                    line_start=10,
                )
            ])
            mock_get_service.return_value = mock_service
            
            tool = mock_mcp._tools.get("code_audit_get_findings")
            result = await tool(repo_id=str(uuid4()), status="open")
            
            assert result["success"] is True
            assert result["count"] == 1
            assert result["findings"][0]["rule_id"] == "complexity-high"
    
    @pytest.mark.asyncio
    async def test_acknowledge_finding_tool(self, mock_mcp, mock_supabase):
        """Test the acknowledge finding MCP tool."""
        register_code_audit_tools(mock_mcp)
        
        with patch("src.mcp_server.features.code_audit.code_audit_tools.get_code_metrics_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.acknowledge_finding = MagicMock(return_value=True)
            mock_get_service.return_value = mock_service
            
            tool = mock_mcp._tools.get("code_audit_acknowledge_finding")
            result = await tool(
                finding_id=str(uuid4()),
                resolution_note="Fixed",
                mark_resolved=True
            )
            
            assert result["success"] is True
            assert result["status"] == "resolved"
    
    @pytest.mark.asyncio
    async def test_get_rules_tool(self, mock_mcp, mock_supabase):
        """Test the get rules MCP tool."""
        register_code_audit_tools(mock_mcp)
        
        from src.server.services.code_metrics_service import AuditRule
        
        with patch("src.mcp_server.features.code_audit.code_audit_tools.get_code_metrics_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_audit_rules = MagicMock(return_value=[
                AuditRule(
                    rule_id="complexity-high",
                    name="High Cyclomatic Complexity",
                    category="complexity",
                    severity="warning",
                )
            ])
            mock_get_service.return_value = mock_service
            
            tool = mock_mcp._tools.get("code_audit_get_rules")
            result = await tool(category="complexity")
            
            assert result["success"] is True
            assert result["count"] == 1
            assert result["rules"][0]["rule_id"] == "complexity-high"


class TestAuditFindingDataStructures:
    """Tests for audit finding data structures."""
    
    def test_audit_finding_creation(self):
        """Test creating audit findings."""
        finding = AuditFinding(
            rule_id="test-rule",
            severity="error",
            message="Test message",
            file_path="test.py",
            line_start=10,
            line_end=20,
        )
        
        assert finding.rule_id == "test-rule"
        assert finding.severity == "error"
        assert finding.to_dict()["line_start"] == 10
    
    def test_code_metrics_serialization(self):
        """Test CodeMetrics serialization."""
        metrics = CodeMetrics(
            total_files=100,
            health_score=85,
            avg_cyclomatic_complexity=5.5,
        )
        
        data = metrics.to_dict()
        assert data["total_files"] == 100
        assert data["health_score"] == 85
        assert data["avg_cyclomatic_complexity"] == 5.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
