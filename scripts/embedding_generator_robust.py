#!/usr/bin/env python3
"""
Robust Embedding Generator with Timeouts and Resume Support
"""

import asyncio
import os
import sys
import signal
import time
from pathlib import Path
from datetime import datetime
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python" / "src"))

from server.services.database.db_connector import get_database_connector, initialize_database

OLLAMA_URL = "http://localhost:11434"
EMBEDDING_MODEL = "bge-large"
BATCH_SIZE = 75  # Smaller batches for reliability
TIMEOUT_SECONDS = 30  # Per-entity timeout

def signal_handler(signum, frame):
    print("\n⚠️  Interrupted - saving progress...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


async def get_embedding_with_timeout(text: str, client: httpx.AsyncClient) -> list[float] | None:
    """Get embedding with strict timeout."""
    try:
        response = await client.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": EMBEDDING_MODEL, "prompt": text[:3000]},  # Shorter text
            timeout=TIMEOUT_SECONDS
        )
        
        if response.status_code == 200:
            data = response.json()
            embedding = data.get("embedding")
            if embedding and len(embedding) == 1024:
                return embedding
        return None
    except httpx.TimeoutError:
        print(f"    ⚠️  Timeout after {TIMEOUT_SECONDS}s")
        return None
    except Exception as e:
        print(f"    ⚠️  Error: {str(e)[:50]}")
        return None


async def process_entity(entity: dict, db, client: httpx.AsyncClient) -> bool:
    """Process a single entity with error handling."""
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
        embedding = await get_embedding_with_timeout(text, client)
        
        if embedding:
            # Store with proper vector format
            vector_str = "[" + ",".join(f"{x:.6f}" for x in embedding) + "]"
            await db.execute(
                "UPDATE archon_code_entities SET embedding_1024 = $1::vector, embedding_model = $2 WHERE id = $3",
                vector_str, EMBEDDING_MODEL, str(entity["id"])
            )
            return True
        else:
            # Mark as failed (set a placeholder to skip next time)
            await db.execute(
                "UPDATE archon_code_entities SET embedding_model = 'failed' WHERE id = $1",
                str(entity["id"])
            )
            return False
            
    except Exception as e:
        print(f"    ✗ Exception: {str(e)[:60]}")
        return False


async def main():
    print("=" * 70)
    print("  ROBUST EMBEDDING GENERATOR")
    print("=" * 70)
    print(f"Started: {datetime.now().isoformat()}")
    print(f"Batch size: {BATCH_SIZE}")
    print(f"Timeout: {TIMEOUT_SECONDS}s per entity")
    print()
    
    # Connect
    print("Connecting to database...")
    await initialize_database()
    db = get_database_connector()
    
    # Check Ollama
    print("Checking Ollama...")
    try:
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{OLLAMA_URL}/api/tags", timeout=5)
            if r.status_code == 200:
                print("  ✓ Ollama running")
            else:
                print(f"  ✗ Status {r.status_code}")
                return 1
    except Exception as e:
        print(f"  ✗ Cannot connect: {e}")
        return 1
    
    # Get stats
    result = await db.fetchrow("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN embedding_1024 IS NOT NULL THEN 1 END) as done,
            COUNT(CASE WHEN embedding_model = 'failed' THEN 1 END) as failed
        FROM archon_code_entities
    """)
    
    total = result["total"]
    done = result["done"]
    failed = result["failed"]
    remaining = total - done - failed
    
    print(f"\nTotal: {total:,}")
    print(f"Done: {done:,} ({100*done/total:.1f}%)")
    print(f"Failed: {failed:,}")
    print(f"Remaining: {remaining:,}")
    print()
    
    if remaining == 0:
        print("✅ All complete!")
        return 0
    
    # Process loop
    total_processed = 0
    batch_num = 0
    start_time = time.time()
    
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS + 5) as client:
        while True:
            batch_num += 1
            
            # Get next batch (entities without embeddings and not marked failed)
            entities = await db.fetch("""
                SELECT id, name, signature, docstring, source_code
                FROM archon_code_entities
                WHERE embedding_1024 IS NULL AND (embedding_model IS NULL OR embedding_model != 'failed')
                ORDER BY created_at
                LIMIT $1
            """, BATCH_SIZE)
            
            if not entities:
                print("\n✅ No more entities to process!")
                break
            
            print(f"\n📦 Batch {batch_num} ({len(entities)} entities)...")
            
            # Process with individual progress
            batch_success = 0
            batch_fail = 0
            
            for i, entity in enumerate(entities, 1):
                name = entity.get("name", "unknown")[:40]
                print(f"  {i}/{len(entities)} {name}...", end=" ", flush=True)
                
                success = await process_entity(entity, db, client)
                
                if success:
                    batch_success += 1
                    print("✓")
                else:
                    batch_fail += 1
                    print("✗")
                
                total_processed += 1
                
                # Brief pause between entities
                await asyncio.sleep(0.05)
            
            # Batch summary
            elapsed = time.time() - start_time
            rate = total_processed / elapsed if elapsed > 0 else 0
            print(f"  Batch complete: {batch_success} ✓, {batch_fail} ✗ | "
                  f"Total: {total_processed} | Rate: {rate:.1f} ent/s")
            
            # Checkpoint every 10 batches
            if batch_num % 10 == 0:
                print(f"\n💾 Checkpoint at {datetime.now().strftime('%H:%M:%S')}")
    
    # Final stats
    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print("COMPLETE")
    print("=" * 70)
    print(f"Processed: {total_processed}")
    print(f"Time: {elapsed/3600:.1f} hours")
    print(f"Rate: {total_processed/elapsed:.1f} ent/s")
    print("=" * 70)
    
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted - progress saved")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n💥 Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
