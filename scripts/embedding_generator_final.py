#!/usr/bin/env python3
"""
Final Embedding Generator - Correct Ollama Usage

Key points from research:
- Use /api/embed (not /api/embeddings) - supports batch
- Batch size 16 (max before quality degradation)
- Ollama serializes internally - don't parallelize HTTP calls
- Process batches sequentially
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime
import httpx
import psycopg2
from psycopg2.extras import RealDictCursor

# Ollama config
OLLAMA_URL = "http://localhost:11434"
EMBEDDING_MODEL = "bge-m3"  # 8192 tokens vs 512 for bge-large - 16x more context!
BATCH_SIZE = 16  # Ollama's sweet spot - max before quality degradation
TIMEOUT = 120.0

# Database config
DB_URL = os.environ.get(
    "ARCHON_DATABASE_URL",
    "postgresql://archon:archon_local_dev@localhost:5434/archon"
)


def get_db_connection():
    """Get synchronous database connection."""
    return psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)


async def generate_embedding_batch(texts: list[str], client: httpx.AsyncClient) -> list[list[float]] | None:
    """Generate embeddings for a batch of texts using Ollama's /api/embed endpoint."""
    try:
        response = await client.post(
            f"{OLLAMA_URL}/api/embed",
            json={
                "model": EMBEDDING_MODEL,
                "input": texts  # Array of strings - proper batch API
            },
            timeout=TIMEOUT
        )
        
        if response.status_code == 200:
            data = response.json()
            embeddings = data.get("embeddings", [])
            if len(embeddings) == len(texts):
                return embeddings
        
        # Log detailed error
        print(f"    ⚠️  Ollama error: {response.status_code}")
        try:
            error_body = response.text[:500]
            print(f"    Response: {error_body}")
        except:
            pass
        return None
        
    except Exception as e:
        print(f"    ⚠️  Request error: {str(e)[:100]}")
        return None


def prepare_entity_text(entity: dict) -> str:
    """Prepare text representation of entity for embedding.
    
    bge-m3 has 8192 token context window vs bge-large's 512.
    Can use ~6000 chars safely (code is token-dense).
    
    Structure:
    1. Name + Signature (most important for semantics)
    2. Docstring (context/intent)
    3. Source code (implementation details)
    """
    parts = []
    
    # Safely get values
    name = entity.get("name", "") or ""
    docstring = entity.get("docstring", "") or ""
    signature = entity.get("signature", "") or ""
    source_code = entity.get("source_code", "") or ""
    
    # Priority 1: Name and signature - defines the entity
    if name:
        if signature:
            parts.append(f"{name}: {signature[:800]}")
        else:
            parts.append(name[:200])
    
    # Priority 2: Docstring - explains intent and usage
    if docstring:
        # Clean up docstring
        clean_doc = docstring.replace('"""', '').replace("'''", '').strip()
        parts.append(clean_doc[:1500])
    
    # Priority 3: Source code - implementation details
    if source_code:
        # Get function/class body without docstring
        # Simple heuristic: take code after docstring ends
        code_parts = source_code.split('"""')
        if len(code_parts) >= 3:
            impl_code = ''.join(code_parts[2:])  # After closing """
        else:
            impl_code = source_code
        
        # Get significant portion of implementation
        impl_code = impl_code.strip()
        if len(impl_code) > 100:
            parts.append(impl_code[:2500])
    
    if not parts:
        parts.append("Unknown entity")
    
    # Join with clear separators
    text = "\n\n".join(parts)
    return text[:5000]  # ~8192 tokens safe limit for bge-m3


def fetch_batch_entities(conn, batch_size: int) -> list[dict]:
    """Fetch a batch of entities needing embeddings."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, name, signature, docstring, source_code
            FROM archon_code_entities
            WHERE embedding_1024 IS NULL
            ORDER BY created_at
            LIMIT %s
        """, (batch_size,))
        return cur.fetchall()


def update_entity_embedding(conn, entity_id: str, embedding: list[float]):
    """Update entity with its embedding."""
    vector_str = "[" + ",".join(f"{x:.6f}" for x in embedding) + "]"
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE archon_code_entities 
            SET embedding_1024 = %s::vector, 
                embedding_model = %s,
                updated_at = NOW()
            WHERE id = %s
        """, (vector_str, EMBEDDING_MODEL, entity_id))
    conn.commit()


async def main():
    print("=" * 70)
    print("  EMBEDDING GENERATOR - FINAL VERSION")
    print("=" * 70)
    print(f"Model: {EMBEDDING_MODEL}")
    print(f"  - bge-m3: 8192 tokens (16x bge-large's 512)")
    print(f"  - Using ~5000 chars for rich code context")
    print(f"Batch size: {BATCH_SIZE} (Ollama optimal)")
    print(f"Endpoint: /api/embed (batch-capable)")
    print()
    
    # Connect to database
    print("Connecting to database...")
    conn = get_db_connection()
    
    # Get stats
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN embedding_1024 IS NOT NULL THEN 1 END) as done
            FROM archon_code_entities
        """)
        row = cur.fetchone()
    
    total = row["total"]
    done = row["done"]
    remaining = total - done
    
    print(f"Total entities: {total:,}")
    print(f"Already embedded: {done:,} ({100*done/total:.1f}%)")
    print(f"Remaining: {remaining:,}")
    print()
    
    if remaining == 0:
        print("✅ All entities have embeddings!")
        conn.close()
        return 0
    
    # Process in batches
    processed = 0
    succeeded = 0
    failed = 0
    start_time = datetime.now()
    batch_num = 0
    
    async with httpx.AsyncClient(timeout=TIMEOUT + 10) as client:
        while True:
            # Get next batch of entities
            entities = fetch_batch_entities(conn, BATCH_SIZE)
            
            if not entities:
                print("\n✅ No more entities to process!")
                break
            
            batch_num += 1
            
            # Prepare texts for batch
            texts = [prepare_entity_text(dict(e)) for e in entities]
            entity_ids = [str(e["id"]) for e in entities]
            
            # Debug: log first text sample
            if batch_num == 1:
                print(f"\n  Sample text (first 200 chars): {repr(texts[0][:200])}")
                print(f"  Text length: {len(texts[0])}")
            
            print(f"Batch {batch_num}: Processing {len(entities)} entities...", end=" ", flush=True)
            
            # Generate embeddings in single batch call
            embeddings = await generate_embedding_batch(texts, client)
            
            if embeddings:
                # Store embeddings
                batch_succeeded = 0
                for entity_id, embedding in zip(entity_ids, embeddings):
                    try:
                        update_entity_embedding(conn, entity_id, embedding)
                        batch_succeeded += 1
                    except Exception as e:
                        print(f"\n    DB error: {e}")
                        conn.rollback()
                
                succeeded += batch_succeeded
                failed += len(entities) - batch_succeeded
                print(f"✓ {batch_succeeded}/{len(entities)}")
            else:
                failed += len(entities)
                print(f"✗ Batch failed")
            
            processed += len(entities)
            
            # Progress stats
            elapsed = (datetime.now() - start_time).total_seconds()
            rate = processed / elapsed if elapsed > 0 else 0
            eta_hours = (remaining - processed) / rate / 3600 if rate > 0 else 0
            
            if batch_num % 10 == 0:
                print(f"\n  Progress: {processed}/{remaining} | Rate: {rate:.1f} ent/s | ETA: {eta_hours:.1f}h")
                print()
    
    conn.close()
    
    # Final stats
    elapsed = (datetime.now() - start_time).total_seconds()
    print("\n" + "=" * 70)
    print("COMPLETE")
    print("=" * 70)
    print(f"Processed: {processed}")
    print(f"Succeeded: {succeeded}")
    print(f"Failed: {failed}")
    print(f"Time: {elapsed/3600:.1f} hours")
    print(f"Final rate: {processed/elapsed:.1f} ent/s" if elapsed > 0 else "N/A")
    print("=" * 70)
    
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n💥 Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
