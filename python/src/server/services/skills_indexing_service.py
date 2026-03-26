"""Skills Indexing Service for ADR-015.

Indexes the skills/ directory into the knowledge base, making it searchable
via semantic search. Skills are versioned with the codebase and stored as
document blobs in archon_document_blobs.
"""

import hashlib
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.server.config.logfire_config import get_logger
from src.server.services.database import get_database_connector
from src.server.services.chunking.chunkers import (
    MarkdownAwareChunker,
    BasicChunker,
)
from src.server.services.chunking.chunker_base import BaseChunker

logger = get_logger(__name__)

SKILLS_EXTENSIONS = frozenset({".md", ".rst", ".org", ".norg"})

SKILLS_CATEGORIES = frozenset(
    {
        "commit-hooks",
        "ide-setup",
        "mcp",
        "prompts",
        "workflows",
    }
)


@dataclass
class SkillFile:
    """Represents a skill file with metadata."""

    path: str
    category: str
    name: str
    content: str
    content_hash: str
    size: int


@dataclass
class IndexResult:
    """Result of indexing a skill file."""

    path: str
    status: str  # indexed, skipped, error
    chunks_created: int = 0
    error: str | None = None


def _compute_hash(content: str) -> str:
    """Compute SHA256 hash of content."""
    return hashlib.sha256(content.encode()).hexdigest()


def _extract_category(path: Path, skills_root: Path) -> str:
    """Extract skill category from relative path."""
    rel_path = path.relative_to(skills_root)
    parts = rel_path.parts
    if len(parts) > 1:
        return parts[0]
    return "uncategorized"


def _extract_name(path: Path) -> str:
    """Extract skill name from filename."""
    return path.stem.replace("-", "_").replace(" ", "_")


def discover_skills(
    skills_root: str | Path | None = None,
    extensions: frozenset[str] = SKILLS_EXTENSIONS,
) -> list[SkillFile]:
    """Discover all skill files in the skills/ directory.

    Args:
        skills_root: Path to skills directory (default: project_root/skills)
        extensions: File extensions to include

    Returns:
        List of SkillFile objects
    """
    if skills_root is None:
        # Find project root
        cwd = Path.cwd()
        for parent in [cwd, *cwd.parents]:
            if (parent / "skills").exists():
                skills_root = parent / "skills"
                break
        if skills_root is None:
            skills_root = Path("skills")

    skills_root = Path(skills_root)
    if not skills_root.exists():
        logger.warning(f"Skills directory not found: {skills_root}")
        return []

    skill_files = []
    for ext in extensions:
        for path in skills_root.rglob(f"*{ext}"):
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                if not content.strip():
                    continue

                skill_files.append(
                    SkillFile(
                        path=str(path.relative_to(skills_root.parent)),
                        category=_extract_category(path, skills_root),
                        name=_extract_name(path),
                        content=content,
                        content_hash=_compute_hash(content),
                        size=len(content),
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to read skill file {path}: {e}")

    logger.info(f"Discovered {len(skill_files)} skill files")
    return skill_files


def _get_chunker_for_file(path: Path) -> BaseChunker:
    """Get appropriate chunker based on file extension."""
    suffix = path.suffix.lower()

    if suffix == ".md":
        return MarkdownAwareChunker(chunk_size=5000)
    else:
        return BasicChunker(chunk_size=5000)


async def index_skill_file(
    skill: SkillFile,
    repo_id: str,
    commit_sha: str | None = None,
) -> IndexResult:
    """Index a single skill file into the knowledge base.

    Args:
        skill: SkillFile to index
        repo_id: Repository UUID
        commit_sha: Current commit SHA

    Returns:
        IndexResult with status
    """
    try:
        db = get_database_connector()

        # Check if already indexed with same hash
        existing = await db.fetchrow(
            """
            SELECT id, content_hash FROM archon_document_blobs
            WHERE source_id = $1 AND blob_uri = $2
            ORDER BY created_at DESC LIMIT 1
            """,
            repo_id,
            skill.path,
        )

        if existing and existing["content_hash"] == skill.content_hash:
            return IndexResult(
                path=skill.path,
                status="unchanged",
            )

        # Chunk the skill content
        chunker = _get_chunker_for_file(Path(skill.path))
        chunks = chunker.chunk(skill.content)

        # Create or update blob record
        blob_id = str(uuid.uuid4())
        await db.execute(
            """
            INSERT INTO archon_document_blobs
            (id, source_id, source_type, blob_uri, content_hash, content_length, download_status)
            VALUES ($1, $2, 'skill', $3, $4, $5, 'downloaded')
            ON CONFLICT (source_id, blob_uri)
            DO UPDATE SET
                content_hash = $4,
                content_length = $5,
                updated_at = NOW()
            RETURNING id
            """,
            blob_id,
            repo_id,
            skill.path,
            skill.content_hash,
            skill.size,
        )

        # Insert chunks
        chunk_count = 0
        for chunk in chunks:
            token_count = len(chunk.content.split()) * 4 // 3
            await db.execute(
                """
                INSERT INTO archon_chunks
                (blob_id, chunk_index, content, token_count, source, commit_sha, file_path)
                VALUES ($1, $2, $3, $4, 'skill', $5, $6)
                """,
                blob_id,
                chunk.index,
                chunk.content,
                token_count,
                commit_sha,
                skill.path,
            )
            chunk_count += 1

        return IndexResult(
            path=skill.path,
            status="indexed",
            chunks_created=chunk_count,
        )

    except Exception as e:
        logger.error(f"Failed to index skill {skill.path}: {e}")
        return IndexResult(
            path=skill.path,
            status="error",
            error=str(e),
        )


async def index_all_skills(
    repo_id: str,
    commit_sha: str | None = None,
    skills_root: str | Path | None = None,
) -> list[IndexResult]:
    """Index all skills in the skills/ directory.

    Args:
        repo_id: Repository UUID
        commit_sha: Current commit SHA
        skills_root: Path to skills directory

    Returns:
        List of IndexResult for each processed file
    """
    skills = discover_skills(skills_root)
    results = []

    for skill in skills:
        result = await index_skill_file(skill, repo_id, commit_sha)
        results.append(result)

    indexed = sum(1 for r in results if r.status == "indexed")
    unchanged = sum(1 for r in results if r.status == "unchanged")
    errors = sum(1 for r in results if r.status == "error")

    logger.info(f"Skills indexing complete: {indexed} indexed, {unchanged} unchanged, {errors} errors")

    return results


async def delete_skill_chunks(
    repo_id: str,
    skill_path: str,
) -> int:
    """Delete chunks for a skill file.

    Args:
        repo_id: Repository UUID
        skill_path: Path to skill file

    Returns:
        Number of chunks deleted
    """
    try:
        db = get_database_connector()

        # Get blob ID
        blob = await db.fetchrow(
            "SELECT id FROM archon_document_blobs WHERE source_id = $1 AND blob_uri = $2",
            repo_id,
            skill_path,
        )

        if not blob:
            return 0

        # Delete chunks
        result = await db.fetchval(
            "DELETE FROM archon_chunks WHERE blob_id = $1 RETURNING COUNT(*)",
            blob["id"],
        )

        # Delete blob
        await db.execute(
            "DELETE FROM archon_document_blobs WHERE id = $1",
            blob["id"],
        )

        return result or 0

    except Exception as e:
        logger.error(f"Failed to delete skill chunks for {skill_path}: {e}")
        return 0
