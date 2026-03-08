"""
Git Commit Classification API endpoints

Handles:
- AI-powered semantic commit classification
- Batch classification of commit history
"""

from fastapi import APIRouter, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel

from ..config.logfire_config import get_logger, logfire
from ..services.git.git_commit_classifier import GitCommitClassifier
from ..services.git.git_diff_service import GitDiffService
from ..services.git.git_repository_service import (
    GitCommitNotFoundError,
    GitError,
    GitRepositoryNotFoundError,
    GitRepositoryService,
)
from ..utils import get_supabase_client

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["git-classification"])


class ClassifyCommitRequest(BaseModel):
    """Request to classify a single commit."""

    model: str = "openai:gpt-4"


class BatchClassifyRequest(BaseModel):
    """Request to batch-classify multiple commits."""

    commit_shas: list[str]
    model: str = "openai:gpt-4"


@router.post("/projects/{project_id}/repository/commits/{commit_sha}/classify")
@logfire.instrument("classify_commit")
async def classify_commit(
    project_id: str,
    commit_sha: str,
    request: ClassifyCommitRequest | None = None,
) -> dict:
    """
    Classify a commit using AI analysis.

    Returns classification metadata including intent, risk level, breaking changes, etc.

    Args:
        project_id: Project identifier
        commit_sha: Commit SHA to classify
        request: Optional classification options (model selection)

    Returns:
        dict: Classification metadata
    """
    try:
        supabase_client = get_supabase_client()
        git_service = GitRepositoryService(supabase_client)

        # Get repository info
        repo_info = await git_service.get_repository_by_project_id(project_id)
        if not repo_info:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"No repository found for project {project_id}",
            )

        repo_path = repo_info["repo_path"]

        # Get commit details
        commit = await git_service.get_commit_by_sha(project_id, commit_sha)
        if not commit:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Commit {commit_sha} not found",
            )

        message = commit["message"]
        parent_sha = commit["parent_shas"][0] if commit.get("parent_shas") else None

        # Initialize classifier
        diff_service = GitDiffService(git_service)
        model = request.model if request else "openai:gpt-4"
        classifier = GitCommitClassifier(diff_service, model=model)

        # Classify commit
        metadata = await classifier.classify_commit(
            repo_path=repo_path,
            commit_sha=commit_sha,
            parent_sha=parent_sha,
            message=message,
        )

        # Update commit metadata in database
        await git_service.update_commit_metadata(project_id, commit_sha, metadata)

        return {
            "commit_sha": commit_sha,
            "classification": metadata,
        }

    except HTTPException:
        raise
    except GitRepositoryNotFoundError as e:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=e.to_dict(),
        ) from e
    except GitCommitNotFoundError as e:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=e.to_dict(),
        ) from e
    except GitError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=e.to_dict(),
        ) from e
    except Exception as e:
        logger.error(f"Error classifying commit {commit_sha}: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        ) from e


@router.post("/projects/{project_id}/repository/commits/classify-batch")
@logfire.instrument("batch_classify_commits")
async def batch_classify_commits(
    project_id: str,
    request: BatchClassifyRequest,
) -> dict:
    """
    Batch-classify multiple commits using AI analysis.

    Useful for classifying historical commits or entire branches.

    Args:
        project_id: Project identifier
        request: Batch classification request with commit SHAs and model

    Returns:
        dict: Summary of classification results with counts and errors
    """
    try:
        supabase_client = get_supabase_client()
        git_service = GitRepositoryService(supabase_client)

        # Get repository info
        repo_info = await git_service.get_repository_by_project_id(project_id)
        if not repo_info:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"No repository found for project {project_id}",
            )

        repo_path = repo_info["repo_path"]

        # Initialize classifier
        diff_service = GitDiffService(git_service)
        classifier = GitCommitClassifier(diff_service, model=request.model)

        # Classify each commit
        results = []
        errors = []

        for commit_sha in request.commit_shas:
            try:
                # Get commit details
                commit = await git_service.get_commit_by_sha(project_id, commit_sha)
                if not commit:
                    errors.append(
                        {
                            "commit_sha": commit_sha,
                            "error": "Commit not found",
                        }
                    )
                    continue

                message = commit["message"]
                parent_sha = (
                    commit["parent_shas"][0] if commit.get("parent_shas") else None
                )

                # Classify commit
                metadata = await classifier.classify_commit(
                    repo_path=repo_path,
                    commit_sha=commit_sha,
                    parent_sha=parent_sha,
                    message=message,
                )

                # Update commit metadata in database
                await git_service.update_commit_metadata(
                    project_id, commit_sha, metadata
                )

                results.append(
                    {
                        "commit_sha": commit_sha,
                        "intent": metadata["intent"],
                        "risk_level": metadata["risk_level"],
                        "confidence": metadata["confidence"],
                    }
                )

            except Exception as e:
                logger.warning(
                    f"Error classifying commit {commit_sha}: {e}", exc_info=True
                )
                errors.append(
                    {
                        "commit_sha": commit_sha,
                        "error": str(e),
                    }
                )

        return {
            "total": len(request.commit_shas),
            "successful": len(results),
            "failed": len(errors),
            "results": results,
            "errors": errors,
        }

    except HTTPException:
        raise
    except GitRepositoryNotFoundError as e:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=e.to_dict(),
        ) from e
    except Exception as e:
        logger.error(f"Error in batch classification: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        ) from e
