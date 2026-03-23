#!/usr/bin/env python3
"""Generate BGE-M3 embeddings - fast batch UPDATE."""

import asyncio
import sys
from pathlib import Path
from sentence_transformers import SentenceTransformer

sys.path.insert(0, "/app/src")

from src.server.services.database.db_connector import (
    get_database_connector,
    initialize_database,
)


async def main():
    await initialize_database()
    db = get_database_connector()
    await db.initialize()

    print("Loading BGE-M3...")
    model = SentenceTransformer("BAAI/bge-m3")
    dim = model.get_sentence_embedding_dimension()
    print(f"Model: {dim} dimensions")

    total = 0
    batch = 0

    while True:
        entities = await db.fetch("""
            SELECT id, name, signature, docstring, source_code
            FROM archon_code_entities 
            WHERE embedding_1024 IS NULL
            LIMIT 2000
        """)

        if not entities:
            print("Done!")
            break

        batch += 1
        texts = []
        ids = []

        for e in entities:
            txt = f"{e['name']} {e.get('signature', '')} {e.get('docstring', '')}"
            if e.get("source_code"):
                txt += " " + e["source_code"][:500]
            texts.append(txt[:2000])
            ids.append(str(e["id"]))

        print(f"Batch {batch}: encoding {len(texts)}...")
        embeddings = model.encode(texts, normalize_embeddings=True)

        # Single UPDATE with CASE to avoid transaction overhead
        for entity_id, emb in zip(ids, embeddings):
            emb_str = "[" + ",".join(str(float(x)) for x in emb) + "]"
            await db.execute(
                """UPDATE archon_code_entities 
                   SET embedding_1024 = $1::vector, embedding_model = 'bge-m3', embedding_dimension = 1024
                   WHERE id = $2""",
                emb_str,
                entity_id,
            )

        total += len(entities)
        print(f"  Total: {total}")

        remaining = await db.fetchval(
            "SELECT COUNT(*) FROM archon_code_entities WHERE embedding_1024 IS NULL"
        )
        print(f"  Remaining: {remaining}")

    print(f"Complete! {total} embeddings")


if __name__ == "__main__":
    asyncio.run(main())
