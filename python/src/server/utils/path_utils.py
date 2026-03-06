"""Path translation utilities for Docker container to host filesystem mapping."""

import os

# Host → Container path mappings
# Users can extend this dict for their specific mount configurations
PATH_MAPPINGS = {
    "/home/zebastjan/dev": "/repos",
}


def translate_host_to_container(host_path: str) -> str:
    """
    Translate host filesystem path to container path.
    Returns original path if no mapping found.

    Args:
        host_path: Path on host machine

    Returns:
        Path accessible from within container
    """
    for host_prefix, container_prefix in PATH_MAPPINGS.items():
        if host_path.startswith(host_prefix):
            return host_path.replace(host_prefix, container_prefix, 1)
    return host_path


def validate_repo_path(repo_path: str) -> tuple[bool, str, str | None]:
    """
    Validate repository path and return container path.

    Args:
        repo_path: Repository path (host or container)

    Returns:
        Tuple of (is_valid, container_path, error_message)
    """
    container_path = translate_host_to_container(repo_path)

    if not os.path.exists(container_path):
        return False, container_path, f"Path does not exist: {container_path}"

    if not os.path.isdir(container_path):
        return False, container_path, f"Path is not a directory: {container_path}"

    git_dir = os.path.join(container_path, ".git")
    if not os.path.exists(git_dir):
        return False, container_path, "Not a Git repository (no .git directory)"

    return True, container_path, None
