# Git Integration Test Suite

Comprehensive test suite for Git repository integration with programmatic fixture generation.

## Overview

This test suite validates Git integration functionality including:
- Repository registration and commit syncing
- Multi-branch support with proper branch tracking
- File content divergence across branches
- File deletion scenarios
- Complex merge commits with multiple parents
- File tree generation and filtering
- Binary file detection and language identification

## Test Structure

### Programmatic Fixture Generators

Located in `fixtures/generators/`, these modules create test repositories on-the-fly:

#### 1. **divergent_files.py**
Creates a repository with file content divergence across branches.

**Structure:**
```
main branch:
  - README.md (shared content)
  - config.json ({"debug": false})
  - settings.yaml (main only)

feature/config-changes branch:
  - README.md (shared content)
  - config.json ({"debug": true, "verbose": true})
  - experiment.py (feature only)
```

**Tests Covered:**
- Same file path with different content (different blob SHA)
- File existence divergence (branch-specific files)
- Proper content retrieval per branch
- File tree filtering by branch

#### 2. **file_deletions.py**
Creates a repository with file deletion scenarios.

**Structure:**
```
Initial state (both branches):
  - app.py
  - legacy.py
  - old_util.py

main branch after deletion:
  - app.py ✓
  - old_util.py ✓
  - legacy.py [deleted]

feature/cleanup branch after deletion:
  - app.py ✓
  - legacy.py ✓
  - old_util.py [deleted]
```

**Tests Covered:**
- Deleted files don't appear in file tree
- Reading deleted files raises GitFileNotFoundError
- File counts differ between branches
- Deletion commits properly tracked

#### 3. **merge_scenarios.py**
Creates a repository with complex merge commits.

**Structure:**
```
* M3 (main) - Merge feature-a and feature-b (2 parents)
|\
| * F2 (feature-b) - Add feature B
* | F1 (feature-a) - Add feature A
|/
* C0 - Initial commit
```

**Tests Covered:**
- Merge commits stored in database
- File tree at merge includes files from both branches
- Feature branches have different files before merge
- All commits properly tracked
- Branch associations correct after merge

#### 4. **edge_cases.py**
Creates a repository with various edge cases.

**Structure:**
```
- README.md (normal file)
- files/unicode_文件名_ファイル_📄.txt (unicode)
- files/special!@#$%^&()_+-=[]{}~`.txt (special chars)
- empty.txt (0 bytes)
- assets/test.png (binary file)
- very/long/path/.../file.txt (240+ character path)
- deeply/nested/.../level10/file.txt (10 levels deep)
```

**Tests Covered:**
- Unicode filename handling
- Special character support in filenames
- Empty file (0 bytes) detection and reading
- Binary file access blocking (returns error, not content)
- Long path support (200+ characters)
- Deep directory nesting (10+ levels)
- Accurate metadata for all edge cases

### Static Test Fixtures

Located in `fixtures/`:
- **simple-commits**: Linear history, basic file tracking
- **multi-branch**: 3 branches with merge commit
- **file-structure**: Complex directory hierarchy, binary files

## Test Files

### test_divergent_files.py (5 tests)
- `test_same_file_different_content_across_branches` - Validates blob SHA differences
- `test_file_content_retrieval_differs_by_branch` - Verifies content differs per branch
- `test_shared_file_has_same_content` - Confirms identical files have same blob SHA
- `test_branch_specific_files_not_in_other_branch` - Validates file existence filtering
- `test_file_count_differs_by_branch` - Confirms correct file counts per branch

### test_file_deletions.py (5 tests)
- `test_deleted_files_not_in_tree` - Deleted files don't appear in tree
- `test_reading_deleted_file_fails` - Proper error handling for deleted files
- `test_file_exists_in_initial_commit` - All files exist before deletions
- `test_file_count_differs_after_deletion` - File counts change after deletions
- `test_deletion_tracked_in_commits` - Deletion commits properly stored

### test_merge_scenarios.py (5 tests)
- `test_merge_commit_has_multiple_parents` - Merge commits stored (⚠️ parent_shas bug)
- `test_merge_commit_file_tree_includes_both_features` - Merged file tree correct
- `test_feature_branches_have_different_files` - Branches diverge correctly
- `test_all_commits_properly_tracked` - All commits synced to database
- `test_branch_associations_after_merge` - Branch arrays properly merged

### test_edge_cases.py (8 tests)
- `test_unicode_filenames_supported` - Unicode characters in filenames work
- `test_special_characters_in_filenames` - Special chars (!@#$%^&) supported
- `test_empty_files_handled_correctly` - 0-byte files properly handled
- `test_binary_file_access_blocked` - Reading binary files returns proper error
- `test_long_file_paths_supported` - Paths 200+ characters work
- `test_deeply_nested_directories_supported` - 10+ nesting levels work
- `test_all_edge_case_files_in_tree` - All edge case files indexed
- `test_file_metadata_accurate_for_edge_cases` - Metadata correct for edge cases

### test_git_repository_integration.py (4 tests)
- `test_register_repository_records_metadata` - Repository registration
- `test_sync_commits_persists_history` - Commit syncing
- `test_get_file_tree_includes_binary_flags` - Binary detection
- `test_sync_commits_merges_branches_on_upsert` - Branch merging

## Running Tests

### Run All Git Integration Tests
```bash
cd /home/zebastjan/dev/archon
uv run pytest python/tests/git_integration/ -v
```

### Run Specific Test Suite
```bash
# Divergent files tests
uv run pytest python/tests/git_integration/test_divergent_files.py -v

# File deletions tests
uv run pytest python/tests/git_integration/test_file_deletions.py -v

# Merge scenarios tests
uv run pytest python/tests/git_integration/test_merge_scenarios.py -v
```

### Run Single Test
```bash
uv run pytest python/tests/git_integration/test_divergent_files.py::test_same_file_different_content_across_branches -v
```

## Test Infrastructure

### FakeSupabaseClient
Mock Supabase client for testing without database:
- Simulates table operations (select, insert, update, upsert)
- Implements RPC function `upsert_git_commit_with_branch_merge`
- Properly merges branch arrays on commit upserts
- Located in `test_git_repository_integration.py`

### Fixtures
- `supabase_client` - Provides FakeSupabaseClient instance
- `git_service` - GitRepositoryService with fake client
- `divergent_fixture` - Programmatically generated divergent-files repo
- `deletions_fixture` - Programmatically generated file-deletions repo
- `merge_fixture` - Programmatically generated merge-scenarios repo

## Fixed Issues

### ✅ parent_shas Now Properly Stored
**Status:** FIXED in migration 019

**Fix Applied:**
- Updated `upsert_git_commit_with_branch_merge` RPC function to accept `p_parent_shas TEXT[]` parameter
- Added `parent_shas` to INSERT and ON CONFLICT UPDATE statements
- Function now returns UUID instead of VOID for better tracking
- Parent SHAs are set on initial insert and preserved on updates (immutable)

**Test Coverage:** `test_merge_commit_has_multiple_parents` validates 2-parent merge commits work correctly

## Coverage Summary

**Total Tests:** 27 (all passing)
- Divergent file scenarios: 5 tests ✅
- File deletion scenarios: 5 tests ✅
- Merge scenarios: 5 tests ✅
- Edge cases: 8 tests ✅
- Basic integration: 4 tests ✅

**Test Coverage:**
- ✅ Multi-branch support
- ✅ File content divergence
- ✅ File deletions
- ✅ Binary file detection
- ✅ Language identification
- ✅ Commit syncing
- ✅ Branch merging
- ✅ File tree generation
- ⚠️ Merge commit parents (bug documented)

## Next Steps (from Roadmap)

### Priority 1: Fix Critical Bugs (Week 1)
- [ ] Fix `parent_shas` not being populated in database
- [ ] Update RPC function to handle `parent_shas`
- [ ] Add test to verify 2-parent merge commits work

### Priority 2: Advanced Test Scenarios (Week 1)
- [ ] Binary file access blocking test (400 error)
- [ ] Unicode/special characters in filenames
- [ ] Very long file paths (255+ characters)
- [ ] Empty files (0 bytes)
- [ ] Deeply nested directories (10+ levels)

### Priority 3: Diff Viewing (Week 2)
- [ ] Implement structured diff endpoint
- [ ] Add diff viewing tests
- [ ] Test hunks, additions, deletions

### Priority 4: Semantic Commit Classification (Week 2)
- [ ] Implement LLM-based commit classification
- [ ] Add classification tests
- [ ] Validate intent, risk, breaking changes

## References

- **Architecture:** `@PRPs/ai_docs/ARCHITECTURE.md`
- **Git Schema:** `migration/0.1.0/017_add_git_tables.sql`
- **RPC Function:** `migration/0.1.0/019_add_commit_upsert_function.sql`
- **Service:** `python/src/server/services/git/git_repository_service.py`
- **API:** `python/src/server/api_routes/git_api.py`
- **Roadmap:** Project planning document with 8-week implementation plan

---

# Ollama Test Support

The test suite supports running against a live Ollama instance for real embedding validation.

## Test Types

- **Mock Tests** (`@pytest.mark.mock`): Fast tests with mocked dependencies
- **Ollama Tests** (`@pytest.mark.ollama`): Tests requiring live Ollama instance

## Running Tests

```bash
# Run all tests (skips Ollama if unavailable)
pytest tests/git_integration/ -v

# Run only mock tests
pytest tests/git_integration/ -v -m mock

# Run only Ollama tests (requires Ollama)
export OLLAMA_TEST_URL=http://localhost:11434
pytest tests/git_integration/ -v -m ollama

# Skip Ollama tests
pytest tests/git_integration/ -v -m "not ollama"
```

## Ollama Setup

### 1. Install and Start Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama serve
```

### 2. Pull Embedding Model

```bash
ollama pull nomic-embed-text
```

### 3. Configure Test URL (optional)

```bash
export OLLAMA_TEST_URL=http://localhost:11434  # default
```

## Test Files with Ollama Support

| File | Marker | Description |
|------|--------|-------------|
| `test_git_embedding_service.py` | mock | Commit embedding with mocked service |
| `test_git_semantic_search.py` | mock | Semantic search tests |
| `test_git_rag_integration.py` | mock | RAG pipeline integration |
| `test_git_mcp_integration.py` | mock | MCP agent tests |
| `test_ollama_integration.py` | ollama | Real Ollama embedding tests |

## Fixtures Available

From `conftest.py`:

- `ollama_url` - URL to Ollama instance
- `ollama_available` - Boolean if Ollama is reachable
- `embedding_provider` - "ollama" or "mock"
- `mock_supabase_client` - Mocked Supabase client
- `mock_embedding_result` - Standard mock embedding (1536-dim)

## CI/CD

Mock tests run without Ollama:

```yaml
- name: Run tests
  run: pytest tests/git_integration/ -m mock
```
