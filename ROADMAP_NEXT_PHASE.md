# Archon Next Phase Roadmap: Code Auditing & Intelligence Platform

**Date:** 2025  
**Theme:** Transform Archon from code storage to comprehensive code intelligence and auditing platform

---

## Executive Summary

Based on our successful code entity infrastructure and the codebase analysis (90/100 quality score, 1,508 entities, 25,896 relationships), we're positioned to build a **code auditing and intelligence platform** that rivals commercial tools like CodeRabbit, SonarQube, and CodeClimate.

**Vision:** Make Archon the open-source standard for AI-powered code auditing, with MCP-native integration.

---

## Phase 1: Metrics Tracking & Trending System

### 1.1 Historical Metrics Storage
**Goal:** Track codebase health over time

**MCP Tools to Add:**
- `codebase_get_metrics_history(repo_id, start_date, end_date)`
- `codebase_compare_commits(repo_id, commit_a, commit_b)`
- `codebase_get_quality_trend(repo_id, metric_type, period)`

### 1.2 Trend Visualization Data
- Time-series metrics export
- Quality regression alerts
- External visualization support

### 1.3 Automated Metric Collection
- Git hook integration for automatic snapshots

---

## Phase 2: Comprehensive Code Auditing System

### 2.1 Audit Rule Engine (50+ Rules)

#### Category A: Security (12 rules)
- Hardcoded credentials detection
- SQL injection patterns
- Insecure HTTP usage
- Weak cryptography
- etc.

#### Category B: Code Quality (15 rules)
- Function too long (>100 lines)
- Class too long (>200 lines)
- Missing docstrings
- Cognitive complexity
- Duplicate code
- etc.

#### Category C: Performance (8 rules)
- N+1 query patterns
- Inefficient loops
- Memory leak risks
- etc.

#### Category D: Maintainability (10 rules)
- TODO/FIXME tracking
- Unused imports
- Deprecated usage
- etc.

#### Category E: Architecture (5 rules)
- God class detection
- Circular dependencies
- etc.

### 2.2 MCP Audit Tools
- `codebase_audit_file()` - Audit specific file
- `codebase_audit_repository()` - Full repo audit
- `codebase_get_audit_history()` - Historical trends
- `codebase_compare_audits()` - Compare two commits

### 2.3 Audit Report Generation
- Executive summary (1-page)
- Detailed report (multi-page)
- Security focus report
- Compliance report (SOC 2, ISO 27001)

---

## Phase 3: Smart Documentation Management

### 3.1 Documentation Gaps Analysis
- Find entities lacking documentation
- Prioritize by usage (high-usage = high priority)
- AI-generated docstring suggestions

### 3.2 Documentation Tasks Auto-Creation
- Automatically create tasks for doc gaps
- Track documentation coverage over time

### 3.3 Docstring Validation
- Check completeness (description, params, returns)
- Validate quality and clarity

---

## Phase 4: Refactoring Intelligence

### 4.1 Refactoring Candidates Detection
- Extract class (god classes)
- Extract method (long functions)
- Move method (wrong class)
- Rename (unclear naming)
- Split service (monolithic services)

### 4.2 Refactoring Plan Generation
- Step-by-step refactoring plans
- Estimated effort
- Risk assessment
- Benefits analysis

### 4.3 Automated Refactoring Tasks
- Create tasks for high-value refactoring
- Track refactoring progress

---

## Phase 5: Worktree Safety & Branch Isolation (CRITICAL)

### 5.1 Problem Statement
Multiple worktrees on different branches can cause:
- Task conflicts and data corruption
- Two worktrees editing same file
- Tasks started in worktree A, continued in worktree B
- Changes lost due to worktree deletion
- OctoFriend instances stepping on each other

### 5.2 Worktree-Aware Task Management

**New Model Fields:**
```python
{
    "worktree_id": "uuid",
    "branch_name": "feature/new-auth",
    "repo_path": "/path/to/worktree",
    "base_branch": "main",
    "is_isolated": true,
    "merge_conflicts_expected": ["src/auth.py"],
}
```

**MCP Tools:**
- `worktree_get_current_info()` - Auto-detect worktree context
- `worktree_list_all(repo_id)` - Show all worktrees + their tasks
- `worktree_create_task(...)` - Create task scoped to worktree
- `worktree_find_conflicts(...)` - Predict conflicts between worktrees
- `worktree_validate_safe_to_work(...)` - Check safety before starting work

### 5.3 Safety Guards

**Automatic Checks Before Task Operations:**
- ✅ Worktree exists and matches branch
- ✅ No concurrent modifications in other worktrees
- ✅ Task not already active in another worktree
- ✅ No uncommitted changes that could be lost
- ✅ Disk space available
- ✅ Worktree not locked by another process

### 5.4 Worktree-Aware Codebase Queries

```python
# Search respects worktree boundaries
async def codebase_find_entity(
    repo_id: str,
    name: str,
    worktree_scope: str = "current",  # "current", "base", "all"
    include_uncommitted: bool = true,
)
```

### 5.5 Automatic Worktree Management

**Setup:**
- Auto-detect git worktrees
- Create isolated task spaces
- Copy relevant tasks from base

**Cleanup:**
- Migrate incomplete tasks before deletion
- Archive completed work
- Preserve history

### 5.6 Git Integration

**Hooks:**
```bash
# Auto-sync worktree context on branch change
post-checkout: archon-cli worktree sync --from-git
```

**Auto-Discovery:**
- Main repo
- Internal worktrees (.worktrees/)
- External worktrees (any path)

---

## Phase 6: CI/CD & Workflow Integration

### 6.1 CI/CD Integration
- GitHub Actions / GitLab CI
- Block PRs with critical issues
- Auto-comment with audit results

### 6.2 PR Review Bot
- Auto-audit on PR creation
- Suggest reviewers based on code ownership
- Link to MCP tools for deeper analysis

### 6.3 IDE Extensions
- VS Code / JetBrains plugins
- Real-time audit feedback
- Quick fixes
- Code lens with relationships

---

## Phase 7: Advanced Intelligence

### 7.1 Semantic Similarity Detection
- Find functionally similar code
- Deduplication opportunities

### 7.2 Architecture Compliance
- Check against documented architecture
- Layer dependency validation

### 7.3 Team Velocity Insights
- Commit frequency trends
- Quality score trends
- Documentation coverage trends

---

## Implementation Priority

### Immediate (This Sprint)
1. ✅ Code entity extraction (DONE)
2. ✅ Basic MCP tools (DONE)
3. 🔄 Metrics tracking system (Phase 1)
4. 🔄 Core auditing rules (Phase 2)
5. 🔄 **Worktree safety system (Phase 5) - CRITICAL**

### Short-term (Next 2 Sprints)
6. Full audit rule engine (50+ rules)
7. MCP audit tools
8. Historical metrics trending
9. Documentation gap analysis

### Medium-term (Next Quarter)
10. CI/CD integration
11. PR review bot
12. Refactoring intelligence
13. Report generation

### Long-term (Next 6 Months)
14. IDE extensions
15. Semantic similarity
16. Team velocity insights
17. Compliance reporting

---

## Success Metrics

**User Adoption:**
- 10+ teams using audit system
- 100+ audits run per week
- 50+ MCP tool calls per day

**Code Quality Impact:**
- Average quality score improvement: +10 points
- Documentation coverage: 95%+
- Critical issues in production: -90%

**Developer Experience:**
- Time to understand codebase: -50%
- Refactoring confidence: +80%
- Code review time: -30%
- **Worktree conflicts: 0** (safety system working)

---

## Comparison with Commercial Tools

| Feature | CodeRabbit | SonarQube | Archon |
|---------|------------|-----------|--------|
| AI-powered reviews | ✅ | ⚠️ | ✅ |
| Semantic search | ❌ | ❌ | ✅ |
| MCP integration | ⚠️ | ❌ | ✅ |
| Code relationships | ❌ | ❌ | ✅ |
| Open source | ❌ | ⚠️ | ✅ |
| Self-hosted | ❌ | ✅ | ✅ |
| Custom rules | ✅ | ✅ | ✅ |
| PR automation | ✅ | ⚠️ | ✅ |
| IDE integration | ✅ | ✅ | 🔄 |
| Refactoring plans | ❌ | ❌ | ✅ |
| **Worktree safety** | ❌ | ❌ | **✅** |

---

## Next Steps

1. Review roadmap and prioritize
2. **Start Phase 1 (Metrics) + Phase 5 (Worktree Safety) in parallel**
3. Define initial audit rules (10 security + 10 quality)
4. Create tasks for each phase
5. Iterate based on usage

**Ready to build the future of code intelligence with worktree safety?**
