#!/usr/bin/env python3
"""
Register all development repositories with code intelligence.

Usage:
    python scripts/register_all_repos.py

This will:
1. Register octofriend (with GitHub linking)
2. Register syllablaze (with GitHub linking)
3. Run ingestion for each
4. Generate BGE-large embeddings
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

from src.server.services.git_repo_manager import get_repo_manager

# Repository configurations
REPOS = [
    {
        "name": "octofriend",
        "local_path": "/home/zebastjan/dev/octofriend",
        "github_url": "https://github.com/zebastjan/octofriend",
    },
    {
        "name": "syllablaze",
        "local_path": "/home/zebastjan/dev/syllablaze",
        "github_url": "https://github.com/zebastjan/syllablaze",
    },
]


async def register_repo(manager, repo_config):
    """Register and ingest a single repository."""
    print(f"\n{'='*60}")
    print(f"Registering: {repo_config['name']}")
    print(f"{'='*60}")
    print(f"  Path: {repo_config['local_path']}")
    print(f"  GitHub: {repo_config['github_url']}")
    
    try:
        # Register with GitHub linking
        config = await manager.register_local_repo(
            local_path=repo_config["local_path"],
            name=repo_config["name"],
            github_url=repo_config["github_url"],
        )
        
        print(f"  Repo ID: {config.repo_id}")
        print(f"  ✓ Registered successfully")
        print(f"  ✓ Git hooks installed")
        
        # Run full ingestion
        print(f"\n  Running full ingestion...")
        result = await manager.full_reingest(config.repo_id)
        
        print(f"    Files: {result.get('files_processed', 0)}")
        print(f"    Entities: {result.get('entities_created', 0)}")
        print(f"    Relationships: {result.get('relationships_created', 0)}")
        
        # Generate embeddings
        print(f"\n  Generating BGE-large embeddings...")
        from src.server.services.embedding_service import generate_embeddings_for_repo
        
        emb_result = await generate_embeddings_for_repo(config.repo_id, 'bge-large')
        print(f"    Embedded: {emb_result['processed']} entities")
        
        return {
            "name": repo_config["name"],
            "repo_id": config.repo_id,
            "status": "success",
            "entities": result.get('entities_created', 0),
            "embeddings": emb_result['processed'],
        }
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return {
            "name": repo_config["name"],
            "status": "error",
            "error": str(e),
        }


async def main():
    print("=" * 60)
    print("Register All Repositories")
    print("=" * 60)
    print()
    print("This will register and ingest all development repositories")
    print("with BGE-large embeddings and GitHub linking.")
    print()
    
    manager = get_repo_manager()
    results = []
    
    for repo_config in REPOS:
        result = await register_repo(manager, repo_config)
        results.append(result)
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    for r in results:
        if r["status"] == "success":
            print(f"✓ {r['name']}: {r['entities']} entities, {r['embeddings']} embeddings")
        else:
            print(f"✗ {r['name']}: {r.get('error', 'unknown error')}")
    
    print()
    print("MCP tools are now available at: http://localhost:8051")
    print("Configure your IDE to use the Archon MCP server.")


if __name__ == "__main__":
    asyncio.run(main())
