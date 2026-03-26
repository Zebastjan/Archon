# Skills Indexing Guide

## Overview

The skills/ directory contains prompts, workflows, and documentation for AI agents.
Indexing makes these searchable via semantic search, enabling agents to find relevant
guidance without knowing exact file names.

## Why Index Skills?

Skills ARE documentation for this project. When an agent asks:
- "How do I create a feature branch?" → finds `skills/workflows/feature-branch.md`
- "What commit hooks are available?" → finds `skills/commit-hooks/doc-maintenance.md`
- "How do I use search tools?" → finds `skills/mcp/version-scoped-search.md`

## Tools

### `skills_index(repo_id, commit_sha=None)`
Index all skills in the skills/ directory.

**When to use:**
- After adding new skill files
- After modifying existing skills
- On first setup

**Example:**
```python
await skills_index(repo_id="uuid")
```

**Returns:**
```json
{
    "success": true,
    "indexed": 5,
    "unchanged": 6,
    "errors": 0
}
```

### `skills_discover()`
Discover all skill files without indexing them.

**When to use:**
- Check what skills exist
- Verify skill file names
- Debug indexing issues

**Example:**
```python
await skills_discover()
```

**Returns:**
```json
{
    "success": true,
    "count": 11,
    "skills": [
        {"path": "skills/commit-hooks/doc-maintenance.md", "category": "commit-hooks", "name": "doc_maintenance"},
        {"path": "skills/prompts/branch-discipline.md", "category": "prompts", "name": "branch_discipline"}
    ]
}
```

### `skills_delete(repo_id, skill_path)`
Delete a skill file from the knowledge base.

**When to use:**
- After removing a skill file from repository
- To clear old skill data

**Example:**
```python
await skills_delete(
    repo_id="uuid",
    skill_path="skills/prompts/old-skill.md"
)
```

## Skill Categories

| Category | Purpose |
|----------|---------|
| `commit-hooks` | What runs on commit (doc-maintenance, test-coverage, code-audit) |
| `ide-setup` | How to configure each IDE (claude-code, opencode, windsurf) |
| `mcp` | MCP tool documentation and guides |
| `prompts` | Reusable prompts for agents (session-bootstrap, branch-discipline) |
| `workflows` | Step-by-step workflows (feature-branch, zig-zag-workflow) |

## Workflow

### Adding a New Skill
1. Create file in appropriate category: `skills/category/name.md`
2. Use kebab-case for filename (e.g., `doc-maintenance.md`)
3. Write clear, actionable content
4. Run `skills_index()` to index it

### Updating a Skill
1. Edit the skill file
2. Run `skills_index()` - only changed files are re-indexed

### Removing a Skill
1. Delete the file from `skills/`
2. Run `skills_delete()` to remove from index

### On First Setup
```python
# Index all skills
await skills_index(repo_id="uuid")

# Verify indexing
await skills_discover()
```

## Current Skills

### commit-hooks/
- `code-audit.md` - Code audit hook documentation
- `test-coverage.md` - Test coverage analysis
- `doc-maintenance.md` - Documentation maintenance

### ide-setup/
- `claude-code.md` - Claude Code setup
- `opencode.md` - OpenCode setup

### mcp/
- `version-scoped-search.md` - Search tool documentation
- `working-tree-reindex.md` - Working tree re-indexing (new)

### prompts/
- `session-bootstrap.md` - Prompt to bootstrap agent
- `branch-discipline.md` - Branch/worktree rules reminder
- `leverage-mcp-tools.md` - How to use MCP tools effectively

### workflows/
- `feature-branch.md` - Feature branch workflow
- `zig-zag-workflow.md` - Context switching workflow

## Troubleshooting

- **Skills not found in search**: Run `skills_index()` to index them
- **Discover returns 0**: Check skills/ directory exists and has .md files
- **Index returns errors**: Check file permissions and encoding
