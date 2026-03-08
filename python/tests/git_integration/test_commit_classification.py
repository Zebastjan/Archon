"""Tests for Git commit classification.

Note: These tests use mocked AI responses to avoid requiring actual LLM API calls.
Integration tests with real LLMs should be added separately.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.server.services.git.git_commit_classifier import (
    CommitClassification,
    GitCommitClassifier,
)
from src.server.services.git.git_diff_service import GitDiffService
from src.server.services.git.git_repository_service import GitRepositoryService
from tests.git_integration.test_git_repository_integration import (
    FakeSupabaseClient,
    _init_git_repository,
    _run_git,
)


@pytest.fixture
def classifier_test_repo(tmp_path: Path):
    """Create a repository for testing classification."""
    repo_path = _init_git_repository(tmp_path / "classifier-test")

    # Create a feature commit
    (repo_path / "feature.py").write_text(
        "def new_feature():\n    return 'feature'\n", encoding="utf-8"
    )
    _run_git(repo_path, "add", "feature.py")
    _run_git(repo_path, "commit", "-m", "feat: add new feature for user authentication")
    feature_commit = _run_git(repo_path, "rev-parse", "HEAD").stdout.strip()
    feature_parent = _run_git(repo_path, "rev-parse", "HEAD^").stdout.strip()

    # Create a bugfix commit
    (repo_path / "bugfix.py").write_text(
        "def fix_bug():\n    return 'fixed'\n", encoding="utf-8"
    )
    _run_git(repo_path, "add", "bugfix.py")
    _run_git(repo_path, "commit", "-m", "fix: resolve null pointer exception in login")
    bugfix_commit = _run_git(repo_path, "rev-parse", "HEAD").stdout.strip()
    bugfix_parent = _run_git(repo_path, "rev-parse", "HEAD^").stdout.strip()

    return {
        "repo_path": str(repo_path),
        "feature_commit": feature_commit,
        "feature_parent": feature_parent,
        "bugfix_commit": bugfix_commit,
        "bugfix_parent": bugfix_parent,
    }


@pytest.fixture
def mock_agent():
    """Create a mocked Pydantic AI agent."""
    agent = MagicMock()

    # Create a mock result with a mock CommitClassification
    async def mock_run(prompt: str):
        # Determine classification based on prompt content
        if "feature" in prompt.lower() or "feat:" in prompt.lower():
            classification = CommitClassification(
                intent="feature",
                risk_level="medium",
                api_breaking=False,
                security_relevant=True,
                performance_impact="low",
                test_coverage="partial",
                confidence=0.85,
                reasoning="New feature implementation with security implications",
            )
        elif "fix" in prompt.lower() or "bug" in prompt.lower():
            classification = CommitClassification(
                intent="bugfix",
                risk_level="low",
                api_breaking=False,
                security_relevant=False,
                performance_impact="none",
                test_coverage="partial",
                confidence=0.90,
                reasoning="Bug fix with targeted changes",
            )
        else:
            classification = CommitClassification(
                intent="chore",
                risk_level="low",
                api_breaking=False,
                security_relevant=False,
                performance_impact="none",
                test_coverage="none",
                confidence=0.70,
                reasoning="General maintenance or unclear intent",
            )

        result = MagicMock()
        result.data = classification
        return result

    agent.run = AsyncMock(side_effect=mock_run)
    return agent


@pytest.mark.asyncio
async def test_classify_feature_commit(
    classifier_test_repo,
    git_service: GitRepositoryService,
    supabase_client: FakeSupabaseClient,
    mock_agent,
) -> None:
    """Test classification of a feature commit."""
    diff_service = GitDiffService(git_service)
    classifier = GitCommitClassifier(diff_service, agent=mock_agent)

    # Classify feature commit
    metadata = await classifier.classify_commit(
        repo_path=classifier_test_repo["repo_path"],
        commit_sha=classifier_test_repo["feature_commit"],
        parent_sha=classifier_test_repo["feature_parent"],
        message="feat: add new feature for user authentication",
    )

    # Verify classification
    assert metadata["intent"] == "feature"
    assert metadata["risk_level"] in ["high", "medium", "low"]
    assert isinstance(metadata["api_breaking"], bool)
    assert isinstance(metadata["security_relevant"], bool)
    assert metadata["performance_impact"] in ["high", "medium", "low", "none"]
    assert metadata["test_coverage"] in ["full", "partial", "none"]
    assert 0.0 <= metadata["confidence"] <= 1.0
    assert "reasoning" in metadata
    assert "classification_timestamp" in metadata


@pytest.mark.asyncio
async def test_classify_bugfix_commit(
    classifier_test_repo,
    git_service: GitRepositoryService,
    supabase_client: FakeSupabaseClient,
    mock_agent,
) -> None:
    """Test classification of a bugfix commit."""
    diff_service = GitDiffService(git_service)
    classifier = GitCommitClassifier(diff_service, agent=mock_agent)

    # Classify bugfix commit
    metadata = await classifier.classify_commit(
        repo_path=classifier_test_repo["repo_path"],
        commit_sha=classifier_test_repo["bugfix_commit"],
        parent_sha=classifier_test_repo["bugfix_parent"],
        message="fix: resolve null pointer exception in login",
    )

    # Verify classification
    assert metadata["intent"] == "bugfix"
    assert metadata["risk_level"] in ["high", "medium", "low"]
    assert "reasoning" in metadata


@pytest.mark.asyncio
async def test_classification_includes_diff_context(
    classifier_test_repo,
    git_service: GitRepositoryService,
    supabase_client: FakeSupabaseClient,
    mock_agent,
) -> None:
    """Test that classification includes diff context in the prompt."""
    diff_service = GitDiffService(git_service)
    classifier = GitCommitClassifier(diff_service, agent=mock_agent)

    # Classify commit
    await classifier.classify_commit(
        repo_path=classifier_test_repo["repo_path"],
        commit_sha=classifier_test_repo["feature_commit"],
        parent_sha=classifier_test_repo["feature_parent"],
        message="feat: add new feature",
    )

    # Verify agent was called with diff information
    mock_agent.run.assert_called_once()
    call_args = mock_agent.run.call_args[0][0]  # Get the prompt
    assert "Changes Summary" in call_args or "Diff" in call_args or "Files" in call_args


@pytest.mark.asyncio
async def test_classification_handles_initial_commit(
    classifier_test_repo,
    git_service: GitRepositoryService,
    supabase_client: FakeSupabaseClient,
    mock_agent,
) -> None:
    """Test that classification handles initial commits (no parent)."""
    diff_service = GitDiffService(git_service)
    classifier = GitCommitClassifier(diff_service, agent=mock_agent)

    # Classify commit with no parent
    metadata = await classifier.classify_commit(
        repo_path=classifier_test_repo["repo_path"],
        commit_sha=classifier_test_repo["feature_commit"],
        parent_sha=None,  # No parent
        message="Initial commit",
    )

    # Should still return valid classification
    assert "intent" in metadata
    assert "risk_level" in metadata
    assert metadata["confidence"] >= 0.0


@pytest.mark.asyncio
async def test_classification_handles_errors_gracefully(
    classifier_test_repo,
    git_service: GitRepositoryService,
    supabase_client: FakeSupabaseClient,
) -> None:
    """Test that classification handles errors gracefully."""
    diff_service = GitDiffService(git_service)

    # Create a mock agent that raises an error
    error_agent = MagicMock()
    error_agent.run = AsyncMock(side_effect=Exception("AI service unavailable"))

    classifier = GitCommitClassifier(diff_service, agent=error_agent)

    # Classify should not raise, but return error metadata
    metadata = await classifier.classify_commit(
        repo_path=classifier_test_repo["repo_path"],
        commit_sha=classifier_test_repo["feature_commit"],
        parent_sha=classifier_test_repo["feature_parent"],
        message="feat: add feature",
    )

    # Should return safe defaults
    assert metadata["intent"] == "unknown"
    assert metadata["confidence"] == 0.0
    assert "error" in metadata


def test_diff_summarization(
    git_service: GitRepositoryService, supabase_client: FakeSupabaseClient
) -> None:
    """Test that diff summarization produces readable output."""
    from src.server.services.git.git_diff_service import FileDiff, StructuredDiff

    diff_service = GitDiffService(git_service)
    # Use a mock agent since we're only testing _summarize_diff
    mock_agent = MagicMock()
    classifier = GitCommitClassifier(diff_service, agent=mock_agent)

    # Create a mock diff
    mock_diff = StructuredDiff(
        from_commit="abc123",
        to_commit="def456",
        files_changed=2,
        additions=10,
        deletions=5,
        files=[
            FileDiff(
                path="src/main.py",
                old_path=None,
                status="modified",
                language="python",
                additions=7,
                deletions=3,
                hunks=[],
                is_binary=False,
            ),
            FileDiff(
                path="tests/test_main.py",
                old_path=None,
                status="added",
                language="python",
                additions=3,
                deletions=0,
                hunks=[],
                is_binary=False,
            ),
        ],
    )

    summary = classifier._summarize_diff(mock_diff)

    # Verify summary content
    assert "Files changed: 2" in summary
    assert "Additions: 10" in summary
    assert "Deletions: 5" in summary
    assert "src/main.py" in summary
    assert "tests/test_main.py" in summary
    assert "python" in summary
