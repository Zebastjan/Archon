# Knowledge Graph Query Skill

Query code evolution, commit history, and branch comparisons.

## When to Use

Use this skill for:
- **Tracking evolution**: "How did this function change over time?"
- **Comparing branches**: "What's different in the feature branch?"
- **Finding origins**: "When was this class first added?"
- **Reviewing commits**: "Show recent code changes"

## When NOT to Use

Do NOT use when:
- You need current code only (use codebase_find_entity)
- You want semantic search (use semantic-code-search)
- Looking for specific implementation details (use function-deep-dive after finding)

## Tools

### codebase_entity_evolution
Track entity versions across commits.

```python
codebase_entity_evolution(
    repo_id="<uuid>",
    entity_name="function_name",
    entity_type="function",  # Optional
    limit=10
)
```

**Returns**: Array of versions with commit SHAs, branches, change types.

### codebase_commits
List commits with change summaries.

```python
codebase_commits(
    repo_id="<uuid>",
    limit=20
)
```

**Returns**: Commits with entity counts, files changed, added/modified/deleted.

### codebase_compare_branches
Compare entities between two branches.

```python
codebase_compare_branches(
    repo_id="<uuid>",
    branch1="main",
    branch2="feature/auth"
)
```

**Returns**: Entities unique to each branch.

### codebase_when_added
Find when entity first appeared.

```python
codebase_when_added(
    repo_id="<uuid>",
    entity_name="ClassName"
)
```

**Returns**: First commit SHA, branch, timestamp.

## Repository IDs

| Repository | ID |
|------------|-----|
| archon | 3e01a03c-f9ef-417d-bdd6-9da6b1d32ad2 |
| syllablaze | 6a783e2e-a0b4-4c1d-8e5f-9g0h1i2j3k4l |
| octofriend | 1c6cdcee-5d4e-4f3a-9b2c-8d7e6f5a4b3c |
| Omnibus | 2f84ad51-f35c-43e8-9f0b-7f69ed3eb88b |

**Note**: Use `code_repos_list()` to get current IDs.

## Workflow Patterns

### Pattern 1: Track Evolution
```
User: "How did load_config evolve?"

Step 1: codebase_entity_evolution(repo_id, "load_config")
Step 2: Review versions chronologically
Step 3: Optional: codebase_get_entity_details for specific version
```

### Pattern 2: Compare Branches
```
User: "What's in feature/auth that's not in main?"

Step 1: codebase_compare_branches(repo_id, "main", "feature/auth")
Step 2: Review entities unique to feature branch
Step 3: Optional: Deep dive on important entities
```

### Pattern 3: Find Origin
```
User: "When was EmbeddingService added?"

Step 1: codebase_when_added(repo_id, "EmbeddingService")
Step 2: Present commit and date
Step 3: Optional: codebase_commits to see context
```

### Pattern 4: Review Recent Activity
```
User: "Show recent commits"

Step 1: codebase_commits(repo_id, limit=10)
Step 2: Present commits with change summaries
Step 3: Optional: codebase_entity_evolution for specific entities
```

## Batching

✅ **Can batch**: Multiple entity_evolution calls (different entities)  
✅ **Can batch**: commits + when_added (independent)  
❌ **Cannot batch**: compare_branches (needs both branches)

## Examples

### Example 1: Evolution Tracking
```
User: "Show how authenticate_user evolved"

Claude: codebase_entity_evolution(
    repo_id="3e01a03c-f9ef-417d-bdd6-9da6b1d32ad2",
    entity_name="authenticate_user",
    entity_type="function"
)

Claude: "Found 3 versions:

**Version 1 (oldest)** - commit abc123
- Branch: feature/auth
- Change: added
- Lines: 45-67

**Version 2** - commit def456  
- Branch: feature/auth
- Change: modified
- Lines: 45-89 (expanded password validation)

**Version 3 (current)** - commit ghi789
- Branch: main
- Change: modified
- Lines: 50-95 (added rate limiting)"
```

### Example 2: Branch Comparison
```
User: "What's different in feature branch?"

Claude: codebase_compare_branches(
    repo_id="3e01a03c-f9ef-417d-bdd6-9da6b1d32ad2",
    branch1="main",
    branch2="feature/api-v2"
)

Claude: "Feature branch has 15 entities not in main:

**Key additions:**
- APIv2Router (class) - src/api/routes.py
- validate_api_key (function) - src/auth/validator.py
- rate_limit_middleware (function) - src/middleware/rate_limit.py

**Modified:**
- authenticate_user (function) - src/auth/login.py
- UserService (class) - src/services/user.py"
```

### Example 3: Find Origin
```
User: "When was EmbeddingService first added?"

Claude: codebase_when_added(
    repo_id="3e01a03c-f9ef-417d-bdd6-9da6b1d32ad2",
    entity_name="EmbeddingService"
)

Claude: "EmbeddingService was first added:
- Commit: 1a2b3c4d
- Branch: feature/embeddings
- Date: 2026-03-20 14:32:15 UTC
- File: src/services/embedding_service.py"
```

## Integration

**After evolution query**:
- Use `codebase_get_entity_details` for specific version
- Use `codebase_get_entity_context` for call graph
- Use `function-deep-dive` for comprehensive analysis

**After branch comparison**:
- Use `impact-analysis` to assess change scope
- Use `semantic-code-search` to find similar patterns
- Use `security-audit` if adding auth code

## Error Handling

| Error | Solution |
|-------|----------|
| "Entity not found" | Check exact name with `codebase_find_entity` |
| "Repo not found" | Use `code_repos_list` to get valid ID |
| "No commits" | Repository needs multi-commit indexing |
| "Branch not found" | Branch may not be indexed yet |

## Performance

- Queries: <100ms with proper indexes
- Branch compare: <500ms for repos <10k entities
- Set reasonable limits (5-20) for readability

## Prerequisites

✅ Multi-commit indexing enabled  
✅ Entities indexed from multiple commits  
✅ Repository registered in archon_code_repos

## See Also

- **semantic-code-search**: Find code by behavior
- **function-deep-dive**: Detailed function analysis
- **impact-analysis**: Assess change scope
- **audit-context**: Get audit findings

## Version

v1.0 - Added 4 knowledge graph tools  
- codebase_entity_evolution  
- codebase_commits  
- codebase_compare_branches  
- codebase_when_added
