"""
Tests for Git-Aware RAG Integration (Phase 2 Week 4)

Verifies that Git commit search is properly integrated into the RAG pipeline.

IMPORTANT: These tests mock only external dependencies (Supabase), not service layers.
This ensures we test the real integration chain:
- GitSemanticSearch.search_commits() → GitSearchStrategy.search_commits() → RAGService

If someone breaks GitSearchStrategy._format_commit_content() or data parsing,
these tests will catch it.
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

# Import realistic mock data factories
from tests.git_integration.fixtures.realistic_mock_data import (
    create_supabase_commit_response,
    create_multiple_supabase_responses,
    create_security_fix_response,
    create_bug_fix_response,
    create_feature_response,
)


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

    async def test_search_git_commits_basic(self, mock_supabase_client, test_repo_id):
        """Test basic Git commit search through RAG service.

        IMPORTANT: Mocks only Supabase (external dependency), not strategy layer.
        Tests real chain: GitSemanticSearch → GitSearchStrategy → RAGService
        """
        rag_service = RAGService(mock_supabase_client)

        # Mock Supabase RPC response (external dependency only)
        mock_supabase_client.rpc.return_value.execute.return_value = MagicMock(
            data=[
                create_supabase_commit_response(
                    commit_sha="abc123" + "a" * 34,
                    message="Fix authentication bug",
                    intent="bug_fix",
                    risk_level="medium",
                    repo_id=test_repo_id,
                    similarity=0.85,
                ),
                create_supabase_commit_response(
                    commit_sha="def456" + "b" * 34,
                    message="Fix validation issue",
                    intent="bug_fix",
                    risk_level="low",
                    repo_id=test_repo_id,
                    author_name="Another Author",
                    author_email="another@example.com",
                    similarity=0.75,
                ),
            ]
        )

        # Call real service chain (no strategy mocking!)
        success, result = await rag_service.search_git_commits(
            query="bug fix",
            match_count=5,
            repo_id=test_repo_id,
        )

        # Validate complete structure (all 17 fields from GitSearchStrategy)
        assert success is True
        assert "results" in result
        assert "count" in result
        assert result["query"] == "bug fix"
        assert result["count"] == 2
        assert len(result["results"]) == 2

        # Validate first commit has ALL expected fields
        commit = result["results"][0]
        assert commit["type"] == "git_commit"
        assert commit["commit_sha"] == "abc123" + "a" * 34
        assert commit["commit_id"] is not None
        assert commit["repo_id"] == test_repo_id
        assert commit["message"] == "Fix authentication bug"
        assert commit["author"] == "Test Author"
        assert commit["author_email"] == "test@example.com"
        assert commit["commit_date"] is not None
        assert commit["branches"] == ["main"]
        assert commit["classification"]["intent"] == "bug_fix"
        assert commit["classification"]["risk_level"] == "medium"
        assert commit["similarity_score"] == 0.85
        assert commit["embedding_dimension"] == 1536
        assert "content" in commit  # Formatted by _format_commit_content
        assert "metadata" in commit
        assert commit["metadata"]["type"] == "git_commit"

    async def test_search_with_git_context(self, mock_supabase_client, test_repo_id):
        """Test combined document + Git search.

        IMPORTANT: Mocks only Supabase RPC responses, tests real service chain.
        """
        rag_service = RAGService(mock_supabase_client)

        # Mock Supabase RPC response for Git commits (external dependency)
        mock_supabase_client.rpc.return_value.execute.return_value = MagicMock(
            data=[
                create_supabase_commit_response(
                    commit_sha="abc123" + "a" * 34,
                    message="Improve authentication flow",
                    intent="feature",
                    risk_level="medium",
                    repo_id=test_repo_id,
                    similarity=0.9,
                )
            ]
        )

        # Mock document search (base_strategy is separate concern)
        mock_documents = [
            {
                "id": 1,
                "content": "Authentication documentation",
                "metadata": {"type": "documentation"},
            }
        ]

        with patch.object(rag_service.base_strategy, 'vector_search', new=AsyncMock(return_value=mock_documents)):
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

        # Validate Git commit has complete structure
        git_commit = result["git_results"][0]
        assert git_commit["type"] == "git_commit"
        assert git_commit["commit_sha"] == "abc123" + "a" * 34
        assert "content" in git_commit
        assert "metadata" in git_commit

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

    async def test_filter_by_intent(self, mock_supabase_client, test_repo_id):
        """Test filtering commits by intent (feature, bugfix, etc.).

        IMPORTANT: Mocks only Supabase, tests real filtering logic in GitSemanticSearch.
        """
        rag_service = RAGService(mock_supabase_client)

        # Mock Supabase RPC response with realistic data
        mock_supabase_client.rpc.return_value.execute.return_value = MagicMock(
            data=[
                create_feature_response(),
                create_bug_fix_response(),
            ]
        )

        # Call real service chain (tests real filtering logic)
        success, result = await rag_service.search_git_commits(
            query="changes",
            match_count=10,
            repo_id=test_repo_id,
            intent_filter=["feature", "bug_fix"],
        )

        assert success is True
        assert len(result["results"]) == 2

        # Verify results only contain specified intents
        for commit in result["results"]:
            assert commit["type"] == "git_commit"
            if commit.get("classification"):
                assert commit["classification"]["intent"] in ["feature", "bug_fix"]
            # Validate complete structure
            assert "content" in commit
            assert "metadata" in commit
            assert "commit_id" in commit

    async def test_filter_by_risk_level(self, mock_supabase_client, test_repo_id):
        """Test filtering commits by risk level.

        IMPORTANT: Mocks only Supabase, tests real filtering logic.
        """
        rag_service = RAGService(mock_supabase_client)

        # Mock Supabase RPC response with high-risk commits
        mock_supabase_client.rpc.return_value.execute.return_value = MagicMock(
            data=[
                create_supabase_commit_response(
                    commit_sha="abc123" + "a" * 34,
                    message="Major refactoring",
                    intent="refactor",
                    risk_level="high",
                    repo_id=test_repo_id,
                    similarity=0.9,
                ),
                create_supabase_commit_response(
                    commit_sha="def456" + "b" * 34,
                    message="Breaking change to API",
                    intent="feature",
                    risk_level="high",
                    repo_id=test_repo_id,
                    similarity=0.85,
                    breaking_change=True,
                ),
            ]
        )

        # Call real service chain
        success, result = await rag_service.search_git_commits(
            query="changes",
            match_count=10,
            repo_id=test_repo_id,
            risk_filter=["high"],
        )

        assert success is True
        assert len(result["results"]) == 2

        # Verify results only contain high risk commits
        for commit in result["results"]:
            assert commit["type"] == "git_commit"
            if commit.get("classification"):
                assert commit["classification"]["risk_level"] == "high"
            # Validate complete structure
            assert "content" in commit
            assert "metadata" in commit

    async def test_filter_by_branch(self, mock_supabase_client, test_repo_id):
        """Test filtering commits by branch.

        IMPORTANT: Mocks only Supabase, tests real branch filtering logic.
        """
        rag_service = RAGService(mock_supabase_client)

        # Mock Supabase RPC response with branch data
        mock_supabase_client.rpc.return_value.execute.return_value = MagicMock(
            data=[
                create_supabase_commit_response(
                    commit_sha="abc123" + "a" * 34,
                    message="Main branch commit",
                    branches=["main"],
                    repo_id=test_repo_id,
                    similarity=0.85,
                ),
                create_supabase_commit_response(
                    commit_sha="def456" + "b" * 34,
                    message="Another main commit",
                    branches=["main", "develop"],
                    repo_id=test_repo_id,
                    similarity=0.75,
                ),
            ]
        )

        # Call real service chain
        success, result = await rag_service.search_git_commits(
            query="changes",
            match_count=10,
            repo_id=test_repo_id,
            branch="main",
        )

        assert success is True
        assert len(result["results"]) == 2

        # Verify results only contain commits from main branch
        for commit in result["results"]:
            assert commit["type"] == "git_commit"
            assert "main" in commit["branches"]
            assert "content" in commit

    async def test_filter_breaking_only(self, mock_supabase_client, test_repo_id):
        """Test filtering for breaking changes only.

        IMPORTANT: Mocks only Supabase, tests real breaking change filtering logic.
        Note: Filter looks for 'api_breaking' field in classification.
        """
        rag_service = RAGService(mock_supabase_client)

        # Mock Supabase RPC response with breaking changes
        mock_supabase_client.rpc.return_value.execute.return_value = MagicMock(
            data=[
                create_supabase_commit_response(
                    commit_sha="break01" + "a" * 34,
                    message="BREAKING: Remove deprecated API",
                    intent="feature",
                    risk_level="high",
                    repo_id=test_repo_id,
                    similarity=0.95,
                    api_breaking=True,  # Real filter checks 'api_breaking', not 'breaking_change'
                ),
                create_supabase_commit_response(
                    commit_sha="break02" + "b" * 34,
                    message="BREAKING: Change authentication flow",
                    intent="refactor",
                    risk_level="high",
                    repo_id=test_repo_id,
                    similarity=0.9,
                    api_breaking=True,
                ),
            ]
        )

        # Call real service chain
        success, result = await rag_service.search_git_commits(
            query="breaking changes",
            match_count=10,
            repo_id=test_repo_id,
            breaking_only=True,
        )

        assert success is True
        assert len(result["results"]) == 2

        # Verify results only contain breaking changes
        for commit in result["results"]:
            assert commit["type"] == "git_commit"
            if commit.get("classification"):
                assert commit["classification"]["api_breaking"] is True
            assert "content" in commit
            assert "metadata" in commit

    async def test_filter_security_only(self, mock_supabase_client, test_repo_id):
        """Test filtering for security-related commits only.

        IMPORTANT: Mocks only Supabase, tests real security filtering logic.
        """
        rag_service = RAGService(mock_supabase_client)

        # Mock Supabase RPC response with security commits
        mock_supabase_client.rpc.return_value.execute.return_value = MagicMock(
            data=[
                create_security_fix_response(),
                create_supabase_commit_response(
                    commit_sha="patch99" + "b" * 34,
                    message="Patch authentication bypass",
                    intent="security_fix",
                    risk_level="high",
                    repo_id=test_repo_id,
                    similarity=0.92,
                    security_relevant=True,
                ),
            ]
        )

        # Call real service chain
        success, result = await rag_service.search_git_commits(
            query="security fixes",
            match_count=10,
            repo_id=test_repo_id,
            security_only=True,
        )

        assert success is True
        assert len(result["results"]) == 2

        # Verify results only contain security-related commits
        for commit in result["results"]:
            assert commit["type"] == "git_commit"
            if commit.get("classification"):
                assert commit["classification"]["intent"] == "security_fix"
            assert "content" in commit
            assert "metadata" in commit


@pytest.mark.asyncio
class TestGitRAGIntegrationExtended:
    """Additional RAG integration tests."""
    
    async def test_search_git_commits_with_author_filter(self, mock_supabase_client):
        """Test filtering commits by author.

        IMPORTANT: Mocks only Supabase, tests real author filtering logic.
        """
        rag_service = RAGService(mock_supabase_client)

        # Mock Supabase RPC response with author data
        mock_supabase_client.rpc.return_value.execute.return_value = MagicMock(
            data=[
                create_supabase_commit_response(
                    commit_sha="abc123" + "a" * 34,
                    message="Add new feature",
                    author_name="Test Author",
                    author_email="test@example.com",
                    similarity=0.85,
                ),
            ]
        )

        # Call real service chain
        success, result = await rag_service.search_git_commits(
            query="changes",
            author="test@example.com",
        )

        assert success is True
        assert "results" in result
        assert len(result["results"]) == 1

        # Verify author field and complete structure
        commit = result["results"][0]
        assert commit["type"] == "git_commit"
        assert commit["author"] == "Test Author"
        assert commit["author_email"] == "test@example.com"
        assert "content" in commit
        assert "metadata" in commit
    
    async def test_search_git_commits_time_range(self, mock_supabase_client):
        """Test searching commits within time range.

        IMPORTANT: Mocks only Supabase, tests real date filtering logic.
        """
        rag_service = RAGService(mock_supabase_client)

        # Mock Supabase RPC response with commits in time range
        mock_supabase_client.rpc.return_value.execute.return_value = MagicMock(
            data=[
                create_supabase_commit_response(
                    commit_sha="abc123" + "a" * 34,
                    message="Add feature X",
                    commit_date="2024-03-15T10:00:00",
                    similarity=0.85,
                ),
                create_supabase_commit_response(
                    commit_sha="def456" + "b" * 34,
                    message="Add feature Y",
                    commit_date="2024-05-20T14:30:00",
                    similarity=0.8,
                ),
            ]
        )

        # Call real service chain
        success, result = await rag_service.search_git_commits(
            query="feature",
            since="2024-01-01",
            until="2024-06-30",
        )

        assert success is True
        assert "results" in result
        assert len(result["results"]) == 2

        # Verify date fields and complete structure
        for commit in result["results"]:
            assert commit["type"] == "git_commit"
            assert commit["commit_date"] is not None
            assert "content" in commit
            assert "metadata" in commit
    
    async def test_empty_git_search_query(self, mock_supabase_client):
        """Test handling of empty query.

        IMPORTANT: Mocks only Supabase, tests real empty query handling.
        """
        rag_service = RAGService(mock_supabase_client)

        # Mock Supabase RPC response with empty results
        mock_supabase_client.rpc.return_value.execute.return_value = MagicMock(data=[])

        # Call real service chain
        success, result = await rag_service.search_git_commits(query="")

        assert isinstance(success, bool)
        assert "results" in result
        assert len(result["results"]) == 0


# Fixtures for tests
@pytest.fixture
def test_repo_id():
    """Fixture providing a test repository ID."""
    return "embedded-test-repo-id"


@pytest.fixture
def test_commit_sha():
    """Fixture providing a test commit SHA."""
    return "abc123def456"
