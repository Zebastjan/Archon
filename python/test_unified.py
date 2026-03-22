#!/usr/bin/env python3
"""
Quick test of the unified server - no HTTP, direct imports.
"""

import asyncio
import sys
sys.path.insert(0, ".")

async def test_config():
    """Test configuration loading."""
    print("=" * 60)
    print("Testing Configuration")
    print("=" * 60)
    
    try:
        from src.server.config.yaml_config import load_config, get_db_dsn
        
        config = load_config()
        print(f"✓ Config loaded")
        print(f"  Server port: {config.server.port}")
        print(f"  Database: {config.database.name}")
        print(f"  User: {config.database.user}")
        print(f"  DSN: {get_db_dsn()}")
        return True
    except Exception as e:
        print(f"✗ Config error: {e}")
        return False


async def test_services():
    """Test service imports."""
    print()
    print("=" * 60)
    print("Testing Service Imports")
    print("=" * 60)
    
    tests = []
    
    try:
        from src.server.services.projects.project_service import ProjectService
        service = ProjectService()
        print("✓ ProjectService imported")
        tests.append(True)
    except Exception as e:
        print(f"✗ ProjectService: {e}")
        tests.append(False)
    
    try:
        from src.server.services.search.rag_service import RAGService
        service = RAGService()
        print("✓ RAGService imported")
        tests.append(True)
    except Exception as e:
        print(f"✗ RAGService: {e}")
        tests.append(False)
    
    try:
        from src.server.services.code_metrics_service import get_code_metrics_service
        service = get_code_metrics_service()
        print("✓ CodeMetricsService imported")
        tests.append(True)
    except Exception as e:
        print(f"✗ CodeMetricsService: {e}")
        tests.append(False)
    
    return all(tests)


async def test_mcp_tools():
    """Test MCP tool registration."""
    print()
    print("=" * 60)
    print("Testing MCP Tool Registration")
    print("=" * 60)
    
    try:
        from mcp.server.fastmcp import FastMCP
        from src.mcp_server.features.projects.project_tools import register_project_tools
        from src.mcp_server.features.rag.rag_tools import register_rag_tools
        from src.mcp_server.features.code_audit.code_audit_tools import register_code_audit_tools
        
        mcp = FastMCP("test")
        
        register_project_tools(mcp)
        print("✓ Project tools registered")
        
        register_rag_tools(mcp)
        print("✓ RAG tools registered")
        
        register_code_audit_tools(mcp)
        print("✓ Code audit tools registered")
        
        tools = mcp._tools if hasattr(mcp, '_tools') else mcp._tool_manager._tools
        print(f"\n  Total tools registered: {len(tools)}")
        for name in sorted(tools.keys()):
            print(f"    - {name}")
        
        return True
    except Exception as e:
        print(f"✗ MCP tools error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_unified_app():
    """Test unified app creation."""
    print()
    print("=" * 60)
    print("Testing Unified App Creation")
    print("=" * 60)
    
    try:
        from src.unified_main import app, mcp
        
        print("✓ FastAPI app created")
        print(f"  Routes: {len(app.routes)}")
        
        print("✓ MCP server created")
        # Get tool count safely
        tool_count = len(mcp._tools) if hasattr(mcp, '_tools') else 'N/A'
        print(f"  MCP tools: {tool_count}")
        
        return True
    except Exception as e:
        print(f"✗ Unified app error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Archon Unified Server Tests")
    print("=" * 60)
    
    results = []
    
    results.append(("Config", await test_config()))
    results.append(("Service Imports", await test_services()))
    results.append(("MCP Tools", await test_mcp_tools()))
    results.append(("Unified App", await test_unified_app()))
    
    print()
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {name}")
    
    all_passed = all(r[1] for r in results)
    
    print()
    if all_passed:
        print("All tests passed!")
        return 0
    else:
        print("Some tests failed.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
