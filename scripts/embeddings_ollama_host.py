#!/usr/bin/env python3
"""Generate BGE-M3 embeddings using Ollama with VRAM guard."""

import asyncio
import subprocess
import sys
import psycopg2
from pathlib import Path

OLLAMA_URL = "http://localhost:11434"
MODEL_NAME = "bge-m3"
BATCH_SIZE = 50
MIN_VRAM_MB = 3000


def get_free_gpu_memory_mb():
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
        return 99999


def generate_embedding(text: str):
    """Generate embedding using curl/Ollama."""
    try:
        import json

        proc = subprocess.run(
            [
                "curl",
                "-s",
                "-X",
                "POST",
                f"{OLLAMA_URL}/api/embeddings",
                "-d",
                f'{{"model": "{MODEL_NAME}", "prompt": {json.dumps(text[:1000])}}}',
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode == 0:
            data = json.loads(proc.stdout)
            return data.get("embedding")
    except Exception as e:
        pass
    return None


def main():
    import os

    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        user="postgres",
        password="postgres",
        database="archon",
    )
    print("Connected to database")
    conn.autocommit = True

    print(f"Starting BGE-M3 embedding generation via Ollama")

    total_processed = 0
    batch_num = 0

    while True:
        free_vram = get_free_gpu_memory_mb()

        if free_vram < MIN_VRAM_MB:
            print(f"⚠️  Low VRAM ({free_vram}MB). Waiting...")
            import time

            time.sleep(30)
            continue

        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT id, name, signature, docstring, source_code
                FROM archon_code_entities 
                WHERE embedding_1024 IS NULL
                LIMIT {BATCH_SIZE}
            """)
            entities = cur.fetchall()

        if not entities:
            print("✅ Done! No more entities.")
            break

        batch_num += 1
        print(f"Batch {batch_num}: {len(entities)} entities...")

        for e in entities:
            entity_id, name, signature, docstring, source_code = e
            txt = f"{name} {signature or ''} {docstring or ''}"
            if source_code:
                txt += " " + source_code[:500]

            emb = generate_embedding(txt[:2000])

            if emb:
                emb_str = "[" + ",".join(str(x) for x in emb) + "]"
                with conn.cursor() as cur:
                    cur.execute(
                        """UPDATE archon_code_entities 
                           SET embedding_1024 = %s::vector, embedding_model = 'bge-m3', embedding_dimension = 1024
                           WHERE id = %s""",
                        (emb_str, entity_id),
                    )
                total_processed += 1

        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM archon_code_entities WHERE embedding_1024 IS NULL"
            )
            remaining = cur.fetchone()[0]

        print(f"  Processed: {total_processed}, Remaining: {remaining}")

    print(f"\n✅ Done! Total: {total_processed}")


if __name__ == "__main__":
    main()
