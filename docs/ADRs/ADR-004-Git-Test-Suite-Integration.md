# ADR-004: Git Test Suite Integration

**Status**: Accepted
**Date**: 2026-03-08
**Authors**: Archon Team
**Related**: ADR-003 (Git Integration Architecture)

## Context

### Current State

Our Git integration testing infrastructure consists of:
- **Custom test generators**: `divergent_files.py`, `file_deletions.py`, `merge_scenarios.py`, `edge_cases.py`
- **Pre-baked fixtures**: `simple-commits`, `multi-branch`, `file-structure`
- **Test coverage**: 27+ tests across 6 test modules, all passing
- **Fast iteration**: Quick unit tests enable rapid development

While this custom infrastructure has served us well for core development, it has limitations:
- Custom tests may miss edge cases encountered over Git's 20+ years of development
- No guarantee our `GitRepositoryService` matches Git's behavior in all corner cases
- We're reinventing the wheel instead of leveraging battle-tested infrastructure
- Limited confidence when handling unusual repository states

### Problem Statement

**User requirement**: Use Git project's official test suite from the git.git repository instead of building custom test infrastructure.

**What was implemented**: Custom test generators and fixtures.

**Gap**: We built our own testing approach rather than leveraging Git's comprehensive test suite (1000+ tests covering every edge case).

### Requirements

1. **Comprehensive coverage** of Git edge cases that 20+ years of development has uncovered
2. **Confidence guarantee** that our implementation matches Git's behavior in corner cases
3. **Battle-tested validation** using industry-standard test infrastructure
4. **Maintain development velocity** - don't slow down iteration speed
5. **Leverage existing work** - the Git project has extensive test coverage we can use

## Decision

Adopt a **hybrid testing approach**:

1. **Keep custom generators** for fast unit testing and development iteration
2. **Integrate Git's official test suite** for comprehensive validation and edge case coverage

This gives us:
- Speed (custom tests run in seconds)
- Confidence (Git tests validate against canonical behavior)
- Best of both worlds (fast iteration + comprehensive validation)

## Architecture

### Git Test Suite Overview

- **Source**: https://github.com/git/git/tree/master/t
- **Framework**: Sharness (POSIX shell-based testing framework)
- **Coverage**: 1000+ tests covering every Git command and edge case
- **Documentation**: Expected outputs documented for each test scenario
- **Test categories**:
  - `t0*.sh` - Basic repository operations
  - `t1*.sh` - Plumbing commands (low-level operations)
  - `t2*.sh` - Porcelain commands (user-facing operations)
  - `t3*.sh` - Merging and conflict resolution
  - `t4*.sh` - Diffs and patches
  - `t5*.sh` - Networking (not relevant for our use case)
  - `t6*.sh` - Advanced features
  - `t7*.sh` - Submodules, attributes, large files

### Integration Strategy

**Three-Layer Approach**:

#### Layer 1: Test Fixture Extraction

Clone git.git repository and extract relevant test repositories:
- Git tests create repositories in `t/trash directory.*` patterns
- Run selected tests to completion
- Capture resulting repository states
- Package as tarball archives for reproducibility

#### Layer 2: Adapter Layer

Translate Git test expectations to our API:
- Map Git CLI commands → `GitRepositoryService` methods
- Convert Sharness assertions → pytest assertions
- Handle output format differences (CLI vs API responses)

Example mappings:
```python
# Git CLI → GitRepositoryService
"git log --oneline" → service.get_commit_history()
"git show HEAD:file.txt" → service.get_file_content()
"git branch" → service.list_branches()
"git ls-tree HEAD" → service.get_file_tree()
```

#### Layer 3: Selective Test Running

We don't need all 1000+ Git tests. Focus on areas relevant to our use case:

**Phase 1: Basic Repository Operations** (t0*.sh)
- Repository initialization
- Commit creation and retrieval
- Branch operations
- Reference handling

**Phase 2: File Operations** (t1*.sh, t2*.sh)
- File content retrieval
- Tree traversal
- File path handling
- Binary file detection

**Phase 3: Advanced Scenarios** (t3*.sh)
- Merge commits (multi-parent)
- Complex branching
- File deletions across branches
- Content divergence

**Phase 4: Edge Cases** (t3900*.sh, t9600*.sh)
- Unicode filenames and content
- Special characters in paths
- Empty files (0 bytes)
- Deep nesting (10+ levels)
- Long file paths (255+ characters)
- Binary files and large blobs

### Implementation Phases

#### Phase 1: Foundation (3 days)

**Goals**:
- Set up Git test infrastructure
- Extract first set of test fixtures
- Build pytest adapter framework
- Run first 10 Git tests against our service

**Deliverables**:
- Cloned git.git repository in `/python/tests/git_integration/upstream/`
- Extraction script for test fixtures
- Basic `GitTestAdapter` class
- 10+ passing tests from t0*.sh suite
- Documentation of test results

#### Phase 2: Core Operations (4 days)

**Goals**:
- Extract fixtures from plumbing and porcelain tests
- Implement adapter for file operations
- Expand test coverage to 50+ tests
- Document pass/fail rates and reasons

**Deliverables**:
- Fixtures from t1*.sh, t2*.sh extracted
- File operation adapters implemented
- 50+ tests running with results documented
- Failure analysis report

#### Phase 3: Advanced Scenarios (5 days)

**Goals**:
- Handle complex merge scenarios
- Test multi-parent commits
- Validate file tree at merge points
- Fix discovered bugs in `GitRepositoryService`

**Deliverables**:
- Fixtures from t3*.sh, t4*.sh extracted
- Merge scenario adapters implemented
- 100+ tests running
- Bug fixes for failures
- Updated service documentation

#### Phase 4: Edge Cases & Polish (3 days)

**Goals**:
- Handle unicode, binary files, large repos
- Achieve 90%+ pass rate on selected tests
- Document known limitations
- CI/CD integration

**Deliverables**:
- All relevant test fixtures extracted
- Edge case handling complete
- 90%+ pass rate achieved
- Known limitations documented
- GitHub Actions workflow configured

### Expected Test Coverage

| Test Category | Git Tests | Selected for Integration | Rationale |
|--------------|-----------|-------------------------|-----------|
| Basic operations (t0*.sh) | ~50 | ~20 | Repository init, commits, branches |
| Plumbing (t1*.sh) | ~150 | ~30 | Low-level file/tree operations |
| Porcelain (t2*.sh) | ~100 | ~20 | User-facing commands we expose |
| Merging (t3*.sh) | ~200 | ~40 | Multi-parent commits, conflicts |
| Diffs (t4*.sh) | ~150 | ~20 | File content comparison |
| Networking (t5*.sh) | ~100 | 0 | Not relevant (no remote ops) |
| Advanced (t6*.sh) | ~150 | ~15 | Attributes, hooks (selective) |
| Submodules (t7*.sh) | ~100 | ~5 | Edge cases only (we reject submodules) |
| **Total** | **~1000** | **~150** | **15% coverage, high relevance** |

## Consequences

### Positive

1. **High confidence in Git compatibility**
   - Our service behavior validated against canonical Git implementation
   - Edge cases we didn't think of are now covered
   - Industry-standard validation approach

2. **Battle-tested coverage**
   - 20+ years of Git development experience captured
   - Real-world scenarios from production Git usage
   - Comprehensive edge case handling

3. **Bug discovery**
   - Will likely expose bugs we haven't encountered
   - Proactive issue detection before production use
   - Improved robustness of `GitRepositoryService`

4. **Documentation of limitations**
   - Clear understanding of what we support vs. don't support
   - Known edge cases documented
   - Informed decisions on future development

### Negative

1. **Additional maintenance overhead**
   - Must update fixtures when Git releases new versions
   - Adapter layer needs maintenance as our API evolves
   - Test suite requires periodic re-runs

2. **Slower test execution for full suite**
   - 150+ tests will take longer than our current 27 tests
   - May need to split into fast/comprehensive test runs
   - CI/CD pipelines will take longer

3. **May expose bugs requiring fixes**
   - Some Git tests may reveal bugs in our implementation
   - Will need time to fix discovered issues
   - Could delay other feature work temporarily

4. **Some tests may not be relevant**
   - Git has features we don't support (submodules, hooks, networking)
   - Need careful curation of which tests to run
   - Adapter layer must handle N/A scenarios gracefully

### Mitigation Strategies

1. **Tiered test execution**:
   - Fast suite (custom tests): Run on every commit (~30 seconds)
   - Comprehensive suite (Git tests): Run nightly or on PR merge (~5 minutes)

2. **Incremental integration**:
   - Start with 10 tests, expand gradually
   - Fix bugs as we go, don't block on 100% pass rate
   - Document known failures with reasons

3. **Clear test categorization**:
   - Mark tests as: supported, unsupported, edge-case-only
   - Skip irrelevant tests explicitly with documentation
   - Focus on high-value test coverage first

## Implementation

See detailed step-by-step guide: `/docs/implementation-guides/git-test-suite-integration.md`

## Alternatives Considered

### Alternative 1: Only Custom Tests (Current Approach)

**Pros**:
- Fast iteration speed
- Full control over test scenarios
- Easy to maintain

**Cons**:
- May miss edge cases
- No canonical validation
- Reinventing the wheel

**Decision**: Rejected as incomplete - need Git validation

### Alternative 2: Only Git Tests

**Pros**:
- Comprehensive coverage
- Canonical validation
- No custom test maintenance

**Cons**:
- Slow iteration (1000+ tests)
- Overkill for development
- Hard to debug failures

**Decision**: Rejected as too slow for development

### Alternative 3: Hybrid Approach (Chosen)

**Pros**:
- Fast iteration (custom tests)
- Comprehensive validation (Git tests)
- Best of both worlds

**Cons**:
- More complex infrastructure
- Two test suites to maintain

**Decision**: Accepted - balances speed and confidence

## Success Metrics

- [ ] Can run 10+ Git tests from t0*.sh suite
- [ ] Can run 50+ Git tests from t1*.sh, t2*.sh suites
- [ ] Can run 30+ Git tests from t3*.sh suite
- [ ] 80%+ pass rate on selected tests
- [ ] All failures documented with reasons and categorization
- [ ] CI/CD integration with nightly runs
- [ ] Documentation of known limitations and unsupported features
- [ ] Bug fixes for all high-priority failures
- [ ] Adapter layer is maintainable and well-documented

## Future Considerations

1. **Incremental Git updates**: When Git releases new versions, re-run test suite and update fixtures
2. **Expanded coverage**: If we add features (e.g., submodule support), integrate relevant Git tests
3. **Performance benchmarks**: Use Git's performance tests to validate our service scales appropriately
4. **Regression prevention**: Add Git tests to CI/CD to catch regressions early

## References

- Git Test Suite: https://github.com/git/git/tree/master/t
- Sharness Framework: https://github.com/chriscool/sharness
- ADR-003: Git Integration Architecture
- Implementation Guide: `/docs/implementation-guides/git-test-suite-integration.md`
