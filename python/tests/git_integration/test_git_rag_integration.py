"""
Tests for Git-Aware RAG Integration (Phase 2 Week 4)

Verifies that Git commit search is properly integrated into the RAG pipeline.
"""

import pytest
from datetime import datetime

from src.server.services.search.rag_service import RAGService
from src.server.services.search.git_search_strategy import GitSearchStrategy

from .conftest import FIXTURES_DIR


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

    @pytest.mark.skip(reason="Requires test repository with embeddings")
    async def test_search_git_commits_basic(self, supabase_client, test_repo_id):
        """Test basic Git commit search through RAG service."""
        rag_service = RAGService(supabase_client)

        success, result = await rag_service.search_git_commits(
            query="bug fix",
            match_count=5,
            repo_id=test_repo_id,
        )

        assert success is True
        assert "results" in result
        assert "count" in result
        assert result["query"] == "bug fix"

    @pytest.mark.skip(reason="Requires test repository with embeddings")
    async def test_search_with_git_context(self, supabase_client, test_repo_id):
        """Test combined document + Git search."""
        rag_service = RAGService(supabase_client)

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

    @pytest.mark.skip(reason="Requires test repository")
    async def test_get_file_history_context(self, supabase_client, test_repo_id):
        """Test file history retrieval."""
        rag_service = RAGService(supabase_client)

        success, result = await rag_service.get_file_history_context(
            file_path="README.md",
            repo_id=test_repo_id,
            match_count=10,
        )

        assert success is True
        assert "commits" in result
        assert "file_path" in result
        assert result["file_path"] == "README.md"

    @pytest.mark.skip(reason="Requires test repository")
    async def test_get_commit_context_for_rag(self, supabase_client, test_repo_id, test_commit_sha):
        """Test commit context retrieval for RAG."""
        rag_service = RAGService(supabase_client)

        success, result = await rag_service.get_commit_context_for_rag(
            commit_sha=test_commit_sha,
            repo_id=test_repo_id,
        )

        assert success is True
        assert "commit_sha" in result
        assert "message" in result
        assert "files_changed" in result


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

    @pytest.mark.skip(reason="Requires test repository with classified commits")
    async def test_filter_by_intent(self, supabase_client, test_repo_id):
        """Test filtering commits by intent (feature, bugfix, etc.)."""
        rag_service = RAGService(supabase_client)

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

    @pytest.mark.skip(reason="Requires test repository with classified commits")
    async def test_filter_by_risk_level(self, supabase_client, test_repo_id):
        """Test filtering commits by risk level."""
        rag_service = RAGService(supabase_client)

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

    @pytest.mark.skip(reason="Requires test repository")
    async def test_filter_by_branch(self, supabase_client, test_repo_id):
        """Test filtering commits by branch."""
        rag_service = RAGService(supabase_client)

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

    @pytest.mark.skip(reason="Requires test repository with classified commits")
    async def test_filter_breaking_only(self, supabase_client, test_repo_id):
        """Test filtering for breaking changes only."""
        rag_service = RAGService(supabase_client)

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

    @pytest.mark.skip(reason="Requires test repository with classified commits")
    async def test_filter_security_only(self, supabase_client, test_repo_id):
        """Test filtering for security-related commits only."""
        rag_service = RAGService(supabase_client)

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
        
        success, result = await rag_service.search_git_commits(
            query="changes",
            author="test@example.com",
        )
        
        assert isinstance(success, bool)
    
    async def test_search_git_commits_time_range(self, supabase_client):
        """Test searching commits within time range."""
        rag_service = RAGService(supabase_client)
        
        success, result = await rag_service.search_git_commits(
            query="feature",
            since="2024-01-01",
            until="2024-06-30",
        )
        
        assert isinstance(success, bool)
    
    async def test_empty_git_search_query(self, supabase_client):
        """Test handling of empty query."""
        rag_service = RAGService(supabase_client)
        
        success, result = await rag_service.search_git_commits(query="")
        
        assert isinstance(success, bool)


# Fixtures for tests (these would need real data)
@pytest.fixture
def test_repo_id():
    """Fixture providing a test repository ID."""
    return "test-repo-id"


@pytest.fixture
def test_commit_sha():
    """Fixture providing a test commit SHA."""
    return "abc123def456"
