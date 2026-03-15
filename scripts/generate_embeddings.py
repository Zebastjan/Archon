#!/usr/bin/env python3
"""
Robust Embedding Generation Script for Archon Code Entities

Generates BGE-large embeddings for code entities that don't have them yet.
Designed to be:
- Resumable (can stop and restart)
- Batch processed (memory efficient)
- Observable (progress logging)
- Fault tolerant (continues on errors)
"""

import asyncio
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

# Load .env file from project root
from dotenv import load_dotenv
project_root = Path(__file__).resolve().parent.parent
env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)
    print(f"✓ Loaded environment from {env_path}")

# Add python/src to path
sys.path.insert(0, '/home/zebastjan/dev/archon/python/src')

try:
    from server.services.database.db_connector import get_database_connector, initialize_database
    from server.services.embedding_service import get_embedding_service
except ImportError:
    from src.server.services.database.db_connector import get_database_connector, initialize_database
    from src.server.services.embedding_service import get_embedding_service


class EmbeddingGenerator:
    """Robust embedding generation with progress tracking and error recovery."""
    
    def __init__(self, batch_size: int = 50, max_retries: int = 3):
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.db = None
        self.embedding_service = None
        self.stats = {
            'processed': 0,
            'succeeded': 0,
            'failed': 0,
            'skipped': 0,
            'start_time': None,
            'errors': []
        }
    
    async def initialize(self):
        """Initialize database and embedding service."""
        print("🔌 Initializing database connection...")
        await initialize_database()
        self.db = get_database_connector()
        await self.db.initialize()
        
        print("🧠 Initializing embedding service...")
        self.embedding_service = get_embedding_service()
        print("✅ Initialization complete\n")
    
    async def get_entities_without_embeddings(self, repo_id: str | None = None) -> list[dict]:
        """Get all entities that need embeddings."""
        if repo_id:
            rows = await self.db.fetch("""
                SELECT id, name, entity_type, signature, docstring, source_code
                FROM archon_code_entities
                WHERE repo_id = $1 AND embedding_1024 IS NULL
                ORDER BY created_at
            """, repo_id)
        else:
            rows = await self.db.fetch("""
                SELECT id, name, entity_type, signature, docstring, source_code
                FROM archon_code_entities
                WHERE embedding_1024 IS NULL
                ORDER BY created_at
            """)
        
        # Convert to dict and ensure IDs are strings
        entities = []
        for row in rows:
            entity = dict(row)
            entity['id'] = str(entity['id'])
            entities.append(entity)
        return entities
    
    async def process_entity(self, entity: dict) -> tuple[bool, str | None]:
        """Process a single entity with retry logic."""
        entity_id = str(entity['id'])  # Ensure string
        
        for attempt in range(self.max_retries):
            try:
                # Generate embedding
                embedding = await self.embedding_service.generate_for_code_entity(
                    name=entity['name'],
                    signature=entity.get('signature'),
                    docstring=entity.get('docstring'),
                    source_code=entity.get('source_code')
                )
                
                if embedding is None:
                    return False, "Embedding generation returned None"
                
                # Convert embedding list to pgvector string format
                if isinstance(embedding, list):
                    embedding_str = '[' + ','.join(str(x) for x in embedding) + ']'
                else:
                    embedding_str = str(embedding)
                
                # Store embedding
                await self.db.execute("""
                    UPDATE archon_code_entities
                    SET embedding_1024 = $1::vector, updated_at = NOW()
                    WHERE id = $2
                """, embedding_str, entity_id)
                
                return True, None
                
            except Exception as e:
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    print(f"    ⚠️  Attempt {attempt + 1} failed for {entity_id[:8]}..., retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    error_msg = f"{type(e).__name__}: {str(e)[:100]}"
                    return False, error_msg
        
        return False, "Max retries exceeded"
    
    async def process_batch(self, entities: list[dict]) -> dict[str, Any]:
        """Process a batch of entities."""
        batch_stats = {'succeeded': 0, 'failed': 0, 'errors': []}
        
        for entity in entities:
            self.stats['processed'] += 1
            success, error = await self.process_entity(entity)
            
            if success:
                batch_stats['succeeded'] += 1
                self.stats['succeeded'] += 1
            else:
                batch_stats['failed'] += 1
                self.stats['failed'] += 1
                batch_stats['errors'].append({
                    'entity_id': entity['id'][:8],
                    'name': entity['name'][:50],
                    'error': error
                })
        
        return batch_stats
    
    async def generate_for_repo(self, repo_id: str, repo_name: str = None):
        """Generate embeddings for all entities in a repository."""
        print(f"\n{'='*60}")
        print(f"🚀 Processing repository: {repo_name or repo_id[:8]}...")
        print(f"{'='*60}")
        
        # Get entities needing embeddings
        entities = await self.get_entities_without_embeddings(repo_id)
        total = len(entities)
        
        if total == 0:
            print(f"✅ Repository already has all embeddings!")
            return
        
        print(f"📊 Found {total} entities needing embeddings")
        print(f"⚙️  Batch size: {self.batch_size}")
        print(f"🎯 Estimated time: {total * 0.5:.0f}s - {total * 2:.0f}s")
        print(f"💻 CPU fans: prepare for takeoff 🌪️\n")
        
        self.stats['start_time'] = time.time()
        
        # Process in batches
        for i in range(0, total, self.batch_size):
            batch = entities[i:i + self.batch_size]
            batch_num = i // self.batch_size + 1
            total_batches = (total + self.batch_size - 1) // self.batch_size
            
            print(f"📦 Batch {batch_num}/{total_batches} ({len(batch)} entities)...", end=' ')
            
            batch_stats = await self.process_batch(batch)
            
            # Calculate progress
            elapsed = time.time() - self.stats['start_time']
            progress = (i + len(batch)) / total * 100
            rate = self.stats['processed'] / elapsed if elapsed > 0 else 0
            eta = (total - self.stats['processed']) / rate if rate > 0 else 0
            
            print(f"✓ {batch_stats['succeeded']} success, {batch_stats['failed']} failed | "
                  f"Progress: {progress:.1f}% | Rate: {rate:.1f} ent/s | ETA: {eta:.0f}s")
            
            # Print any errors from this batch
            if batch_stats['errors']:
                for err in batch_stats['errors'][:3]:  # Show first 3 errors
                    print(f"    ❌ {err['entity_id']}: {err['error']}")
                if len(batch_stats['errors']) > 3:
                    print(f"    ... and {len(batch_stats['errors']) - 3} more errors")
        
        # Final summary
        elapsed = time.time() - self.stats['start_time']
        print(f"\n✅ Repository complete!")
        print(f"   Total: {self.stats['processed']}")
        print(f"   Succeeded: {self.stats['succeeded']}")
        print(f"   Failed: {self.stats['failed']}")
        print(f"   Time: {elapsed:.1f}s")
        print(f"   Rate: {self.stats['processed'] / elapsed:.1f} entities/second")
    
    async def generate_all(self, repo_filter: list[str] = None):
        """Generate embeddings for all repositories."""
        await self.initialize()
        
        # Get list of repos with entities needing embeddings
        rows = await self.db.fetch("""
            SELECT DISTINCT repo_id,
                   COUNT(*) FILTER (WHERE embedding_1024 IS NULL) as missing,
                   COUNT(*) as total
            FROM archon_code_entities
            GROUP BY repo_id
            HAVING COUNT(*) FILTER (WHERE embedding_1024 IS NULL) > 0
            ORDER BY COUNT(*) FILTER (WHERE embedding_1024 IS NULL) DESC
        """)
        
        repos = [dict(row) for row in rows]
        
        if not repos:
            print("✅ All entities already have embeddings!")
            return
        
        print(f"\n📊 Repositories needing embeddings:")
        for r in repos:
            pct = r['missing'] / r['total'] * 100
            print(f"   {str(r['repo_id'])[:8]}...: {r['missing']}/{r['total']} missing ({pct:.0f}%)")
        
        # Process each repo
        for repo in repos:
            repo_id = str(repo['repo_id'])
            
            # Skip if not in filter
            if repo_filter and repo_id not in repo_filter:
                print(f"\n⏭️  Skipping {repo_id[:8]}... (not in filter)")
                continue
            
            # Reset stats for this repo
            self.stats = {
                'processed': 0,
                'succeeded': 0,
                'failed': 0,
                'skipped': 0,
                'start_time': None,
                'errors': []
            }
            
            await self.generate_for_repo(repo_id, repo_id[:8])
        
        print(f"\n{'='*60}")
        print("🎉 All embedding generation complete!")
        print(f"{'='*60}")


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate embeddings for code entities')
    parser.add_argument('--repo', help='Specific repository ID to process')
    parser.add_argument('--batch-size', type=int, default=50, help='Batch size (default: 50)')
    parser.add_argument('--max-retries', type=int, default=3, help='Max retries per entity (default: 3)')
    
    args = parser.parse_args()
    
    # Ensure environment is set
    if not os.getenv('ARCHON_DATABASE_URL'):
        os.environ['ARCHON_DATABASE_URL'] = 'postgresql://archon:archon_local_dev@localhost:5434/archon'
    
    print("🚀 Archon Embedding Generator")
    print("=" * 60)
    print(f"⏰ Started: {datetime.now().isoformat()}")
    print(f"💾 Database: {os.getenv('ARCHON_DATABASE_URL', 'NOT SET')}")
    print(f"⚙️  Batch size: {args.batch_size}")
    print(f"🔁 Max retries: {args.max_retries}")
    print("=" * 60)
    
    generator = EmbeddingGenerator(
        batch_size=args.batch_size,
        max_retries=args.max_retries
    )
    
    try:
        if args.repo:
            await generator.initialize()
            await generator.generate_for_repo(args.repo)
        else:
            await generator.generate_all()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user. Progress has been saved.")
        print("   You can safely restart to continue.")
    except Exception as e:
        print(f"\n\n💥 Fatal error: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
