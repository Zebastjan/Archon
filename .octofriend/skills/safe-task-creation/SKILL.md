# Safe Task Creation Skill

Create development tasks with proper safety checks, conflict detection, and full context preservation.

## When to Use

Use this skill when:
- Starting work on a new feature
- Creating a bug fix task
- Planning refactoring work
- Anytime you're about to modify code

## When NOT to Use

Do NOT use when:
- Just reading/exploring code (no task needed)
- The task already exists (use manage_task to update)
- You're not in a git worktree (can't validate safety)

## Pre-Flight Safety Checklist

Before creating ANY task, validate:

1. ✅ In a git repository (`worktree_get_current_info`)
2. ✅ No conflicts with active work (`worktree_find_conflicts`)
3. ✅ Safe to modify target files (`worktree_validate_safe_to_work`)
4. ✅ Target entities identified (`codebase_find_entity`)

## Workflow

### Step 1: Discovery Batch

Run these calls in parallel:

```
worktree_get_current_info()
find_tasks(filter_by="status", filter_value="doing")  # Check what's active
find_projects(query="<project_name>")  # Get project_id
```

### Step 2: Target Identification

If target files/entities specified:

```
codebase_find_entity(repo_id, name="<target>")
```

Or if creating without specific targets, skip to Step 3.

### Step 3: Safety Validation Batch

Run these calls in parallel:

```
worktree_validate_safe_to_work(file_paths=["path1", "path2"])
worktree_find_conflicts(file_paths=["path1", "path2"])
```

**If unsafe**: Report conflicts and STOP. Do not create task.

**If safe**: Proceed to Step 4.

### Step 4: Task Creation

```
worktree_create_task(
    project_id="<project_id>",
    title="<title>",
    description="<detailed description with acceptance criteria>",
    status="todo",
    assignee="User",
    file_paths=["path1", "path2"],
    entity_ids=["ent1", "ent2"]
)
```

## Safety Rules

**NEVER create a task if**:
- `worktree_validate_safe_to_work` returns `is_safe: false`
- `worktree_find_conflicts` returns conflicts in ACTIVE status (doing, review)
- Another task in the same project modifies the same files

**ALWAYS include**:
- Specific file paths that will be modified
- Entity IDs if known
- Clear description with acceptance criteria

## Batching Rules

**Step 1** (Discovery): Batch 3 calls
- `worktree_get_current_info` + `find_tasks` + `find_projects`

**Step 2** (Target ID): 1 call if needed
- `codebase_find_entity`

**Step 3** (Safety): Batch 2 calls
- `worktree_validate_safe_to_work` + `worktree_find_conflicts`

**Step 4** (Creation): 1 call
- `worktree_create_task`

**Maximum**: 4 calls (3 batches + 1 single)

## Task Description Template

Use this structure for task descriptions:

```markdown
## Objective
[Clear statement of what needs to be done]

## Context
[Any relevant background from code analysis]

## Files to Modify
- [file_path] - [reason]

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Tests updated (if applicable)

## Related Entities
- [entity_name] ([entity_id])
```

## Example Invocation

User: "Create a task to fix the SQL injection in auth.py"

Claude: [Step 1 batch: worktree_get_current_info, find_tasks, find_projects]
→ Current branch: main, No active tasks, Project: archon (proj-123)

Claude: [Step 2: codebase_find_entity(repo_id, name="authenticate_user")]
→ Found: authenticate_user (ent-789) in auth.py:45-78

Claude: [Step 3 batch: worktree_validate_safe_to_work(["auth.py"]), worktree_find_conflicts(["auth.py"])]
→ is_safe: true, no conflicts found

Claude: [Step 4: worktree_create_task(...)]

Claude: "✅ Task created successfully!

**Task**: Fix SQL injection vulnerability in authentication
**ID**: task-456
**Status**: todo
**Safety**: Validated ✓

The task has been created with full context:
- Target entity: authenticate_user (ent-789)
- File to modify: auth.py
- No conflicts with existing work
- Worktree safety validated"
