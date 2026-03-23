#!/usr/bin/env python3
"""
Fast Overnight Embedding Generator - Auto-Optimizing

- Dynamic batch sizing based on GPU memory
- Concurrent processing within batches  
- Batches DB updates
- Target: 50-100+ ent/sec on RTX 3060
"""

import asyncio
import os
import sys
import time
import signal
import subprocess
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python" / "src"))

import asyncpg
import httpx

# Configuration
OLLAMA_URL = "http://localhost:11434"
MODEL = "bge-m3"
TARGET_GPU_UTIL = 75  # Target GPU utilization %
MAX_RETRIES = 3
CHECKPOINT_EVERY = 5000

# Dynamic settings (will adjust)
CURRENT_BATCH_SIZE = 64
CONCURRENT_REQUESTS = 8  # Parallel embedding requests

shutdown_requested = False


def get_gpu_memory():
    """Get free GPU memory in MB."""
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.free,memory.total,utilization.gpu',
             '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(',')
            free_mb = float(parts[0])
            total_mb = float(parts[1])
            util = float(parts[2])
            return free_mb, total_mb, util
    except:
        pass
    return 8000, 12000, 50  # Safe defaults


def optimize_batch_size(free_mb, util):
    """Adjust batch size based on available VRAM and utilization."""
    global CURRENT_BATCH_SIZE, CONCURRENT_REQUESTS

    # BGE-M3 uses ~1.5GB at batch 64
    # Scale based on free memory with headroom
    usable_mb = free_mb - 1500  # Keep 1.5GB headroom

    if usable_mb > 6000:
        new_batch = 128
        new_concurrent = 16
    elif usable_mb > 4000:
        new_batch = 96
        new_concurrent = 12
    elif usable_mb > 2500:
        new_batch = 64
        new_concurrent = 8
    else:
        new_batch = 32
        new_concurrent = 4

    # Adjust based on utilization
    if util > 90:
        new_batch = max(32, new_batch // 2)
        new_concurrent = max(4, CONCURRENT_REQUESTS // 2)
    elif util < 50 and free_mb > 4000:
        new_batch = min(128, int(new_batch * 1.2))

    changed = (new_batch != CURRENT_BATCH_SIZE)
    CURRENT_BATCH_SIZE = new_batch
    CONCURRENT_REQUESTS = new_concurrent
    return changed


def handle_signal(sig, frame):
    global shutdown_requested
    print(f"\n[{datetime.now().isoformat()}] Finishing current batch...")
    shutdown_requested = True


signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)


async def get_embedding_single(text: str, client: httpx.AsyncClient, sem: asyncio.Semaphore) -> list[float] | None:
    """Get single embedding with semaphore control."""
    async with sem:
        for attempt in range(MAX_RETRIES):
            try:
                response = await client.post(
                    f"{OLLAMA_URL}/api/embeddings",
                    json={"model": MODEL, "prompt": text[:4000]},
                    timeout=30.0
                )
                if response.status_code == 200:
                    data = response.json()
                    emb = data.get("embedding")
                    if emb and len(emb) >= 1024:
                        return emb[:1024]
            except Exception:
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))
        return None


def prepare_text(entity: dict) -> str:
    """Prepare text for embedding."""
    parts = []
    if entity.get("name"):
        parts.append(f"Name: {entity['name']}")
    if entity.get("signature"):
        parts.append(f"Sig: {entity['signature'][:400]}")
    if entity.get("docstring"):
        parts.append(f"Doc: {entity['docstring'][:600]}")
    if entity.get("source_code"):
        parts.append(f"Code: {entity['source_code'][:1000]}")
    return "\n".join(parts) if parts else entity.get("name", "unknown")


async def process_batch(rows: list, conn: asyncpg.Connection, client: httpx.AsyncClient) -> tuple[int, int]:
    """Process a batch with concurrent requests."""
    texts = [prepare_text(dict(r)) for r in rows]
    ids = [str(r["id"]) for r in rows]

    sem = asyncio.Semaphore(CONCURRENT_REQUESTS)

    # Get embeddings concurrently
    tasks = [get_embedding_single(text, client, sem) for text in texts]
    embeddings = await asyncio.gather(*tasks, return_exceptions=True)

    # Prepare DB updates
    updates = []
    failed = 0

    for eid, emb in zip(ids, embeddings):
        if isinstance(emb, Exception) or emb is None:
            failed += 1
            continue

        vector_str = "[" + ",".join(f"{x:.6f}" for x in emb) + "]"
        updates.append((vector_str, MODEL, eid))

    # Batch update
    if updates:
        try:
            await conn.executemany(
                """UPDATE archon_code_entities
                   SET embedding_1024 = $1::vector,
                       embedding_model = $2,
                       updated_at = NOW()
                   WHERE id = $3""",
                updates
            )
        except Exception as e:
            print(f"  DB batch error: {e}")
            failed += len(updates)
            return 0, len(updates)

    return len(updates), failed


async def main():
    print("=" * 70)
    print("  FAST EMBEDDING GENERATOR - AUTO-OPTIMIZING")
    print("=" * 70)
    print(f"Started: {datetime.now().isoformat()}")
    print(f"Model: {MODEL}")
    print()

    # Check GPU
    free_mb, total_mb, util = get_gpu_memory()
    print(f"GPU: {free_mb:.0f}MB free / {total_mb:.0f}MB total ({util:.0f}% util)")
    optimize_batch_size(free_mb, util)
    print(f"Initial settings: batch={CURRENT_BATCH_SIZE}, concurrent={CONCURRENT_REQUESTS}")
    print()

    # Connect DB
    DB_HOST = os.getenv("ARCHON_DB_HOST", "127.0.0.1")
    DB_PORT = os.getenv("ARCHON_DB_PORT", "5434")
    DB_PASS = os.getenv("ARCHON_DB_PASSWORD", "archon_local_dev")
    DSN = f"postgresql://archon:{DB_PASS}@{DB_HOST}:{DB_PORT}/archon"

    conn = await asyncpg.connect(DSN)
    print("Connected to database")

    # Get counts
    row = await conn.fetchrow("""
        SELECT COUNT(*) as total,
               COUNT(CASE WHEN embedding_1024 IS NOT NULL THEN 1 END) as done
        FROM archon_code_entities
    """)

    total, done = row["total"], row["done"]
    remaining = total - done

    print(f"Total: {total:,} | Done: {done:,} | Remaining: {remaining:,}")
    print()

    if remaining == 0:
        print("✅ All done!")
        await conn.close()
        return 0

    # Main loop
    processed = 0
    failed_total = 0
    batch_num = 0
    start_time = time.time()
    last_optimize = start_time
    last_checkpoint = done

    print(f"Starting... (Ctrl+C to stop gracefully)")
    print()

    async with httpx.AsyncClient(timeout=60.0, limits=httpx.Limits(max_connections=20)) as client:
        while not shutdown_requested:
            batch_num += 1

            # Re-optimize every 60 seconds
            now = time.time()
            if now - last_optimize > 60:
                free_mb, total_mb, util = get_gpu_memory()
                changed = optimize_batch_size(free_mb, util)
                if changed:
                    print(f"\n  [GPU] {free_mb:.0f}MB free, {util:.0f}% util -> batch={CURRENT_BATCH_SIZE}, concurrent={CONCURRENT_REQUESTS}\n")
                last_optimize = now

            # Fetch batch
            rows = await conn.fetch(f"""
                SELECT id, name, signature, docstring, source_code
                FROM archon_code_entities
                WHERE embedding_1024 IS NULL
                ORDER BY created_at
                LIMIT {CURRENT_BATCH_SIZE}
            """)

            if not rows:
                print("\n✅ Complete! No more entities.")
                break

            # Process batch
            batch_start = time.time()
            succeeded, failed = await process_batch(rows, conn, client)
            batch_time = time.time() - batch_start

            processed += succeeded
            failed_total += failed

            # Progress report
            current_done = done + processed
            if current_done - last_checkpoint >= CHECKPOINT_EVERY or batch_num <= 3:
                elapsed = time.time() - start_time
                rate = processed / elapsed if elapsed > 0 else 0
                pct = 100 * current_done / total
                eta_hours = (remaining - processed) / rate / 3600 if rate > 0 else 0

                print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                      f"{current_done:,}/{total:,} ({pct:.1f}%) | "
                      f"Rate: {rate:.1f}/s | ETA: {eta_hours:.1f}h | "
                      f"Batch: {batch_time:.1f}s | Failed: {failed_total}")

                last_checkpoint = current_done

    # Final stats
    elapsed = time.time() - start_time
    print()
    print("=" * 70)
    print("  DONE")
    print("=" * 70)
    print(f"Processed: {processed:,}")
    print(f"Failed: {failed_total:,}")
    print(f"Time: {elapsed/3600:.1f}h")
    print(f"Avg rate: {processed/elapsed:.1f}/s" if elapsed > 0 else "N/A")
    print(f"Ended: {datetime.now().isoformat()}")

    await conn.close()
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nStopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
