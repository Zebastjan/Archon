"""Shared MCP tool helpers.

Common utility functions used across MCP tool modules to avoid duplication.
"""

MAX_DESCRIPTION_LENGTH = 1000


def truncate_text(text: str, max_length: int = MAX_DESCRIPTION_LENGTH) -> str:
    """Truncate text to maximum length with ellipsis.

    Args:
        text: The text to truncate
        max_length: Maximum length before truncation (default: 1000)

    Returns:
        Truncated text with ellipsis if needed, or original text
    """
    if text and len(text) > max_length:
        return text[: max_length - 3] + "..."
    return text


def optimize_response(data: dict, description_field: str = "description") -> dict:
    """Generic response optimizer for MCP tools.

    Optimizes a data object for MCP response by:
    - Truncating description fields
    - Limiting large lists to first N items
    - Adding count fields for truncated lists

    Args:
        data: The data object to optimize
        description_field: Field name for description text (default: "description")

    Returns:
        Optimized copy of the data object
    """
    result = data.copy()

    # Truncate description
    if description_field in result and result[description_field]:
        result[description_field] = truncate_text(result[description_field])

    # Handle common list fields
    list_fields = [
        ("features", 3),
        ("sources", None),  # Will be removed, not truncated
        ("code_examples", None),  # Will be removed, not truncated
        ("documents", 10),
        ("tasks", 10),
        ("versions", 10),
    ]

    for field, limit in list_fields:
        if field in result and isinstance(result[field], list):
            result[f"{field}_count"] = len(result[field])
            if limit is not None and len(result[field]) > limit:
                result[field] = result[field][:limit]

    return result


def paginate_results(items: list, page: int, per_page: int) -> tuple[list, dict]:
    """Paginate a list of items.

    Args:
        items: List of items to paginate
        page: Page number (1-indexed)
        per_page: Items per page

    Returns:
        Tuple of (paginated_items, pagination_info)
    """
    total = len(items)
    total_pages = (total + per_page - 1) // per_page
    page = max(1, page)

    start = (page - 1) * per_page
    end = start + per_page
    paginated = items[start:end]

    pagination_info = {
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }

    return paginated, pagination_info


def format_not_found_error(resource_type: str, identifier: str) -> dict:
    """Format a standard not found error response.

    Args:
        resource_type: Type of resource (e.g., "project", "task")
        identifier: The ID or name that was not found

    Returns:
        Standardized error response dict
    """
    return {
        "success": False,
        "error": f"{resource_type} not found",
        "error_type": "NotFoundError",
        "resource_type": resource_type,
        "identifier": identifier,
    }


def format_validation_error(field: str, message: str) -> dict:
    """Format a standard validation error response.

    Args:
        field: The field that failed validation
        message: Human-readable error message

    Returns:
        Standardized error response dict
    """
    return {
        "success": False,
        "error": f"Validation error: {message}",
        "error_type": "ValidationError",
        "field": field,
        "message": message,
    }
