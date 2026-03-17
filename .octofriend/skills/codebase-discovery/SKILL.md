# Codebase Discovery Skill

Rapid initial exploration of any codebase to understand its structure, scale, and existing issues.

## When to Use

Use this skill when:
- Starting work on a new codebase
- Getting an overview before diving into details
- Onboarding to a new project
- Planning work across multiple repositories

## When NOT to Use

Do NOT use when:
- You already have detailed context about the codebase
- You're focusing on a single specific function (use function-deep-dive instead)
- You need audit findings only (use audit_get_context directly)

## Workflow

### Step 1: Discovery Batch
Run these calls in parallel using the batch tool:

```
find_projects(query="<project_name>")  # If project name known
OR
find_projects()  # List all projects

codebase_get_repository_stats(repo_id)
audit_get_context(repo_name)
worktree_get_current_info()
```

### Step 2: Analysis
From the results:
1. **Project Overview**: Identify the project from find_projects results
2. **Repository Stats**: Note total files, entities, languages, complexity
3. **Audit Context**: Review existing findings grouped by source
4. **Git Context**: Current branch, uncommitted changes, worktree state

### Step 3: Presentation
Structure your response as:

```markdown
# Codebase Overview: [Project Name]

## Summary
- **Total Files**: X | **Entities**: Y | **Languages**: [list]
- **Health Indicators**: Avg complexity, TODO/FIXME counts
- **Current Context**: Branch [name], [N] uncommitted changes

## Key Directories/Files
[List most important based on entity counts]

## Existing Findings
[Summarize from audit_get_context results]
- Critical: X | Error: Y | Warning: Z
- Top sources: [list]

## Recommendations
- [Suggested next steps based on findings]
```

## Batching Rules

**MUST batch these calls** - they are independent:
- `find_projects` + `codebase_get_repository_stats` + `audit_get_context` + `worktree_get_current_info`

**Tool call limit**: This skill should use exactly **1 batch call** for discovery.

## Error Handling

| Error | Action |
|-------|--------|
| Repository not found | Ask user for correct repo name/ID |
| No audit findings | Report "No existing findings found" |
| Worktree not in git | Report "Not in a git repository" |

## Example Invocation

User: "Explore the archon codebase"

Claude: [runs batch with find_projects(query="archon"), codebase_get_repository_stats, audit_get_context, worktree_get_current_info]

Claude: "# Codebase Overview: Archon

**Summary**: 127 files, 842 entities across Python (78%), TypeScript (15%), SQL (7%)
**Health**: Avg cyclomatic complexity 4.2, 23 TODOs, 5 FIXMEs
**Current**: On branch feature/multi-language, 42 uncommitted changes

**Key Files**:
- python/src/mcp_server/mcp_server.py (32 entities)
- python/src/server/services/ (127 entities across services/)

**Existing Findings**:
- Critical: 0 | Error: 3 | Warning: 12
- Main sources: semgrep (10), audit_rules (5)

**Recommended Next Steps**:
1. Address 3 ERROR-level findings in authentication code
2. Review complexity in mcp_server.py (score: 8.5)"
