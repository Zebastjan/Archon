"""
Test Git Semantic Search integration with vector similarity search.

Phase 2 tests for semantic commit search functionality.
"""

import sys
from unittest.mock import MagicMock, AsyncMock, patch
import math

# Mock modules before importing
sys.modules['src.server.db_connector'] = MagicMock()
sys.modules['src.server.db_connector'].get_db_client = MagicMock(return_value=MagicMock())
sys.modules['openai'] = MagicMock()
sys.modules['src.server.services.embeddings'] = MagicMock()
sys.modules['src.server.services.embeddings.embedding_service'] = MagicMock()
sys.modules['src.server.services.embeddings.embedding_service'].create_embedding = AsyncMock(return_value=[0.1] * 1536)
sys.modules['src.server.services.embeddings.contextual_embedding_service'] = MagicMock()

import pytest
from datetime import datetime
from typing import Any

from src.server.services.git.git_semantic_search import (
    GitSemanticSearch,
    SearchFilters,
    CommitSearchResult,
)


@pytest.fixture
def mock_supabase_client():
    """Provide mocked Supabase client with chainable methods."""
    client = MagicMock()
    # Setup the RPC method to return mock results
    rpc_mock = MagicMock()
    rpc_mock.execute.return_value = MagicMock(data=[])
    client.rpc.return_value = rpc_mock
    
    # Setup table method
    table_mock = MagicMock()
    table_mock.select.return_value = table_mock
    table_mock.eq.return_value = table_mock
    table_mock.contains.return_value = table_mock
    table_mock.gte.return_value = table_mock
    table_mock.lte.return_value = table_mock
    table_mock.or_.return_value = table_mock
    table_mock.not_.return_value = table_mock
    table_mock.is_.return_value = table_mock
    table_mock.limit.return_value = table_mock
    table_mock.execute.return_value = MagicMock(data=[])
    client.table.return_value = table_mock
    
    return client


@pytest.fixture
def git_semantic_search(mock_supabase_client):
    """Provide GitSemanticSearch with mocked client."""
    return GitSemanticSearch(supabase_client=mock_supabase_client)


class TestSearchCommits:
    """Tests for semantic commit search."""

    @pytest.mark.asyncio
    async def test_search_commits_basic(self, git_semantic_search, mock_supabase_client):
        """Find commits by semantic query."""
        # Mock RPC response
        mock_supabase_client.rpc.return_value.execute.return_value = MagicMock(
            data=[
                {
                    "id": "commit-1",
                    "commit_sha": "abc123",
                    "message": "Add authentication",
                    "similarity": 0.85,
                }
            ]
        )
        
        results = await git_semantic_search.search_commits(
            query="authentication changes",
            limit=10
        )
        
        assert len(results) == 1
        assert results[0].commit_sha == "abc123"
        assert results[0].similarity_score == 0.85

    @pytest.mark.asyncio
    async def test_search_commits_with_repo_filter(self, git_semantic_search, mock_supabase_client):
        """Filter by repository."""
        mock_supabase_client.rpc.return_value.execute.return_value = MagicMock(data=[])
        
        await git_semantic_search.search_commits(
            query="feature",
            filters=SearchFilters(repo_id="repo-123")
        )
        
        # Verify RPC was called with repo filter
        call_args = mock_supabase_client.rpc.call_args
        assert call_args[1]["filter_repo_id"] == "repo-123"

    @pytest.mark.asyncio
    async def test_search_commits_with_branch_filter(self, git_semantic_search, mock_supabase_client):
        """Filter by branch."""
        mock_supabase_client.rpc.return_value.execute.return_value = MagicMock(data=[])
        
        await git_semantic_search.search_commits(
            query="fix",
            filters=SearchFilters(branch="main")
        )
        
        call_args = mock_supabase_client.rpc.call_args
        assert call_args[1]["filter_branch"] == "main"

    @pytest.mark.asyncio
    async def test_search_commits_date_range(self, git_semantic_search, mock_supabase_client):
        """Filter by date range."""
        mock_supabase_client.rpc.return_value.execute.return_value = MagicMock(data=[])
        
        since = datetime(2024, 1, 1)
        until = datetime(2024, 12, 31)
        
        await git_semantic_search.search_commits(
            query="changes",
            filters=SearchFilters(since=since, until=until)
        )
        
        call_args = mock_supabase_client.rpc.call_args
        assert call_args[1]["filter_since"] == since.isoformat()
        assert call_args[1]["filter_until"] == until.isoformat()

    @pytest.mark.asyncio
    async def test_search_commits_intent_filter(self, git_semantic_search, mock_supabase_client):
        """Filter by classification intent."""
        mock_supabase_client.rpc.return_value.execute.return_value = MagicMock(
            data=[
                {
                    "id": "c1",
                    "commit_sha": "abc111",
                    "message": "Feature commit",
                    "metadata": {"intent": "feature"},
                    "similarity": 0.9,
                }
            ]
        )
        
        results = await git_semantic_search.search_commits(
            query="new feature",
            filters=SearchFilters(intent_filter=["feature"])
        )
        
        # Intent filter is applied post-query
        assert all(r.classification.get("intent") == "feature" for r in results)

    @pytest.mark.asyncio
    async def test_search_commits_risk_filter(self, git_semantic_search, mock_supabase_client):
        """Filter by risk level."""
        mock_supabase_client.rpc.return_value.execute.return_value = MagicMock(
            data=[
                {
                    "id": "c1",
                    "commit_sha": "abc111",
                    "metadata": {"risk_level": "high"},
                    "similarity": 0.8,
                }
            ]
        )
        
        results = await git_semantic_search.search_commits(
            query="changes",
            filters=SearchFilters(risk_filter=["high"])
        )
        
        assert all(r.classification.get("risk_level") == "high" for r in results)

    @pytest.mark.asyncio
    async def test_search_commits_min_similarity(self, git_semantic_search, mock_supabase_client):
        """Filter by minimum similarity threshold."""
        mock_supabase_client.rpc.return_value.execute.return_value = MagicMock(
            data=[
                {"id": "c1", "commit_sha": "abc111", "similarity": 0.9},
                {"id": "c2", "commit_sha": "abc222", "similarity": 0.3},  # Below threshold
            ]
        )
        
        results = await git_semantic_search.search_commits(
            query="test",
            min_similarity=0.5
        )
        
        assert all(r.similarity_score >= 0.5 for r in results)

    @pytest.mark.asyncio
    async def test_search_commits_no_results(self, git_semantic_search, mock_supabase_client):
        """Handle empty results gracefully."""
        mock_supabase_client.rpc.return_value.execute.return_value = MagicMock(data=[])
        
        results = await git_semantic_search.search_commits(
            query="nonexistent concept"
        )
        
        assert results == []


class TestFindSimilarCommits:
    """Tests for finding similar commits."""

    @pytest.mark.asyncio
    async def test_find_similar_commits(self, git_semantic_search, mock_supabase_client):
        """Find commits similar to reference."""
        # Mock commit lookup
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{
                "id": "ref-commit",
                "embedding_1536": [0.1] * 1536,
            }]
        )
        
        # Mock search results
        mock_supabase_client.rpc.return_value.execute.return_value = MagicMock(
            data=[
                {"id": "c2", "commit_sha": "abc222", "similarity": 0.85},
                {"id": "c3", "commit_sha": "abc333", "similarity": 0.75},
            ]
        )
        
        results = await git_semantic_search.find_similar_commits(
            commit_sha="abc111",
            repo_id="repo-123"
        )
        
        assert len(results) >= 1
        assert all(r.commit_sha != "abc111" for r in results)  # Excludes self

    @pytest.mark.asyncio
    async def test_find_similar_commits_excludes_self(self, git_semantic_search, mock_supabase_client):
        """Reference commit is excluded from results."""
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "ref", "embedding_1536": [0.1] * 1536}]
        )
        
        mock_supabase_client.rpc.return_value.execute.return_value = MagicMock(
            data=[
                {"id": "ref", "commit_sha": "abc111", "similarity": 1.0},  # Self
                {"id": "c2", "commit_sha": "abc222", "similarity": 0.8},
            ]
        )
        
        results = await git_semantic_search.find_similar_commits(
            commit_sha="abc111",
            repo_id="repo-123"
        )
        
        assert all(r.commit_sha != "abc111" for r in results)


class TestCosineSimilarity:
    """Tests for similarity calculation."""

    def test_cosine_similarity_identical_vectors(self, git_semantic_search):
        """Identical vectors have similarity 1.0."""
        vec = [1.0, 0.0, 0.0]
        similarity = git_semantic_search._cosine_similarity(vec, vec)
        assert similarity == 1.0

    def test_cosine_similarity_orthogonal_vectors(self, git_semantic_search):
        """Orthogonal vectors have similarity 0.0."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        similarity = git_semantic_search._cosine_similarity(vec1, vec2)
        assert similarity == 0.0

    def test_cosine_similarity_opposite_vectors(self, git_semantic_search):
        """Opposite vectors have similarity -1.0."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [-1.0, 0.0, 0.0]
        similarity = git_semantic_search._cosine_similarity(vec1, vec2)
        assert similarity == -1.0

    def test_cosine_similarity_different_dimensions(self, git_semantic_search):
        """Error on dimension mismatch."""
        vec1 = [1.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]
        with pytest.raises(ValueError, match="same dimension"):
            git_semantic_search._cosine_similarity(vec1, vec2)


class TestParseResults:
    """Tests for result parsing."""

    def test_parse_search_results_format(self, git_semantic_search):
        """Correct result object structure."""
        raw_data = [
            {
                "id": "c1",
                "commit_sha": "abc123",
                "repo_id": "repo-1",
                "message": "Test commit",
                "author_name": "Test Author",
                "author_email": "test@example.com",
                "commit_date": "2024-01-15T10:30:00",
                "branches": ["main"],
                "metadata": {"intent": "feature"},
                "similarity": 0.85,
            }
        ]
        
        results = git_semantic_search._parse_search_results(raw_data, 1536)
        
        assert len(results) == 1
        assert isinstance(results[0], CommitSearchResult)
        assert results[0].commit_sha == "abc123"
        assert results[0].similarity_score == 0.85
        assert results[0].embedding_dimension == 1536

    def test_parse_with_classification(self, git_semantic_search):
        """Classification metadata in parsed results."""
        raw_data = [
            {
                "id": "c1",
                "commit_sha": "abc123",
                "metadata": {
                    "intent": "bugfix",
                    "risk_level": "medium",
                    "api_breaking": True,
                },
                "similarity": 0.9,
            }
        ]
        
        results = git_semantic_search._parse_search_results(raw_data, 1536)
        
        assert results[0].classification["intent"] == "bugfix"
        assert results[0].classification["risk_level"] == "medium"


class TestClassificationFilters:
    """Tests for post-query classification filtering."""

    def test_apply_intent_filter(self, git_semantic_search):
        """Filter by intent post-query."""
        commits = [
            CommitSearchResult(
                commit_id="c1",
                commit_sha="abc111",
                repo_id="r1",
                message="Feature",
                similarity_score=0.9,
                embedding_dimension=1536,
                classification={"intent": "feature"}
            ),
            CommitSearchResult(
                commit_id="c2",
                commit_sha="abc222",
                repo_id="r1",
                message="Bugfix",
                similarity_score=0.8,
                embedding_dimension=1536,
                classification={"intent": "bugfix"}
            ),
        ]
        
        filters = SearchFilters(intent_filter=["feature"])
        filtered = git_semantic_search._apply_classification_filters(commits, filters)
        
        assert len(filtered) == 1
        assert filtered[0].commit_sha == "abc111"

    def test_apply_breaking_only_filter(self, git_semantic_search):
        """Filter to only breaking changes."""
        commits = [
            CommitSearchResult(
                commit_id="c1",
                commit_sha="abc111",
                repo_id="r1",
                message="Breaking",
                similarity_score=0.9,
                embedding_dimension=1536,
                classification={"api_breaking": True}
            ),
            CommitSearchResult(
                commit_id="c2",
                commit_sha="abc222",
                repo_id="r1",
                message="Normal",
                similarity_score=0.8,
                embedding_dimension=1536,
                classification={"api_breaking": False}
            ),
        ]
        
        filters = SearchFilters(breaking_only=True)
        filtered = git_semantic_search._apply_classification_filters(commits, filters)
        
        assert len(filtered) == 1
        assert filtered[0].commit_sha == "abc111"

    def test_apply_security_only_filter(self, git_semantic_search):
        """Filter to only security commits."""
        commits = [
            CommitSearchResult(
                commit_id="c1",
                commit_sha="abc111",
                repo_id="r1",
                message="Security fix",
                similarity_score=0.9,
                embedding_dimension=1536,
                classification={"security_relevant": True}
            ),
            CommitSearchResult(
                commit_id="c2",
                commit_sha="abc222",
                repo_id="r1",
                message="Normal",
                similarity_score=0.8,
                embedding_dimension=1536,
                classification={}
            ),
        ]
        
        filters = SearchFilters(security_only=True)
        filtered = git_semantic_search._apply_classification_filters(commits, filters)
        
        assert len(filtered) == 1
        assert filtered[0].commit_sha == "abc111"


class TestFallbackSearch:
    """Tests for fallback when RPC unavailable."""

    @pytest.mark.asyncio
    async def test_fallback_search_when_rpc_unavailable(self, git_semantic_search, mock_supabase_client):
        """Use direct SQL when RPC fails."""
        # Make RPC fail
        mock_supabase_client.rpc.side_effect = Exception("RPC not available")
        
        # Mock fallback query
        mock_supabase_client.table.return_value.select.return_value.not_.return_value.is_.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[]
        )
        
        # Should not raise exception
        results = await git_semantic_search.search_commits(query="test")
        assert results == []


class TestEdgeCases:
    """Edge case handling."""

    @pytest.mark.asyncio
    async def test_search_with_empty_query(self, git_semantic_search, mock_supabase_client):
        """Handle empty query gracefully."""
        mock_supabase_client.rpc.return_value.execute.return_value = MagicMock(data=[])
        
        results = await git_semantic_search.search_commits(query="")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_limit_capped_at_100(self, git_semantic_search, mock_supabase_client):
        """Limit is capped at 100."""
        mock_supabase_client.rpc.return_value.execute.return_value = MagicMock(data=[])
        
        await git_semantic_search.search_commits(query="test", limit=500)
        
        call_args = mock_supabase_client.rpc.call_args
        assert call_args[1]["match_count"] <= 100

    def test_rag_compatible_formatting(self, git_semantic_search):
        """Results formatted for RAG pipeline compatibility."""
        result = CommitSearchResult(
            commit_id="c1",
            commit_sha="abc123",
            repo_id="r1",
            message="Test commit",
            author_name="Author",
            similarity_score=0.9,
            embedding_dimension=1536,
            branches=["main", "develop"],
            classification={"intent": "feature"}
        )
        
        # Verify all required fields for RAG
        assert result.commit_sha
        assert result.message is not None
        assert result.similarity_score >= 0.0
        assert result.embedding_dimension > 0
