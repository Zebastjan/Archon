# Impact Analysis Skill

Understand the full scope of changes by mapping dependencies, callers, and potential conflicts.

## When to Use

Use this skill when:
- Planning to modify a function/class
- Refactoring code
- Assessing risk of a change
- Understanding "what will break"
- Preparing for a significant code change

## When NOT to Use

Do NOT use when:
- Just reading code (use function-deep-dive)
- The change is trivial (e.g., comment update)
- You haven't identified the target yet (use codebase_search_by_semantics)

## Workflow

### Step 1: Locate Target

```
codebase_find_entity(repo_id, name="<target_name>", entity_type="<type>")
```

**If multiple matches**: Present options or ask for clarification.

### Step 2: Impact Analysis Batch

Run these calls in parallel:

```
codebase_get_entity_context(
    entity_id,
    include_callers=True,
    include_callees=True,
    max_depth=2  # Deeper for impact analysis
)
code_audit_analyze_entity(entity_id)
worktree_find_conflicts(file_paths=[target_file_path])
```

### Step 3: Extended Impact (Optional)

For each significant caller, analyze their context:

```
codebase_get_entity_context(caller_id, include_callers=True, max_depth=1)
```

**Only do this for**:
- Callers with high complexity
- Callers that are themselves widely used
- Critical path functions

### Step 4: Presentation

Structure your response:

```markdown
# Impact Analysis: [target_name]

**Location**: [file_path]:[line_start]-[line_end]
**Type**: [function/class/method]

## Complexity Assessment
- Cyclomatic Complexity: [X]
- Risk Level: [Low/Medium/High/Critical]
- [Based on complexity + caller count]

## Upstream Impact (Called By)
[Tree structure showing who calls this]

### Direct Callers ([count])
- [caller_name] ([file]:[line]) - [complexity] - [brief description]

### Indirect Callers (depth 2) ([count])
- [indirect_caller] → [direct_caller] → [target]

## Downstream Impact (Calls)
[What this function depends on]

### Direct Dependencies ([count])
- [callee_name] in [file]:[line]

## Worktree Conflicts
[From worktree_find_conflicts]
- ✅ No conflicts
- OR
- ⚠️ Conflicts with: [task_id] modifying [file]

## Risk Assessment

| Factor | Rating | Notes |
|--------|--------|-------|
| Complexity | [Low/Med/High] | [Justification] |
| Caller Count | [Low/Med/High] | [X direct, Y indirect] |
| Critical Path | [Yes/No] | [Is this in critical flows?] |
| Test Coverage | [Unknown/Low/Med/High] | [If known] |

## Recommendations
1. [Specific recommendation based on analysis]
2. [Testing strategy]
3. [Rollback plan if applicable]
```

## Complexity Risk Matrix

Use this to assess overall risk:

| Cyclomatic Complexity | Caller Count | Risk Level |
|----------------------|--------------|------------|
| 1-5 | 1-3 | Low |
| 1-5 | 4-10 | Medium |
| 6-10 | 1-3 | Medium |
| 6-10 | 4-10 | High |
| 11+ | Any | High |
| Any | 11+ | Critical |

## Batching Rules

**Step 2 MUST be batched** - independent calls:
- `codebase_get_entity_context` + `code_audit_analyze_entity` + `worktree_find_conflicts`

**Step 3** (Extended): Batch up to 5 caller contexts at a time

**Maximum calls**:
- Basic analysis: 2 calls (1 locate + 1 batch)
- Extended analysis: 2 + ceil(caller_count/5) batches

## Depth Configuration

| Use Case | max_depth | Rationale |
|----------|-----------|-----------|
| Quick impact check | 1 | Direct callers only |
| Standard analysis | 2 | See indirect impact |
| Deep refactoring | 3 | Full dependency tree |

## Example Invocation

User: "What will break if I change the authenticate function?"

Claude: [Step 1: codebase_find_entity(repo_id, name="authenticate")]
→ Found: authenticate (ent-123) in auth.py:45-89

Claude: [Step 2 batch: codebase_get_entity_context, code_audit_analyze_entity, worktree_find_conflicts]
→ Context: 8 direct callers, 12 indirect (depth 2)
→ Complexity: 7 (medium)
→ Conflicts: None

Claude: "# Impact Analysis: authenticate

**Location**: auth.py:45-89
**Type**: function

## Complexity Assessment
- Cyclomatic Complexity: 7
- Risk Level: **HIGH** (medium complexity + high caller count)

## Upstream Impact

### Direct Callers (8)
- `login_user` (routes.py:45) - complexity: 4 - HTTP login endpoint
- `refresh_token` (auth.py:156) - complexity: 3 - Token refresh
- `api_middleware` (middleware.py:23) - complexity: 9 - **HIGH COMPLEXITY**
- `sso_callback` (oauth.py:78) - complexity: 5 - OAuth callback
- [4 more...]

### Indirect Callers (12)
- `web_login` → `login_user` → authenticate
- `mobile_api` → `api_middleware` → authenticate
- [10 more...]

## Risk Assessment

| Factor | Rating | Notes |
|--------|--------|-------|
| Complexity | Medium | CC=7, manageable but not trivial |
| Caller Count | High | 8 direct, 12 indirect |
| Critical Path | **YES** | Authentication is core flow |
| Test Coverage | Unknown | Recommend checking tests |

## Recommendations
1. **Create comprehensive tests** before changing - this is critical auth code
2. **Stage changes** - consider feature flag for gradual rollout
3. **Review api_middleware** carefully - highest complexity caller (CC=9)
4. **Coordinate with team** - 8 direct callers suggests many integration points"
