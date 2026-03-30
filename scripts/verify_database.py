#!/usr/bin/env python3
"""
Database Verification Script for Archon

This script verifies that the database is in the correct state.
Run this after any restart to ensure database integrity.
"""

import asyncio
import sys
import os

sys.path.insert(0, '/home/zebastjan/dev/archon/python/src')

from server.services.database.db_connector import get_database_connector

REQUIRED_EXTENSIONS = ['vector', 'pgcrypto', 'pg_trgm']
REQUIRED_TABLES = [
    'archon_projects', 'archon_tasks', 'archon_sources', 'archon_settings',
    'archon_code_entities', 'archon_code_relationships', 'archon_code_examples',
    'archon_commits', 'archon_blobs', 'archon_file_changes',
    'archon_audit_findings', 'archon_audit_rules', 'archon_audit_runs',
    'archon_embeddings', 'archon_embedding_models', 'archon_chunks',
    'archon_documents', 'archon_document_blobs', 'archon_pages',
    'archon_page_metadata', 'archon_knowledge_items', 'archon_summaries',
    'archon_code_repos', 'archon_code_metrics', 'archon_file_metrics',
    'archon_operation_progress', 'archon_semgrep_findings', 'archon_semgrep_config',
    'archon_crawl_url_state', 'archon_crawled_pages',
    'archon_project_sources', 'archon_prompts',
    'archon_migrations', 'archon_embedding_sets'
]

REQUIRED_SETTINGS = [
    'MCP_TRANSPORT', 'HOST', 'PORT', 'MODEL_CHOICE',
    'USE_CONTEXTUAL_EMBEDDINGS', 'USE_HYBRID_SEARCH', 'USE_AGENTIC_RAG', 'USE_RERANKING',
    'LOGFIRE_ENABLED', 'PROJECTS_ENABLED', 'LLM_PROVIDER', 'EMBEDDING_MODEL'
]

async def verify_database():
    """Verify database is in correct state."""
    errors = []
    warnings = []
    
    try:
        db = get_database_connector()
        
        # Check extensions
        print("🔍 Checking PostgreSQL extensions...")
        for ext in REQUIRED_EXTENSIONS:
            result = await db.fetchrow(
                "SELECT extname FROM pg_extension WHERE extname = $1", ext
            )
            if result:
                print(f"  ✅ {ext}")
            else:
                errors.append(f"Missing extension: {ext}")
                print(f"  ❌ {ext} - MISSING")
        
        # Check tables
        print("\n🔍 Checking database tables...")
        existing_tables = await db.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename LIKE 'archon_%'"
        )
        existing_table_names = {row['tablename'] for row in existing_tables}
        
        for table in REQUIRED_TABLES:
            if table in existing_table_names:
                print(f"  ✅ {table}")
            else:
                errors.append(f"Missing table: {table}")
                print(f"  ❌ {table} - MISSING")
        
        # Check settings
        print("\n🔍 Checking archon_settings...")
        for setting in REQUIRED_SETTINGS:
            result = await db.fetchrow(
                "SELECT key FROM archon_settings WHERE key = $1", setting
            )
            if result:
                print(f"  ✅ {setting}")
            else:
                warnings.append(f"Missing setting: {setting}")
                print(f"  ⚠️  {setting} - MISSING")
        
        # Summary
        print(f"\n{'='*60}")
        print(f"Database Verification Summary")
        print(f"{'='*60}")
        print(f"Total tables required: {len(REQUIRED_TABLES)}")
        print(f"Tables found: {len(existing_table_names)}")
        print(f"Extensions required: {len(REQUIRED_EXTENSIONS)}")
        print(f"Settings required: {len(REQUIRED_SETTINGS)}")
        
        if errors:
            print(f"\n❌ ERRORS ({len(errors)}):")
            for error in errors:
                print(f"  - {error}")
        
        if warnings:
            print(f"\n⚠️  WARNINGS ({len(warnings)}):")
            for warning in warnings:
                print(f"  - {warning}")
        
        if not errors and not warnings:
            print("\n✅ Database is fully operational!")
            return 0
        elif not errors:
            print("\n⚠️  Database has warnings but is functional")
            return 1
        else:
            print("\n❌ Database has critical errors and needs repair")
            return 2
            
    except Exception as e:
        print(f"\n❌ Database connection failed: {e}")
        return 2

if __name__ == "__main__":
    exit_code = asyncio.run(verify_database())
    sys.exit(exit_code)
