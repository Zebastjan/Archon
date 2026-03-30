"""Custom exception hierarchy for Archon.

This module provides a coherent, system-wide exception handling strategy.
All Archon-specific exceptions inherit from ArchonError for consistent handling.

Usage:
    from src.server.exceptions import NotFoundError, ValidationError

    raise NotFoundError("User not found", resource="user", id=user_id)
    raise ValidationError("Invalid email format", field="email", value=email)
"""

from typing import Any


class ArchonError(Exception):
    """Base exception for all Archon errors.

    Provides structured error information with context for logging and debugging.
    All custom exceptions should inherit from this class.

    Attributes:
        message: Human-readable error description
        code: Machine-readable error code (e.g., "NOT_FOUND", "VALIDATION_ERROR")
        status_code: HTTP status code for API responses
        details: Additional context about the error
    """

    code: str = "INTERNAL_ERROR"
    status_code: int = 500

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        **details: Any,
    ):
        """Initialize the exception with context.

        Args:
            message: Human-readable error description
            code: Optional override for machine-readable code
            status_code: Optional override for HTTP status code
            **details: Additional context (e.g., resource, id, field)
        """
        self.message = message
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        self.details = details
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for JSON serialization.

        Returns:
            Dict with error_type, message, code, and any additional details.
        """
        return {
            "error_type": self.__class__.__name__,
            "code": self.code,
            "message": self.message,
            "status_code": self.status_code,
            "details": self.details,
        }

    def __repr__(self) -> str:
        details_str = ", ".join(f"{k}={v!r}" for k, v in self.details.items())
        return f"{self.__class__.__name__}({self.message!r}{', ' + details_str if details_str else ''})"


class NotFoundError(ArchonError):
    """Raised when a requested resource is not found.

    Use for:
    - Database lookups that return no results
    - Files that don't exist
    - API endpoints for non-existent resources

    Example:
        raise NotFoundError(
            "Knowledge item not found",
            resource="knowledge_item",
            id=item_id
        )
    """

    code = "NOT_FOUND"
    status_code = 404


class ValidationError(ArchonError):
    """Raised when input validation fails.

    Use for:
    - Invalid request parameters
    - Schema validation failures
    - Business rule violations

    Example:
        raise ValidationError(
            "Invalid email format",
            field="email",
            value=email,
            constraint="must contain @"
        )
    """

    code = "VALIDATION_ERROR"
    status_code = 422


class ServiceError(ArchonError):
    """Raised when an external service call fails.

    Use for:
    - API calls to external services (OpenAI, Ollama, etc.)
    - Network failures
    - Service timeouts

    Example:
        raise ServiceError(
            "OpenAI API request failed",
            service="openai",
            endpoint="/v1/embeddings",
            original_error=str(e)
        )
    """

    code = "SERVICE_ERROR"
    status_code = 502


class ConfigurationError(ArchonError):
    """Raised when configuration is missing or invalid.

    Use for:
    - Missing required environment variables
    - Invalid configuration values
    - Missing config files

    Example:
        raise ConfigurationError(
            "Missing required environment variable",
            variable="OPENAI_API_KEY",
            hint="Set OPENAI_API_KEY in your .env file"
        )
    """

    code = "CONFIGURATION_ERROR"
    status_code = 500


class StorageError(ArchonError):
    """Raised when database or storage operations fail.

    Use for:
    - Database connection failures
    - Query execution errors
    - File system operations

    Example:
        raise StorageError(
            "Database query failed",
            operation="INSERT",
            table="archon_sources",
            original_error=str(e)
        )
    """

    code = "STORAGE_ERROR"
    status_code = 500


class AuthenticationError(ArchonError):
    """Raised when authentication or authorization fails.

    Use for:
    - Invalid credentials
    - Missing authentication tokens
    - Permission denied

    Example:
        raise AuthenticationError(
            "Invalid API key",
            provider="openai",
            hint="Check your API key in Settings"
        )
    """

    code = "AUTHENTICATION_ERROR"
    status_code = 401


class AuthorizationError(ArchonError):
    """Raised when user lacks permission for an operation.

    Use for:
    - Insufficient permissions
    - Access to restricted resources
    - Role-based access control violations

    Example:
        raise AuthorizationError(
            "Admin access required",
            required_role="admin",
            current_role="user"
        )
    """

    code = "AUTHORIZATION_ERROR"
    status_code = 403


class RateLimitError(ArchonError):
    """Raised when rate limits are exceeded.

    Use for:
    - API rate limiting
    - Quota exhaustion
    - Throttling

    Example:
        raise RateLimitError(
            "Rate limit exceeded",
            service="openai",
            retry_after=60
        )
    """

    code = "RATE_LIMIT_ERROR"
    status_code = 429


class ConflictError(ArchonError):
    """Raised when there's a conflict with current state.

    Use for:
    - Duplicate entries
    - State conflicts
    - Concurrent modification

    Example:
        raise ConflictError(
            "Knowledge item already exists",
            resource="knowledge_item",
            url=url
        )
    """

    code = "CONFLICT_ERROR"
    status_code = 409


class TimeoutError(ArchonError):
    """Raised when an operation times out.

    Use for:
    - Long-running operations
    - External service timeouts
    - Async operation timeouts

    Example:
        raise TimeoutError(
            "Embedding generation timed out",
            operation="generate_embeddings",
            timeout_seconds=300
        )
    """

    code = "TIMEOUT_ERROR"
    status_code = 504
