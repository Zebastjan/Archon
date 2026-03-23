#!/usr/bin/env python3
"""Generate BGE-M3 embeddings using Ollama with VRAM guard.

Features:
- Uses Ollama's bge-m3 model (GPU-accelerated)
- VRAM monitoring: pauses if <3GB free
- Batch processing for efficiency
- Progress tracking
"""

import asyncio
import httpx
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, "/app/src")

from src.server.services.database.db_connector import (
    get_database_connector,
    initialize_database,
)


OLLAMA_URL = "http://172.17.0.1:11434"
MODEL_NAME = "bge-m3"
BATCH_SIZE = 50
MIN_VRAM_MB = 3000  # Minimum free VRAM required


def get_free_gpu_memory_mb() -> int:
    """Get free GPU memory in MB."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return int(result.stdout.strip())
    except Exception:
        return 99999  # Assume plenty if can't check


async def generate_embedding(
    client: httpx.AsyncClient, text: str
) -> list[float] | None:
    """Generate embedding for a single text using Ollama."""
    try:
        response = await client.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": MODEL_NAME, "prompt": text},
            timeout=30.0,
        )
        if response.status_code == 200:
            return response.json().get("embedding")
    except Exception as e:
        print(f"Embedding error: {e}")
    return None


async def main():
    await initialize_database()
    db = get_database_connector()
    await db.initialize()

    print(f"Starting BGE-M3 embedding generation via Ollama")
    print(f"VRAM threshold: {MIN_VRAM_MB}MB")

    client = httpx.AsyncClient()
    total_processed = 0
    batch_num = 0

    try:
        while True:
            # Check VRAM before each batch
            free_vram = get_free_gpu_memory_mb()
            print(f"Free VRAM: {free_vram}MB")

            if free_vram < MIN_VRAM_MB:
                print(f"⚠️  Low VRAM ({free_vram}MB < {MIN_VRAM_MB}MB). Waiting 30s...")
                await asyncio.sleep(30)
                continue

            # Get entities without embeddings
            entities = await db.fetch(f"""
                SELECT id, name, signature, docstring, source_code
                FROM archon_code_entities 
                WHERE embedding_1024 IS NULL
                LIMIT {BATCH_SIZE}
            """)

            if not entities:
                print("✅ No more entities without embeddings!")
                break

            batch_num += 1
            texts = []
            ids = []

            for e in entities:
                txt = f"{e['name']} {e.get('signature', '')} {e.get('docstring', '')}"
                if e.get("source_code"):
                    txt += " " + e["source_code"][:500]
                texts.append(txt[:2000])
                ids.append(str(e["id"]))

            print(f"Batch {batch_num}: generating {len(texts)} embeddings...")

            # Generate embeddings
            embeddings = []
            for txt in texts:
                emb = await generate_embedding(client, txt)
                embeddings.append(emb)

            # Update database
            for entity_id, emb in zip(ids, embeddings):
                if emb:
                    emb_str = "[" + ",".join(str(x) for x in emb) + "]"
                    await db.execute(
                        """UPDATE archon_code_entities 
                           SET embedding_1024 = $1::vector, embedding_model = 'bge-m3', embedding_dimension = 1024
                           WHERE id = $2""",
                        emb_str,
                        entity_id,
                    )
                    total_processed += 1

            remaining = await db.fetchval(
                "SELECT COUNT(*) FROM archon_code_entities WHERE embedding_1024 IS NULL"
            )
            print(f"  Processed: {total_processed}, Remaining: {remaining}")

            # Check VRAM after batch
            free_after = get_free_gpu_memory_mb()
            if free_after < MIN_VRAM_MB:
                print(f"⚠️  VRAM low after batch ({free_after}MB). Pausing...")
                await asyncio.sleep(15)

    finally:
        await client.aclose()

    print(f"\n✅ Done! Total embeddings: {total_processed}")


if __name__ == "__main__":
    asyncio.run(main())
