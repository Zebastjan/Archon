"""Test Git Embedding Service integration with embedding generation and storage.

Phase 1 tests for commit embedding functionality.
These tests use mocks and don't require external services.
"""

import sys
from unittest.mock import MagicMock, patch, AsyncMock

# Mock modules before importing git_embedding_service
sys.modules['src.server.db_connector'] = MagicMock()
sys.modules['src.server.db_connector'].get_db_client = MagicMock(return_value=MagicMock())
sys.modules['openai'] = MagicMock()
sys.modules['src.server.services.embeddings'] = MagicMock()
sys.modules['src.server.services.embeddings.embedding_service'] = MagicMock()

# Create async mock for embedding functions
async def mock_create_embeddings_batch(*args, **kwargs):
    return MagicMock(
        embeddings=[[0.1] * 1536],
        has_failures=False,
        failed_items=[]
    )

sys.modules['src.server.services.embeddings.embedding_service'].create_embeddings_batch = mock_create_embeddings_batch
sys.modules['src.server.services.embeddings.embedding_service'].create_embedding = AsyncMock(return_value=[0.1] * 1536)
sys.modules['src.server.services.embeddings.embedding_service'].EmbeddingBatchResult = MagicMock
sys.modules['src.server.services.embeddings.contextual_embedding_service'] = MagicMock()

import pytest
from datetime import datetime
from pathlib import Path

from src.server.services.git.git_embedding_service import (
    GitEmbeddingService,
    CommitEmbeddingResult,
)

# All tests in this file use mocks
pytestmark = pytest.mark.mock


@pytest.fixture
def git_embedding_service(mock_supabase_client):
    """Provide GitEmbeddingService with mocked supabase."""
    return GitEmbeddingService(supabase_client=mock_supabase_client)


class TestFormatCommitForEmbedding:
    """Tests for commit text formatting before embedding."""

    def test_format_commit_for_embedding_message(self, git_embedding_service):
        """Format commit message text for embedding."""
        text = git_embedding_service.format_commit_for_embedding(
            commit_sha="abc123",
            message="Add user authentication feature",
            source="message"
        )
        assert "Add user authentication feature" in text
        assert "abc123" not in text  # SHA should not be in content

    def test_format_commit_for_embedding_with_metadata(self, git_embedding_service):
        """Include intent and risk classification in embedding text."""
        text = git_embedding_service.format_commit_for_embedding(
            commit_sha="abc123",
            message="Fix critical security vulnerability",
            metadata={
                "intent": "security_fix",
                "risk_level": "high",
                "security_relevant": True,
            },
            source="message"
        )
        assert "Intent: security_fix" in text
        assert "Risk: high" in text
        assert "Security-related" in text
        assert "Fix critical security vulnerability" in text

    def test_format_commit_for_embedding_diff(self, git_embedding_service):
        """Format diff summary for embedding."""
        text = git_embedding_service.format_commit_for_embedding(
            commit_sha="abc123",
            message="Update API endpoints",
            diff_summary="Modified 3 files: src/api.py, tests/test_api.py",
            source="diff"
        )
        assert "Changes:" in text
        assert "Modified 3 files" in text

    def test_format_commit_for_embedding_combined(self, git_embedding_service):
        """Combine message and diff for richer embedding."""
        text = git_embedding_service.format_commit_for_embedding(
            commit_sha="abc123",
            message="Refactor database layer",
            diff_summary="5 files changed, 200 insertions",
            metadata={"intent": "refactor", "risk_level": "medium"},
            source="combined"
        )
        assert "Intent: refactor" in text
        assert "Refactor database layer" in text
        assert "Changes:" in text


class TestEmbedCommit:
    """Tests for single commit embedding."""

    @pytest.mark.asyncio
    async def test_embed_commit_success(self, git_embedding_service, mock_supabase_client, mock_embedding_result):
        """Generate embedding for single commit and store in DB."""
        # Setup mock commit data
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{
                "id": "commit-uuid",
                "commit_sha": "abc123def456",
                "message": "Add feature X",
                "author_name": "Test Author",
                "metadata": {"intent": "feature"}
            }]
        )
        
        with patch("src.server.services.git.git_embedding_service.create_embeddings_batch", 
                   return_value=mock_embedding_result):
            result = await git_embedding_service.embed_commit(
                repo_id="repo-123",
                commit_sha="abc123def456",
                source="message"
            )
        
        assert result.success is True
        assert result.commit_sha == "abc123def456"
        assert result.embedding_dimension == 1536

    @pytest.mark.asyncio
    async def test_embed_commit_stores_in_db(self, git_embedding_service, mock_supabase_client, mock_embedding_result):
        """Verify embedding is stored in correct DB column."""
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "commit-uuid", "commit_sha": "abc123", "message": "Test", "metadata": {}}]
        )
        
        with patch("src.server.services.git.git_embedding_service.create_embeddings_batch",
                   return_value=mock_embedding_result):
            await git_embedding_service.embed_commit("repo-123", "abc123")
        
        # Verify update was called with correct column
        update_call = mock_supabase_client.table.return_value.update.call_args
        assert "embedding_1536" in update_call[0][0]

    @pytest.mark.asyncio
    async def test_embed_commit_missing_commit(self, git_embedding_service, mock_supabase_client):
        """Error handling when commit doesn't exist."""
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )
        
        result = await git_embedding_service.embed_commit("repo-123", "nonexistent")
        
        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_embed_commit_missing_diff(self, git_embedding_service, mock_supabase_client):
        """Error when diff required but not provided."""
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "commit-uuid", "commit_sha": "abc123", "message": "Test", "metadata": {}}]
        )
        
        result = await git_embedding_service.embed_commit(
            "repo-123", "abc123", source="diff"  # Requires diff_summary
        )
        
        assert result.success is False
        assert "diff_summary required" in result.error


class TestEmbedCommitsBatch:
    """Tests for batch commit embedding."""

    @pytest.mark.asyncio
    async def test_embed_commits_batch_success(self, git_embedding_service, mock_supabase_client):
        """Batch process multiple commits successfully."""
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[
                {"id": "c1", "commit_sha": "abc111", "message": "Commit 1", "metadata": {}},
                {"id": "c2", "commit_sha": "abc222", "message": "Commit 2", "metadata": {}},
            ]
        )
        
        mock_batch_result = MagicMock(
            embeddings=[[0.1]*1536, [0.2]*1536],
            has_failures=False,
            failed_items=[]
        )
        
        with patch("src.server.services.git.git_embedding_service.create_embeddings_batch",
                   return_value=mock_batch_result):
            results = await git_embedding_service.embed_commits_batch(
                repo_id="repo-123",
                commit_shas=["abc111", "abc222"],
                batch_size=50
            )
        
        assert len(results) == 2
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_embed_commits_batch_partial_failure(self, git_embedding_service, mock_supabase_client):
        """Handle partial failures gracefully."""
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[
                {"id": "c1", "commit_sha": "abc111", "message": "Commit 1", "metadata": {}},
                {"id": "c2", "commit_sha": "abc222", "message": "Commit 2", "metadata": {}},
            ]
        )
        
        mock_batch_result = MagicMock(
            embeddings=[[0.1]*1536],  # Only 1 success
            has_failures=True,
            failed_items=[{"batch_index": 1, "error": "Rate limit exceeded"}]
        )
        
        with patch("src.server.services.git.git_embedding_service.create_embeddings_batch",
                   return_value=mock_batch_result):
            results = await git_embedding_service.embed_commits_batch("repo-123", ["abc111", "abc222"])
        
        successes = [r for r in results if r.success]
        failures = [r for r in results if not r.success]
        assert len(successes) == 1
        assert len(failures) == 1

    @pytest.mark.asyncio
    async def test_embed_commits_batch_no_commits(self, git_embedding_service, mock_supabase_client):
        """Handle empty commit list."""
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )
        
        results = await git_embedding_service.embed_commits_batch("repo-123", ["nonexistent"])
        
        assert results == []


class TestEmbeddingStorage:
    """Tests for embedding storage details."""

    @pytest.mark.asyncio
    async def test_embedding_dimension_columns(self, git_embedding_service, mock_supabase_client, mock_embedding_result):
        """Store embedding in correct dimension column."""
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "c1", "commit_sha": "abc123", "message": "Test", "metadata": {}}]
        )
        
        # Test 1536 dimension (OpenAI default)
        with patch("src.server.services.git.git_embedding_service.create_embeddings_batch",
                   return_value=mock_embedding_result):
            result = await git_embedding_service.embed_commit("repo-123", "abc123")
        
        assert result.embedding_dimension == 1536

    @pytest.mark.asyncio
    async def test_embedding_model_metadata(self, git_embedding_service, mock_supabase_client, mock_embedding_result):
        """Store model name and timestamp metadata."""
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "c1", "commit_sha": "abc123", "message": "Test", "metadata": {}}]
        )
        
        with patch("src.server.services.git.git_embedding_service.create_embeddings_batch",
                   return_value=mock_embedding_result):
            await git_embedding_service.embed_commit("repo-123", "abc123")
        
        update_args = mock_supabase_client.table.return_value.update.call_args[0][0]
        assert "embedding_model" in update_args
        assert "embedding_timestamp" in update_args
        assert "embedding_source" in update_args


class TestEdgeCases:
    """Edge case handling."""

    @pytest.mark.asyncio
    async def test_embed_empty_commit_message(self, git_embedding_service, mock_supabase_client, mock_embedding_result):
        """Handle empty commit messages gracefully."""
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "c1", "commit_sha": "abc123", "message": "", "metadata": {}}]
        )
        
        with patch("src.server.services.git.git_embedding_service.create_embeddings_batch",
                   return_value=mock_embedding_result):
            result = await git_embedding_service.embed_commit("repo-123", "abc123")
        
        assert result.success is True  # Should still succeed

    @pytest.mark.asyncio
    async def test_embed_commit_already_embedded(self, git_embedding_service, mock_supabase_client, mock_embedding_result):
        """Idempotent - can re-embed same commit."""
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{
                "id": "c1",
                "commit_sha": "abc123",
                "message": "Test",
                "metadata": {},
                "embedding_1536": [0.1]*1536,  # Already has embedding
                "embedding_model": "old-model"
            }]
        )
        
        with patch("src.server.services.git.git_embedding_service.create_embeddings_batch",
                   return_value=mock_embedding_result):
            result = await git_embedding_service.embed_commit("repo-123", "abc123")
        
        # Should overwrite with new embedding
        assert result.success is True
        update_call = mock_supabase_client.table.return_value.update.call_args
        assert "embedding_1536" in update_call[0][0]
