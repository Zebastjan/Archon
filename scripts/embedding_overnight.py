#!/usr/bin/env python3
"""
Overnight Embedding Generator - Simple & Robust

- Uses BGE-M3 (1024-dim, high quality)
- Resumes automatically where left off
- Memory-safe batch processing
- Logs progress every 1000 entities
- Won't crash the system
"""

import asyncio
import os
import sys
import time
import signal
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python" / "src"))

import asyncpg
import httpx

# Configuration - SIMPLE and SAFE
OLLAMA_URL = "http://localhost:11434"
MODEL = "bge-m3"
BATCH_SIZE = 32  # Safe batch size for RTX 3060
CHECKPOINT_EVERY = 1000  # Log progress every 1000
MAX_RETRIES = 3
RETRY_DELAY = 5

# Database config from environment
DB_HOST = os.getenv("ARCHON_DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("ARCHON_DB_PORT", "5434"))
DB_USER = os.getenv("ARCHON_DB_USER", "archon")
DB_PASS = os.getenv("ARCHON_DB_PASSWORD", "archon_local_dev")
DB_NAME = os.getenv("ARCHON_DB_NAME", "archon")

DSN = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Graceful shutdown flag
shutdown_requested = False


def handle_signal(sig, frame):
    global shutdown_requested
    print(f"\n[{datetime.now().isoformat()}] Shutdown requested, finishing current batch...")
    shutdown_requested = True


signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)


async def get_embedding_batch(texts: list[str], client: httpx.AsyncClient) -> list[list[float] | None]:
    """Get embeddings for a batch of texts."""
    embeddings = []

    for text in texts:
        if shutdown_requested:
            embeddings.append(None)
            continue

        for attempt in range(MAX_RETRIES):
            try:
                response = await client.post(
                    f"{OLLAMA_URL}/api/embeddings",
                    json={"model": MODEL, "prompt": text[:4000]},
                    timeout=60.0
                )

                if response.status_code == 200:
                    data = response.json()
                    emb = data.get("embedding")
                    if emb and len(emb) >= 1024:
                        embeddings.append(emb[:1024])  # Take first 1024 dims
                        break
                else:
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(RETRY_DELAY)
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY)
        else:
            embeddings.append(None)

    return embeddings


def prepare_text(entity: dict) -> str:
    """Prepare entity text for embedding."""
    parts = []

    # Most important: name and signature
    if entity.get("name"):
        parts.append(f"Name: {entity['name']}")

    if entity.get("signature"):
        parts.append(f"Signature: {entity['signature'][:500]}")

    if entity.get("docstring"):
        parts.append(f"Docs: {entity['docstring'][:800]}")

    if entity.get("source_code"):
        parts.append(f"Code: {entity['source_code'][:1200]}")

    if not parts:
        parts.append(entity.get("name", "unknown"))

    return "\n".join(parts)


async def main():
    print("=" * 70)
    print("  OVERNIGHT EMBEDDING GENERATOR")
    print("=" * 70)
    print(f"Started: {datetime.now().isoformat()}")
    print(f"Model: {MODEL}")
    print(f"Database: {DB_HOST}:{DB_PORT}/{DB_NAME}")
    print(f"Batch size: {BATCH_SIZE}")
    print()

    # Connect to database
    print("Connecting to database...")
    conn = await asyncpg.connect(DSN)
    print("Connected!")

    # Get counts
    row = await conn.fetchrow("""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN embedding_1024 IS NOT NULL THEN 1 END) as done
        FROM archon_code_entities
    """)

    total = row["total"]
    done = row["done"]
    remaining = total - done

    print(f"Total entities: {total:,}")
    print(f"Already done: {done:,} ({100*done/total:.1f}%)")
    print(f"Remaining: {remaining:,}")
    print()

    if remaining == 0:
        print("✅ Nothing to do! All entities have embeddings.")
        await conn.close()
        return 0

    # Main processing loop
    processed = 0
    failed = 0
    start_time = time.time()
    last_checkpoint = done

    print(f"Starting processing... (Press Ctrl+C to stop gracefully)")
    print()

    async with httpx.AsyncClient(timeout=120.0) as client:
        while not shutdown_requested:
            # Get batch
            rows = await conn.fetch(f"""
                SELECT id, name, signature, docstring, source_code
                FROM archon_code_entities
                WHERE embedding_1024 IS NULL
                ORDER BY created_at
                LIMIT {BATCH_SIZE}
            """)

            if not rows:
                print("\n✅ All done! No more entities to process.")
                break

            # Prepare texts
            texts = [prepare_text(dict(r)) for r in rows]
            ids = [str(r["id"]) for r in rows]

            # Get embeddings
            embeddings = await get_embedding_batch(texts, client)

            # Update database
            for entity_id, emb in zip(ids, embeddings):
                if emb:
                    try:
                        vector_str = "[" + ",".join(f"{x:.6f}" for x in emb) + "]"
                        await conn.execute(
                            """UPDATE archon_code_entities
                               SET embedding_1024 = $1::vector,
                                   embedding_model = $2,
                                   updated_at = NOW()
                               WHERE id = $3""",
                            vector_str, MODEL, entity_id
                        )
                        processed += 1
                    except Exception as e:
                        print(f"  DB error: {e}")
                        failed += 1
                else:
                    failed += 1

            # Progress report
            current_done = done + processed
            if current_done - last_checkpoint >= CHECKPOINT_EVERY:
                elapsed = time.time() - start_time
                rate = processed / elapsed if elapsed > 0 else 0
                pct = 100 * current_done / total
                eta_hours = (remaining - processed) / rate / 3600 if rate > 0 else 0

                print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                      f"Progress: {current_done:,}/{total:,} ({pct:.1f}%) | "
                      f"Rate: {rate:.1f}/s | "
                      f"ETA: {eta_hours:.1f}h | "
                      f"Failed: {failed}")

                last_checkpoint = current_done

            # Brief pause to let system breathe
            await asyncio.sleep(0.1)

    # Final stats
    elapsed = time.time() - start_time
    print()
    print("=" * 70)
    print("  COMPLETE")
    print("=" * 70)
    print(f"Processed this session: {processed:,}")
    print(f"Failed: {failed:,}")
    print(f"Time: {elapsed/3600:.1f} hours")
    print(f"Final rate: {processed/elapsed:.1f} ent/s" if elapsed > 0 else "N/A")
    print(f"Ended: {datetime.now().isoformat()}")
    print("=" * 70)

    await conn.close()
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Stopped by user (will resume on restart)")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n💥 Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
