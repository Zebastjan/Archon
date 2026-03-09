"""
Realistic mock data factories for Git integration tests.

These factories generate data matching real implementation structures:
- Supabase RPC responses (what comes from database)
- CommitSearchResult objects (what GitSemanticSearch returns)
- Formatted dicts (what GitSearchStrategy.search_commits returns)

Purpose: Ensure tests validate real behavior, not our assumptions.
"""

from datetime import datetime
from typing import Any


def create_supabase_commit_response(
    commit_sha: str = "abc123def456",
    message: str = "Test commit message",
    intent: str = "feature",
    risk_level: str = "medium",
    repo_id: str = "test-repo-id",
    author_name: str = "Test Author",
    author_email: str = "test@example.com",
    commit_date: str | None = "2024-01-15T10:30:00",
    branches: list[str] | None = None,
    similarity: float = 0.85,
    commit_id: str | None = None,
    diff_summary: str | None = None,
    **extra_metadata: Any,
) -> dict[str, Any]:
    """
    Create Supabase RPC response matching real schema.

    This matches what GitSemanticSearch._parse_commit_result() expects from
    the database search_git_commits_semantic() RPC function.

    Args:
        commit_sha: Git commit SHA (40 chars, but 8-char prefix works for tests)
        message: Commit message text
        intent: Classification intent (feature, bug_fix, security_fix, etc.)
        risk_level: Risk level (low, medium, high)
        repo_id: Repository UUID
        author_name: Commit author name
        author_email: Commit author email
        commit_date: ISO format datetime string (or None)
        branches: List of branch names
        similarity: Similarity score (0.0 to 1.0)
        commit_id: Commit UUID (auto-generated if None)
        diff_summary: Summary of file changes
        **extra_metadata: Additional metadata fields

    Returns:
        Dict matching Supabase RPC response structure
    """
    if branches is None:
        branches = ["main"]

    if commit_id is None:
        commit_id = f"commit-{commit_sha[:8]}"

    return {
        "id": commit_id,
        "commit_sha": commit_sha,
        "repo_id": repo_id,
        "message": message,
        "author_name": author_name,
        "author_email": author_email,
        "commit_date": commit_date,
        "branches": branches,
        "metadata": {
            "intent": intent,
            "risk_level": risk_level,
            **extra_metadata,
        },
        "similarity": similarity,
        "diff_summary": diff_summary,
    }


def create_commit_search_result_dict(
    commit_sha: str = "abc123def456",
    message: str = "Test commit message",
    intent: str = "feature",
    risk_level: str = "medium",
    repo_id: str = "test-repo-id",
    author_name: str = "Test Author",
    author_email: str = "test@example.com",
    commit_date: str | None = "2024-01-15T10:30:00",
    branches: list[str] | None = None,
    similarity_score: float = 0.85,
    embedding_dimension: int = 1536,
    commit_id: str | None = None,
    diff_summary: str | None = None,
    **extra_metadata: Any,
) -> dict[str, Any]:
    """
    Create dict matching GitSearchStrategy.search_commits() output.

    This is what RAGService.search_git_commits() returns in result["results"].
    It matches the formatting in git_search_strategy.py lines 102-128.

    All 17 fields are included to match real implementation:
    1. type
    2. commit_sha
    3. commit_id
    4. repo_id
    5. message
    6. author
    7. author_email
    8. commit_date
    9. branches
    10. classification
    11. similarity_score
    12. embedding_dimension
    13. diff_summary
    14. content (formatted by _format_commit_content)
    15. metadata (nested dict with type, repo_id, commit_sha, branches, classification)

    Args:
        Same as create_supabase_commit_response()
        embedding_dimension: Embedding vector dimension (384, 768, 1024, 1536, 3072)

    Returns:
        Dict matching GitSearchStrategy formatted output
    """
    if branches is None:
        branches = ["main"]

    if commit_id is None:
        commit_id = f"commit-{commit_sha[:8]}"

    classification = {
        "intent": intent,
        "risk_level": risk_level,
        **extra_metadata,
    }

    # Format content matching _format_commit_content() logic
    content_parts = [f"Commit: {commit_sha[:8]}"]

    if message:
        content_parts.append(f"Message: {message}")

    if classification:
        content_parts.append(f"Type: {intent} (risk: {risk_level})")

    if author_name:
        content_parts.append(f"Author: {author_name}")

    if commit_date:
        # Parse date for formatting
        try:
            date_obj = datetime.fromisoformat(commit_date.replace("Z", "+00:00"))
            content_parts.append(f"Date: {date_obj.strftime('%Y-%m-%d')}")
        except Exception:
            pass

    if branches:
        content_parts.append(f"Branches: {', '.join(branches[:3])}")

    if diff_summary:
        content_parts.append(f"Changes: {diff_summary[:200]}")

    content = " | ".join(content_parts)

    return {
        "type": "git_commit",
        "commit_sha": commit_sha,
        "commit_id": commit_id,
        "repo_id": repo_id,
        "message": message,
        "author": author_name,
        "author_email": author_email,
        "commit_date": commit_date,
        "branches": branches,
        "classification": classification,
        "similarity_score": similarity_score,
        "embedding_dimension": embedding_dimension,
        "diff_summary": diff_summary,
        "content": content,
        "metadata": {
            "type": "git_commit",
            "repo_id": repo_id,
            "commit_sha": commit_sha,
            "branches": branches,
            "classification": classification,
        },
    }


def create_multiple_supabase_responses(count: int = 3, base_similarity: float = 0.9) -> list[dict[str, Any]]:
    """
    Create multiple diverse Supabase responses for testing.

    Args:
        count: Number of responses to generate
        base_similarity: Starting similarity score (decreases by 0.1 for each)

    Returns:
        List of Supabase response dicts with varied data
    """
    intents = ["feature", "bug_fix", "refactor", "security_fix", "documentation"]
    risk_levels = ["low", "medium", "high"]

    responses = []
    for i in range(count):
        similarity = max(0.1, base_similarity - (i * 0.1))
        intent = intents[i % len(intents)]
        risk = risk_levels[i % len(risk_levels)]

        responses.append(
            create_supabase_commit_response(
                commit_sha=f"commit{i:03d}" + "a" * 32,
                message=f"Test commit {i}: {intent}",
                intent=intent,
                risk_level=risk,
                similarity=similarity,
                author_name=f"Author {i}",
                author_email=f"author{i}@example.com",
                branches=[f"branch-{i}", "main"] if i % 2 == 0 else ["main"],
                diff_summary=f"Modified {i + 1} files" if i % 3 == 0 else None,
            )
        )

    return responses


def create_multiple_formatted_results(count: int = 3, base_similarity: float = 0.9, embedding_dimension: int = 1536) -> list[dict[str, Any]]:
    """
    Create multiple diverse formatted results matching GitSearchStrategy output.

    Args:
        count: Number of results to generate
        base_similarity: Starting similarity score
        embedding_dimension: Embedding vector dimension

    Returns:
        List of formatted result dicts
    """
    intents = ["feature", "bug_fix", "refactor", "security_fix", "documentation"]
    risk_levels = ["low", "medium", "high"]

    results = []
    for i in range(count):
        similarity = max(0.1, base_similarity - (i * 0.1))
        intent = intents[i % len(intents)]
        risk = risk_levels[i % len(risk_levels)]

        results.append(
            create_commit_search_result_dict(
                commit_sha=f"commit{i:03d}" + "a" * 32,
                message=f"Test commit {i}: {intent}",
                intent=intent,
                risk_level=risk,
                similarity_score=similarity,
                embedding_dimension=embedding_dimension,
                author_name=f"Author {i}",
                author_email=f"author{i}@example.com",
                branches=[f"branch-{i}", "main"] if i % 2 == 0 else ["main"],
                diff_summary=f"Modified {i + 1} files" if i % 3 == 0 else None,
            )
        )

    return results


# Common test scenarios

def create_security_fix_response() -> dict[str, Any]:
    """Create a security fix commit response for testing security-related queries."""
    return create_supabase_commit_response(
        commit_sha="sec123" + "a" * 34,
        message="Fix XSS vulnerability in user input",
        intent="security_fix",
        risk_level="high",
        author_name="Security Team",
        author_email="security@example.com",
        branches=["security-patch", "main"],
        diff_summary="Modified 3 files: UserInput.tsx, sanitize.ts, tests/",
        similarity=0.95,
        security_relevant=True,  # Required for security_only filter
    )


def create_bug_fix_response() -> dict[str, Any]:
    """Create a bug fix commit response for testing bug-related queries."""
    return create_supabase_commit_response(
        commit_sha="bug456" + "a" * 34,
        message="Fix null pointer exception in authentication",
        intent="bug_fix",
        risk_level="medium",
        author_name="Dev Team",
        author_email="dev@example.com",
        branches=["bugfix/auth-null", "main"],
        diff_summary="Modified 2 files: auth.py, tests/test_auth.py",
        similarity=0.88,
    )


def create_feature_response() -> dict[str, Any]:
    """Create a feature commit response for testing feature-related queries."""
    return create_supabase_commit_response(
        commit_sha="feat789" + "a" * 34,
        message="Add dark mode support to UI",
        intent="feature",
        risk_level="low",
        author_name="Frontend Team",
        author_email="frontend@example.com",
        branches=["feature/dark-mode", "develop"],
        diff_summary="Modified 15 files: theme system overhaul",
        similarity=0.82,
    )
