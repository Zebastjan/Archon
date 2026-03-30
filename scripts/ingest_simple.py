#!/usr/bin/env python3
"""Minimal repo ingestion without dotenv dependency."""
import argparse
import asyncio
import os
import sys
import uuid
from pathlib import Path

# Add python to path
PYTHON_DIR = Path(__file__).parent.parent / "python"
sys.path.insert(0, str(PYTHON_DIR))

# Set environment directly
os.environ["ARCHON_DATABASE_URL"] = "postgresql://archon:archon@localhost:5432/archon"

import logging
from src.server.services.code_entity_service import CodeEntityService
from src.server.services.languages import get_language_for_file

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(message)s')

SKIP_PATTERNS = [
    "__pycache__", ".git", ".venv", "venv", "node_modules",
    ".pytest_cache", ".ruff_cache", ".mypy_cache", "dist", "build",
    ".egg-info", ".tox", ".coverage", "htmlcov", ".archon",
]

def is_supported_file(path: Path) -> bool:
    if any(part.startswith(".") or part in SKIP_PATTERNS for part in path.parts):
        return False
    return get_language_for_file(str(path)) is not None

def discover_files(repo_path: Path) -> list[str]:
    files = []
    extensions = [".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs"]
    for ext in extensions:
        for file_path in repo_path.rglob(f"*{ext}"):
            if is_supported_file(file_path):
                files.append(str(file_path.relative_to(repo_path)))
    return files

class SimpleFileProvider:
    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
    
    async def get_content(self, repo_id: str, commit_sha: str, file_path: str) -> str:
        full_path = self.repo_path / file_path
        try:
            return full_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logger.warning(f"Failed to read {file_path}: {e}")
            return ""

async def ingest_repository(repo_path: Path, name: str | None = None) -> dict:
    logger.info(f"🔍 Scanning {repo_path}...")
    
    repo_id = str(uuid.uuid4())
    repo_name = name or repo_path.name
    
    files = discover_files(repo_path)
    logger.info(f"📁 Found {len(files)} source files")
    
    if not files:
        return {"status": "error", "message": "No supported files found"}
    
    by_ext = {}
    for f in files:
        ext = Path(f).suffix
        by_ext[ext] = by_ext.get(ext, 0) + 1
    
    for ext, count in sorted(by_ext.items(), key=lambda x: -x[1]):
        logger.info(f"  {ext}: {count} files")
    
    service = CodeEntityService()
    file_provider = SimpleFileProvider(repo_path)
    
    logger.info("🚀 Starting extraction...")
    
    results = await service.extract_and_store_entities(
        repo_id=repo_id,
        commit_sha="HEAD",
        file_paths=files,
        file_content_getter=file_provider.get_content,
    )
    
    return {
        "status": "success",
        "repo_id": repo_id,
        "repo_name": repo_name,
        "files_processed": results["processed"],
        "entities_created": results["entities_created"],
        "relationships_created": results["relationships_created"],
        "errors": len(results["errors"]),
    }

def main():
    parser = argparse.ArgumentParser(description="Quick repo ingestion")
    parser.add_argument("path", nargs="?", default=".", help="Path to repository")
    parser.add_argument("--name", help="Name for the repository")
    args = parser.parse_args()
    
    repo_path = Path(args.path).resolve()
    
    if not repo_path.exists():
        print(f"❌ Path does not exist: {repo_path}", file=sys.stderr)
        sys.exit(1)
    
    if not repo_path.is_dir():
        print(f"❌ Path is not a directory: {repo_path}", file=sys.stderr)
        sys.exit(1)
    
    result = asyncio.run(ingest_repository(repo_path, args.name))
    
    if result["status"] == "error":
        print(f"❌ {result['message']}", file=sys.stderr)
        sys.exit(1)
    
    print("\n" + "=" * 50)
    print(f"✅ Ingestion Complete: {result['repo_name']}")
    print("=" * 50)
    print(f"Repo ID: {result['repo_id']}")
    print(f"Files processed: {result['files_processed']}")
    print(f"Entities created: {result['entities_created']}")
    print(f"Relationships: {result['relationships_created']}")
    print(f"Errors: {result['errors']}")
    print(f"\n💡 Use this repo_id with MCP tools: {result['repo_id']}")

if __name__ == "__main__":
    main()
