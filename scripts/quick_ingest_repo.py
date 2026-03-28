#!/usr/bin/env python3
"""
Quick repo ingestion - no fuss, no muss.

Usage:
    # Ingest current directory
    python scripts/quick_ingest_repo.py
    
    # Ingest specific repo
    python scripts/quick_ingest_repo.py /path/to/repo
    
    # Ingest with specific name
    python scripts/quick_ingest_repo.py /path/to/repo --name my-project

Environment:
    ARCHON_DATABASE_URL - PostgreSQL connection string
    OLLAMA_URL - Ollama endpoint (optional, for embeddings)
"""

import argparse
import asyncio
import os
import sys
import uuid
from pathlib import Path

# Add python to path
PYTHON_DIR = Path(__file__).parent.parent / "python"
sys.path.insert(0, str(PYTHON_DIR))

# Load environment from .env file
from dotenv import load_dotenv
ENV_FILE = Path(__file__).parent.parent / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)

import logging

from src.server.services.code_entity_service import CodeEntityService
from src.server.services.languages import get_language_for_file

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(message)s')


# Common files to skip
SKIP_PATTERNS = [
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "node_modules",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "dist",
    "build",
    ".egg-info",
    ".tox",
    ".coverage",
    "htmlcov",
]


def is_supported_file(path: Path) -> bool:
    """Check if file should be processed."""
    if any(part.startswith(".") or part in SKIP_PATTERNS for part in path.parts):
        return False
    return get_language_for_file(str(path)) is not None


def discover_files(repo_path: Path) -> list[str]:
    """Discover all supported source files in repo."""
    files = []
    
    # Priority: Python, TypeScript/JavaScript, and Nim files
    extensions = [".py", ".ts", ".tsx", ".js", ".jsx", ".nim", ".nims", ".nimble"]
    
    for ext in extensions:
        for file_path in repo_path.rglob(f"*{ext}"):
            if is_supported_file(file_path):
                files.append(str(file_path.relative_to(repo_path)))
    
    return files


class SimpleFileProvider:
    """Simple file content provider that reads from disk."""
    
    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
    
    async def get_content(self, repo_id: str, commit_sha: str, file_path: str) -> str:
        """Read file content from disk."""
        full_path = self.repo_path / file_path
        try:
            return full_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logger.warning(f"Failed to read {file_path}: {e}")
            return ""


async def ingest_repository(repo_path: Path, name: str | None = None) -> dict:
    """
    Ingest a repository into Archon.
    
    Args:
        repo_path: Path to repository
        name: Optional name for the repo
        
    Returns:
        Ingestion results
    """
    logger.info(f"🔍 Scanning {repo_path}...")
    
    # Generate repo ID
    repo_id = str(uuid.uuid4())
    repo_name = name or repo_path.name
    
    # Discover files
    files = discover_files(repo_path)
    logger.info(f"📁 Found {len(files)} source files")
    
    if not files:
        return {"status": "error", "message": "No supported files found"}
    
    # Show file breakdown
    by_ext = {}
    for f in files:
        ext = Path(f).suffix
        by_ext[ext] = by_ext.get(ext, 0) + 1
    
    for ext, count in sorted(by_ext.items(), key=lambda x: -x[1]):
        logger.info(f"  {ext}: {count} files")
    
    # Initialize service
    service = CodeEntityService()
    file_provider = SimpleFileProvider(repo_path)
    
    # Extract and store
    logger.info("🚀 Starting extraction...")
    
    results = await service.extract_and_store_entities(
        repo_id=repo_id,
        commit_sha="HEAD",  # Could get actual git HEAD
        file_paths=files,
        file_content_getter=file_provider.get_content,
    )
    
    # Get stats
    stats = await service.get_repository_stats(repo_id)
    
    return {
        "status": "success",
        "repo_id": repo_id,
        "repo_name": repo_name,
        "files_processed": results["processed"],
        "entities_created": results["entities_created"],
        "relationships_created": results["relationships_created"],
        "errors": len(results["errors"]),
        "stats": stats,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Quickly ingest a code repository into Archon",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Ingest current directory
  %(prog)s /path/to/project         # Ingest specific directory
  %(prog)s . --name my-app          # Ingest with custom name
        """,
    )
    
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to repository (default: current directory)",
    )
    parser.add_argument(
        "--name",
        help="Name for the repository (default: directory name)",
    )
    parser.add_argument(
        "--embeddings",
        action="store_true",
        help="Generate embeddings (requires Ollama)",
    )
    parser.add_argument(
        "--model",
        default="nomic-embed-text",
        help="Embedding model to use (default: nomic-embed-text)",
    )
    
    args = parser.parse_args()
    
    repo_path = Path(args.path).resolve()
    
    if not repo_path.exists():
        print(f"❌ Path does not exist: {repo_path}", file=sys.stderr)
        sys.exit(1)
    
    if not repo_path.is_dir():
        print(f"❌ Path is not a directory: {repo_path}", file=sys.stderr)
        sys.exit(1)
    
    # Run ingestion
    result = asyncio.run(ingest_repository(repo_path, args.name))
    
    if result["status"] == "error":
        print(f"❌ {result['message']}", file=sys.stderr)
        sys.exit(1)
    
    # Print results
    print("\n" + "=" * 50)
    print(f"✅ Ingestion Complete: {result['repo_name']}")
    print("=" * 50)
    print(f"Repo ID: {result['repo_id']}")
    print(f"Files processed: {result['files_processed']}")
    print(f"Entities created: {result['entities_created']}")
    print(f"Relationships: {result['relationships_created']}")
    print(f"Errors: {result['errors']}")
    
    if result['stats'].get('by_type'):
        print("\n📊 Entities by type:")
        for t, count in sorted(result['stats']['by_type'].items(), key=lambda x: -x[1]):
            print(f"  {t}: {count}")
    
    if result['stats'].get('by_language'):
        print("\n🌐 By language:")
        for lang, count in sorted(result['stats']['by_language'].items(), key=lambda x: -x[1]):
            print(f"  {lang}: {count}")
    
    print("\n💡 Next steps:")
    print(f"  - Query: archon_repo_stats('{result['repo_id']}')")
    print(f"  - Search: archon_find_entity('{result['repo_id']}', 'function_name')")
    
    return result['repo_id']


if __name__ == "__main__":
    main()
