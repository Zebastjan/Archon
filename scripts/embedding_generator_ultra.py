#!/usr/bin/env python3
"""
Ultra-Robust Embedding Generator - Aggressive Timeouts
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python" / "src"))

from server.services.database.db_connector import get_database_connector, initialize_database

OLLAMA_URL = "http://localhost:11434"
EMBEDDING_MODEL = "bge-large"
BATCH_SIZE = 50
TIMEOUT = 15  # Aggressive 15-second timeout


async def get_embedding(text: str, client: httpx.AsyncClient) -> list[float] | None:
    try:
        response = await client.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": EMBEDDING_MODEL, "prompt": text[:3000]},
            timeout=TIMEOUT
        )
        
        if response.status_code == 200:
            data = response.json()
            embedding = data.get("embedding")
            if embedding and len(embedding) == 1024:
                return embedding
        return None
    except httpx.TimeoutException:
        print(f"    ⚠️  Timeout")
        return None
    except Exception as e:
        print(f"    ⚠️  Error: {str(e)[:40]}")
        return None


async def main():
    print("=" * 70)
    print("  ULTRA-ROBUST EMBEDDING GENERATOR")
    print(f"  Timeout: {TIMEOUT}s per entity")
    print("=" * 70)
    print()
    
    await initialize_database()
    db = get_database_connector()
    
    result = await db.fetchrow("""
        SELECT COUNT(*) as total, 
               COUNT(CASE WHEN embedding_1024 IS NOT NULL THEN 1 END) as done
        FROM archon_code_entities
    """)
    
    total, done = result["total"], result["done"]
    print(f"Total: {total:,} | Done: {done:,} | Remaining: {total-done:,}")
    print()
    
    processed = 0
    succeeded = 0
    failed = 0
    start = datetime.now()
    
    async with httpx.AsyncClient(timeout=TIMEOUT + 5) as client:
        while True:
            entities = await db.fetch(f"""
                SELECT id, name, signature, docstring, source_code
                FROM archon_code_entities
                WHERE embedding_1024 IS NULL
                ORDER BY created_at
                LIMIT {BATCH_SIZE}
            """)
            
            if not entities:
                break
            
            print(f"Batch ({len(entities)} entities)...")
            
            for i, entity in enumerate(entities, 1):
                name = entity.get("name", "unknown")[:50]
                print(f"  {i}/{len(entities)} {name}...", end=" ", flush=True)
                
                # Prepare text (shorter to avoid timeouts)
                parts = []
                if entity.get("docstring"):
                    parts.append(entity["docstring"][:800])
                if entity.get("signature"):
                    parts.append(entity["signature"][:400])
                if entity.get("source_code"):
                    parts.append(entity["source_code"][:1200])
                if not parts:
                    parts.append(entity.get("name", "")[:150])
                
                text = "\n".join(parts)
                
                # Get embedding with timeout
                embedding = await get_embedding(text, client)
                
                if embedding:
                    try:
                        vector_str = "[" + ",".join(f"{x:.6f}" for x in embedding) + "]"
                        await db.execute(
                            "UPDATE archon_code_entities SET embedding_1024 = $1::vector, embedding_model = $2 WHERE id = $3",
                            vector_str, EMBEDDING_MODEL, str(entity["id"])
                        )
                        print("✓")
                        succeeded += 1
                    except Exception as e:
                        print(f"✗ DB: {str(e)[:30]}")
                        failed += 1
                else:
                    print("✗ (timeout/error)")
                    failed += 1
                
                processed += 1
            
            # Batch summary
            elapsed = (datetime.now() - start).total_seconds()
            rate = processed / elapsed if elapsed > 0 else 0
            print(f"  Batch: {succeeded}✓ {failed}✗ | Rate: {rate:.1f} ent/s | Total: {processed}")
            print()
    
    print(f"\n✅ Done! {succeeded}✓ {failed}✗ in {(datetime.now()-start).total_seconds()/3600:.1f}h")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted")
