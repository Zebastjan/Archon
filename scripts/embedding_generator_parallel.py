#!/usr/bin/env python3
"""
Parallel GPU Embedding Generator

Uses multiple concurrent workers to maximize GPU throughput.
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

# Parallel settings
BATCH_SIZE = 75  # Larger batches for GPU efficiency
MAX_CONCURRENT = 4  # Number of parallel workers
TIMEOUT = 60


async def get_embedding(text: str, client: httpx.AsyncClient) -> list[float] | None:
    """Get embedding from Ollama."""
    try:
        response = await client.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": EMBEDDING_MODEL, "prompt": text[:4000]},
            timeout=TIMEOUT
        )
        
        if response.status_code == 200:
            data = response.json()
            embedding = data.get("embedding")
            if embedding and len(embedding) == 1024:
                return embedding
        return None
    except:
        return None


async def process_entity(entity: dict, db, client: httpx.AsyncClient, sem: asyncio.Semaphore) -> bool:
    """Process a single entity with semaphore for concurrency control."""
    async with sem:
        try:
            # Prepare text
            parts = []
            if entity.get("docstring"):
                parts.append(entity["docstring"][:1000])
            if entity.get("signature"):
                parts.append(entity["signature"][:500])
            if entity.get("source_code"):
                parts.append(entity["source_code"][:1500])
            if not parts:
                parts.append(entity.get("name", "")[:200])
            
            text = "\n".join(parts)
            
            # Get embedding
            embedding = await get_embedding(text, client)
            
            if embedding:
                vector_str = "[" + ",".join(f"{x:.6f}" for x in embedding) + "]"
                await db.execute(
                    "UPDATE archon_code_entities SET embedding_1024 = $1::vector, embedding_model = $2 WHERE id = $3",
                    vector_str, EMBEDDING_MODEL, str(entity["id"])
                )
                return True
            return False
            
        except Exception as e:
            return False


async def process_batch_parallel(entities: list, db, client: httpx.AsyncClient, max_concurrent: int) -> tuple[int, int]:
    """Process batch with parallel workers."""
    sem = asyncio.Semaphore(max_concurrent)
    
    tasks = [process_entity(entity, db, client, sem) for entity in entities]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    succeeded = sum(1 for r in results if r is True)
    failed = len(results) - succeeded
    
    return succeeded, failed


async def main():
    print("=" * 70)
    print(f"  PARALLEL GPU EMBEDDING GENERATOR ({MAX_CONCURRENT} workers)")
    print("=" * 70)
    print(f"Started: {datetime.now().isoformat()}")
    print(f"Batch size: {BATCH_SIZE}")
    print(f"Max concurrent: {MAX_CONCURRENT}")
    print()
    
    # Initialize
    await initialize_database()
    db = get_database_connector()
    
    # Get stats
    result = await db.fetchrow("""
        SELECT COUNT(*) as total, 
               COUNT(CASE WHEN embedding_1024 IS NOT NULL THEN 1 END) as done
        FROM archon_code_entities
    """)
    
    total, done = result["total"], result["done"]
    remaining = total - done
    
    print(f"Total: {total:,}")
    print(f"Done: {done:,} ({100*done/total:.1f}%)")
    print(f"Remaining: {remaining:,}")
    print()
    
    if remaining == 0:
        print("✅ All done!")
        return 0
    
    # Process with parallel workers
    total_processed = 0
    batch_num = 0
    start_time = datetime.now()
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        while True:
            batch_num += 1
            
            # Get batch
            entities = await db.fetch(f"""
                SELECT id, name, signature, docstring, source_code
                FROM archon_code_entities
                WHERE embedding_1024 IS NULL
                ORDER BY created_at
                LIMIT {BATCH_SIZE}
            """)
            
            if not entities:
                print("\n✅ No more entities!")
                break
            
            print(f"\n📦 Batch {batch_num} ({len(entities)} entities, {MAX_CONCURRENT} parallel workers)...")
            
            batch_start = datetime.now()
            succeeded, failed = await process_batch_parallel(entities, db, client, MAX_CONCURRENT)
            batch_time = (datetime.now() - batch_start).total_seconds()
            
            total_processed += len(entities)
            
            # Stats
            elapsed = (datetime.now() - start_time).total_seconds()
            rate = total_processed / elapsed if elapsed > 0 else 0
            
            print(f"  ✓ {succeeded} ✓, {failed} ✗ in {batch_time:.1f}s | "
                  f"Rate: {rate:.1f} ent/s | Processed: {total_processed}")
    
    # Final
    elapsed = (datetime.now() - start_time).total_seconds()
    print("\n" + "=" * 70)
    print("COMPLETE")
    print("=" * 70)
    print(f"Processed: {total_processed}")
    print(f"Time: {elapsed/3600:.1f} hours")
    print(f"Final rate: {total_processed/elapsed:.1f} ent/s")
    print("=" * 70)
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted")
        sys.exit(1)
