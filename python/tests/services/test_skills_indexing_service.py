"""Tests for Skills Indexing Service."""

import pytest
import tempfile
from pathlib import Path

from src.server.services.skills_indexing_service import (
    SkillFile,
    discover_skills,
    _compute_hash,
    _extract_category,
    _extract_name,
    _get_chunker_for_file,
)


class TestComputeHash:
    """Test content hash computation."""

    def test_basic_hash(self):
        """Test basic hash computation."""
        content = "# Skill\n\nSkill content."
        hash1 = _compute_hash(content)
        hash2 = _compute_hash(content)
        assert hash1 == hash2
        assert len(hash1) == 64

    def test_different_content_different_hash(self):
        """Different content produces different hash."""
        hash1 = _compute_hash("# Skill A")
        hash2 = _compute_hash("# Skill B")
        assert hash1 != hash2


class TestExtractCategory:
    """Test category extraction from path."""

    def test_commit_hooks_category(self):
        """Commit hooks category is extracted."""
        root = Path("/project/skills")
        path = Path("/project/skills/commit-hooks/doc-maintenance.md")
        assert _extract_category(path, root) == "commit-hooks"

    def test_prompts_category(self):
        """Prompts category is extracted."""
        root = Path("/project/skills")
        path = Path("/project/skills/prompts/branch-discipline.md")
        assert _extract_category(path, root) == "prompts"

    def test_root_file_uncategorized(self):
        """File in root is uncategorized."""
        root = Path("/project/skills")
        path = Path("/project/skills/readme.md")
        assert _extract_category(path, root) == "uncategorized"


class TestExtractName:
    """Test name extraction from filename."""

    def test_basic_name(self):
        """Basic filename is converted to name."""
        path = Path("/skills/doc-maintenance.md")
        assert _extract_name(path) == "doc_maintenance"

    def test_kebab_case(self):
        """Kebab-case is converted to snake_case."""
        path = Path("/skills/test-coverage-check.md")
        assert _extract_name(path) == "test_coverage_check"


class TestGetChunker:
    """Test chunker selection."""

    def test_markdown_chunker(self):
        """Markdown files use MarkdownAwareChunker."""
        chunker = _get_chunker_for_file(Path("test.md"))
        assert chunker.__class__.__name__ == "MarkdownAwareChunker"

    def test_other_files_use_basic(self):
        """Other files use BasicChunker."""
        chunker = _get_chunker_for_file(Path("test.rst"))
        assert chunker.__class__.__name__ == "BasicChunker"


class TestDiscoverSkills:
    """Test skill file discovery."""

    def test_no_directory_returns_empty(self):
        """Missing directory returns empty list."""
        skills = discover_skills("/nonexistent/path")
        assert skills == []

    def test_discovers_markdown_files(self):
        """Markdown files in skills/ are discovered."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skills_dir = Path(tmpdir) / "skills"
            skills_dir.mkdir()

            # Create skill files
            (skills_dir / "test-skill.md").write_text("# Test Skill\n\nContent here.")
            (skills_dir / "nested").mkdir()
            (skills_dir / "nested" / "nested-skill.md").write_text("# Nested Skill")

            skills = discover_skills(skills_dir)
            assert len(skills) == 2
            assert all(s.path.endswith(".md") for s in skills)

    def test_ignores_empty_files(self):
        """Empty files are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skills_dir = Path(tmpdir) / "skills"
            skills_dir.mkdir()

            # Create empty file
            (skills_dir / "empty.md").write_text("")
            (skills_dir / "whitespace.md").write_text("   \n  ")
            (skills_dir / "content.md").write_text("# Has content")

            skills = discover_skills(skills_dir)
            assert len(skills) == 1
            assert skills[0].name == "content"
