#!/usr/bin/env python3
"""Index repositories for code audit.

Usage:
    python scripts/index_repos.py [repo_name]
    
Examples:
    python scripts/index_repos.py archon
    python scripts/index_repos.py syllablaze
    python scripts/index_repos.py all
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg2
from psycopg2.extras import RealDictCursor

from src.server.services.code_entity_service import CodeEntityService
from src.server.services.languages import CodeEntity, CodeRelationship, get_language_for_file


def get_repo_files(repo_path: str, extensions: list[str] = None) -> list[str]:
    """Get all source files from a repository."""
    if extensions is None:
        extensions = ['.py', '.ts', '.js', '.tsx', '.jsx']
    
    files = []
    repo_path = Path(repo_path)
    
    # Skip common directories
    skip_dirs = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 
                 'dist', 'build', '.pytest_cache', '.mypy_cache', '.ruff_cache',
                 '.benchmarks', '.git_integration'}
    
    for ext in extensions:
        for file_path in repo_path.rglob(f'*{ext}'):
            # Skip if in excluded directory
            if any(skip_dir in str(file_path) for skip_dir in skip_dirs):
                continue
            # Make path relative to repo root
            relative_path = str(file_path.relative_to(repo_path))
            files.append(relative_path)
    
    return sorted(files)


def get_file_content(repo_path: str, commit_sha: str, file_path: str) -> str:
    """Get file content from disk."""
    full_path = Path(repo_path) / file_path
    try:
        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception as e:
        print(f"  Warning: Could not read {file_path}: {e}")
        return ""


async def index_repository(repo_id: str, repo_name: str, repo_path: str) -> dict[str, Any]:
    """Index a single repository."""
    
    print(f"\n{'=' * 70}")
    print(f"Indexing: {repo_name}")
    print(f"Path: {repo_path}")
    print(f"{'=' * 70}\n")
    
    # Get files to index
    print("Scanning for source files...")
    files = get_repo_files(repo_path)
    print(f"Found {len(files)} source files")
    
    if not files:
        print("No source files found!")
        return {"error": "No files found"}
    
    # Show sample files
    print("\nSample files:")
    for f in files[:5]:
        print(f"  - {f}")
    if len(files) > 5:
        print(f"  ... and {len(files) - 5} more")
    
    # Create service and index
    service = CodeEntityService()
    
    # Define content getter
    async def content_getter(repo_id: str, commit_sha: str, file_path: str) -> str:
        return get_file_content(repo_path, commit_sha, file_path)
    
    print(f"\nExtracting entities from {len(files)} files...")
    print("(This may take a few minutes)\n")
    
    results = await service.extract_and_store_entities(
        repo_id=repo_id,
        commit_sha="HEAD",  # Use HEAD as placeholder
        file_paths=files,
        file_content_getter=content_getter,
    )
    
    print(f"\nIndexing complete!")
    print(f"  Files processed: {results['processed']}")
    print(f"  Entities created: {results['entities_created']}")
    print(f"  Relationships created: {results['relationships_created']}")
    print(f"  Errors: {len(results['errors'])}")
    
    if results['errors']:
        print("\nFirst 5 errors:")
        for err in results['errors'][:5]:
            print(f"  - {err['file']}: {err['error'][:80]}")
    
    # Get final stats
    stats = await service.get_repository_stats(repo_id)
    print(f"\nRepository stats:")
    print(f"  Total entities: {stats.get('total_entities', 0)}")
    print(f"  Total files: {stats.get('total_files', 0)}")
    print(f"  By type: {stats.get('by_type', {})}")
    print(f"  By language: {stats.get('by_language', {})}")
    
    return results


def get_repos_from_db() -> list[dict]:
    """Get all repositories from database."""
    conn = psycopg2.connect(
        host="localhost",
        port=5434,
        database="archon",
        user="archon",
        password="archon_local_dev"
    )
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT id, name, local_path, github_owner, github_repo, github_url
            FROM archon_code_repos
            ORDER BY name
        """)
        repos = cur.fetchall()
    
    conn.close()
    return repos


async def main():
    """Main entry point."""
    target_repo = sys.argv[1] if len(sys.argv) > 1 else "all"
    
    print("=" * 70)
    print("Repository Indexing Tool")
    print("=" * 70)
    
    # Get repos from database
    repos = get_repos_from_db()
    
    print(f"\nFound {len(repos)} repositories in database:")
    for repo in repos:
        print(f"  - {repo['name']}: {repo['local_path']}")
        if repo['github_url']:
            print(f"    GitHub: {repo['github_url']}")
    
    # Filter repos to index
    if target_repo == "all":
        repos_to_index = [r for r in repos if r['name'] in ['archon', 'syllablaze']]
    else:
        repos_to_index = [r for r in repos if r['name'] == target_repo]
    
    if not repos_to_index:
        print(f"\nError: Repository '{target_repo}' not found!")
        print(f"Available: {', '.join(r['name'] for r in repos)}")
        sys.exit(1)
    
    # Index each repo
    for repo in repos_to_index:
        # Check if path exists
        if not Path(repo['local_path']).exists():
            print(f"\nError: Path does not exist: {repo['local_path']}")
            continue
        
        results = await index_repository(
            repo_id=str(repo['id']),
            repo_name=repo['name'],
            repo_path=repo['local_path'],
        )
        
        if 'error' in results:
            print(f"\nFailed to index {repo['name']}: {results['error']}")


if __name__ == "__main__":
    asyncio.run(main())
