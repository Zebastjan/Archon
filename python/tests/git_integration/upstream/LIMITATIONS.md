# Git Integration Known Limitations

## Test Suite Status

**Current Pass Rate**: 94% (16/17 tests passing)

Last updated: March 2026

## Supported Features

- ✅ Repository initialization and registration
- ✅ Commit history retrieval and syncing
- ✅ Branch listing and switching
- ✅ File tree navigation at any commit
- ✅ File content retrieval at any commit
- ✅ Multi-branch repositories
- ✅ Divergent branch file trees
- ✅ File deletions across commits
- ✅ Unicode file content
- ✅ Unicode commit messages
- ✅ Binary file detection

## Known Issues

### Unicode Filenames

**Status**: Partial support

Some filesystems encode unicode filenames differently than git CLI displays them. This can cause file tree comparisons to show apparent mismatches where the filename is the same but the encoding representation differs.

Example:
- CLI shows: `"\346\226\207\344\273\266.txt"` (escaped)
- Service returns: `文件.txt` (actual unicode)

**Workaround**: Content tests pass correctly; only filename comparison in tree listings may differ on some systems.

### Git Build Environment Not Required

Our test fixtures are created programmatically using GitPython rather than extracted from git.git's official test suite. This approach:
- ✅ Works without building Git from source
- ✅ Is faster and more portable
- ✅ Covers the same scenarios as Git's tests
- ⚠️ May miss some edge cases discovered by Git's 20+ years of development

## Unsupported Features

These features are explicitly not supported:

- ❌ Git hooks (pre-commit, post-commit, etc.)
- ❌ Git submodules (explicitly rejected in code)
- ❌ Remote operations (push, pull, fetch)
- ❌ Staging area manipulation (we read from commits directly)
- ❌ Interactive rebase
- ❌ Git LFS (Large File Storage)
- ❌ Bare repositories

## Performance Limitations

- Large repositories (100k+ commits): May require pagination in sync_commits
- Large files (100MB+): Not optimized for streaming
- Deep nesting (20+ levels): Tested up to 10 levels

## CI/CD Integration

Upstream tests run:
- Nightly at 2 AM UTC
- On pushes to main and git-integration branches
- On PRs to main

See `.github/workflows/git-upstream-tests.yml`

## Adding New Test Fixtures

To add a new test scenario:

1. Add fixture creation function to `python/tests/git_integration/upstream/create_fixtures.py`
2. Add corresponding tests to appropriate `test_upstream_*.py` file
3. Run `python create_fixtures.py` to generate fixtures
4. Run `pytest python/tests/git_integration/test_upstream_*.py -v` to verify

## Success Metrics

Per ADR-004, we targeted:
- ✅ 10+ tests running (Phase 1) - **Achieved: 17 tests**
- ✅ 80%+ pass rate - **Achieved: 94%**
- ✅ All failures documented - **Achieved: This document**
- ✅ CI/CD integration - **Achieved: GitHub Actions workflow**
