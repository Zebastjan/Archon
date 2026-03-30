"""Centralized error handling utilities for Archon API Server.

Provides consistent error formatting and response generation for FastAPI endpoints.
Based on the MCPErrorFormatter pattern from mcp_server/utils/error_handling.py.

TODO: Eventually merge with MCP error handling for a unified approach.
"""

import json
from typing import Any

from fastapi import HTTPException


def format_api_error(
    message: str,
    error_type: str = "api_error",
    details: dict[str, Any] | None = None,
    suggestion: str | None = None,
) -> dict[str, Any]:
    """Format an error response with consistent structure.

    Args:
        message: User-friendly error message
        error_type: Category of error (e.g., "validation_error", "not_found")
        details: Additional context about the error
        suggestion: Actionable suggestion for resolving the error

    Returns:
        Structured error dictionary for HTTPException detail
    """
    error_response: dict[str, Any] = {
        "success": False,
        "error": {
            "type": error_type,
            "message": message,
        },
    }

    if details:
        error_response["error"]["details"] = details

    if suggestion:
        error_response["error"]["suggestion"] = suggestion

    return error_response


def not_found_error(
    resource_type: str,
    resource_id: str | None = None,
    suggestion: str | None = None,
) -> HTTPException:
    """Create a 404 Not Found error.

    Args:
        resource_type: Type of resource (e.g., "project", "task")
        resource_id: Optional resource identifier
        suggestion: Optional suggestion for resolution

    Returns:
        HTTPException with 404 status
    """
    message = f"{resource_type} not found"
    if resource_id:
        message = f"{resource_type} '{resource_id}' not found"

    details = {"resource_type": resource_type}
    if resource_id:
        details["resource_id"] = resource_id

    return HTTPException(
        status_code=404,
        detail=format_api_error(
            message=message,
            error_type="not_found",
            details=details,
            suggestion=suggestion or f"Check that the {resource_type} exists and you have access to it",
        ),
    )


def validation_error(
    field: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> HTTPException:
    """Create a 422 Validation Error.

    Args:
        field: The field that failed validation
        message: Validation error message
        details: Additional validation context

    Returns:
        HTTPException with 422 status
    """
    error_details = {"field": field}
    if details:
        error_details.update(details)

    return HTTPException(
        status_code=422,
        detail=format_api_error(
            message=f"Validation failed: {message}",
            error_type="validation_error",
            details=error_details,
            suggestion=f"Check the '{field}' field and try again",
        ),
    )


def authentication_error(
    message: str = "Authentication required",
    details: dict[str, Any] | None = None,
) -> HTTPException:
    """Create a 401 Authentication Error.

    Args:
        message: Authentication error message
        details: Additional context

    Returns:
        HTTPException with 401 status
    """
    return HTTPException(
        status_code=401,
        detail=format_api_error(
            message=message,
            error_type="authentication_error",
            details=details,
            suggestion="Check your credentials and try again",
        ),
    )


def authorization_error(
    message: str = "Access denied",
    details: dict[str, Any] | None = None,
) -> HTTPException:
    """Create a 403 Authorization Error.

    Args:
        message: Authorization error message
        details: Additional context

    Returns:
        HTTPException with 403 status
    """
    return HTTPException(
        status_code=403,
        detail=format_api_error(
            message=message,
            error_type="authorization_error",
            details=details,
            suggestion="You may need additional permissions for this action",
        ),
    )


def service_error(
    service_name: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> HTTPException:
    """Create a 502 Service Error.

    Args:
        service_name: Name of the service that failed
        message: Service error message
        details: Additional context

    Returns:
        HTTPException with 502 status
    """
    return HTTPException(
        status_code=502,
        detail=format_api_error(
            message=f"Service '{service_name}' error: {message}",
            error_type="service_error",
            details={"service": service_name, **(details or {})},
            suggestion=f"Check the {service_name} service status and try again",
        ),
    )


def internal_error(
    message: str = "An unexpected error occurred",
    details: dict[str, Any] | None = None,
) -> HTTPException:
    """Create a 500 Internal Server Error.

    Args:
        message: Error message
        details: Additional context (may be logged but not returned to client)

    Returns:
        HTTPException with 500 status
    """
    return HTTPException(
        status_code=500,
        detail=format_api_error(
            message=message,
            error_type="internal_error",
            details=details,
            suggestion="Please try again or contact support if the issue persists",
        ),
    )


def conflict_error(
    resource_type: str,
    resource_id: str,
    message: str | None = None,
) -> HTTPException:
    """Create a 409 Conflict Error.

    Args:
        resource_type: Type of resource
        resource_id: Resource identifier
        message: Optional custom message

    Returns:
        HTTPException with 409 status
    """
    default_message = f"{resource_type} '{resource_id}' already exists"
    return HTTPException(
        status_code=409,
        detail=format_api_error(
            message=message or default_message,
            error_type="conflict_error",
            details={"resource_type": resource_type, "resource_id": resource_id},
            suggestion=f"Use a different name or update the existing {resource_type}",
        ),
    )
