#!/usr/bin/env python3
"""
Code Entity Embedding Generator v2 - Fixed for asyncpg
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime
import httpx

# Add path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python" / "src"))

from server.services.database.db_connector import get_database_connector, initialize_database

OLLAMA_URL = "http://localhost:11434"
EMBEDDING_MODEL = "bge-large"
BATCH_SIZE = 50


async def get_embedding(text: str, client: httpx.AsyncClient) -> list[float] | None:
    """Get embedding from Ollama."""
    try:
        response = await client.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": EMBEDDING_MODEL, "prompt": text[:4000]},
            timeout=60.0
        )
        
        if response.status_code == 200:
            data = response.json()
            embedding = data.get("embedding")
            if embedding and len(embedding) == 1024:
                return embedding
        return None
    except Exception as e:
        print(f"  Error: {e}")
        return None


async def prepare_text(entity: dict) -> str:
    """Prepare text for embedding."""
    parts = []
    if entity.get("docstring"):
        parts.append(entity["docstring"])
    if entity.get("signature"):
        parts.append(entity["signature"])
    if entity.get("source_code"):
        parts.append(entity["source_code"][:2000])
    if not parts:
        parts.append(entity.get("name", ""))
    return "\n".join(parts)


async def main():
    print("=" * 70)
    print("  ARCHON EMBEDDING GENERATOR v2")
    print("=" * 70)
    print(f"Started: {datetime.now().isoformat()}")
    print()
    
    # Connect to database
    print("Connecting...")
    await initialize_database()
    db = get_database_connector()
    
    # Check Ollama
    print("Checking Ollama...")
    async with httpx.AsyncClient() as check_client:
        try:
            resp = await check_client.get(f"{OLLAMA_URL}/api/tags", timeout=5.0)
            if resp.status_code == 200:
                print("  ✓ Ollama running")
            else:
                print(f"  ✗ Status {resp.status_code}")
                return 1
        except Exception as e:
            print(f"  ✗ Cannot connect: {e}")
            return 1
    
    # Get count
    result = await db.fetchrow("""
        SELECT COUNT(*) as total, 
               COUNT(CASE WHEN embedding_1024 IS NOT NULL THEN 1 END) as done
        FROM archon_code_entities
    """)
    
    total = result["total"]
    done = result["done"]
    remaining = total - done
    
    print(f"\nTotal: {total:,}")
    print(f"Done: {done:,}")
    print(f"Remaining: {remaining:,}")
    print()
    
    if remaining == 0:
        print("✅ All done!")
        return 0
    
    # Get entities to process
    entities = await db.fetch("""
        SELECT id, name, signature, docstring, source_code
        FROM archon_code_entities
        WHERE embedding_1024 IS NULL
        ORDER BY created_at
        LIMIT 100
    """)
    
    print(f"Processing {len(entities)} entities...")
    print()
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        for i, entity in enumerate(entities):
            text = await prepare_text(entity)
            embedding = await get_embedding(text, client)
            
            if embedding:
                # Use plain SQL with proper vector syntax
                vector_str = "[" + ",".join(str(x) for x in embedding) + "]"
                await db.execute(
                    "UPDATE archon_code_entities SET embedding_1024 = $1::vector, embedding_model = $2 WHERE id = $3",
                    vector_str, EMBEDDING_MODEL, str(entity["id"])
                )
                print(f"  {i+1}/{len(entities)} ✓ {entity['name'][:40]}")
            else:
                print(f"  {i+1}/{len(entities)} ✗ {entity['name'][:40]} (failed)")
            
            await asyncio.sleep(0.05)
    
    print("\n✅ Batch complete!")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted")
        sys.exit(1)
