"""
Tests for Git-Aware RAG Integration (Phase 2 Week 4)

Verifies that Git commit search is properly integrated into the RAG pipeline.
"""

import sys
from unittest.mock import MagicMock, AsyncMock, patch

# Mock modules before importing
sys.modules['openai'] = MagicMock()
sys.modules['src.server.db_connector'] = MagicMock()
sys.modules['src.server.services.embeddings'] = MagicMock()
sys.modules['src.server.services.embeddings.embedding_service'] = MagicMock()
sys.modules['src.server.services.embeddings.embedding_service'].create_embedding = AsyncMock(return_value=[0.1] * 1536)

import pytest
from datetime import datetime

from src.server.services.search.rag_service import RAGService
from src.server.services.search.git_search_strategy import GitSearchStrategy


@pytest.mark.asyncio
class TestGitSearchStrategy:
    """Test the Git search strategy integration."""

    async def test_git_strategy_initialization(self, supabase_client):
        """Test that GitSearchStrategy initializes correctly."""
        strategy = GitSearchStrategy(supabase_client)

        assert strategy.supabase_client is not None
        assert strategy.git_search is not None

    async def test_format_commit_content(self, supabase_client):
        """Test commit content formatting for RAG."""
        from dataclasses import dataclass
        from typing import Any

        @dataclass
        class MockCommitResult:
            commit_sha: str = "abc123def"
            message: str = "Fix authentication bug"
            author_name: str = "Test Author"
            author_email: str = "test@example.com"
            commit_date: datetime = datetime(2024, 1, 15)
            branches: list[str] = None
            classification: dict[str, Any] = None
            similarity_score: float = 0.85
            embedding_dimension: int = 1536
            diff_summary: str = "Fixed login validation"

            def __post_init__(self):
                if self.branches is None:
                    self.branches = ["main"]
                if self.classification is None:
                    self.classification = {"intent": "bugfix", "risk_level": "medium"}

        strategy = GitSearchStrategy(supabase_client)
        mock_result = MockCommitResult()

        content = strategy._format_commit_content(mock_result)

        assert "Commit: abc123de" in content
        assert "Message: Fix authentication bug" in content
        assert "Type: bugfix (risk: medium)" in content
        assert "Author: Test Author" in content
        assert "Date: 2024-01-15" in content
        assert "Branches: main" in content


@pytest.mark.asyncio
class TestRAGServiceGitIntegration:
    """Test Git integration into RAG service."""

    async def test_rag_service_has_git_strategy(self, supabase_client):
        """Test that RAG service includes Git strategy."""
        rag_service = RAGService(supabase_client)

        assert hasattr(rag_service, 'git_strategy')
        assert isinstance(rag_service.git_strategy, GitSearchStrategy)

    async def test_search_git_commits_basic(self, supabase_client, test_repo_id):
        """Test basic Git commit search through RAG service."""
        rag_service = RAGService(supabase_client)

        # Mock the git_strategy.search_commits method
        mock_commits = [
            {
                "type": "git_commit",
                "commit_sha": "abc123",
                "message": "Fix authentication bug",
                "author": "Test Author",
                "similarity_score": 0.85,
            },
            {
                "type": "git_commit",
                "commit_sha": "def456",
                "message": "Fix validation issue",
                "author": "Another Author",
                "similarity_score": 0.75,
            },
        ]

        with patch.object(rag_service.git_strategy, 'search_commits', new=AsyncMock(return_value=mock_commits)):
            success, result = await rag_service.search_git_commits(
                query="bug fix",
                match_count=5,
                repo_id=test_repo_id,
            )

        assert success is True
        assert "results" in result
        assert "count" in result
        assert result["query"] == "bug fix"
        assert result["count"] == 2
        assert len(result["results"]) == 2

    async def test_search_with_git_context(self, supabase_client, test_repo_id):
        """Test combined document + Git search."""
        rag_service = RAGService(supabase_client)

        # Mock document search results
        mock_documents = [
            {
                "id": 1,
                "content": "Authentication documentation",
                "metadata": {"type": "documentation"},
            }
        ]

        # Mock git commit results
        mock_git_commits = [
            {
                "type": "git_commit",
                "commit_sha": "abc123",
                "message": "Improve authentication flow",
                "similarity_score": 0.9,
            }
        ]

        with patch.object(rag_service.base_strategy, 'vector_search', new=AsyncMock(return_value=mock_documents)), \
             patch.object(rag_service.git_strategy, 'search_commits', new=AsyncMock(return_value=mock_git_commits)):
            success, result = await rag_service.search_with_git_context(
                query="authentication",
                match_count=5,
                include_git_commits=True,
                git_match_count=3,
                repo_id=test_repo_id,
            )

        assert success is True
        assert "document_results" in result
        assert "git_results" in result
        assert "document_count" in result
        assert "git_count" in result
        assert result["document_count"] == 1
        assert result["git_count"] == 1

    async def test_get_file_history_context(self, supabase_client, test_repo_id):
        """Test file history retrieval."""
        rag_service = RAGService(supabase_client)

        # Mock file history results
        mock_file_history = [
            {
                "type": "git_commit_file_change",
                "commit_sha": "abc123",
                "message": "Update README.md",
                "file_path": "README.md",
                "commit_date": "2024-01-15T10:00:00",
            },
            {
                "type": "git_commit_file_change",
                "commit_sha": "def456",
                "message": "Initial README.md",
                "file_path": "README.md",
                "commit_date": "2024-01-01T10:00:00",
            },
        ]

        with patch.object(rag_service.git_strategy, 'search_commits_for_file', new=AsyncMock(return_value=mock_file_history)):
            success, result = await rag_service.get_file_history_context(
                file_path="README.md",
                repo_id=test_repo_id,
                match_count=10,
            )

        assert success is True
        assert "commits" in result
        assert "file_path" in result
        assert result["file_path"] == "README.md"
        assert len(result["commits"]) == 2

    async def test_get_commit_context_for_rag(self, supabase_client, test_repo_id, test_commit_sha):
        """Test commit context retrieval for RAG."""
        rag_service = RAGService(supabase_client)

        # Mock commit context
        mock_context = {
            "commit_sha": test_commit_sha,
            "message": "Fix authentication bug",
            "author": "Test Author",
            "author_email": "test@example.com",
            "commit_date": "2024-01-15T10:00:00",
            "files_changed": 3,
            "files": [
                {"path": "src/auth.py", "is_binary": False},
                {"path": "tests/test_auth.py", "is_binary": False},
                {"path": "README.md", "is_binary": False},
            ],
            "classification": {"intent": "bugfix", "risk_level": "medium"},
        }

        with patch.object(rag_service.git_strategy, 'get_commit_context', new=AsyncMock(return_value=mock_context)):
            success, result = await rag_service.get_commit_context_for_rag(
                commit_sha=test_commit_sha,
                repo_id=test_repo_id,
            )

        assert success is True
        assert "commit_sha" in result
        assert "message" in result
        assert "files_changed" in result
        assert result["commit_sha"] == test_commit_sha
        assert result["files_changed"] == 3


@pytest.mark.asyncio
class TestGitRAGErrorHandling:
    """Test error handling in Git RAG integration."""

    async def test_search_commits_with_invalid_date(self, supabase_client):
        """Test handling of invalid date filters."""
        rag_service = RAGService(supabase_client)

        # Invalid ISO date should be handled gracefully
        success, result = await rag_service.search_git_commits(
            query="test",
            since="invalid-date",
        )

        # Should either fail with error or handle gracefully
        assert "error" in result or success is False

    async def test_get_commit_context_not_found(self, supabase_client):
        """Test handling of non-existent commit."""
        rag_service = RAGService(supabase_client)

        success, result = await rag_service.get_commit_context_for_rag(
            commit_sha="nonexistent123456",
            repo_id="test-repo-id",
        )

        assert success is False
        assert "error" in result


@pytest.mark.asyncio
class TestGitRAGFiltering:
    """Test filtering capabilities in Git RAG search."""

    async def test_filter_by_intent(self, supabase_client, test_repo_id):
        """Test filtering commits by intent (feature, bugfix, etc.)."""
        rag_service = RAGService(supabase_client)

        # Mock commits with intent classification
        mock_commits = [
            {
                "type": "git_commit",
                "commit_sha": "abc123",
                "message": "Add new feature",
                "classification": {"intent": "feature", "risk_level": "medium"},
                "similarity_score": 0.85,
            },
            {
                "type": "git_commit",
                "commit_sha": "def456",
                "message": "Fix bug",
                "classification": {"intent": "bugfix", "risk_level": "low"},
                "similarity_score": 0.75,
            },
        ]

        with patch.object(rag_service.git_strategy, 'search_commits', new=AsyncMock(return_value=mock_commits)):
            success, result = await rag_service.search_git_commits(
                query="changes",
                match_count=10,
                repo_id=test_repo_id,
                intent_filter=["feature", "bugfix"],
            )

        assert success is True
        # Verify results only contain specified intents
        for commit in result["results"]:
            if commit.get("classification"):
                assert commit["classification"].get("intent") in ["feature", "bugfix"]

    async def test_filter_by_risk_level(self, supabase_client, test_repo_id):
        """Test filtering commits by risk level."""
        rag_service = RAGService(supabase_client)

        # Mock commits with high risk level
        mock_commits = [
            {
                "type": "git_commit",
                "commit_sha": "abc123",
                "message": "Major refactoring",
                "classification": {"intent": "refactor", "risk_level": "high"},
                "similarity_score": 0.9,
            },
            {
                "type": "git_commit",
                "commit_sha": "def456",
                "message": "Breaking change to API",
                "classification": {"intent": "feature", "risk_level": "high"},
                "similarity_score": 0.85,
            },
        ]

        with patch.object(rag_service.git_strategy, 'search_commits', new=AsyncMock(return_value=mock_commits)):
            success, result = await rag_service.search_git_commits(
                query="changes",
                match_count=10,
                repo_id=test_repo_id,
                risk_filter=["high"],
            )

        assert success is True
        # Verify results only contain high risk commits
        for commit in result["results"]:
            if commit.get("classification"):
                assert commit["classification"].get("risk_level") == "high"

    async def test_filter_by_branch(self, supabase_client, test_repo_id):
        """Test filtering commits by branch."""
        rag_service = RAGService(supabase_client)

        # Mock commits from main branch
        mock_commits = [
            {
                "type": "git_commit",
                "commit_sha": "abc123",
                "message": "Main branch commit",
                "branches": ["main"],
                "similarity_score": 0.85,
            },
            {
                "type": "git_commit",
                "commit_sha": "def456",
                "message": "Another main commit",
                "branches": ["main", "develop"],
                "similarity_score": 0.75,
            },
        ]

        with patch.object(rag_service.git_strategy, 'search_commits', new=AsyncMock(return_value=mock_commits)):
            success, result = await rag_service.search_git_commits(
                query="changes",
                match_count=10,
                repo_id=test_repo_id,
                branch="main",
            )

        assert success is True
        # Verify results only contain commits from main branch
        for commit in result["results"]:
            assert "main" in commit.get("branches", [])

    async def test_filter_breaking_only(self, supabase_client, test_repo_id):
        """Test filtering for breaking changes only."""
        rag_service = RAGService(supabase_client)

        # Mock commits with breaking changes
        mock_commits = [
            {
                "type": "git_commit",
                "commit_sha": "abc123",
                "message": "BREAKING: Remove deprecated API",
                "classification": {"intent": "feature", "risk_level": "high", "breaking_change": True},
                "similarity_score": 0.95,
            },
            {
                "type": "git_commit",
                "commit_sha": "def456",
                "message": "BREAKING: Change authentication flow",
                "classification": {"intent": "refactor", "risk_level": "high", "breaking_change": True},
                "similarity_score": 0.9,
            },
        ]

        with patch.object(rag_service.git_strategy, 'search_commits', new=AsyncMock(return_value=mock_commits)):
            success, result = await rag_service.search_git_commits(
                query="changes",
                match_count=10,
                repo_id=test_repo_id,
                breaking_only=True,
            )

        assert success is True
        # Verify results only contain breaking changes
        for commit in result["results"]:
            if commit.get("classification"):
                assert commit["classification"].get("breaking_change") is True

    async def test_filter_security_only(self, supabase_client, test_repo_id):
        """Test filtering for security-related commits only."""
        rag_service = RAGService(supabase_client)

        # Mock security-related commits
        mock_commits = [
            {
                "type": "git_commit",
                "commit_sha": "abc123",
                "message": "Fix SQL injection vulnerability",
                "classification": {"intent": "security", "risk_level": "high", "security_relevant": True},
                "similarity_score": 0.95,
            },
            {
                "type": "git_commit",
                "commit_sha": "def456",
                "message": "Patch authentication bypass",
                "classification": {"intent": "security", "risk_level": "critical", "security_relevant": True},
                "similarity_score": 0.92,
            },
        ]

        with patch.object(rag_service.git_strategy, 'search_commits', new=AsyncMock(return_value=mock_commits)):
            success, result = await rag_service.search_git_commits(
                query="changes",
                match_count=10,
                repo_id=test_repo_id,
                security_only=True,
            )

        assert success is True
        # Verify results only contain security-related commits
        for commit in result["results"]:
            if commit.get("classification"):
                assert commit["classification"].get("security_relevant") is True


@pytest.mark.asyncio
class TestGitRAGIntegrationExtended:
    """Additional RAG integration tests."""
    
    async def test_search_git_commits_with_author_filter(self, supabase_client):
        """Test filtering commits by author."""
        rag_service = RAGService(supabase_client)

        # Mock commits from specific author
        mock_commits = [
            {
                "type": "git_commit",
                "commit_sha": "abc123",
                "message": "Add new feature",
                "author": "Test Author",
                "author_email": "test@example.com",
                "similarity_score": 0.85,
            },
        ]

        with patch.object(rag_service.git_strategy, 'search_commits', new=AsyncMock(return_value=mock_commits)):
            success, result = await rag_service.search_git_commits(
                query="changes",
                author="test@example.com",
            )

        assert success is True
        assert "results" in result
        for commit in result["results"]:
            assert commit["author_email"] == "test@example.com"
    
    async def test_search_git_commits_time_range(self, supabase_client):
        """Test searching commits within time range."""
        rag_service = RAGService(supabase_client)

        # Mock commits within time range
        mock_commits = [
            {
                "type": "git_commit",
                "commit_sha": "abc123",
                "message": "Add feature X",
                "commit_date": "2024-03-15T10:00:00",
                "similarity_score": 0.85,
            },
            {
                "type": "git_commit",
                "commit_sha": "def456",
                "message": "Add feature Y",
                "commit_date": "2024-05-20T14:30:00",
                "similarity_score": 0.8,
            },
        ]

        with patch.object(rag_service.git_strategy, 'search_commits', new=AsyncMock(return_value=mock_commits)):
            success, result = await rag_service.search_git_commits(
                query="feature",
                since="2024-01-01",
                until="2024-06-30",
            )

        assert success is True
        assert "results" in result
        assert len(result["results"]) == 2
    
    async def test_empty_git_search_query(self, supabase_client):
        """Test handling of empty query."""
        rag_service = RAGService(supabase_client)

        # Mock empty results for empty query
        with patch.object(rag_service.git_strategy, 'search_commits', new=AsyncMock(return_value=[])):
            success, result = await rag_service.search_git_commits(query="")

        assert isinstance(success, bool)
        assert "results" in result


# Fixtures for tests
@pytest.fixture
def test_repo_id():
    """Fixture providing a test repository ID."""
    return "embedded-test-repo-id"


@pytest.fixture
def test_commit_sha():
    """Fixture providing a test commit SHA."""
    return "abc123def456"
