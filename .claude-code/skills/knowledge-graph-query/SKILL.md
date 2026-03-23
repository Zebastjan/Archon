# Knowledge Graph Query Skill

Query code evolution and cross-commit/branch relationships using the knowledge graph.

## When to Use

Use this skill when:
- Tracking how a function/class evolved over time
- Comparing code between branches
- Finding when an entity was first added
- Understanding commit-level changes
- Auditing code history

## Available Tools

### 1. codebase_entity_evolution
**Purpose**: Track entity versions across commits

```python
codebase_entity_evolution(
    repo_id="<repo_uuid>",
    entity_name="function_name",
    entity_type="function",  # Optional
    limit=10
)
```

**Returns**: All versions with commit SHAs, branches, change types

**Example**: Find how `authenticate_user` changed over time

### 2. codebase_commits
**Purpose**: List commits with change summaries

```python
codebase_commits(
    repo_id="<repo_uuid>",
    limit=20
)
```

**Returns**: Commits with entity counts, files changed, added/modified/deleted breakdown

**Example**: See recent commit activity

### 3. codebase_compare_branches
**Purpose**: Compare entities between two branches

```python
codebase_compare_branches(
    repo_id="<repo_uuid>",
    branch1="main",
    branch2="feature/auth"
)
```

**Returns**: Entities unique to each branch

**Example**: See what's different in feature branch

### 4. codebase_when_added
**Purpose**: Find when entity first appeared

```python
codebase_when_added(
    repo_id="<repo_uuid>",
    entity_name="UserService"
)
```

**Returns**: First commit SHA, branch, timestamp

**Example**: Find origin of a class

## Workflow Patterns

### Pattern 1: Track Function Evolution
```
1. codebase_entity_evolution(repo_id, entity_name="load_config")
2. Review versions chronologically
3. Use codebase_get_entity_details for specific version
```

### Pattern 2: Compare Branches
```
1. codebase_compare_branches(repo_id, branch1="main", branch2="feature")
2. Review entities unique to each branch
3. Deep dive on important differences
```

### Pattern 3: Audit New Code
```
1. codebase_commits(repo_id, limit=5)
2. Identify recent commits
3. codebase_when_added for specific entities
```

## Batching Rules

✅ **CAN batch**:
- Multiple entity_evolution calls (different entities)
- commits + when_added (independent)

❌ **CANNOT batch**:
- compare_branches depends on branches existing
- Sequential queries requiring user review

## Example Session

**User**: "Show me how the load_config function evolved"

Claude:
1. Call: `codebase_entity_evolution(repo_id, "load_config")`
2. Review: 3 versions found
3. Present:
   ```markdown
   # Evolution of load_config
   
   ## Version 1 (oldest) - commit abc123
   - Branch: feature/config-refactor
   - Change: added
   - Lines: 45-67
   
   ## Version 2 - commit def456
   - Branch: feature/config-refactor
   - Change: modified
   - Lines: 45-89 (expanded)
   
   ## Version 3 (latest) - commit ghi789
   - Branch: main
   - Change: modified
   - Lines: 50-95 (moved)
   ```

## Repository IDs

Use these IDs when calling tools:

| Repository | ID |
|------------|-----|
| archon | 3e01a03c-f9ef-417d-bdd6-9da6b1d32ad2 |
| syllablaze | 6a783e2e-a0b4-4c1d-8e5f-9g0h1i2j3k4l |
| octofriend | 1c6cdcee-5d4e-4f3a-9b2c-8d7e6f5a4b3c |
| Omnibus | 2f84ad51-f35c-43e8-9f0b-7f69ed3eb88b |

**Note**: Get current IDs with `code_repos_list()`

## Prerequisites

- Multi-commit indexing must be enabled (already done)
- Database must have entities from multiple commits
- Embeddings generated for semantic comparison

## Integration with Other Skills

**After finding entity in evolution**:
- Use `function-deep-dive` for detailed analysis
- Use `impact-analysis` to see downstream effects
- Use `semantic-code-search` to find similar patterns

## Error Handling

| Error | Solution |
|-------|----------|
| "Entity not found" | Check exact name with codebase_find_entity |
| "Repo not found" | Run code_repos_list to get valid IDs |
| "No commits" | Repository may need multi-commit indexing |
| "No branches" | Only one branch indexed, need more commits |

## Performance Notes

- Queries are fast (<100ms) with proper indexes
- Limit results to avoid overwhelming output
- Use specific entity_type filters when possible
- Branch comparisons can be slow for large repos

## Examples

### Example 1: Track Function Changes
```python
# Find evolution
result = await codebase_entity_evolution(
    repo_id="3e01a03c-f9ef-417d-bdd6-9da6b1d32ad2",
    entity_name="generate_embeddings",
    entity_type="function",
    limit=5
)

# Present to user
for v in result["versions"]:
    print(f"{v['commit_sha']}: {v['change_type']} ({v['lines']})")
```

### Example 2: Compare Feature Branch
```python
result = await codebase_compare_branches(
    repo_id="3e01a03c-f9ef-417d-bdd6-9da6b1d32ad2",
    branch1="main",
    branch2="feature/knowledge-graph"
)

print(f"Only in feature branch: {result['only_in_branch2']['count']} entities")
```

### Example 3: Find Origin
```python
result = await codebase_when_added(
    repo_id="3e01a03c-f9ef-417d-bdd6-9da6b1d32ad2",
    entity_name="EmbeddingService"
)

print(f"First appeared in commit {result['commit_sha']} on {result['first_seen']}")
```
