#!/bin/bash
# Git hooks setup for automatic code re-indexing on commit/branch change
# Run this from each repository you want to auto-sync

set -e

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "")

if [ -z "$REPO_ROOT" ]; then
    echo "Error: Not in a git repository"
    exit 1
fi

HOOKS_DIR="$REPO_ROOT/.git/hooks"
REPO_NAME=$(basename "$REPO_ROOT")

echo "Setting up git hooks for $REPO_NAME..."

# Create post-commit hook
cat > "$HOOKS_DIR/post-commit" << 'EOF'
#!/bin/bash
# Auto-sync code entities to Archon after each commit

REPO_NAME=$(basename $(git rev-parse --show-toplevel))
REPO_ID=$(cd /home/zebastjan/dev/archon/python && python -c "
import asyncio
from src.server.services.database import get_database_connector

async def get_repo_id():
    db = get_database_connector()
    result = await db.fetchrow(
        'SELECT id FROM archon_code_repos WHERE name = \$1',
        '$REPO_NAME'
    )
    print(result['id'] if result else '')

asyncio.run(get_repo_id())
")

if [ -n "$REPO_ID" ]; then
    echo "[Archon] Queueing code sync for $REPO_NAME..."
    curl -s -X POST http://localhost:8181/api/code-repos/$REPO_ID/sync \
        -H "Content-Type: application/json" \
        -d '{"incremental": true}' > /dev/null 2>&1 || true
fi
EOF
chmod +x "$HOOKS_DIR/post-commit"

# Create post-checkout hook (for branch switches)
cat > "$HOOKS_DIR/post-checkout" << 'EOF'
#!/bin/bash
# Auto-sync when switching branches
PREVIOUS_HEAD=$1
NEW_HEAD=$2
BRANCH_SWITCH=$3

if [ "$BRANCH_SWITCH" = "1" ]; then
    BRANCH_NAME=$(git branch --show-current)
    REPO_NAME=$(basename $(git rev-parse --show-toplevel))
    
    echo "[Archon] Branch switched to $BRANCH_NAME, syncing worktree context..."
    
    # Update worktree context in database
    cd /home/zebastjan/dev/archon/python && python -c "
import asyncio
import sys
sys.path.insert(0, '.')

async def sync_context():
    from src.server.services.worktree_service import get_worktree_service
    service = get_worktree_service()
    # Just detect context - tasks will pick up new branch
    ctx = service.detect_worktree_context()
    print(f'Worktree context: {ctx.branch_name}')

asyncio.run(sync_context())
" 2>/dev/null || true
fi
EOF
chmod +x "$HOOKS_DIR/post-checkout"

echo "✓ Git hooks installed for $REPO_NAME"
echo "  - post-commit: Auto-sync after commits"
echo "  - post-checkout: Track branch switches"
