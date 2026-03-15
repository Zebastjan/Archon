#!/usr/bin/env python3
"""Register octofriend and syllablaze repositories with Archon."""

import asyncio
import sys
import os

# Set environment variables before importing archon modules
os.environ['ARCHON_DATABASE_URL'] = 'postgresql://archon:archon_local_dev@localhost:5434/archon'
os.environ['ARCHON_DB_USER'] = 'archon'
os.environ['ARCHON_DB_PASSWORD'] = 'archon_local_dev'
os.environ['ARCHON_DB_NAME'] = 'archon'
os.environ['ARCHON_DB_PORT'] = '5434'

# Add python/src to path
sys.path.insert(0, '/home/zebastjan/dev/archon/python/src')
sys.path.insert(0, '/home/zebastjan/dev/archon/python')

try:
    from server.services.git_repo_manager import get_repo_manager
except ImportError:
    from src.server.services.git_repo_manager import get_repo_manager


async def register_repositories():
    """Register octofriend and syllablaze repositories."""
    manager = get_repo_manager()
    
    repos_to_register = [
        {
            'local_path': '/home/zebastjan/dev/octofriend',
            'name': 'octofriend',
            'github_url': 'https://github.com/synthetic-lab/octofriend'
        },
        {
            'local_path': '/home/zebastjan/dev/syllablaze', 
            'name': 'syllablaze',
            'github_url': 'https://github.com/Zebastjan/Syllablaze'
        }
    ]
    
    for repo_info in repos_to_register:
        print(f"\n{'='*60}")
        print(f"Registering: {repo_info['name']}")
        print(f"Local path: {repo_info['local_path']}")
        print(f"GitHub URL: {repo_info['github_url']}")
        print(f"{'='*60}")
        
        try:
            config = await manager.register_local_repo(
                local_path=repo_info['local_path'],
                name=repo_info['name'],
                github_url=repo_info['github_url']
            )
            print(f"✓ Successfully registered!")
            print(f"  Repository ID: {config.repo_id}")
            print(f"  Local path: {config.local_path}")
            print(f"  GitHub: {config.github_owner}/{config.github_repo}")
            
            # Show git info
            if config.last_commit:
                print(f"  Last commit: {config.last_commit[:8]}")
            
        except Exception as e:
            print(f"✗ Failed to register: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'='*60}")
    print("Registration complete!")
    print(f"{'='*60}")
    
    # List all registered repos
    print("\nRegistered repositories:")
    repos = await manager.get_registered_repos()
    for repo in repos:
        print(f"  - {repo['name']} ({repo['repo_id'][:8]}...): {repo['github_url']}")


if __name__ == '__main__':
    asyncio.run(register_repositories())
