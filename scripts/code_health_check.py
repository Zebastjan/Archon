#!/usr/bin/env python3
"""Quick health check for code intelligence system."""

import os
import sys
import asyncio
from pathlib import Path

# Force local database
os.environ["ARCHON_DATABASE_URL"] = "postgresql://archon:archon_local_dev@localhost:5434/archon"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python"))

import httpx
from src.server.services.database import get_database_connector, initialize_database, close_database


async def main():
    print("=" * 80)
    print("CODE INTELLIGENCE HEALTH CHECK")
    print("=" * 80)
    
    # Check Ollama
    print("\n1. Checking Ollama...")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://localhost:11434/api/tags", timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                models = [m["name"] for m in data.get("models", [])]
                embed_models = [m for m in models if "bge" in m.lower() or "embed" in m.lower()]
                if embed_models:
                    print(f"   ✅ Running - {len(embed_models)} embedding models available")
                else:
                    print(f"   ⚠️  Running but no embedding models found")
                    print(f"      Available: {', '.join(models[:3])}")
            else:
                print(f"   ❌ Returned status {resp.status_code}")
    except Exception as e:
        print(f"   ❌ Cannot connect: {e}")
    
    # Check Database
    print("\n2. Checking Database...")
    try:
        await initialize_database()
        db = get_database_connector()
        
        # Get stats
        stats = await db.fetchrow("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN embedding_1024 IS NOT NULL THEN 1 END) as with_emb
            FROM archon_code_entities
        """)
        
        total = stats['total']
        with_emb = stats['with_emb']
        pct = (with_emb / total * 100) if total > 0 else 0
        
        print(f"   ✅ Connected")
        print(f"   Entities: {total:,}")
        print(f"   Embeddings: {with_emb:,} ({pct:.1f}%)")
        
        if with_emb == 0:
            print(f"\n   ❌ CRITICAL: No embeddings generated!")
            print(f"      Semantic search will NOT work.")
        
        # Per-repo breakdown
        print("\n3. Per-Repository Status:")
        repos = await db.fetch("""
            SELECT r.name, 
                COUNT(e.id) as entities,
                COUNT(CASE WHEN e.embedding_1024 IS NOT NULL THEN 1 END) as embeddings
            FROM archon_code_repos r
            LEFT JOIN archon_code_entities e ON e.repo_id = r.id
            GROUP BY r.id, r.name
            ORDER BY r.name
        """)
        
        for repo in repos:
            pct = (repo['embeddings'] / repo['entities'] * 100) if repo['entities'] > 0 else 0
            status = "✅" if pct == 100 else "❌" if pct == 0 else "⚠️"
            print(f"   {status} {repo['name']:15} {repo['entities']:6,} entities, {pct:5.1f}% embedded")
        
        await close_database()
        
    except Exception as e:
        print(f"   ❌ Database error: {e}")
    
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS:")
    print("=" * 80)
    print("1. Generate embeddings: python scripts/generate_embeddings.py")
    print("2. Setup git hooks: ./scripts/setup_git_hooks.sh")
    print("3. Run full sync: ./scripts/full_code_sync.py")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
