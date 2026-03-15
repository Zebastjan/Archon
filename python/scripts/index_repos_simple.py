#!/usr/bin/env python3
"""Simple repository indexer using direct PostgreSQL inserts.

Usage:
    python scripts/index_repos_simple.py [repo_name]
    
Examples:
    python scripts/index_repos_simple.py archon
    python scripts/index_repos_simple.py syllablaze
    python scripts/index_repos_simple.py all
"""

import ast
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor


def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(
        host="localhost",
        port=5434,
        database="archon",
        user="archon",
        password="archon_local_dev"
    )


def get_repo_files(repo_path: str) -> list[str]:
    """Get all Python files from a repository."""
    files = []
    repo_path = Path(repo_path)
    
    # Skip directories
    skip_dirs = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 
                 'dist', 'build', '.pytest_cache', '.mypy_cache', 
                 '.ruff_cache', '.benchmarks', '.git_integration'}
    
    for ext in ['.py']:
        for file_path in repo_path.rglob(f'*{ext}'):
            if any(skip_dir in str(file_path) for skip_dir in skip_dirs):
                continue
            relative_path = str(file_path.relative_to(repo_path))
            files.append(relative_path)
    
    return sorted(files)


def extract_python_entities(content: str, file_path: str) -> tuple[list[dict], list[dict]]:
    """Extract entities from Python source code."""
    entities = []
    relationships = []
    
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        print(f"    Syntax error in {file_path}: {e}")
        return entities, relationships
    
    # Track class and function definitions
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            # Extract class info
            entity = {
                "name": node.name,
                "entity_type": "class",
                "line_start": node.lineno,
                "line_end": node.end_lineno if hasattr(node, 'end_lineno') else node.lineno,
                "signature": f"class {node.name}",
                "docstring": ast.get_docstring(node),
                "source_code": ast.unparse(node) if hasattr(ast, 'unparse') else "",
            }
            entities.append(entity)
            
            # Check for inheritance (relationships)
            for base in node.bases:
                if isinstance(base, ast.Name):
                    relationships.append({
                        "source": node.name,
                        "target": base.id,
                        "type": "INHERITS",
                    })
        
        elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            # Determine if method or function
            parent = getattr(node, 'parent', None)
            entity_type = "method" if parent and isinstance(parent, ast.ClassDef) else "function"
            
            # Get signature
            args_str = ", ".join(arg.arg for arg in node.args.args if arg.arg != 'self')
            signature = f"def {node.name}({args_str})"
            
            entity = {
                "name": node.name,
                "entity_type": entity_type,
                "line_start": node.lineno,
                "line_end": node.end_lineno if hasattr(node, 'end_lineno') else node.lineno,
                "signature": signature,
                "docstring": ast.get_docstring(node),
                "source_code": ast.unparse(node) if hasattr(ast, 'unparse') else "",
            }
            entities.append(entity)
    
    # Track imports (relationships)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                relationships.append({
                    "source": "module",
                    "target": alias.name,
                    "type": "IMPORTS",
                })
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                relationships.append({
                    "source": "module",
                    "target": f"{module}.{alias.name}" if module else alias.name,
                    "type": "IMPORTS",
                })
    
    return entities, relationships


def index_repository(repo_id: str, repo_name: str, repo_path: str) -> dict[str, Any]:
    """Index a single repository."""
    
    print(f"\n{'=' * 70}")
    print(f"Indexing: {repo_name}")
    print(f"Path: {repo_path}")
    print(f"{'=' * 70}\n")
    
    # Get Python files
    print("Scanning for Python files...")
    files = get_repo_files(repo_path)
    print(f"Found {len(files)} Python files")
    
    if not files:
        print("No Python files found!")
        return {"error": "No files found"}
    
    # Show sample
    print("\nSample files:")
    for f in files[:5]:
        print(f"  - {f}")
    if len(files) > 5:
        print(f"  ... and {len(files) - 5} more")
    
    # Connect to database
    conn = get_db_connection()
    
    # Clear existing entities for this repo
    print(f"\nClearing existing entities for {repo_name}...")
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM archon_code_relationships WHERE source_entity_id IN (SELECT id FROM archon_code_entities WHERE repo_id = %s)",
            (repo_id,)
        )
        cur.execute(
            "DELETE FROM archon_code_entities WHERE repo_id = %s",
            (repo_id,)
        )
        conn.commit()
    print("Cleared existing data")
    
    # Process files
    total_entities = 0
    total_relationships = 0
    errors = []
    
    print(f"\nProcessing {len(files)} files...")
    print("(This may take a few minutes)\n")
    
    for i, file_path in enumerate(files, 1):
        if i % 50 == 0:
            print(f"  Progress: {i}/{len(files)} files ({i*100//len(files)}%)")
        
        full_path = Path(repo_path) / file_path
        try:
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            errors.append({"file": file_path, "error": str(e)})
            continue
        
        # Extract entities
        entities, relationships = extract_python_entities(content, file_path)
        
        # Insert entities
        entity_id_map = {}
        with conn.cursor() as cur:
            for entity in entities:
                try:
                    cur.execute("""
                        INSERT INTO archon_code_entities (
                            repo_id, file_path, line_start, line_end, entity_type,
                            name, signature, docstring, source_code, language, commit_sha
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        repo_id, file_path, entity["line_start"], entity["line_end"],
                        entity["entity_type"], entity["name"], entity["signature"],
                        entity["docstring"], entity["source_code"], "python", "HEAD"
                    ))
                    result = cur.fetchone()
                    if result:
                        entity_id_map[entity["name"]] = result[0]
                        total_entities += 1
                except Exception as e:
                    errors.append({"file": file_path, "error": f"Entity insert: {e}"})
            
            conn.commit()
        
        # Insert relationships
        with conn.cursor() as cur:
            for rel in relationships:
                source_id = entity_id_map.get(rel["source"])
                # Note: target_id would need lookup in full implementation
                # For now, we skip relationships without resolved IDs
                pass
        
        total_relationships += len(relationships)
    
    print(f"\nIndexing complete!")
    print(f"  Files processed: {len(files)}")
    print(f"  Entities created: {total_entities}")
    print(f"  Relationships found: {total_relationships}")
    print(f"  Errors: {len(errors)}")
    
    # Get final stats
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT entity_type, COUNT(*) as count
            FROM archon_code_entities
            WHERE repo_id = %s
            GROUP BY entity_type
        """, (repo_id,))
        by_type = {r["entity_type"]: r["count"] for r in cur.fetchall()}
    
    print(f"\nRepository stats:")
    print(f"  Total entities: {total_entities}")
    print(f"  By type: {by_type}")
    
    conn.close()
    
    return {
        "processed": len(files),
        "entities_created": total_entities,
        "relationships_created": total_relationships,
        "errors": errors,
    }


def get_repos_from_db() -> list[dict]:
    """Get all repositories from database."""
    conn = get_db_connection()
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT id, name, local_path, github_owner, github_repo, github_url
            FROM archon_code_repos
            ORDER BY name
        """)
        repos = cur.fetchall()
    
    conn.close()
    return repos


def main():
    """Main entry point."""
    target_repo = sys.argv[1] if len(sys.argv) > 1 else "all"
    
    print("=" * 70)
    print("Repository Indexing Tool (Simple)")
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
        if not Path(repo['local_path']).exists():
            print(f"\nError: Path does not exist: {repo['local_path']}")
            continue
        
        results = index_repository(
            repo_id=str(repo['id']),
            repo_name=repo['name'],
            repo_path=repo['local_path'],
        )
        
        if 'error' in results:
            print(f"\nFailed to index {repo['name']}: {results['error']}")


if __name__ == "__main__":
    main()
