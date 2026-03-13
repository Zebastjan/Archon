#!/usr/bin/env python3
"""
Ingest Archon's own codebase for dogfooding.

This script:
1. Registers the Archon repository
2. Syncs commits
3. Extracts code entities (functions, classes, methods)
4. Generates embeddings using Ollama
5. Generates summaries for extracted entities

Usage:
    python scripts/ingest_archon_repo.py
"""

import asyncio
import os
import sys
from pathlib import Path

# Add python directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

from src.server.services.database import get_database_connector, initialize_database
from src.server.services.git.git_repository_service import GitRepositoryService
from src.server.services.code_entity_service import CodeEntityService
from src.server.services.languages import get_language_for_file
from src.server.config.logfire_config import get_logger

logger = get_logger(__name__)


# Archon repo paths to analyze
ARCHON_REPO_PATH = Path(__file__).parent.parent
PYTHON_SOURCE_DIR = ARCHON_REPO_PATH / "python" / "src"
TYPESCRIPT_SOURCE_DIR = ARCHON_REPO_PATH / "archon-ui-main" / "src"


async def setup_database():
    """Initialize database connection."""
    logger.info("Initializing database connection...")
    await initialize_database()
    db = get_database_connector()
    await db.initialize()
    return db


async def register_repository(git_service: GitRepositoryService) -> str:
    """Register Archon repository in the database."""
    logger.info(f"Registering Archon repository: {ARCHON_REPO_PATH}")
    
    # Check if already registered
    db = get_database_connector()
    result = await db.fetch(
        "SELECT id FROM archon_git_repositories WHERE repo_url = $1",
        str(ARCHON_REPO_PATH)
    )
    
    if result:
        repo_id = result[0]["id"]
        logger.info(f"Repository already registered: {repo_id}")
        return repo_id
    
    # Create source entry first
    source_result = await db.fetchrow(
        """
        INSERT INTO archon_sources (source_id, source_url, source_display_name, title, metadata)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (source_id) DO UPDATE SET updated_at = NOW()
        RETURNING source_id
        """,
        "archon-self",
        str(ARCHON_REPO_PATH),
        "Archon Codebase",
        "Archon Self-Ingestion",
        {"knowledge_type": "git_repository", "self_ingestion": True}
    )
    
    source_id = source_result["source_id"]
    
    # Register repository
    success, result = git_service.register_repository(
        repo_path=str(ARCHON_REPO_PATH),
        source_id=source_id,
        config={"self_ingestion": True}
    )
    
    if not success:
        raise Exception(f"Failed to register repository: {result}")
    
    repo_id = result["repo_id"]
    logger.info(f"Repository registered: {repo_id}")
    return repo_id


async def sync_and_extract(git_service: GitRepositoryService, repo_id: str):
    """Sync commits and extract code entities."""
    logger.info("Syncing commits and extracting code entities...")
    
    # Get current branch
    try:
        branch_name = git_service.get_current_branch(str(ARCHON_REPO_PATH))
    except Exception as e:
        logger.warning(f"Could not get branch, using 'main': {e}")
        branch_name = "main"
    
    logger.info(f"Using branch: {branch_name}")
    
    # Sync commits with entity extraction
    success, result = await git_service.sync_commits_with_code_entities(
        repo_id=repo_id,
        branch_name=branch_name,
        extract_entities=True,
        entity_batch_size=50
    )
    
    if not success:
        raise Exception(f"Failed to sync: {result}")
    
    logger.info(f"Sync complete: {result}")
    return result


async def analyze_extraction_results(repo_id: str):
    """Analyze what was extracted."""
    db = get_database_connector()
    
    # Count entities by type
    type_counts = await db.fetch(
        """
        SELECT entity_type, COUNT(*) as count
        FROM archon_code_entities
        WHERE repo_id = $1
        GROUP BY entity_type
        ORDER BY count DESC
        """,
        repo_id
    )
    
    logger.info("Extraction results:")
    logger.info("=" * 50)
    for row in type_counts:
        logger.info(f"  {row['entity_type']}: {row['count']}")
    
    # Count by language
    lang_counts = await db.fetch(
        """
        SELECT language, COUNT(*) as count
        FROM archon_code_entities
        WHERE repo_id = $1
        GROUP BY language
        ORDER BY count DESC
        """,
        repo_id
    )
    
    logger.info("\nBy language:")
    for row in lang_counts:
        logger.info(f"  {row['language']}: {row['count']}")
    
    # Sample some interesting entities
    sample_entities = await db.fetch(
        """
        SELECT name, entity_type, language, file_path
        FROM archon_code_entities
        WHERE repo_id = $1
        ORDER BY entity_type, name
        LIMIT 20
        """,
        repo_id
    )
    
    logger.info("\nSample extracted entities:")
    for entity in sample_entities:
        logger.info(f"  [{entity['entity_type']}] {entity['name']} ({entity['language']})")


async def generate_embeddings(repo_id: str, embedding_service):
    """Generate embeddings for extracted entities."""
    logger.info("Generating embeddings...")
    
    code_entity_service = CodeEntityService()
    
    # This would use the embedding service to generate embeddings
    # For now, just log that we would do this
    logger.info("Embedding generation would use Ollama with bge-large")
    logger.info(f"Target: archon_code_entities.embedding_1024 for repo {repo_id}")


async def main():
    """Main ingestion workflow."""
    logger.info("=" * 60)
    logger.info("Archon Self-Ingestion Script")
    logger.info("=" * 60)
    
    try:
        # Step 1: Setup database
        db = await setup_database()
        logger.info("✅ Database connected")
        
        # Step 2: Initialize services
        git_service = GitRepositoryService()
        logger.info("✅ Git service initialized")
        
        # Step 3: Register repository
        repo_id = await register_repository(git_service)
        logger.info(f"✅ Repository registered: {repo_id}")
        
        # Step 4: Sync and extract
        result = await sync_and_extract(git_service, repo_id)
        logger.info("✅ Commits synced and entities extracted")
        
        # Step 5: Analyze results
        await analyze_extraction_results(repo_id)
        
        # Step 6: Generate embeddings (placeholder)
        await generate_embeddings(repo_id, None)
        
        logger.info("=" * 60)
        logger.info("Ingestion complete!")
        logger.info("=" * 60)
        logger.info(f"Repository ID: {repo_id}")
        logger.info("\nNext steps:")
        logger.info("  1. Query entities via MCP: codebase_find_entity")
        logger.info("  2. Explore relationships: codebase_get_entity_context")
        logger.info("  3. Search semantically: codebase_search_by_semantics")
        
    except Exception as e:
        logger.exception("Ingestion failed")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
