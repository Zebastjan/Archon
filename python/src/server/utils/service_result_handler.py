"""Service result handler for converting error dictionaries to exceptions.

This module provides utilities to handle the (success, result) tuple pattern
used by services, converting error dictionaries to proper exceptions.

TODO: Eventually services should raise exceptions directly instead of returning
tuples with error dictionaries.
"""

from typing import Any

from fastapi import HTTPException


def handle_service_result(
    success: bool,
    result: dict[str, Any],
    *,
    resource_type: str = "resource",
    resource_id: str | None = None,
) -> dict[str, Any]:
    """Handle service result tuple and raise appropriate HTTP exceptions.

    Converts error dictionaries to proper HTTPException instances based on
    error type detection. Eliminates string-matching error handling.

    Args:
        success: Whether the service call succeeded
        result: The result dict (either success data or error info)
        resource_type: Type of resource for "not found" errors (e.g., "project", "task")
        resource_id: Optional resource ID for error messages

    Returns:
        The result dict on success

    Raises:
        HTTPException: 404 if "not found" in error, 500 otherwise
    """
    if not success:
        error_msg = result.get("error", "Unknown error").lower()

        # Check for "not found" patterns
        if "not found" in error_msg or "does not exist" in error_msg or "doesn't exist" in error_msg:
            detail = {"error": f"{resource_type} not found", "resource_id": resource_id, **result}
            raise HTTPException(status_code=404, detail=detail)

        # Check for validation errors
        if "validation" in error_msg or "invalid" in error_msg or "required" in error_msg:
            detail = {"error": f"{resource_type} validation failed", **result}
            raise HTTPException(status_code=422, detail=detail)

        # Check for authentication errors
        if "unauthorized" in error_msg or "permission" in error_msg or "forbidden" in error_msg:
            detail = {"error": f"Access denied for {resource_type}", **result}
            raise HTTPException(status_code=403, detail=detail)

        # Generic error
        detail = {"error": f"Failed to {resource_type}", **result}
        raise HTTPException(status_code=500, detail=detail)

    return result
