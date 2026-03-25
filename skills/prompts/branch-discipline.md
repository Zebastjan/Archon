# Branch Discipline Prompt

Remind agents to always work on the correct branch. Never commit to
a branch just because you happen to be on it.

## Prompt

```
Branch discipline is critical. Before implementing ANY change:

1. **Identify the task**: What are you working on?
   - A bug fix → should be on a `fix/` or `bugfix/` branch
   - A new feature → should be on a `feature/` branch
   - Documentation → can be on any branch
   - Hotfix → should be on a `hotfix/` branch

2. **Verify current branch matches the task**:
   - Run `worktree_get_current_info()` to see current branch
   - If branch doesn't match task → DO NOT proceed

3. **Switch to correct branch if needed**:
   ```python
   # Save current position
   await worktree_push()
   
   # Check if branch exists
   branches = await worktree_list_all()
   
   # Switch or create
   await worktree_switch("feature/new-feature")
   # OR
   await worktree_create("feature/new-feature", "main")
   ```

4. **After switch, everything auto-scopes**:
   - MCP tools automatically filter to current branch
   - Search results only show code at HEAD
   - No manual configuration needed

## Critical Rules

- **NEVER** commit to main/master directly
- **NEVER** commit to a branch just because you're on it
- **ALWAYS** verify branch before implementing
- **ALWAYS** use `worktree_push()` before switching
- **ALWAYS** use `worktree_pop()` to return to previous

## Decision Tree

```
What am I working on?
│
├─ Bug fix → Need `fix/` or `bugfix/` branch
│   └─ Current branch starts with "fix/"? → OK
│   └─ Otherwise → Switch or create
│
├─ New feature → Need `feature/` branch
│   └─ Current branch starts with "feature/"? → OK
│   └─ Otherwise → Switch or create
│
├─ Documentation → Any branch OK
│
├─ Hotfix → Need `hotfix/` branch
│   └─ Current branch starts with "hotfix/"? → OK
│   └─ Otherwise → Switch or create
│
└─ Not sure → Ask user for guidance
```

## Example Scenarios

### Scenario 1: User asks to fix a bug
```
User: "Fix the login timeout issue"
Agent: 
  1. Check current branch: worktree_get_current_info()
  2. If not on fix/* branch: worktree_create("fix/login-timeout", "main")
  3. Restart MCP from new worktree
  4. Implement fix
  5. commit_with_review(message="fix: Resolve login timeout issue")
```

### Scenario 2: User asks to add a feature
```
User: "Add dark mode support"
Agent:
  1. Check current branch: worktree_get_current_info()
  2. If not on feature/* branch: worktree_create("feature/dark-mode", "main")
  3. Restart MCP from new worktree
  4. Implement feature
  5. commit_with_review(message="feat: Add dark mode support")
```
