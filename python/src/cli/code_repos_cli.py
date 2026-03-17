"""CLI commands for code repository management.

Provides commands for creating and indexing code repositories.
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx


def create_and_index_repo(name: str, local_path: str, github_url: str | None = None, 
                          wait: bool = False, timeout: int = 300, poll_interval: int = 5) -> dict:
    """
    Create and index a code repository.
    
    Args:
        name: Repository display name
        local_path: Absolute path to local git repository
        github_url: Optional GitHub URL
        wait: If True, block until indexing completes
        timeout: Maximum seconds to wait
        poll_interval: Seconds between status checks
        
    Returns:
        Status dictionary
    """
    api_url = "http://localhost:8181"
    
    # Create and index
    response = httpx.post(
        f"{api_url}/api/code_repos/create-and-index",
        json={
            "name": name,
            "local_path": local_path,
            "github_url": github_url,
        },
        timeout=30.0
    )
    
    if response.status_code != 200:
        print(f"❌ Failed to create repo: {response.text}", file=sys.stderr)
        sys.exit(1)
    
    result = response.json()
    
    if not result.get("success"):
        print(f"❌ Error: {result.get('error_message', 'Unknown error')}", file=sys.stderr)
        sys.exit(1)
    
    repo_id = result.get("repo_id")
    status = result.get("status")
    existing = result.get("existing", False)
    
    if existing:
        print(f"ℹ️  Repository '{name}' already exists (repo_id: {repo_id})")
    else:
        print(f"✅ Created repository '{name}' (repo_id: {repo_id})")
    
    print(f"   Status: {status}")
    
    # Wait for ready if requested
    if wait and status in ["queued", "indexing"]:
        print(f"\n⏳ Waiting for indexing to complete (timeout: {timeout}s)...")
        
        start_time = time.time()
        dots = 0
        
        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                print(f"\n⚠️  Timeout after {timeout}s. Indexing continues in background.")
                result["message"] = f"Timeout after {timeout}s. Indexing continues in background."
                break
            
            time.sleep(poll_interval)
            
            # Poll status
            status_response = httpx.get(
                f"{api_url}/api/code_repos/{repo_id}/status",
                timeout=10.0
            )
            
            if status_response.status_code == 200:
                status_data = status_response.json()
                current_status = status_data.get("status")
                entities_count = status_data.get("entities_count", 0)
                
                # Update dots
                dots = (dots + 1) % 4
                print(f"\r   Status: {current_status} ({entities_count} entities indexed){'.' * dots}{' ' * (4-dots)}", end="", flush=True)
                
                if current_status == "ready":
                    print(f"\n✅ Indexing complete! {entities_count} entities indexed.")
                    result["status"] = "ready"
                    result["entities_count"] = entities_count
                    result["last_synced"] = status_data.get("last_synced")
                    break
                elif current_status == "error":
                    print(f"\n❌ Indexing failed: {status_data.get('error_message', 'Unknown error')}")
                    result["status"] = "error"
                    result["error_message"] = status_data.get("error_message")
                    break
    
    return result


def add_repo_command(args: argparse.Namespace) -> int:
    """Add a repository and optionally wait for indexing."""
    result = create_and_index_repo(
        name=args.name,
        local_path=args.root_path,
        github_url=args.github_url,
        wait=args.wait,
        timeout=args.timeout,
        poll_interval=args.poll_interval,
    )
    
    if result.get("status") == "ready":
        print(f"\n🎉 Repository '{args.name}' is ready for use!")
        print(f"   You can now run: audit_get_context(repo_name='{args.name}')")
        return 0
    elif result.get("status") == "error":
        print(f"\n❌ Failed to index repository", file=sys.stderr)
        return 1
    else:
        print(f"\n⏳ Repository is still indexing. Check status with:")
        print(f"   curl http://localhost:8181/api/code_repos/{result.get('repo_id')}/status")
        return 0


def list_repos_command(args: argparse.Namespace) -> int:
    """List all registered repositories."""
    api_url = "http://localhost:8181"
    
    response = httpx.get(f"{api_url}/api/code_repos", timeout=10.0)
    
    if response.status_code != 200:
        print(f"❌ Failed to list repos: {response.text}", file=sys.stderr)
        return 1
    
    repos = response.json()
    
    if not repos:
        print("No repositories registered.")
        return 0
    
    print()
    print("=" * 80)
    print("REGISTERED CODE REPOSITORIES")
    print("=" * 80)
    print()
    
    for repo in repos:
        status = repo.get("status", "unknown")
        status_emoji = {
            "ready": "✅",
            "indexing": "⏳",
            "queued": "⏸️",
            "error": "❌",
            "created": "📝",
        }.get(status, "❓")
        
        print(f"{status_emoji} {repo.get('name')}")
        print(f"   Repo ID: {repo.get('repo_id')}")
        print(f"   Path: {repo.get('local_path')}")
        print(f"   Status: {status}")
        print(f"   Entities: {repo.get('entities_count', 0)}")
        
        if repo.get('github_url'):
            print(f"   GitHub: {repo.get('github_url')}")
        
        if repo.get('last_synced'):
            print(f"   Last Synced: {repo.get('last_synced')}")
        
        print()
    
    print(f"Total: {len(repos)} repositories")
    print()
    
    return 0


def get_status_command(args: argparse.Namespace) -> int:
    """Get status of a specific repository."""
    api_url = "http://localhost:8181"
    
    response = httpx.get(
        f"{api_url}/api/code_repos/{args.repo_id}/status",
        timeout=10.0
    )
    
    if response.status_code == 404:
        print(f"❌ Repository {args.repo_id} not found", file=sys.stderr)
        return 1
    elif response.status_code != 200:
        print(f"❌ Failed to get status: {response.text}", file=sys.stderr)
        return 1
    
    status = response.json()
    
    print()
    print("=" * 60)
    print("REPOSITORY STATUS")
    print("=" * 60)
    print()
    print(f"Repo ID: {status.get('repo_id')}")
    print(f"Name: {status.get('name')}")
    print(f"Status: {status.get('status')}")
    print(f"Entities: {status.get('entities_count', 0)}")
    print(f"Local Path: {status.get('local_path')}")
    
    if status.get('last_synced'):
        print(f"Last Synced: {status.get('last_synced')}")
    
    if status.get('last_commit'):
        print(f"Last Commit: {status.get('last_commit')[:8]}...")
    
    print()
    
    return 0


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="archon-code-repos",
        description="Code repository management CLI for Archon",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s add --name Omnibus --root-path /home/zebastjan/dev/Omnibus
  %(prog)s add --name Archon --root-path /home/zebastjan/dev/archon --wait
  %(prog)s add --name MyRepo --root-path /path/to/repo --github-url https://github.com/user/repo
  %(prog)s list
  %(prog)s status --repo-id 550e8400-e29b-41d4-a716-446655440000
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Add repo command
    add_parser = subparsers.add_parser(
        "add",
        help="Create and index a repository"
    )
    add_parser.add_argument(
        "--name",
        required=True,
        help="Repository display name (e.g., 'Omnibus')"
    )
    add_parser.add_argument(
        "--root-path",
        required=True,
        help="Absolute path to local git repository"
    )
    add_parser.add_argument(
        "--github-url",
        help="Optional GitHub URL (e.g., https://github.com/user/repo)"
    )
    add_parser.add_argument(
        "--wait",
        action="store_true",
        help="Wait for indexing to complete before returning"
    )
    add_parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Maximum seconds to wait (default: 300)"
    )
    add_parser.add_argument(
        "--poll-interval",
        type=int,
        default=5,
        help="Seconds between status checks (default: 5)"
    )
    
    # List repos command
    list_parser = subparsers.add_parser(
        "list",
        help="List all registered repositories"
    )
    
    # Get status command
    status_parser = subparsers.add_parser(
        "status",
        help="Get status of a specific repository"
    )
    status_parser.add_argument(
        "--repo-id",
        required=True,
        help="Repository UUID"
    )
    
    args = parser.parse_args()
    
    if args.command == "add":
        return add_repo_command(args)
    elif args.command == "list":
        return list_repos_command(args)
    elif args.command == "status":
        return get_status_command(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
