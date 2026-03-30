#!/usr/bin/env python3
"""Generate BGE-M3 embeddings - runs on host, accesses DB via docker exec."""

import subprocess
import json
import time
import psycopg2

OLLAMA_URL = "http://localhost:11434"
MODEL_NAME = "bge-m3"
BATCH_SIZE = 100
MIN_VRAM_MB = 3000


def get_free_gpu_memory_mb():
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return int(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError):
        return 99999


def generate_embedding(text: str):
    try:
        proc = subprocess.run(
            [
                "curl",
                "-s",
                "-X",
                "POST",
                f"{OLLAMA_URL}/api/embeddings",
                "-d",
                json.dumps({"model": MODEL_NAME, "prompt": text[:1000]}),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode == 0:
            data = json.loads(proc.stdout)
            return data.get("embedding")
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        pass
    return None


def main():
    # Connect to dockerized postgres via docker exec
    print("Starting BGE-M3 embedding via Ollama (host)")

    total = 0
    batch = 0

    while True:
        # Check VRAM
        free = get_free_gpu_memory_mb()
        if free < MIN_VRAM_MB:
            print(f"⚠️  Low VRAM ({free}MB). Waiting 30s...")
            time.sleep(30)
            continue

        # Get entities via docker exec
        result = subprocess.run(
            [
                "docker",
                "exec",
                "archon",
                "psql",
                "-U",
                "postgres",
                "-d",
                "archon",
                "-t",
                "-c",
                f"SELECT id, name, COALESCE(signature,''), COALESCE(docstring,''), COALESCE(source_code,'') FROM archon_code_entities WHERE embedding_1024 IS NULL LIMIT {BATCH_SIZE}",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print(f"DB error: {result.stderr}")
            break

        lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
        if not lines:
            print("✅ Done! No more entities.")
            break

        batch += 1
        print(f"Batch {batch}: {len(lines)} entities...")

        for line in lines:
            parts = line.split("|")
            if len(parts) < 5:
                continue
            entity_id = parts[0].strip()
            name = parts[1].strip()
            signature = parts[2].strip()
            docstring = parts[3].strip()
            source_code = parts[4].strip()

            txt = f"{name} {signature} {docstring}"
            if source_code:
                txt += " " + source_code[:500]

            emb = generate_embedding(txt[:2000])

            if emb:
                emb_str = "[" + ",".join(str(x) for x in emb) + "]"
                subprocess.run(
                    [
                        "docker",
                        "exec",
                        "archon",
                        "psql",
                        "-U",
                        "postgres",
                        "-d",
                        "archon",
                        "-c",
                        f"UPDATE archon_code_entities SET embedding_1024 = '{emb_str}'::vector, embedding_model = 'bge-m3', embedding_dimension = 1024 WHERE id = '{entity_id}'",
                    ],
                    capture_output=True,
                )
                total += 1

        # Check remaining
        result = subprocess.run(
            [
                "docker",
                "exec",
                "archon",
                "psql",
                "-U",
                "postgres",
                "-d",
                "archon",
                "-t",
                "-c",
                "SELECT COUNT(*) FROM archon_code_entities WHERE embedding_1024 IS NULL",
            ],
            capture_output=True,
            text=True,
        )
        remaining = int(result.stdout.strip()) if result.returncode == 0 else 0

        print(f"  Processed: {total}, Remaining: {remaining}")

    print(f"\n✅ Complete! Total: {total}")


if __name__ == "__main__":
    main()
