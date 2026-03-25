# Archon Project — Strategic Planning Document
## "Where We're Going and What We Need to Figure Out"
### Status: DRAFT — Requires Codebase Review Before ADRs Can Be Written
#### Prepared: 2026-03-24 | Authors: Project team + Perplexity session synthesis

---

> **⚠️ IMPORTANT CONTEXT FOR WHOEVER PICKS THIS UP**
>
> This document was assembled from a design session *without direct access to the
> current codebase*. All sections marked **[NEEDS CODEBASE REVIEW]** require a
> developer or agent with full repo access to audit actual implementation status
> before any ADRs are drafted or milestones committed to. Treat everything here
> as *intent and direction*, not confirmed current state.
>
> **Known recent architectural changes that may invalidate older assumptions:**
> - Moved from Supabase + Weaviate multi-service to **single Postgres container** (ADR-004)
> - Consolidated from 4 MCP server implementations to **one STDIO-based server** (ADR-003)
> - Significant refactoring has occurred — auditing/testing subsystems need re-audit
> - Documentation cleanup removed 70+ stale files (ADR-006); old audit/triage reports deleted

---

## 1. Current Confirmed Architecture (from existing ADRs)

These decisions are recorded and accepted. Any new work must be consistent with them.

| ADR | Decision | Status |
|-----|----------|--------|
| ADR-003 | Single STDIO MCP server (`mcp_server_stdio.py`) via `docker exec` | Accepted |
| ADR-004 | Single-container architecture, embedded Postgres, no microservices | Accepted |
| ADR-005 | BGE-M3 embeddings for code intelligence, knowledge graph over entities | Accepted |
| ADR-006 | Stale docs deleted; Git history is the archive; only current docs in tree | Accepted |
| ADR-003-Git | Git-Aware Knowledge Base: Git as source of truth, DB is queryable mirror | Accepted |
| ADR-004-Git | Hybrid testing: custom unit tests (fast) + official Git test suite (comprehensive) | Accepted |

**Key infrastructure facts:**
- Transport: STDIO only (no HTTP/SSE ports exposed)
- IDE config standard: `docker exec -i archon python -m src.mcpserver.mcp_server_stdio`
- Claude Code specifically: must use `claude mcp add` CLI, not manual JSON
- Embeddings: BGE-M3 via Ollama (local, no external API dependency)
- DB: Postgres inside single Docker container
- Git integration: `GitRepositoryService`, migrations 017+018, 16 unit tests passing

---

## 2. Version-Scoped Search & Branch Synchronization

### 2.1 Problem Statement

MCP semantic search results may currently be **polluted by content from old commits,
deleted files, and past implementations** of functions that no longer exist at HEAD.
This is a correctness problem — agents get stale context without knowing it.

A concrete example: if `foo()` was deleted in the current commit, a search for
"how does foo work" should return nothing (or a tombstone note), not the old
implementation. If an agent is specifically investigating history ("what did foo
look like two commits ago?"), then and only then should historical content appear.

### 2.2 What We Believe Has Been Built [NEEDS CODEBASE REVIEW]

ADR-003-Git (Git-Aware Knowledge Base) describes:
- `archon_git_repositories`, `archon_git_commits`, `archon_git_files` tables
- `archon_document_blobs` linked to `git_file_id` and `git_commit_id`
- `GitRepositoryService` with commit syncing, file tree navigation, deletion tracking
- `GitSearchContext` for branch/commit-filtered RAG queries
- Phase 1 (branch heads only) declared complete

**What is NOT yet confirmed:**
- Whether MCP tools actually *use* `GitSearchContext` by default on every search
- Whether `is_deleted` files are properly excluded from default search results
- Whether the "current branch/commit" is automatically resolved at MCP server startup
  or whether agents must pass it explicitly
- Whether the `code_chunks_live` materialized view (or equivalent) exists and is
  populated correctly at HEAD

### 2.3 Goals for This Feature Area

1. **Zero-noise default**: Every MCP semantic search defaults to HEAD of the current
   worktree's branch. No agent prompt overhead required.
2. **Automatic context binding**: MCP server resolves `current_branch` and
   `current_commit_sha` at startup from its working directory. Re-checks on each
   request (cheap `git rev-parse HEAD` call).
3. **Explicit time-travel**: Agents can opt in to history via dedicated tools:
   - `search_at_commit(commit_sha, query)`
   - `history_for_symbol(symbol_name)`
   - `search_on_branch(branch_name, query)`
4. **Worktree-aware**: One MCP server per worktree. Switching context = switching
   worktree, not passing commit SHAs in every message.

### 2.4 ADRs To Write [PENDING CODEBASE REVIEW]

- **ADR-007: Version-Scoped Search as Default Behavior**
  - Decision: MCP search always scoped to HEAD unless explicitly overridden
  - Schema: confirm or add `code_chunks_live` view; `is_deleted` exclusion logic
  - Test strategy: see Section 3

- **ADR-008: Worktree-Per-Context Model**
  - Decision: one worktree = one agent context = one MCP server instance
  - Startup contract: MCP server reads `git rev-parse HEAD` and `--abbrev-ref HEAD`
  - Zig-zag workflow: context stack, jump-back mechanism

### 2.5 Tests Needed [NEEDS CODEBASE REVIEW]

Write a version-pollution test harness:
- Fixture repo with commit A (has `foo()` in `foo.py`) and commit B (deletes `foo.py`)
- With MCP server at commit B: assert search for "foo function" returns 0 current results
- With time-travel tool at commit A SHA: assert "foo function" is found
- Separate fixture: two branches with divergent implementations of same function;
  assert each branch's MCP server only returns its own version
- Renamed file test: old path should not appear in current search

---

## 3. Commit-Hook Automation Pipeline

### 3.1 Problem Statement

Currently, housekeeping (docs updates, test coverage review, dead code detection,
project status report generation) is ad-hoc and manual. This creates drift between
code and documentation, accumulates dead code, and leaves agents without up-to-date
context when starting a session.

### 3.2 Goals

Run a lightweight local-agent workflow on every `git commit` (post-commit hook)
using **local models** (e.g., local LLM via Ollama) — NOT cloud APIs — so:
- No latency cost or API cost for routine housekeeping
- Works offline / air-gapped
- Scales with commit frequency

### 3.3 Three-Stage Hook Pipeline

**Stage 1: Documentation Maintenance**
- Parse git diff for changed/added/deleted files and functions
- Cross-reference against existing docs (via MCP search on `docs/`)
- Output: a delta report — "these docs are now stale or missing"
- Local agent action: either auto-update light docs OR create a TODO task in Archon
- Skill file: `skills/commit-hooks/doc-maintenance.md`

**Stage 2: Test Coverage Analysis**
- Map changed functions to existing test files
- Identify: new functions with no test, changed function signatures that break tests,
  deleted functions whose tests are now orphaned
- Output: TODO list of test gaps, NOT auto-generated tests (too risky without review)
- Flag: "this function changed and has no test coverage — needs attention"
- Skill file: `skills/commit-hooks/test-coverage.md`

**Stage 3: Code Audit (Light)**
- Dead code detection: functions/classes defined but never called or imported
- Duplicate detector: similar implementations that could be consolidated
- Orphaned config: environment variables or config keys referenced but not used
- Known bad patterns: look for patterns we've explicitly banned (e.g., multiple MCP
  server registrations — the "4 MCP servers" problem that just bit us)
- Output: a non-blocking advisory report; does NOT fail the commit

### 3.4 Implementation Approach [NEEDS CODEBASE REVIEW]

- Hook script lives at `.git/hooks/post-commit` (or managed via `pre-commit` framework)
- Triggers a lightweight Python script that invokes local Ollama model
- All output written to `.archon/hooks/last-run.json` and surfaced in the
  project status bundle (see Section 5)
- Must be fast: target < 30 seconds for typical commit; skip expensive analysis on
  large/merge commits

### 3.5 ADRs To Write [PENDING CODEBASE REVIEW]

- **ADR-009: Commit-Hook Automation and Local Agent Housekeeping**
  - Decision: post-commit hook, local model only, 3-stage pipeline
  - Non-blocking: hook never fails the commit
  - Output: `.archon/hooks/` directory, feeds into status bundle

---

## 4. Intelligent Code Auditing System

### 4.1 Background

We previously began building a code auditing system inspired by CodeRabbit (which
we encountered on a PR submission). A significant amount of foundational work was
done. However, recent major refactoring has left the status of this work **unknown**
— it needs a full audit of the audit system itself.

### 4.2 What We Were Building [NEEDS CODEBASE REVIEW]

The intended architecture had these layers:

**Layer 1: Base Auditor**
- Runs static analysis and LLM-based code review on changed files
- Produces raw findings: severity, category, file, line, description

**Layer 2: Triage / Meta-Audit**
- A local model reviews the raw findings
- Filters noise, deduplicates, prioritizes
- Key insight: we call this "meta-audit" not triage — the model is *auditing the
  auditor*, not just filtering
- Output: curated finding list with confidence scores

**Layer 3: Feedback Loop / Learning System**
This is the most novel and important part. The system tracks:
- Every finding that was flagged
- Whether it was marked "intentional", "won't fix", "false positive", or "real bug"
- Whether a related bug was later filed or encountered in production

**The core learning mechanism:**
If a finding was previously marked "false positive" or "won't fix" AND later a real
bug is filed that matches the same category/location, the system:
1. Detects the correlation automatically
2. Flags: "We audited for this. We dismissed it. We got burned. Why?"
3. Feeds this back into auditor calibration: raise confidence on similar patterns
4. Generates a retrospective task: "Review our dismissal of [finding] — was our
   triage logic wrong?"

Similarly, if we audit for race conditions and then hit a race condition:
- System checks: "Was this location/pattern in our audit results?"
- If yes and dismissed: trigger the retrospective
- If yes and not acted on: trigger escalation
- If no: trigger: "Our auditor missed this — how do we improve detection?"

### 4.3 Goals for the Auditing System

1. **Signal-to-noise ratio**: dramatically reduce false positives over time through
   the meta-audit feedback loop
2. **Coverage confidence**: track *what we're auditing for* so we know our blind spots
3. **Self-improving**: each audit episode makes the next one smarter
4. **Integrated with commit hooks**: light audit runs at every commit; deep audit
   runs on PR or explicit trigger
5. **Local-first**: core triage runs on local model (Ollama); escalation to cloud
   model only for high-severity or novel patterns

### 4.4 Audit Categories to Track

- Race conditions / async safety
- Dead code / unreachable branches
- Duplicate/redundant implementations (e.g., the 4-MCP-server problem)
- Security: hardcoded secrets, unsafe deserialization, SQL injection patterns
- API contract violations: changed function signatures without downstream updates
- Test coverage gaps
- Documentation drift: code changed but docs not updated

### 4.5 Database Schema Needed [NEEDS CODEBASE REVIEW]

```
audit_runs
  id, commit_sha, branch, run_at, run_type (light/deep), model_used

audit_findings
  id, audit_run_id, file_path, line_start, line_end, category,
  severity, description, raw_finding, meta_score, status
  (status: open / intentional / wont_fix / false_positive / fixed)

audit_outcomes
  id, finding_id, outcome_type (bug_filed / bug_hit_production / validated_correct),
  outcome_at, notes, related_issue_id

audit_learning_events
  id, finding_id, outcome_id, event_type (false_negative / dismissed_then_hit /
  correct_dismissal), retrospective_task_id, created_at
```

### 4.6 ADRs To Write [PENDING CODEBASE REVIEW]

- **ADR-010: Intelligent Code Auditing System**
  - Decision: 3-layer architecture (base auditor → meta-audit → feedback loop)
  - Schema: audit_runs, audit_findings, audit_outcomes, audit_learning_events
  - Integration with commit hooks (Stage 3) and test system

- **ADR-011: Audit Feedback Loop and Learning Mechanism**
  - Decision: correlation engine between dismissed findings and later bugs
  - Model: local-first (Ollama) with cloud escalation policy

### 4.7 Immediate Audit of the Audit System [NEEDS CODEBASE REVIEW]

Before writing ADRs, someone with codebase access needs to answer:
- What auditing code currently exists? (search for `audit`, `triage`, `CodeRabbit`
  in the codebase)
- Are there any existing audit-related tables in Postgres migrations?
- Are there any audit-related MCP tools registered?
- What was deleted or broken during the recent refactoring?
- Is there a `AUDIT.md` or `TRIAGE.md` that ADR-006 flagged for deletion? Retrieve
  via `git show` to understand what was built.

---

## 5. Project Status Bundle (Per-Commit Context Package)

### 5.1 Problem Statement

Every time a new agent session starts (Claude, Kimi, OpenCode, Windsurf, etc.),
the agent starts with zero context about the current state of the project. This
creates expensive warm-up overhead and leads to agents working from stale
assumptions (as demonstrated in this very planning session).

### 5.2 What We Want

A directory `.archon/context/` committed with every push (or updated by post-commit
hook) containing:

```
.archon/context/
  STATUS.md          # "What's going on right now" — human and agent readable
  QUICKSTART.md      # How to spin up the project at this exact commit
  AGENTS.md          # MCP server config, available tools, IDE setup
  ARCHITECTURE.md    # Current architecture summary (auto-generated from ADRs)
  CHANGES.md         # AI-enhanced changelog: what changed and WHY
  KNOWN_ISSUES.md    # Open bugs, dismissed audit findings, tech debt
  hooks-last-run.json # Output of last commit hook pipeline run
```

`STATUS.md` should be the "paste into Perplexity / attach to new agent session"
document. It answers:
- What is this project?
- What's the current branch and what is it for?
- What was just changed?
- What are the active work items?
- What tools/MCP servers are available?
- What should the agent NOT do (guardrails)?

### 5.3 Generation Strategy

- Lightweight post-commit script (part of hook pipeline)
- Templates with `git log --oneline -10`, current ADR summary, open task list
- Local model fills in the "why" sections from commit messages + diff
- Committed to the repo so it's version-controlled and branch-specific

### 5.4 ADRs To Write [PENDING CODEBASE REVIEW]

- **ADR-012: Per-Commit Context Bundle**
  - Decision: `.archon/context/` directory, updated at every commit
  - Generator: post-commit hook script, local model, template-based
  - Usage: auto-attached to agent sessions, pasteable to external tools

---

## 6. Skills & Prompts Repository

### 6.1 Problem Statement

Skills, workflows, and prompts for AI agents are currently scattered, undocumented,
and not synchronized across IDEs (OpenCode, Windsurf, OctoFriend/Octofriend,
Claude Code). We're building significant infrastructure — it's critical that agents
actually use it to the maximum. Skills and prompts ARE documentation for this project.

### 6.2 Proposed Structure

A sibling repository `archon-skills` (or a `skills/` directory in the main repo):

```
skills/
  commit-hooks/
    doc-maintenance.md
    test-coverage.md
    code-audit-light.md
  mcp/
    search-usage-guide.md      # How to use MCP tools correctly
    version-scoped-search.md   # How to use branch/commit context tools
    time-travel-guide.md       # How to query historical code
  workflows/
    feature-branch.md          # Branch discipline for new features
    zig-zag-workflow.md        # How to handle context switching
    audit-review.md            # How to process audit findings
    pr-prep.md                 # Pre-PR checklist
  ide-setup/
    claude-code.md
    windsurf.md
    opencode.md
    octofriend.md
  prompts/
    session-bootstrap.md       # Prompt to bootstrap agent with context bundle
    branch-discipline.md       # Remind agent of branch/worktree rules
    audit-meta-review.md       # Prompt for meta-audit step
```

### 6.3 Key Principles

- Skills are versioned alongside the codebase — when a tool's API changes, the
  skill for that tool must be updated in the same commit (enforced by commit hook Stage 1)
- Skills are the canonical source for how to USE the infrastructure we've built
- `AGENTS.md` in the context bundle references skills for each available tool
- Skills for each IDE include the exact MCP config that IDE needs (informed by
  ADR-003's lessons about config location drift)

### 6.4 ADRs To Write [PENDING CODEBASE REVIEW]

- **ADR-013: Skills and Prompts as First-Class Project Documentation**
  - Decision: `skills/` directory in main repo, versioned with code
  - Enforcement: commit hook Stage 1 checks for skill drift on tool changes
  - Portability: `scripts/sync-skills.sh` installs to per-IDE config directories

---

## 7. Branch & Worktree Discipline

### 7.1 Problem Statement

We've experienced "zig-zag" workflows — working on Feature A, hitting something
related to Feature B, pivoting, then needing to return to A. Without structure,
this leads to mixed uncommitted changes, confused agents, and polluted search results.

### 7.2 Goals

- One worktree per active work item (branch = worktree = MCP server context)
- Context stack: track active worktrees and support "jump back to previous context"
- Agent onboarding: when agent starts in a worktree, it automatically gets the
  context bundle for that branch
- IDE skills define the specific commands for creating/switching worktrees in each tool

### 7.3 Zig-Zag Workflow Pattern

When an agent hits a dependency during work on Branch A:
1. Stash or commit WIP on Branch A worktree
2. Create or switch to Branch B worktree (or existing branch)
3. MCP server in Branch B context auto-binds to Branch B HEAD
4. Complete Branch B work
5. Jump back: context stack returns to Branch A worktree
6. Branch A MCP server re-checks HEAD and resumes

This should be codified as a skill: `workflows/zig-zag-workflow.md`

### 7.4 ADRs To Write [PENDING CODEBASE REVIEW]

- **ADR-014: Worktree-Per-Context and Branch Discipline**
  - Decision: one git worktree per active agent context
  - MCP server startup contract: bind to `cwd` worktree
  - Context stack: mechanism and storage (`.archon/context-stack.json`?)

---

## 8. Summary of ADRs To Draft (After Codebase Review)

| ADR | Title | Depends On |
|-----|-------|------------|
| ADR-007 | Version-Scoped Search as Default | Codebase review of current MCP tools |
| ADR-008 | Worktree-Per-Context Model | ADR-007 |
| ADR-009 | Commit-Hook Automation Pipeline | Current hook infrastructure review |
| ADR-010 | Intelligent Code Auditing System | Audit of existing audit code |
| ADR-011 | Audit Feedback Loop and Learning | ADR-010 |
| ADR-012 | Per-Commit Context Bundle | ADR-009 |
| ADR-013 | Skills & Prompts as Documentation | All of the above |
| ADR-014 | Worktree and Branch Discipline | ADR-007, ADR-008 |

---

## 9. Immediate Action Items for Codebase Agent

**Whoever picks this up with codebase access, please do the following in order:**

### Step 1: Audit the Audit System
```bash
# Find all audit-related code
grep -r "audit" src/ --include="*.py" -l
grep -r "triage" src/ --include="*.py" -l
grep -r "CodeRabbit" . --include="*.py" --include="*.md" -l

# Recover deleted audit docs from git history
git log --all --oneline -- "*AUDIT*" "*TRIAGE*"
git show <commit>:path/to/AUDIT.md  # for each found
```

### Step 2: Audit the MCP Tools
```bash
# What tools are currently registered?
grep -r "mcp.tool" src/ --include="*.py"
grep -r "@tool" src/mcpserver/ --include="*.py"

# Do any tools accept branch/commit parameters?
grep -r "branch" src/mcpserver/ --include="*.py"
grep -r "commit_sha" src/mcpserver/ --include="*.py"
grep -r "GitSearchContext" src/ --include="*.py"
```

### Step 3: Check Version-Scoping Status
```bash
# Is GitSearchContext used in MCP search tools?
grep -r "GitSearchContext" src/mcpserver/ --include="*.py"

# Is there a live/current view for chunks?
# Check DB migrations for views or filtered tables
ls migrations/ | sort
grep -r "is_deleted" migrations/
grep -r "branch" migrations/
```

### Step 4: Check Commit Hook Status
```bash
ls .git/hooks/
cat .git/hooks/post-commit 2>/dev/null || echo "No post-commit hook"
find . -name "*.sh" | xargs grep -l "post.commit" 2>/dev/null
```

### Step 5: Inventory Test Coverage for Auditing + Search
```bash
ls tests/
grep -r "audit" tests/ --include="*.py" -l
grep -r "version" tests/ --include="*.py" -l
grep -r "branch" tests/ --include="*.py" -l
```

### Step 6: Document What You Find
Create `.archon/context/STATUS.md` with current actual state, then write the ADRs
in `docs/ADRs/` using the standard template from existing ADRs.

---

## 10. Glossary / Key Terms for New Agent Context

| Term | Meaning |
|------|---------|
| STDIO MCP | The single MCP server transport we use (`mcp_server_stdio.py`) |
| `docker exec` pattern | How IDEs invoke the MCP server inside the container |
| Worktree | A git working tree checked out to a specific branch; one per agent session |
| Meta-audit | LLM reviewing audit findings to reduce noise; "auditing the auditor" |
| Feedback loop | Correlation engine linking dismissed audit findings to later real bugs |
| Context bundle | `.archon/context/` directory committed with current project state |
| BGE-M3 | The embedding model used for all code/doc semantic search |
| `GitSearchContext` | The branch/commit filter applied to RAG queries |
| Skills repo | `skills/` directory; prompts and workflows versioned with the code |
| Zig-zag | Switching between related branches mid-task; managed via context stack |
| Local agent | Ollama-backed model used for commit hooks and triage (no cloud API) |

---

*Document ends. Next step: open codebase, run Step 1–6 above, then draft ADRs 007–014.*
