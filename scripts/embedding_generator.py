#!/usr/bin/env python3
"""
Code Entity Embedding Generator for Archon
Generates embeddings using Ollama for all code entities.
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime
import httpx
import json

# Add paths BEFORE other imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python" / "src"))

# Now imports will work
from server.services.database.db_connector import get_database_connector, initialize_database

# Ollama configuration
OLLAMA_URL = "http://localhost:11434"
EMBEDDING_MODEL = "bge-large"
BATCH_SIZE = 50


async def get_ollama_embedding(text: str, client: httpx.AsyncClient) -> list[float] | None:
    """Get embedding from Ollama."""
    try:
        response = await client.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": EMBEDDING_MODEL, "prompt": text[:4000]},  # Limit text length
            timeout=60.0
        )
        
        if response.status_code == 200:
            data = response.json()
            embedding = data.get("embedding")
            if embedding and len(embedding) == 1024:
                return embedding
        return None
    except Exception as e:
        print(f"  Error getting embedding: {e}")
        return None


async def prepare_entity_text(entity: dict) -> str:
    """Prepare text representation of entity for embedding."""
    parts = []
    
    if entity.get("docstring"):
        parts.append(entity["docstring"])
    
    if entity.get("signature"):
        parts.append(entity["signature"])
    
    if entity.get("source_code"):
        source = entity["source_code"][:2000]
        parts.append(source)
    
    if not parts:
        parts.append(entity.get("name", ""))
    
    return "\n".join(parts)


async def process_batch(entities: list, db, client: httpx.AsyncClient) -> tuple[int, int]:
    """Process a batch of entities."""
    succeeded = 0
    failed = 0
    
    for entity in entities:
        try:
            text = await prepare_entity_text(entity)
            embedding = await get_ollama_embedding(text, client)
            
            if embedding:
                # Store in database
                await db.execute(
                    """UPDATE archon_code_entities 
                    SET embedding_1024 = $1::vector, 
                        embedding_dimension = 1024,
                        embedding_model = $2,
                        updated_at = NOW()
                    WHERE id = $3""",
                    embedding, EMBEDDING_MODEL, entity["id"]
                )
                succeeded += 1
            else:
                failed += 1
                
        except Exception as e:
            print(f"  Failed {entity['id'][:8]}: {e}")
            failed += 1
    
    return succeeded, failed


async def main():
    print("=" * 70)
    print("  ARCHON CODE ENTITY EMBEDDING GENERATOR")
    print("=" * 70)
    print(f"Started: {datetime.now().isoformat()}")
    print(f"Ollama: {OLLAMA_URL}")
    print(f"Model: {EMBEDDING_MODEL}")
    print(f"Batch size: {BATCH_SIZE}")
    print()
    
    # Initialize database
    print("Connecting to database...")
    await initialize_database()
    db = get_database_connector()
    
    # Check Ollama
    print("Checking Ollama...")
    async with httpx.AsyncClient() as check_client:
        try:
            resp = await check_client.get(f"{OLLAMA_URL}/api/tags", timeout=5.0)
            if resp.status_code == 200:
                print("  ✓ Ollama is running")
            else:
                print(f"  ✗ Ollama returned {resp.status_code}")
                return 1
        except Exception as e:
            print(f"  ✗ Cannot connect to Ollama: {e}")
            return 1
    
    # Count entities
    result = await db.fetchrow("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN embedding_1024 IS NOT NULL THEN 1 END) as with_emb
        FROM archon_code_entities
    """)
    
    total = result["total"]
    current = result["with_emb"]
    remaining = total - current
    
    print()
    print(f"Total entities: {total:,}")
    print(f"Already embedded: {current:,}")
    print(f"Remaining: {remaining:,}")
    print()
    
    if remaining == 0:
        print("✅ All entities already have embeddings!")
        return 0
    
    # Get entities without embeddings
    print("Fetching entities...")
    entities = await db.fetch("""
        SELECT id, name, entity_type, signature, docstring, source_code
        FROM archon_code_entities
        WHERE embedding_1024 IS NULL
        ORDER BY created_at
    """)
    
    print(f"Processing {len(entities)} entities in batches of {BATCH_SIZE}...")
    print()
    
    # Process in batches
    total_succeeded = 0
    total_failed = 0
    batch_num = 0
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        for i in range(0, len(entities), BATCH_SIZE):
            batch_num += 1
            batch = entities[i:i + BATCH_SIZE]
            
            print(f"Batch {batch_num}: {len(batch)} entities...", end=" ", flush=True)
            
            succeeded, failed = await process_batch(batch, db, client)
            total_succeeded += succeeded
            total_failed += failed
            
            progress = (i + len(batch)) / len(entities) * 100
            print(f"✓ {succeeded} ok, {failed} fail | {progress:.1f}% complete")
            
            # Small delay to not overwhelm Ollama
            await asyncio.sleep(0.1)
    
    print()
    print("=" * 70)
    print("COMPLETE")
    print("=" * 70)
    print(f"Total succeeded: {total_succeeded:,}")
    print(f"Total failed: {total_failed:,}")
    print(f"New embeddings: {total_succeeded:,}")
    print(f"Total embedded: {current + total_succeeded:,} / {total:,}")
    print("=" * 70)
    
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user. Progress saved.")
        sys.exit(1)
