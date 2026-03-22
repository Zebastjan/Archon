#!/usr/bin/env python3
"""Code repository sync status and operations."""

import os
import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Set environment before any imports
os.environ["ARCHON_DATABASE_URL"] = "postgresql://archon:archon_local_dev@localhost:5434/archon"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python"))

from src.server.services.database import get_database_connector, initialize_database, close_database


async def show_status():
    db = get_database_connector()
    
    print("\n" + "=" * 80)
    print("CODE REPOSITORY INDEX STATUS")
    print("=" * 80)
    
    repos = await db.fetch("SELECT id, name, local_path, updated_at FROM archon_code_repos ORDER BY name")
    
    total_entities = 0
    total_with_embeddings = 0
    total_with_docstrings = 0
    
    for repo in repos:
        stats = await db.fetchrow("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN embedding_1024 IS NOT NULL THEN 1 END) as with_embeddings,
                COUNT(CASE WHEN docstring IS NOT NULL AND docstring != '' THEN 1 END) as with_docstrings,
                COUNT(CASE WHEN source_code IS NOT NULL THEN 1 END) as with_source
            FROM archon_code_entities
            WHERE repo_id = $1
        """, repo['id'])
        
        total_entities += stats['total']
        total_with_embeddings += stats['with_embeddings']
        total_with_docstrings += stats['with_docstrings']
        
        embed_pct = 100 * stats['with_embeddings'] / max(stats['total'], 1)
        doc_pct = 100 * stats['with_docstrings'] / max(stats['total'], 1)
        
        # Status emoji
        if stats['with_embeddings'] == stats['total'] and stats['total'] > 0:
            status = "✅"
        elif stats['with_embeddings'] > 0:
            status = "⚠️"
        else:
            status = "❌"
        
        print(f"\n{status} {repo['name']}")
        print(f"   Path: {repo['local_path']}")
        print(f"   Entities: {stats['total']:,}")
        print(f"   Embeddings: {stats['with_embeddings']:,} ({embed_pct:.1f}%)")
        print(f"   Docstrings: {stats['with_docstrings']:,} ({doc_pct:.1f}%)")
        print(f"   Source stored: {stats['with_source']:,}")
        print(f"   Last updated: {repo['updated_at']}")
    
    # Overall summary
    print("\n" + "-" * 80)
    print("OVERALL SUMMARY")
    print("-" * 80)
    total_embed_pct = 100 * total_with_embeddings / max(total_entities, 1)
    total_doc_pct = 100 * total_with_docstrings / max(total_entities, 1)
    print(f"Total entities: {total_entities:,}")
    print(f"With embeddings: {total_with_embeddings:,} ({total_embed_pct:.1f}%)")
    print(f"With docstrings: {total_with_docstrings:,} ({total_doc_pct:.1f}%)")
    
    # Relationships
    rel_count = await db.fetchval("SELECT COUNT(*) FROM archon_code_relationships")
    print(f"Total relationships: {rel_count:,}")
    
    print("\n" + "=" * 80)
    if total_with_embeddings == 0:
        print("STATUS: ❌ EMBEDDINGS MISSING")
        print("=" * 80)
        print("\nThe index has entity extraction and relationships, but ZERO embeddings.")
        print("This means semantic search and similarity features will NOT work.")
        print("\nTo generate embeddings, you need to:")
        print("  1. Have Ollama running with an embedding model (e.g., bge-large)")
        print("  2. Run the embedding generation pipeline")
        print("  3. Set up automatic re-indexing on git commits")
    elif total_embed_pct < 100:
        print("STATUS: ⚠️ PARTIAL EMBEDDINGS")
        print("=" * 80)
        print(f"\nOnly {total_embed_pct:.1f}% of entities have embeddings.")
        print("Some semantic search features may not work properly.")
    else:
        print("STATUS: ✅ FULLY INDEXED")
        print("=" * 80)
        print("\nAll entities have embeddings and the index is complete!")
    print("=" * 80)


async def main():
    await initialize_database()
    try:
        await show_status()
    finally:
        await close_database()


if __name__ == "__main__":
    asyncio.run(main())
