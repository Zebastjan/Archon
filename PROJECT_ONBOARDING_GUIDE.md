# Archon Project Onboarding Guide

## Quick Start

### Automatic Setup (Recommended)

```bash
# 1. Set up git template (run once)
~/dev/archon/scripts/setup-git-template.sh

# 2. Add tools to your shell
source ~/.bashrc

# 3. Initialize a new or existing project
archon-project-init ~/dev/my-new-project
# or
cd ~/dev/existing-project && archon-project-init .
```

## What Gets Set Up Automatically

When you run `archon-project-init`, the following happens:

1. **Git Hooks** - Installed for auto-sync:
   - `post-commit` - Queues incremental sync after each commit
   - `post-checkout` - Updates worktree context on branch switch
   - `post-merge` - Full re-sync after merges

2. **Project Registration** - Added to Archon database:
   - Repository ID assigned
   - Path registered
   - Language detected (Python, TypeScript, Nim, Rust)

3. **Configuration Files**:
   - `.archon/config.yaml` - Project settings
   - `.archonignore` - Files to exclude from indexing

4. **Initial Indexing** - Code extracted and stored:
   - Functions, classes, methods identified
   - Relationships (calls, inherits, defines) built
   - Source code stored in database

## Commands Available

| Command | Purpose |
|---------|---------|
| `archon-project-init <path>` | Initialize a project with Archon |
| `archon-embeddings [repo]` | Generate embeddings (background) |
| `archon-health` | Check system health |
| `archon` | Quick cd to archon directory |

## Workflow

### Starting a New Project

```bash
# Create and enter new project
mkdir ~/dev/my-project && cd ~/dev/my-project

# Initialize with Archon (also runs git init if needed)
archon-project-init .

# ... do work ...

# First commit triggers initial indexing
git add .
git commit -m "Initial commit"
```

### Working with Existing Projects

```bash
# Any project in ~/dev/* will auto-initialize when you enter
cd ~/dev/some-project

# If hooks aren't installed, run:
archon-project-init .

# Check project health
archon-health

# Start embedding generation in background
archon-embeddings my-project
```

### Repository Sync Behavior

| Action | Sync Type | Trigger |
|--------|-----------|---------|
| `git commit` | Incremental | post-commit hook |
| `git checkout <branch>` | Context update | post-checkout hook |
| `git merge` | Full re-sync | post-merge hook |
| Manual trigger | On-demand | `archon-embeddings` |

## Project Types

### Nim Projects

Nim gets special treatment:
- Tree-sitter parsing for procedures, types, templates
- Pragma extraction (async, inline, etc.)
- Generic type parameter detection
- "object of" inheritance tracking

```bash
# If Nim extraction seems incomplete:
~/dev/archon/scripts/fix-nim-extraction
```

### TypeScript/JavaScript Projects

- React/JSX support
- Type definitions extracted
- Import/export relationships tracked

### Python Projects

- Class inheritance tracked
- Decorator support
- Type hints extracted

## Background Processes

### Embedding Generation

Embeddings are CPU-intensive. Run them in background:

```bash
# All repos
archon-embeddings

# Specific repo
archon-embeddings my-project

# Check progress
tail -f ~/.local/log/archon-embeddings.log

# Check if running
pgrep -f "generate_embeddings"
```

### Monitoring

Health check runs automatically via git hooks, but you can:

```bash
# Manual check
archon-health

# Add to crontab for daily checks
echo "0 9 * * * /home/zebastjan/.local/bin/archon-health >> /var/log/archon-health.log 2>&1" | crontab -
```

## Troubleshooting

### Hooks Not Running

```bash
# Reinstall hooks
archon-project-init .

# Or manually reinit
git init  # Reapplies template hooks
```

### Database Connection Issues

Ensure environment is set:

```bash
export ARCHON_DATABASE_URL="postgresql://archon:archon_local_dev@localhost:5434/archon"
```

### Ollama Not Responding

```bash
# Start Ollama
ollama serve &

# Verify
ollama list
```

### Project Not Showing in Archon

```bash
# Re-register
archon-project-init /path/to/project

# Verify
cd ~/dev/archon
. python/.venv/bin/activate
python -c "
from src.server.services.database import get_database_connector, initialize_database
import asyncio

async def check():
    await initialize_database()
    db = get_database_connector()
    repos = await db.fetch('SELECT name FROM archon_code_repos ORDER BY name')
    for r in repos:
        print(f'  - {r[\"name\"]}')

asyncio.run(check())
"
```

## Configuration Reference

### `.archon/config.yaml`

```yaml
project:
  name: my-project
  language: python  # python, typescript, nim, rust, go, etc.
  auto_sync: true
  sync_on_commit: true
  sync_on_branch_switch: true
  
code_intelligence:
  extract_entities: true
  build_relationships: true
  generate_embeddings: true
  index_frequency: commit
  
analysis:
  semgrep_rules: ["security", "quality"]
  audit_on_change: true
  coverage_threshold: 80
```

### `.archonignore`

Similar to `.gitignore` - patterns for files to exclude from code indexing:

```
# Dependencies
node_modules/
vendor/

# Tests
*_test.py
tests/

# Generated
*.generated.ts
gen/
```

## Advanced: Custom Workflows

### Meta-Workflow Setup

For establishing project-specific workflows:

1. Initialize project with Archon
2. Create `.archon/workflow.md` describing project conventions
3. Define in `.archon/config.yaml`:
   - Testing approach
   - Documentation standards
   - Review requirements

Example workflow file:

```markdown
# My Project Workflow

## Language: Nim
## Testing: unittest
## Docs: Nim doc comments

### Development Flow
1. Create task in Archon
2. Branch: feature/<description>
3. Write tests first
4. Implement with doc comments
5. Run `nim doc` to verify
6. Commit triggers auto-sync
```

## Summary

**Automatic (happens without thinking):**
- Git hooks auto-installed
- Commits trigger code indexing
- Branch switches update context
- Embeddings generate in background

**Manual (when you need to):**
- `archon-project-init` - New project setup
- `archon-health` - Health check
- `archon-embeddings` - Force embedding generation

**Goal:** Zero-friction code intelligence for every project.
