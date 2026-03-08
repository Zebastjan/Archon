"""Semantic commit classification service using AI.

Analyzes commit messages and diffs to automatically classify commits by intent,
risk level, breaking changes, and other semantic properties.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from ...config.logfire_config import get_logger
from .git_diff_service import GitDiffService, StructuredDiff

logger = get_logger(__name__)


# Pydantic models for classification results
class CommitClassification(BaseModel):
    """AI-generated classification of a commit."""

    intent: Literal[
        "feature", "bugfix", "refactor", "security-fix", "performance", "docs", "test", "chore"
    ] = Field(
        description="Primary intent/purpose of the commit"
    )

    risk_level: Literal["high", "medium", "low"] = Field(
        description="Risk level of this change (likelihood of introducing issues)"
    )

    api_breaking: bool = Field(
        description="Whether this change breaks existing API contracts or interfaces"
    )

    security_relevant: bool = Field(
        description="Whether this change has security implications (auth, crypto, validation, etc.)"
    )

    performance_impact: Literal["high", "medium", "low", "none"] = Field(
        description="Expected impact on performance (positive or negative)"
    )

    test_coverage: Literal["full", "partial", "none"] = Field(
        description="Extent of test coverage for this change"
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score for this classification (0.0-1.0)",
    )

    reasoning: str = Field(
        description="Brief explanation of the classification decisions"
    )


class GitCommitClassifier:
    """Service for AI-powered commit classification."""

    def __init__(self, diff_service: GitDiffService, model: str = "openai:gpt-4"):
        """
        Initialize commit classifier.

        Args:
            diff_service: Service for generating diffs
            model: Pydantic AI model string (e.g., "openai:gpt-4", "anthropic:claude-sonnet-4")
        """
        self.diff_service = diff_service
        self.model = model

        # Create Pydantic AI agent for classification
        self.agent = Agent(
            model=self.model,
            result_type=CommitClassification,
            system_prompt="""You are an expert code reviewer analyzing Git commits.

Your task is to classify commits based on their message and diff to help developers
understand the nature and risk of changes.

Classification Guidelines:

**Intent:**
- feature: New functionality or capabilities
- bugfix: Fixing broken behavior
- refactor: Code restructuring without changing behavior
- security-fix: Addressing security vulnerabilities
- performance: Optimizing speed or resource usage
- docs: Documentation changes only
- test: Test additions or modifications
- chore: Build, dependencies, tooling, or other maintenance

**Risk Level:**
- high: Major changes, complex logic, security-critical, or high blast radius
- medium: Moderate changes with contained scope
- low: Small, simple, well-tested changes

**API Breaking:**
- true: Changes function signatures, removes endpoints, modifies contracts
- false: Backwards-compatible or internal changes only

**Security Relevant:**
- true: Authentication, authorization, cryptography, input validation, data exposure
- false: No security implications

**Performance Impact:**
- high: Database schema, caching, algorithm complexity
- medium: Additional queries, moderate resource usage
- low: Negligible impact
- none: No performance implications

**Test Coverage:**
- full: Comprehensive test changes included
- partial: Some tests but incomplete coverage
- none: No test changes

Be concise but accurate. When uncertain, prefer conservative estimates (higher risk, lower confidence).""",
        )

    async def classify_commit(
        self,
        repo_path: str,
        commit_sha: str,
        parent_sha: str | None,
        message: str,
    ) -> dict[str, Any]:
        """
        Classify a commit using AI analysis.

        Args:
            repo_path: Path to Git repository
            commit_sha: Commit SHA to classify
            parent_sha: Parent commit SHA (for diff), None for initial commit
            message: Commit message

        Returns:
            Dictionary with classification results and metadata:
            {
                "intent": "feature",
                "risk_level": "medium",
                "api_breaking": false,
                "security_relevant": true,
                "performance_impact": "low",
                "test_coverage": "partial",
                "confidence": 0.87,
                "classification_model": "openai:gpt-4",
                "classification_timestamp": "2024-01-01T00:00:00Z",
                "reasoning": "..."
            }
        """
        try:
            # Get diff if parent exists
            diff_summary = "Initial commit (no diff available)"
            if parent_sha:
                try:
                    diff = self.diff_service.get_diff(
                        repo_path=repo_path,
                        from_sha=parent_sha,
                        to_sha=commit_sha,
                    )
                    diff_summary = self._summarize_diff(diff)
                except Exception as e:
                    logger.warning(f"Could not generate diff for {commit_sha}: {e}")
                    diff_summary = f"Diff unavailable: {e}"

            # Prepare prompt
            prompt = f"""Analyze this commit and provide classification:

**Commit Message:**
{message}

**Changes Summary:**
{diff_summary}

Provide your classification based on the commit message and changes."""

            # Run AI classification
            result = await self.agent.run(prompt)

            classification = result.data

            # Build metadata dict
            metadata = {
                "intent": classification.intent,
                "risk_level": classification.risk_level,
                "api_breaking": classification.api_breaking,
                "security_relevant": classification.security_relevant,
                "performance_impact": classification.performance_impact,
                "test_coverage": classification.test_coverage,
                "confidence": classification.confidence,
                "reasoning": classification.reasoning,
                "classification_model": self.model,
                "classification_timestamp": datetime.now(UTC).isoformat(),
            }

            return metadata

        except Exception as e:
            logger.error(f"Error classifying commit {commit_sha}: {e}", exc_info=True)
            # Return minimal metadata on error
            return {
                "intent": "unknown",
                "risk_level": "medium",
                "api_breaking": False,
                "security_relevant": False,
                "performance_impact": "none",
                "test_coverage": "none",
                "confidence": 0.0,
                "reasoning": f"Classification failed: {str(e)}",
                "classification_model": self.model,
                "classification_timestamp": datetime.now(UTC).isoformat(),
                "error": str(e),
            }

    def _summarize_diff(self, diff: StructuredDiff) -> str:
        """
        Summarize a diff for AI consumption.

        Args:
            diff: Structured diff object

        Returns:
            Human-readable summary of changes
        """
        lines = [
            f"Files changed: {diff.files_changed}",
            f"Additions: {diff.additions}",
            f"Deletions: {diff.deletions}",
            "",
            "Files:",
        ]

        for file_diff in diff.files[:10]:  # Limit to first 10 files
            status_emoji = {
                "added": "➕",
                "deleted": "➖",
                "modified": "✏️",
                "renamed": "📝",
            }.get(file_diff.status, "")

            lines.append(
                f"  {status_emoji} {file_diff.path} ({file_diff.status}): "
                f"+{file_diff.additions} -{file_diff.deletions}"
            )

            # Add language if available
            if file_diff.language:
                lines[-1] += f" [{file_diff.language}]"

        if len(diff.files) > 10:
            lines.append(f"  ... and {len(diff.files) - 10} more files")

        return "\n".join(lines)
