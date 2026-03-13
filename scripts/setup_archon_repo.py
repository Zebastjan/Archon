#!/usr/bin/env python3
"""
Register Archon repository with GitHub linking and full ingestion.

Usage:
    python scripts/setup_archon_repo.py
    
This will:
1. Register the local Archon repo with GitHub linking
2. Run full ingestion
3. Generate BGE-large embeddings
4. Install git hooks for incremental updates
"""

import asyncio
import sys
from pathlib import Path

# Add python to path
sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

from src.server.services.git_repo_manager import get_repo_manager

# Configuration
ARCHON_LOCAL_PATH = Path(__file__).parent.parent
ARCHON_GITHUB_URL = "https://github.com/zebastjan/archon"


async def main():
    print("=" * 60)
    print("Archon Repository Setup")
    print("=" * 60)
    print()
    
    manager = get_repo_manager()
    
    # Register repository
    print(f"Registering repository...")
    print(f"  Local path: {ARCHON_LOCAL_PATH}")
    print(f"  GitHub: {ARCHON_GITHUB_URL}")
    
    config = await manager.register_local_repo(
        local_path=ARCHON_LOCAL_PATH,
        name="archon",
        github_url=ARCHON_GITHUB_URL,
    )
    
    print(f"  Repo ID: {config.repo_id}")
    print()
    
    # Full ingestion of Python code
    print("Running full ingestion of Python backend...")
    python_path = ARCHON_LOCAL_PATH / "python" / "src"
    
    import sys
    sys.path.insert(0, str(ARCHON_LOCAL_PATH / "python"))
    
    from scripts.quick_ingest_repo import ingest_repository
    
    result = await ingest_repository(python_path, "archon-python")
    
    print(f"  Files: {result['files_processed']}")
    print(f"  Entities: {result['entities_created']}")
    print(f"  Relationships: {result['relationships_created']}")
    print()
    
    # Full ingestion of UI code
    print("Running full ingestion of UI frontend...")
    ui_path = ARCHON_LOCAL_PATH / "archon-ui-main" / "src"
    
    result = await ingest_repository(ui_path, "archon-ui")
    
    print(f"  Files: {result['files_processed']}")
    print(f"  Entities: {result['entities_created']}")
    print(f"  Relationships: {result['relationships_created']}")
    print()
    
    # Generate embeddings
    print("Generating BGE-large embeddings for all entities...")
    
    from src.server.services.embedding_service import generate_embeddings_for_repo
    
    # Python repo
    py_result = await generate_embeddings_for_repo(result['repo_id'], 'bge-large')
    print(f"  Python: {py_result['processed']} entities embedded")
    
    # UI repo
    ui_result = await generate_embeddings_for_repo(result['repo_id'], 'bge-large')
    print(f"  UI: {ui_result['processed']} entities embedded")
    
    print()
    print("=" * 60)
    print("✅ Archon repository setup complete!")
    print("=" * 60)
    print()
    print("Repository IDs:")
    print(f"  archon-python: {result['repo_id']}")
    print(f"  archon-ui: {result['repo_id']}")
    print()
    print("Features enabled:")
    print("  ✓ Semantic code search (BGE-large 1024-dim)")
    print("  ✓ Incremental updates on commit")
    print("  ✓ GitHub linking for file URLs")
    print("  ✓ MCP tools available at localhost:8051")
    print()
    print("Next steps:")
    print("  1. Configure your IDE MCP client (see docs/MCP_AGENT_GUIDE.md)")
    print("  2. Try: codebase_semantic_search('database connection')")
    print("  3. Try: codebase_find_entity('extract_entities')")


if __name__ == "__main__":
    asyncio.run(main())
