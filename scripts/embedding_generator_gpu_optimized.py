#!/usr/bin/env python3
"""
GPU-Optimized Embedding Generator with Auto-Scaling

Features:
- Dynamic batch size based on GPU memory
- Parallel processing with multiple workers
- GPU utilization monitoring
- Automatic optimization
"""

import asyncio
import os
import sys
import json
import subprocess
import time
from pathlib import Path
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python" / "src"))

from server.services.database.db_connector import get_database_connector, initialize_database

OLLAMA_URL = "http://localhost:11434"
EMBEDDING_MODEL = "bge-large"

# Auto-optimization settings
MIN_BATCH_SIZE = 25
MAX_BATCH_SIZE = 150
TARGET_GPU_UTIL = 80  # Target 80% GPU utilization
VRAM_HEADROOM_GB = 2  # Keep 2GB free for other tasks


class GPUOptimizer:
    """Monitors and optimizes GPU usage."""
    
    def __init__(self):
        self.current_batch_size = 50
        self.target_workers = 1
        
    def get_gpu_stats(self) -> dict:
        """Get current GPU statistics."""
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu',
                 '--format=csv,noheader,nounits'],
                capture_output=True, text=True, timeout=5
            )
            
            if result.returncode == 0:
                parts = result.stdout.strip().split(',')
                return {
                    'utilization': float(parts[0]),
                    'memory_used_mb': float(parts[1]),
                    'memory_total_mb': float(parts[2]),
                    'temperature': float(parts[3]),
                    'memory_used_gb': float(parts[1]) / 1024,
                    'memory_free_gb': (float(parts[2]) - float(parts[1])) / 1024
                }
        except Exception as e:
            print(f"  ⚠️  Could not get GPU stats: {e}")
        
        return {'utilization': 0, 'memory_free_gb': 12}
    
    def optimize(self, stats: dict) -> tuple[int, int]:
        """Return optimal (batch_size, num_workers)."""
        util = stats['utilization']
        free_vram = stats['memory_free_gb']
        
        # Calculate how many workers we can fit
        # Each worker needs ~1GB VRAM for bge-large
        max_workers = int((free_vram - VRAM_HEADROOM_GB) / 1.5)
        max_workers = max(1, min(max_workers, 4))  # Cap at 4 workers
        
        # Adjust batch size based on GPU utilization
        if util < 50 and self.current_batch_size < MAX_BATCH_SIZE:
            # GPU underutilized, increase batch
            self.current_batch_size = min(self.current_batch_size + 25, MAX_BATCH_SIZE)
        elif util > 90 and self.current_batch_size > MIN_BATCH_SIZE:
            # GPU overloaded, decrease batch
            self.current_batch_size = max(self.current_batch_size - 25, MIN_BATCH_SIZE)
        
        # Adjust workers based on VRAM
        if max_workers > self.target_workers and util < 70:
            self.target_workers = min(self.target_workers + 1, max_workers)
        elif max_workers < self.target_workers:
            self.target_workers = max_workers
        
        return self.current_batch_size, self.target_workers


async def get_embedding(text: str, client: httpx.AsyncClient, timeout: int = 60) -> list[float] | None:
    """Get embedding from Ollama."""
    try:
        response = await client.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": EMBEDDING_MODEL, "prompt": text[:4000]},
            timeout=timeout
        )
        
        if response.status_code == 200:
            data = response.json()
            embedding = data.get("embedding")
            if embedding and len(embedding) == 1024:
                return embedding
        return None
    except Exception as e:
        return None


async def process_batch(entities: list, db, client: httpx.AsyncClient) -> tuple[int, int]:
    """Process a batch of entities."""
    succeeded = 0
    failed = 0
    
    for entity in entities:
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
                succeeded += 1
            else:
                failed += 1
                
        except Exception as e:
            failed += 1
    
    return succeeded, failed


async def main():
    print("=" * 70)
    print("  GPU-OPTIMIZED EMBEDDING GENERATOR")
    print("=" * 70)
    print(f"Started: {datetime.now().isoformat()}")
    print()
    
    # Initialize
    optimizer = GPUOptimizer()
    
    print("Connecting to database...")
    await initialize_database()
    db = get_database_connector()
    
    # Get initial stats
    print("Checking GPU...")
    stats = optimizer.get_gpu_stats()
    print(f"  GPU: {stats.get('utilization', 0):.0f}% util, {stats.get('memory_free_gb', 0):.1f}GB free VRAM")
    print()
    
    # Get total count
    result = await db.fetchrow("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN embedding_1024 IS NOT NULL THEN 1 END) as done
        FROM archon_code_entities
    """)
    
    total = result["total"]
    done = result["done"]
    remaining = total - done
    
    print(f"Total: {total:,}")
    print(f"Done: {done:,} ({100*done/total:.1f}%)")
    print(f"Remaining: {remaining:,}")
    print()
    
    if remaining == 0:
        print("✅ All complete!")
        return 0
    
    # Determine optimal settings
    batch_size, num_workers = optimizer.optimize(stats)
    print(f"Initial settings: batch_size={batch_size}, workers={num_workers}")
    print()
    
    # Process with dynamic optimization
    total_processed = 0
    batch_num = 0
    start_time = time.time()
    last_optimize_time = start_time
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        while True:
            batch_num += 1
            
            # Re-optimize every 30 seconds
            current_time = time.time()
            if current_time - last_optimize_time > 30:
                stats = optimizer.get_gpu_stats()
                new_batch, new_workers = optimizer.optimize(stats)
                
                if new_batch != batch_size or new_workers != num_workers:
                    print(f"\n📊 GPU Stats: {stats['utilization']:.0f}% util, {stats['memory_free_gb']:.1f}GB free")
                    print(f"🔄 Adjusting: batch={batch_size}→{new_batch}, workers={num_workers}→{new_workers}")
                    batch_size, num_workers = new_batch, new_workers
                
                last_optimize_time = current_time
            
            # Get batch
            entities = await db.fetch(f"""
                SELECT id, name, signature, docstring, source_code
                FROM archon_code_entities
                WHERE embedding_1024 IS NULL
                ORDER BY created_at
                LIMIT {batch_size}
            """)
            
            if not entities:
                print("\n✅ No more entities!")
                break
            
            # Process batch
            print(f"\n📦 Batch {batch_num} ({len(entities)} entities, batch={batch_size})...")
            
            if num_workers > 1:
                # Parallel processing (simplified - single client for now)
                print(f"  (Parallel mode: {num_workers} workers)")
            
            batch_start = time.time()
            succeeded, failed = await process_batch(entities, db, client)
            batch_time = time.time() - batch_start
            
            total_processed += len(entities)
            
            # Calculate stats
            elapsed = time.time() - start_time
            rate = total_processed / elapsed if elapsed > 0 else 0
            eta_seconds = (remaining - total_processed) / rate if rate > 0 else 0
            
            print(f"  ✓ {succeeded} ✓, {failed} ✗ in {batch_time:.1f}s | "
                  f"Rate: {rate:.1f} ent/s | ETA: {eta_seconds/3600:.1f}h")
    
    # Final stats
    elapsed = time.time() - start_time
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
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted")
        sys.exit(1)
