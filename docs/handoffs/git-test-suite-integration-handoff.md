# Git Test Suite Integration - Handoff Document

## Task Summary

**Goal**: Integrate Git's official test suite (from git.git repository) into Archon's testing infrastructure to validate `GitRepositoryService` against battle-tested edge cases.

**Priority**: High - Addresses critical gap identified in roadmap assessment

**Timeline**: 1-2 weeks (15 days broken into 4 phases)

**Branch**: `git-integration` (work will continue on this branch in parallel with Phase 2 embeddings work)

---

## Context & Background

### Why This Task Exists

**User Requirement**: Use Git project's battle-tested test infrastructure from the git.git repository (Sharness-based tests from `t/` directory) instead of building custom test infrastructure.

**What Was Built**: Custom test generators (`divergent_files.py`, `file_deletions.py`, `merge_scenarios.py`, `edge_cases.py`) covering basic scenarios.

**The Gap**: We built our own testing approach rather than leveraging Git's comprehensive test suite (1000+ tests covering 20+ years of edge cases).

**The Solution**: Adopt a **hybrid approach**:
- Keep custom generators for fast iteration during development
- Add Git's official test suite for comprehensive validation

### Current State

**Existing Test Infrastructure** (DO NOT DELETE - these are valuable):
- Location: `/home/zebastjan/dev/archon/python/tests/git_integration/`
- Custom fixtures: `fixtures/generators/*.py` (4 generators)
- Pre-baked fixtures: `fixtures/simple-commits/`, `fixtures/multi-branch/`, etc.
- Test coverage: 27+ tests, all passing
- Purpose: Fast unit tests for development iteration

**What You Will Add**:
- Git test fixtures extracted from git.git repository
- Adapter layer to translate Git CLI commands → `GitRepositoryService` API calls
- 50-150 upstream Git tests validating our service behavior
- CI/CD integration for continuous validation

---

## Key Documents

You have three documents to guide your work:

### 1. ADR-004: Git Test Suite Integration

**Location**: `/home/zebastjan/dev/archon/docs/ADRs/ADR-004-Git-Test-Suite-Integration.md`

**Purpose**: Decision rationale and architecture

**Key Sections**:
- Context: Why we need Git's test suite
- Decision: Hybrid approach (custom + Git tests)
- Architecture: Three-layer integration strategy
- Implementation phases: 4 phases over 15 days
- Success metrics: 80%+ pass rate on 50+ tests

**Read this first** to understand the "why" and overall approach.

### 2. Implementation Guide: Git Test Suite Integration

**Location**: `/home/zebastjan/dev/archon/docs/implementation-guides/git-test-suite-integration.md`

**Purpose**: Step-by-step instructions with code examples

**Key Sections**:
- Phase 1: Setup & Foundation (3 days) - Clone git.git, extract fixtures, build adapter
- Phase 2: Core File Operations (4 days) - File tree, content retrieval tests
- Phase 3: Advanced Scenarios (5 days) - Merge commits, branching tests
- Phase 4: Edge Cases & CI/CD (3 days) - Unicode, binary files, CI/CD integration

**Use this as your execution guide** - follow step-by-step.

### 3. Handoff Document (This Document)

**Purpose**: Task summary, success criteria, and handoff checklist

---

## Success Criteria

When you complete this task, the following should be true:

### Phase 1 Success (Day 3)
- [ ] Git repository cloned to `/python/tests/git_integration/upstream/git/`
- [ ] Fixture extraction script created: `upstream/extract_fixtures.py`
- [ ] Adapter layer created: `upstream/git_test_adapter.py`
- [ ] 10+ test fixtures extracted (e.g., t0001-init, t0002-gitfile)
- [ ] Basic tests passing: `test_upstream_basic.py` with 4+ tests
- [ ] Documentation: `upstream/README.md` explaining setup

### Phase 2 Success (Day 7)
- [ ] 20+ file operation fixtures extracted (t1*.sh, t2*.sh)
- [ ] File operation tests implemented: `test_upstream_files.py`
- [ ] 20+ tests passing covering file tree, content retrieval, path handling
- [ ] Pass rate: 70%+ (some tests may fail - document why)

### Phase 3 Success (Day 12)
- [ ] 30+ merge/branch fixtures extracted (t3*.sh)
- [ ] Merge tests implemented: `test_upstream_merges.py`
- [ ] 30+ tests passing covering multi-parent commits, file deletions, branching
- [ ] Pass rate: 80%+ on selected tests
- [ ] Bug fixes: Any discovered bugs in `GitRepositoryService` are fixed or documented

### Phase 4 Success (Day 15)
- [ ] Edge case fixtures extracted (t3900*.sh, t9600*.sh)
- [ ] Edge case tests implemented: `test_upstream_edge.py`
- [ ] 10-15 edge case tests passing (unicode, binary files, special characters)
- [ ] CI/CD workflow created: `.github/workflows/git-upstream-tests.yml`
- [ ] Documentation: `docs/git-integration-limitations.md` with known limitations
- [ ] Final pass rate: 80%+ overall across all upstream tests

### Overall Success
- [ ] Total: 50+ Git tests running and passing
- [ ] All failures documented with reasons (known limitations)
- [ ] CI/CD integrated and passing
- [ ] No regressions in existing custom tests (27+ tests still passing)
- [ ] Pull request opened for review

---

## Critical Files

### Files You Will Create

**Test Infrastructure**:
- `/python/tests/git_integration/upstream/extract_fixtures.py` - Fixture extraction script
- `/python/tests/git_integration/upstream/git_test_adapter.py` - Adapter layer
- `/python/tests/git_integration/upstream/README.md` - Setup documentation

**Test Files**:
- `/python/tests/git_integration/test_upstream_basic.py` - Phase 1 tests
- `/python/tests/git_integration/test_upstream_files.py` - Phase 2 tests
- `/python/tests/git_integration/test_upstream_merges.py` - Phase 3 tests
- `/python/tests/git_integration/test_upstream_edge.py` - Phase 4 tests

**CI/CD**:
- `.github/workflows/git-upstream-tests.yml` - GitHub Actions workflow
- `/python/tests/git_integration/upstream/fixture_list.txt` - List of fixtures to extract

**Documentation**:
- `/docs/git-integration-limitations.md` - Known limitations and unsupported features

### Files You Must NOT Modify (Preserve Existing Work)

**DO NOT DELETE OR BREAK**:
- `/python/tests/git_integration/fixtures/generators/*.py` - Custom generators
- `/python/tests/git_integration/test_*.py` - Existing 27+ tests
- `/python/src/server/services/git/git_repository_service.py` - Core service (unless fixing bugs)

**Why**: These are valuable for fast iteration during development. Your Git tests are for comprehensive validation, not replacement.

### Files You May Need to Fix

If Git tests reveal bugs in our service:
- `/python/src/server/services/git/git_repository_service.py` - Core service implementation
- Document any bugs you can't fix in `/docs/git-integration-limitations.md`

---

## Step-by-Step Execution Plan

### Week 1: Foundation & Core Operations

**Days 1-3: Phase 1**
1. Clone git.git repository
2. Read a few test scripts to understand structure
3. Build fixture extraction script
4. Extract 10 basic fixtures (t0*.sh)
5. Build adapter layer (`GitTestAdapter` class)
6. Write 4+ basic tests
7. Verify tests pass

**Days 4-7: Phase 2**
1. Extract 20+ file operation fixtures (t1*.sh, t2*.sh)
2. Extend adapter with file operation methods
3. Write 20+ file operation tests
4. Run tests, document failures
5. Fix any obvious bugs in `GitRepositoryService`

### Week 2: Advanced Scenarios & Polish

**Days 8-12: Phase 3**
1. Extract 30+ merge/branch fixtures (t3*.sh)
2. Extend adapter with merge handling
3. Write 30+ merge tests
4. Focus on multi-parent commits, file deletions
5. Fix bugs discovered by tests

**Days 13-15: Phase 4**
1. Extract edge case fixtures (unicode, binary files)
2. Write 10-15 edge case tests
3. Build CI/CD workflow
4. Document known limitations
5. Write upstream/README.md with setup instructions
6. Run full test suite, verify 80%+ pass rate
7. Open pull request for review

---

## Questions & Clarifications

### When You Get Stuck

If you encounter issues during implementation:

1. **Consult ADR-003**: Git Integration Architecture
   - Location: `/docs/ADRs/ADR-003-Git-Integration-Architecture.md`
   - Explains `GitRepositoryService` design and database schema

2. **Review existing tests**: `/python/tests/git_integration/test_*.py`
   - See how we currently test Git functionality
   - Use similar patterns for upstream tests

3. **Check service implementation**: `/python/src/server/services/git/git_repository_service.py`
   - Understand what methods are available
   - See how they work internally

4. **Git test documentation**: https://github.com/git/git/blob/master/t/README
   - Official Git test suite README
   - Explains Sharness framework and test conventions

### Common Pitfalls to Avoid

1. **Don't try to run all 1000+ Git tests**: Focus on relevant tests (see fixture_list.txt)
2. **Don't aim for 100% pass rate**: 80%+ is success, document failures
3. **Don't break existing tests**: Run `pytest python/tests/git_integration/test_*.py` regularly
4. **Don't overcomplicate the adapter**: Start simple, add complexity as needed
5. **Don't skip documentation**: Known limitations are valuable for users

### What to Do About Test Failures

**If a Git test fails**:

1. **Investigate**: Is it a bug in our service or expected limitation?
2. **Fix if possible**: Simple bugs should be fixed in `GitRepositoryService`
3. **Document if not**: Add to `git-integration-limitations.md` with explanation
4. **Categorize**: High priority (core feature) vs Low priority (edge case)

**Examples of acceptable failures**:
- Git hooks (not supported, documented as limitation)
- Submodules (explicitly rejected per ADR-003)
- Remote operations (out of scope)

**Examples of must-fix failures**:
- File content mismatch (core functionality)
- Missing commits in history (core functionality)
- Wrong file tree structure (core functionality)

---

## Parallel Work Coordination

### Stream 2: Phase 2 Embeddings (Main Development)

While you work on Git test suite integration, another agent is implementing Phase 2 features on the `feature/phase-2-embeddings` branch:

- Commit message embeddings
- Diff summary embeddings
- Semantic search API
- Git-aware RAG integration
- UI for semantic search

**Your work is independent** - no coordination needed until merge time.

### Integration Point

After both streams complete:
1. Merge your Git test improvements to main
2. Run your Git tests against Phase 2 embeddings changes
3. Validate that embeddings/search work correctly with Git fixtures

---

## Handoff Checklist

Before marking this task complete:

### Code Deliverables
- [ ] `extract_fixtures.py` script working and documented
- [ ] `git_test_adapter.py` with comprehensive adapter methods
- [ ] `test_upstream_basic.py` with 4+ tests (Phase 1)
- [ ] `test_upstream_files.py` with 20+ tests (Phase 2)
- [ ] `test_upstream_merges.py` with 30+ tests (Phase 3)
- [ ] `test_upstream_edge.py` with 10+ tests (Phase 4)
- [ ] 50+ total upstream tests passing with 80%+ pass rate

### Infrastructure Deliverables
- [ ] Git repository cloned to `upstream/git/`
- [ ] Test fixtures extracted to `fixtures/upstream/`
- [ ] CI/CD workflow in `.github/workflows/git-upstream-tests.yml`
- [ ] Workflow passing in GitHub Actions

### Documentation Deliverables
- [ ] `upstream/README.md` explaining setup and usage
- [ ] `docs/git-integration-limitations.md` with known limitations
- [ ] Failure analysis report (which tests fail and why)
- [ ] `fixture_list.txt` with curated list of relevant fixtures

### Testing & Quality
- [ ] All existing tests still pass (27+ custom tests)
- [ ] No regressions introduced in `GitRepositoryService`
- [ ] Bug fixes tested and validated
- [ ] CI/CD workflow runs on push and nightly

### Pull Request
- [ ] Branch: `git-integration`
- [ ] Title: "feat: Integrate Git's official test suite for comprehensive validation"
- [ ] Description includes:
  - Summary of work done
  - Test pass/fail statistics
  - Known limitations discovered
  - Link to ADR-004 and implementation guide
- [ ] Ready for review

---

## Getting Started

**Your first steps**:

1. Read ADR-004 to understand the "why" (15 minutes)
2. Read the implementation guide Phase 1 section (30 minutes)
3. Set up your environment and clone git.git (30 minutes)
4. Follow Step 1.1 through Step 1.7 in the implementation guide (4-6 hours)
5. By end of Day 1, you should have basic tests passing

**Recommended approach**: Follow the implementation guide step-by-step. It's designed to build incrementally, so each phase depends on the previous one.

**Questions?** Refer to the "Questions & Clarifications" section above.

---

## Contact & Support

If you need clarification or encounter blockers:

- Reference documents: ADR-003, ADR-004, implementation guide
- Check existing test patterns: `/python/tests/git_integration/test_*.py`
- Review service implementation: `git_repository_service.py`
- Git test documentation: https://github.com/git/git/blob/master/t/README

**Remember**: The goal is comprehensive validation, not perfection. 80%+ pass rate with documented limitations is success!

---

## Completion Criteria

This task is complete when:

✅ Pull request is opened with all deliverables
✅ CI/CD workflow is green (passing)
✅ 50+ Git tests passing with 80%+ pass rate
✅ Documentation is complete and accurate
✅ No regressions in existing tests
✅ Ready for review and merge

**Good luck!** You're doing important work to ensure Archon's Git integration is rock-solid and battle-tested.
