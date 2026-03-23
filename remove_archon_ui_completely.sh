#!/bin/bash
# COMPLETELY REMOVE ARCHON-UI FROM THE SYSTEM
# This script removes archon-ui from:
# 1. Database (entities, repo record)
# 2. Documentation files
# 3. Python code references
# 4. The actual directory

set -e

echo "=========================================="
echo "REMOVING ARCHON-UI COMPLETELY"
echo "=========================================="
echo ""

# Step 1: Remove from database
echo "Step 1: Removing from database..."
cd /home/zebastjan/dev/archon/python
source .venv/bin/activate 2>/dev/null || true

python3 << 'PYTHON_EOF'
import asyncio
import sys
sys.path.insert(0, "src")

from server.services.database.db_connector import get_database_connector, initialize_database

async def remove_archon_ui():
    print("  Connecting to database...")
    await initialize_database()
    db = get_database_connector()
    
    # Get archon-ui repo ID
    repo = await db.fetchrow(
        "SELECT id FROM archon_code_repos WHERE name ILIKE '%archon-ui%' OR name ILIKE '%archon_ui%'"
    )
    
    if not repo:
        print("  No archon-ui repo found in database")
        return
    
    repo_id = repo["id"]
    print(f"  Found archon-ui repo: {repo_id}")
    
    # Count entities
    count = await db.fetchval(
        "SELECT COUNT(*) FROM archon_code_entities WHERE repo_id = $1",
        repo_id
    )
    print(f"  Entities to delete: {count:,}")
    
    # Delete relationships first
    await db.execute("""
        DELETE FROM archon_code_relationships 
        WHERE source_entity_id IN (
            SELECT id FROM archon_code_entities WHERE repo_id = $1
        ) OR target_entity_id IN (
            SELECT id FROM archon_code_entities WHERE repo_id = $1
        )
    """, repo_id)
    print("  Deleted relationships")
    
    # Delete entities
    await db.execute(
        "DELETE FROM archon_code_entities WHERE repo_id = $1",
        repo_id
    )
    print("  Deleted entities")
    
    # Delete repo record
    await db.execute(
        "DELETE FROM archon_code_repos WHERE id = $1",
        repo_id
    )
    print("  Deleted repo record")
    
    print("  ✓ Database cleanup complete")

asyncio.run(remove_archon_ui())
PYTHON_EOF

echo ""
echo "Step 2: Removing archon-ui references from documentation..."

# Remove from AGENTS.md
if [ -f /home/zebastjan/dev/archon/.opencode/AGENTS.md ]; then
    sed -i '/archon-ui/d' /home/zebastjan/dev/archon/.opencode/AGENTS.md
    sed -i '/59f97679-1483-4be6-822b-5798e6c29679/d' /home/zebastjan/dev/archon/.opencode/AGENTS.md
    sed -i '/archon-ui-main/d' /home/zebastjan/dev/archon/.opencode/AGENTS.md
    echo "  ✓ Cleaned .opencode/AGENTS.md"
fi

# Remove from MCP_AGENT_GUIDE.md
if [ -f /home/zebastjan/dev/archon/docs/MCP_AGENT_GUIDE.md ]; then
    sed -i '/archon-ui/d' /home/zebastjan/dev/archon/docs/MCP_AGENT_GUIDE.md
    sed -i '/59f97679-1483-4be6-822b-5798e6c29679/d' /home/zebastjan/dev/archon/docs/MCP_AGENT_GUIDE.md
    echo "  ✓ Cleaned docs/MCP_AGENT_GUIDE.md"
fi

# Remove from MCP_SETUP_SUMMARY.md
if [ -f /home/zebastjan/dev/archon/MCP_SETUP_SUMMARY.md ]; then
    sed -i '/archon-ui/d' /home/zebastjan/dev/archon/MCP_SETUP_SUMMARY.md
    sed -i '/59f97679-1483-4be6-822b-5798e6c29679/d' /home/zebastjan/dev/archon/MCP_SETUP_SUMMARY.md
    echo "  ✓ Cleaned MCP_SETUP_SUMMARY.md"
fi

echo ""
echo "Step 3: Removing archon-ui references from Python code..."

# Remove from codebase_tools.py
if [ -f /home/zebastjan/dev/archon/python/src/server/mcp_server/codebase_tools.py ]; then
    sed -i '/archon-ui/d' /home/zebastjan/dev/archon/python/src/server/mcp_server/codebase_tools.py
    echo "  ✓ Cleaned codebase_tools.py"
fi

# Remove from scripts
if [ -f /home/zebastjan/dev/archon/scripts/setup_archon_repo.py ]; then
    sed -i '/archon-ui/d' /home/zebastjan/dev/archon/scripts/setup_archon_repo.py
    sed -i '/archon_ui/d' /home/zebastjan/dev/archon/scripts/setup_archon_repo.py
    echo "  ✓ Cleaned scripts/setup_archon_repo.py"
fi

if [ -f /home/zebastjan/dev/archon/scripts/ingest_archon_repo.py ]; then
    sed -i '/archon-ui/d' /home/zebastjan/dev/archon/scripts/ingest_archon_repo.py
    sed -i '/TYPESCRIPT_SOURCE_DIR/d' /home/zebastjan/dev/archon/scripts/ingest_archon_repo.py
    echo "  ✓ Cleaned scripts/ingest_archon_repo.py"
fi

if [ -f /home/zebastjan/dev/archon/analyze_archon_codebase.py ]; then
    sed -i '/archon-ui/d' /home/zebastjan/dev/archon/analyze_archon_codebase.py
    echo "  ✓ Cleaned analyze_archon_codebase.py"
fi

echo ""
echo "Step 4: Removing archon-ui directory..."

ARCHON_UI_DIR="/home/zebastjan/dev/archon/archon-ui-main"
if [ -d "$ARCHON_UI_DIR" ]; then
    echo "  Found archon-ui-main directory"
    echo "  Size: $(du -sh $ARCHON_UI_DIR | cut -f1)"
    
    # Move to trash instead of permanent delete (safer)
    TRASH_DIR="/home/zebastjan/.trash/archon-ui-main-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$TRASH_DIR"
    mv "$ARCHON_UI_DIR" "$TRASH_DIR/"
    echo "  ✓ Moved to $TRASH_DIR"
    echo "  (Delete permanently with: rm -rf $TRASH_DIR)"
else
    echo "  archon-ui-main directory not found (already removed?)"
fi

echo ""
echo "Step 5: Updating docker-compose if needed..."

# Check if archon-ui is in docker-compose
if [ -f /home/zebastjan/dev/archon/docker-compose.yml ]; then
    if grep -q "archon-ui" /home/zebastjan/dev/archon/docker-compose.yml; then
        sed -i '/archon-ui/,/^[a-z]/d' /home/zebastjan/dev/archon/docker-compose.yml
        echo "  ✓ Cleaned docker-compose.yml"
    fi
fi

echo ""
echo "=========================================="
echo "REMOVAL COMPLETE"
echo "=========================================="
echo ""
echo "Summary:"
echo "  - Database: archon-ui repo and all entities deleted"
echo "  - Documentation: References removed"
echo "  - Code: References removed from Python files"
echo "  - Directory: Moved to trash"
echo ""
echo "Remaining repos:"
echo "  - archon-python (76abe5b8...)"
echo "  - syllablaze (c8b210fa...)"
echo "  - octofriend (358e1fae...)"
echo ""
