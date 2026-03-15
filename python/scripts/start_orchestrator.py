#!/usr/bin/env python3
"""Start the Cephalosage Orchestrator service.

Usage:
    python scripts/start_orchestrator.py
    
Environment:
    ORCHESTRATOR_PORT: Port to run on (default: 8080)
    LOCAL_LLM_URL: URL of local LLM (default: http://localhost:11434)
    LOCAL_LLM_MODEL: Model name (default: llama3.2)
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.orchestrator.orchestrator_service import start_orchestrator

if __name__ == "__main__":
    print("=" * 60)
    print("Cephalosage Orchestrator Service")
    print("=" * 60)
    print()
    print("Configuration:")
    print("  - Service: Local orchestration for code audits")
    print("  - LLM Integration: Ollama-compatible API")
    print("  - Endpoints:")
    print("    * GET  /health - Health check")
    print("    * POST /orchestrator/repo_health_check - Orchestrated audit")
    print("    * POST /orchestrator/plan_refactors - Refactoring planner")
    print()
    print("Press Ctrl+C to stop")
    print("=" * 60)
    print()
    
    start_orchestrator()
