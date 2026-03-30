#!/usr/bin/env python3
"""
Fast GPU Embedding Generator - Sequential but with large batches
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python" / "src"))

from server.services.database.db_connector import (
    get_database_connector,
    initialize_database,
)

OLLAMA_URL = "http://localhost:11434"
EMBEDDING_MODEL = "bge-large"
BATCH_SIZE = 100  # Larger batches for GPU efficiency


async def get_embedding(text: str, client: httpx.AsyncClient) -> list[float] | None:
    try:
        response = await client.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": EMBEDDING_MODEL, "prompt": text[:4000]},
            timeout=60.0,
        )

        if response.status_code == 200:
            data = response.json()
            embedding = data.get("embedding")
            if embedding and len(embedding) == 1024:
                return embedding
        return None
    except (httpx.HTTPError, json.JSONDecodeError):
        return None


async def main():
    print("=" * 70)
    print("  FAST GPU EMBEDDING GENERATOR")
    print("=" * 70)
    print(f"Batch size: {BATCH_SIZE}")
    print()

    await initialize_database()
    db = get_database_connector()

    result = await db.fetchrow("""
        SELECT COUNT(*) as total, 
               COUNT(CASE WHEN embedding_1024 IS NOT NULL THEN 1 END) as done
        FROM archon_code_entities
    """)

    total, done = result["total"], result["done"]
    print(f"Total: {total:,} | Done: {done:,} | Remaining: {total - done:,}")
    print()

    if total - done == 0:
        print("✅ Complete!")
        return

    processed = 0
    start = datetime.now()

    async with httpx.AsyncClient(timeout=120.0) as client:
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

            print(f"Processing {len(entities)} entities...", end=" ", flush=True)

            batch_start = datetime.now()
            succeeded = 0

            for entity in entities:
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
                embedding = await get_embedding(text, client)

                if embedding:
                    vector_str = "[" + ",".join(f"{x:.6f}" for x in embedding) + "]"
                    await db.execute(
                        "UPDATE archon_code_entities SET embedding_1024 = $1::vector, embedding_model = $2 WHERE id = $3",
                        vector_str,
                        EMBEDDING_MODEL,
                        str(entity["id"]),
                    )
                    succeeded += 1

            processed += len(entities)
            elapsed = (datetime.now() - start).total_seconds()
            rate = processed / elapsed if elapsed > 0 else 0

            print(
                f"✓ {succeeded}/{len(entities)} | Rate: {rate:.1f} ent/s | Total: {processed}"
            )

    print(
        f"\n✅ Done! Processed {processed} in {(datetime.now() - start).total_seconds() / 3600:.1f}h"
    )


if __name__ == "__main__":
    asyncio.run(main())
