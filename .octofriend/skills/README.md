# Archon Code Intelligence Skills

Batched, optimized skills for effective use of Archon MCP Code Intelligence tools.

## Quick Reference

| Skill | Use When | Calls | Batch Pattern |
|-------|----------|-------|---------------|
| `codebase-discovery` | Starting on new codebase | 4 | Single batch |
| `quick-health-check` | Code audit/quality check | 1 | Single super-tool |
| `function-deep-dive` | Understanding specific function | 4 | 1 locate + 1 batch(3) |
| `audit-context` | Getting audit findings | 1 | Single super-tool |
| `safe-task-creation` | Creating dev tasks | 6 | 2 batches + 1 create |
| `impact-analysis` | Assessing change scope | 4 | 1 locate + 1 batch(3) |
| `security-audit` | Security review | 2 | Single batch(2) |
| `semantic-code-search` | Finding code by behavior | 1 | Single call |
| `knowledge-graph-query` | Code evolution/branch compare | 1-2 | Sequential (depends on user) |

## Skill Details

### P0 (Critical)

#### codebase-discovery
**Files**: 4 parallel calls batched into 1
```
Batch: find_projects + codebase_get_repository_stats + audit_get_context + worktree_get_current_info
```
**Best For**: Initial codebase exploration, onboarding, planning

#### quick-health-check
**Files**: 1 orchestrated super-tool call
```
orchestrated_repo_health_check(repo_id, focus="full|security|tdd|docs|maintainability|db")
```
**Best For**: Comprehensive audits with LLM-powered insights

#### function-deep-dive
**Files**: 2 calls (1 locate + 1 batch of 3)
```
Step 1: codebase_find_entity(repo_id, name)
Step 2 (BATCH): codebase_get_entity_details + codebase_get_entity_context + code_audit_analyze_entity
```
**Best For**: Understanding specific functions, debugging, review prep

#### audit-context
**Files**: 1 super-tool call
```
audit_get_context(repo_name)
```
**Best For**: Triage, finding existing issues, cross-referencing
**Replaces**: 4-5 separate audit calls

### P1 (High Value)

#### safe-task-creation
**Files**: 6 calls across 3 steps
```
Step 1 (BATCH): worktree_get_current_info + find_tasks + find_projects
Step 2 (BATCH): worktree_validate_safe_to_work + worktree_find_conflicts
Step 3: worktree_create_task (if safe)
```
**Best For**: Development workflow, ensuring safety before changes

#### impact-analysis
**Files**: 4 calls (1 locate + 1 batch of 3)
```
Step 1: codebase_find_entity(repo_id, name)
Step 2 (BATCH): codebase_get_entity_context(max_depth=2) + code_audit_analyze_entity + worktree_find_conflicts
```
**Best For**: Refactoring planning, risk assessment

#### security-audit
**Files**: 2 parallel calls batched into 1
```
Batch: orchestrated_repo_health_check(focus="security") + db_security_audit
```
**Best For**: Security reviews, vulnerability detection

#### semantic-code-search
**Files**: 1 call
```
codebase_search_by_semantics(repo_id, query="2-5 keywords", top_k=10)
```
**Best For**: Finding code by behavior, not name

#### knowledge-graph-query
**Files**: 1-2 calls depending on workflow
```
Single: codebase_entity_evolution | codebase_commits | codebase_compare_branches | codebase_when_added
Sequential: Query → Review → Optional deep dive
```
**Best For**: Tracking code evolution, comparing branches, finding when code was added
**Tools**:
- `codebase_entity_evolution`: Track entity versions across commits
- `codebase_commits`: List commits with change summaries  
- `codebase_compare_branches`: Compare entities between branches
- `codebase_when_added`: Find first appearance of entity

## Batching Rules

### ✅ ALWAYS Batch (Independent Operations)
- Discovery operations (project lookup, stats, audit context)
- Entity details + context + metrics (for deep dive)
- Safety validations (validate + conflicts)
- Multiple security checks

### ❌ NEVER Batch (Sequential Dependencies)
- Entity lookup → operations on that entity (need entity_id)
- Safety check → task creation (only create if safe)
- Search → deep dive (need to select from results)

## Efficiency Gains

| Workflow | Before Batching | After Batching | Improvement |
|----------|----------------|----------------|-------------|
| Codebase discovery | 4 sequential | 1 batch | 75% faster |
| Function deep dive | 3 sequential | 1 batch | 66% faster |
| Security audit | 2 sequential | 1 batch | 50% faster |
| Audit context | 4-5 calls | 1 call | 75-80% faster |

## Usage Examples

### Exploring a New Codebase
```
User: "Explore the archon codebase"
→ Use: codebase-discovery skill
→ Single batch of 4 calls
→ Result: Full overview with stats and findings
```

### Understanding a Function
```
User: "How does authenticate_user work?"
→ Use: function-deep-dive skill
→ 2 calls: locate + batch of 3
→ Result: Source, metrics, and call graph
```

### Security Review
```
User: "Run a security audit"
→ Use: security-audit skill
→ Single batch of 2 calls
→ Result: Comprehensive security findings
```

### Creating a Task
```
User: "Create a task to fix the auth bug"
→ Use: safe-task-creation skill
→ 3 steps with safety validation
→ Result: Task created only if safe to proceed
```

## Skill Selection Decision Tree

```
Starting work?
├── New codebase → codebase-discovery
├── Specific function → function-deep-dive
├── Audit/quality → quick-health-check
└── Security focus → security-audit

Need to find code?
├── Know the name → codebase_find_entity
└── Know the behavior → semantic-code-search

Planning changes?
├── Create task → safe-task-creation
├── Assess impact → impact-analysis
└── Check existing issues → audit-context
```

## Configuration

These skills are automatically loaded from `.octofriend/skills/` when Octofriend initializes. The `octofriend.json5` file includes skill definitions in the system context.

To use a skill, simply follow the user's intent and the skill triggers described above. The batching patterns will be applied automatically.
