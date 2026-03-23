#!/usr/bin/env python3
"""
BGE-M3 Embedding Worker with Checkpointing and VRAM Management

Features:
- Uses BGE-M3 model (better than BGE-Large)
- Checkpointing: Saves progress every N embeddings
- VRAM-aware: Monitors GPU memory, pauses when low
- Single-worker: Won't crash Wayland
- Resume capability: Can restart from where it left off
- Batch processing: Configurable batch size
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

# Database setup
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python" / "src"))

# Configuration
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODEL_NAME = "bge-m3"  # Better than bge-large
BATCH_SIZE = 20  # Conservative for VRAM safety
CHECKPOINT_INTERVAL = 100  # Save progress every N entities
MIN_VRAM_GB = 3.0  # Keep at least 3GB free for Wayland/system
EMBEDDING_DIM = 1024  # BGE-M3 produces 1024-dim embeddings

CHECKPOINT_FILE = Path.home() / ".archon_embedding_checkpoint.json"


class VRAMMonitor:
    """Monitor GPU VRAM and pause when running low."""

    def __init__(self, min_vram_gb: float = MIN_VRAM_GB):
        self.min_vram_gb = min_vram_gb
        self.last_stats = None

    def get_stats(self) -> dict[str, Any]:
        """Get current GPU stats."""
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                parts = result.stdout.strip().split(",")
                total_mb = float(parts[2])
                used_mb = float(parts[1])
                free_mb = total_mb - used_mb

                stats = {
                    "utilization": float(parts[0]),
                    "memory_used_mb": used_mb,
                    "memory_total_mb": total_mb,
                    "memory_free_mb": free_mb,
                    "memory_free_gb": free_mb / 1024,
                    "temperature": float(parts[3]),
                }
                self.last_stats = stats
                return stats
        except Exception as e:
            print(f"  ⚠️  Could not get GPU stats: {e}")

        # Return safe defaults if nvidia-smi fails
        return {
            "utilization": 0,
            "memory_free_gb": 12.0,  # Assume plenty of VRAM
            "temperature": 40,
        }

    def is_safe_to_proceed(self) -> bool:
        """Check if we have enough VRAM to continue."""
        stats = self.get_stats()
        free_gb = stats.get("memory_free_gb", 0)

        if free_gb < self.min_vram_gb:
            print(f"\n⚠️  LOW VRAM: {free_gb:.1f}GB free (need {self.min_vram_gb}GB)")
            print("   Pausing to let system recover...")
            return False

        return True

    def wait_for_vram(self, timeout: int = 300):
        """Wait until VRAM is available."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            stats = self.get_stats()
            free_gb = stats.get("memory_free_gb", 0)

            if free_gb >= self.min_vram_gb:
                print(f"✓ VRAM recovered: {free_gb:.1f}GB free")
                return True

            print(f"  Waiting for VRAM... {free_gb:.1f}GB free")
            time.sleep(10)

        print("⚠️  Timeout waiting for VRAM")
        return False


class CheckpointManager:
    """Manage embedding progress checkpointing."""

    def __init__(self, checkpoint_file: Path = CHECKPOINT_FILE):
        self.checkpoint_file = checkpoint_file

    def save(
        self, processed_count: int, failed_count: int, last_entity_id: str | None = None
    ):
        """Save checkpoint."""
        checkpoint = {
            "processed": processed_count,
            "failed": failed_count,
            "last_entity_id": last_entity_id,
            "timestamp": datetime.now().isoformat(),
            "model": MODEL_NAME,
        }
        self.checkpoint_file.write_text(json.dumps(checkpoint, indent=2))

    def load(self) -> dict[str, Any]:
        """Load checkpoint."""
        if self.checkpoint_file.exists():
            try:
                return json.loads(self.checkpoint_file.read_text())
            except Exception as e:
                print(f"  ⚠️  Failed to load checkpoint: {e}")
        return {"processed": 0, "failed": 0, "last_entity_id": None}

    def clear(self):
        """Clear checkpoint after successful completion."""
        if self.checkpoint_file.exists():
            self.checkpoint_file.unlink()


async def get_ollama_embedding(
    text: str, client: httpx.AsyncClient
) -> list[float] | None:
    """Get embedding from Ollama BGE-M3."""
    try:
        response = await client.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": MODEL_NAME, "prompt": text[:4000]},
            timeout=60.0,
        )

        if response.status_code == 200:
            data = response.json()
            embedding = data.get("embedding")
            if embedding and len(embedding) == EMBEDDING_DIM:
                return embedding
        else:
            print(f"  ⚠️  Ollama returned {response.status_code}")
        return None
    except Exception as e:
        print(f"  ⚠️  Error getting embedding: {e}")
        return None


def prepare_entity_text(entity: dict) -> str:
    """Prepare text representation of entity for embedding."""
    parts = []

    if entity.get("docstring"):
        parts.append(entity["docstring"][:1000])

    if entity.get("signature"):
        parts.append(entity["signature"][:500])

    if entity.get("source_code"):
        parts.append(entity["source_code"][:1500])

    if not parts:
        parts.append(entity.get("name", "")[:200])

    return "\n".join(parts)


async def process_entities_with_checkpointing():
    """Main processing loop with checkpointing."""
    print("=" * 80)
    print(f"BGE-M3 EMBEDDING WORKER")
    print(f"Model: {MODEL_NAME} ({EMBEDDING_DIM} dimensions)")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 80)
    print()

    # Initialize components
    from server.services.database.db_connector import (
        get_database_connector,
        initialize_database,
    )

    vram_monitor = VRAMMonitor()
    checkpoint_mgr = CheckpointManager()

    # Load checkpoint
    checkpoint = checkpoint_mgr.load()
    already_processed = checkpoint.get("processed", 0)
    already_failed = checkpoint.get("failed", 0)
    last_entity_id = checkpoint.get("last_entity_id")

    if already_processed > 0:
        print(f"📋 Resuming from checkpoint: {already_processed} already processed")
        print()

    # Connect to database
    print("Connecting to database...")
    await initialize_database()
    db = get_database_connector()

    # Get total count
    total_result = await db.fetchrow("""
        SELECT COUNT(*) as total,
               COUNT(CASE WHEN embedding_1024 IS NOT NULL THEN 1 END) as done
        FROM archon_code_entities
    """)
    total = total_result["total"]
    done = total_result["done"]
    remaining = total - done

    print(f"Total entities: {total:,}")
    print(f"Already embedded: {done:,}")
    print(f"Remaining: {remaining:,}")
    print()

    if remaining == 0:
        print("✅ All entities already have embeddings!")
        checkpoint_mgr.clear()
        return

    # Check Ollama
    print("Checking Ollama...")
    async with httpx.AsyncClient() as check_client:
        try:
            resp = await check_client.get(f"{OLLAMA_URL}/api/tags", timeout=5.0)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                model_names = [m.get("name") for m in models]
                if MODEL_NAME in model_names:
                    print(f"  ✓ Ollama running with {MODEL_NAME}")
                else:
                    print(f"  ⚠️  {MODEL_NAME} not found in Ollama")
                    print(f"     Available: {', '.join(model_names[:5])}")
                    print(f"     Run: ollama pull {MODEL_NAME}")
                    return
            else:
                print(f"  ✗ Ollama returned {resp.status_code}")
                return
        except Exception as e:
            print(f"  ✗ Cannot connect to Ollama: {e}")
            return

    # Check VRAM
    print("\nChecking GPU...")
    stats = vram_monitor.get_stats()
    print(f"  Free VRAM: {stats['memory_free_gb']:.1f}GB")
    print(f"  Target: Keep {MIN_VRAM_GB}GB free for Wayland")
    print()

    if not vram_monitor.is_safe_to_proceed():
        print("⚠️  Not enough VRAM to start. Close other GPU apps or wait.")
        return

    # Process entities
    print(f"Processing {remaining} entities...")
    print(f"Batch size: {BATCH_SIZE}")
    print(f"Checkpoint every: {CHECKPOINT_INTERVAL} entities")
    print()

    processed_total = already_processed
    failed_total = already_failed
    batch_num = 0
    start_time = time.time()

    async with httpx.AsyncClient(timeout=60.0) as client:
        while True:
            batch_num += 1

            # Check VRAM before each batch
            if not vram_monitor.is_safe_to_proceed():
                # Save checkpoint before waiting
                checkpoint_mgr.save(processed_total, failed_total, last_entity_id)
                print(f"\n📋 Checkpoint saved: {processed_total} processed")

                if not vram_monitor.wait_for_vram():
                    print("⚠️  Could not recover VRAM. Stopping.")
                    break

            # Get next batch
            query = """
                SELECT id, name, signature, docstring, source_code
                FROM archon_code_entities
                WHERE embedding_1024 IS NULL
            """
            if last_entity_id:
                query += " AND id > $1 ORDER BY id LIMIT $2"
                entities = await db.fetch(query, last_entity_id, BATCH_SIZE)
            else:
                query += " ORDER BY id LIMIT $1"
                entities = await db.fetch(query, BATCH_SIZE)

            if not entities:
                print("\n✅ No more entities to process!")
                break

            # Process batch
            batch_start = time.time()
            succeeded = 0
            failed = 0

            for entity in entities:
                try:
                    text = prepare_entity_text(entity)
                    embedding = await get_ollama_embedding(text, client)

                    if embedding:
                        # Store in database
                        vector_str = "[" + ",".join(f"{x:.6f}" for x in embedding) + "]"
                        await db.execute(
                            """
                            UPDATE archon_code_entities
                            SET embedding_1024 = $1::vector,
                                embedding_model = $2,
                                embedding_dimension = $3,
                                updated_at = NOW()
                            WHERE id = $4
                        """,
                            vector_str,
                            MODEL_NAME,
                            EMBEDDING_DIM,
                            str(entity["id"]),
                        )
                        succeeded += 1
                    else:
                        failed += 1

                except Exception as e:
                    print(f"  ⚠️  Failed {entity['id'][:8]}: {e}")
                    failed += 1

                processed_total += 1
                last_entity_id = str(entity["id"])

            failed_total += failed
            batch_time = time.time() - batch_start

            # Progress report
            elapsed = time.time() - start_time
            rate = processed_total / elapsed if elapsed > 0 else 0
            eta = (
                (remaining - (processed_total - already_processed)) / rate
                if rate > 0
                else 0
            )

            print(
                f"Batch {batch_num}: {succeeded}✓ {failed}✗ | "
                f"Total: {processed_total:,} | Rate: {rate:.1f}/s | ETA: {eta / 3600:.1f}h"
            )

            # Checkpoint
            if processed_total % CHECKPOINT_INTERVAL < BATCH_SIZE:
                checkpoint_mgr.save(processed_total, failed_total, last_entity_id)
                print(f"  📋 Checkpoint saved")

            # Brief pause between batches
            await asyncio.sleep(0.5)

    # Final stats
    elapsed = time.time() - start_time
    print("\n" + "=" * 80)
    print("COMPLETE")
    print("=" * 80)
    print(f"Processed: {processed_total - already_processed:,} (new)")
    print(f"Total: {processed_total:,}")
    print(f"Failed: {failed_total}")
    print(f"Time: {elapsed / 3600:.1f} hours")
    print(f"Final rate: {(processed_total - already_processed) / elapsed:.1f} ent/s")
    print("=" * 80)

    # Clear checkpoint on success
    checkpoint_mgr.clear()


if __name__ == "__main__":
    try:
        asyncio.run(process_entities_with_checkpointing())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        print("Progress saved to checkpoint file. Run again to resume.")
        sys.exit(1)
