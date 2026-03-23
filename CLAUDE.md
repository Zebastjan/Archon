# CLAUDE.md

Archon: AI agent framework built on Pydantic AI with PostgreSQL backend.

## Task Execution Protocol (CRITICAL)

### Before Starting Any Task
1. State the objective clearly: "My goal is [specific outcome]"
2. State current status: "Currently [what's broken/not working]"
3. Define success criteria: "This task will be complete when [specific result]"

### During Task Execution
1. **Verify after each significant action** - Don't assume success, confirm it
2. **When stuck (same error repeated 3+ times), STOP and report:**
   - What I've tried
   - The exact error/results
   - My hypothesis about the cause
   - "What would you like me to try next?"
3. **Never loop infinitely** - After 3 attempts with no progress, ask for direction

### After Task Completion (or giving up)
1. Explicitly state: "Task complete" or "Task failed - here's why"
2. Report final status
3. Ask: "Would you like me to continue, or try a different approach?"

### Anti-Patterns to Avoid
- Running commands in a loop without verifying success
- Moving to "next step" without confirming current step worked
- Not reporting status when stuck
- Continuing silently when progress has stalled

---

## Project Philosophy (Beta)

- **Fix forward** — Remove deprecated code immediately, no backwards compatibility
- **Fail fast and loud** — Service startup, auth, and data validation errors should crash
- **Complete but log** — Batch processing should finish the queue, report failures per item
- **Never store corrupted data** — Skip failed items entirely rather than storing nulls/bad embeddings

## Critical Constraints

**NEVER:**
- Store zero embeddings, null foreign keys, or malformed JSON
- Return None to indicate failure — raise with details instead
- Accept silent data corruption in critical services

**ALWAYS:**
- Use `uv` for Python dependency management
- Route DB operations through `db_connector.py` (PostgreSQL asyncpg wrapper)
- Test on both X11 and Wayland when changing window management (if applicable)

## Architecture References

- Core patterns: `@PRPs/ai_docs/ARCHITECTURE.md`
- Data fetching: `@PRPs/ai_docs/DATA_FETCHING_ARCHITECTURE.md`
- Service pattern: `python/src/server/api_routes/` → `services/` → Database

## Git & Branch Discipline

- One working copy per repo — do NOT create a new top-level folder for each branch.
- Use branches inside the existing `archon` repo instead of cloning again for feature work.
- Long-lived branches:
  - `main` — latest development (PR target for contributors)
  - `stable` — recommended for day-to-day use and deployments
- Short-lived branches:
  - `feature/<short-description>` for new work
  - `fix/<short-description>` for bug fixes

### Agent branch handling

- The agent MUST only make changes against an explicitly specified branch.
- The caller MUST tell the agent which branch to use (e.g. `branch=feature/git-integration-cleanup`).
- If no branch is specified, the agent MUST refuse to modify code and instead reply:
  - That the branch was not provided.
  - That it cannot make changes until a branch name is given.
- The agent MUST NOT silently:
  - Switch branches,
  - Create new branches,
  - Or assume a default branch (like `main` or `stable`) when one is not specified.
- Once a branch is specified, the agent MUST stay on that branch for the duration of the task.

