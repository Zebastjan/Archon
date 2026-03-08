# Git Upstream Test Suite

This directory contains test fixtures and adapters for validating `GitRepositoryService` against Git scenarios.

## Quick Start

```bash
# Create all test fixtures
cd /home/zebastjan/dev/archon/python/tests/git_integration/upstream
python create_fixtures.py

# Run upstream tests
pytest /home/zebastjan/dev/archon/python/tests/git_integration/test_upstream_*.py -v
```

## Architecture

```
upstream/
├── create_fixtures.py       # Programmatic fixture creation
├── extract_fixtures.py      # Script to extract from git.git (requires build)
├── git_test_adapter.py      # Adapter: Git CLI ↔ Service API
├── git/                      # Cloned git.git repository
├── README.md                 # This file
└── LIMITATIONS.md           # Known issues and limitations

fixtures/upstream/
├── t0001-init/              # Basic repository
├── t1000-read-tree/         # File tree operations
├── t3200-branch/            # Branch operations
├── t3400-rebase/            # Divergent branches
├── t3600-rm/                # File deletions
└── t3900-unicode/           # Unicode content
```

## Files

| Test File | Fixtures | Description |
|-----------|----------|-------------|
| `test_upstream_basic.py` | t0001-init | Repository init, commit history |
| `test_upstream_files.py` | t1000-read-tree | File tree, content retrieval |
| `test_upstream_branch.py` | t3200-branch | Branch listing, switching |
| `test_upstream_merge.py` | t3400-rebase, t3600-rm | Divergent branches, deletions |
| `test_upstream_edge.py` | t3900-unicode | Unicode handling |

## Adapter Layer

The `GitTestAdapter` class translates between Git CLI commands and `GitRepositoryService` API calls:

```python
adapter = GitTestAdapter(repo_path, service, repo_id)

# CLI equivalents
adapter.get_commit_sha("HEAD")           # git rev-parse HEAD
adapter.get_file_tree_cli("HEAD")        # git ls-tree -r --name-only HEAD
adapter.get_file_content_cli("file.txt") # git show HEAD:file.txt

# Service equivalents
adapter.get_file_tree_service(sha)
adapter.get_file_content_service("file.txt", sha)

# Assertions
adapter.assert_file_content_matches("file.txt", sha)
adapter.assert_file_tree_matches(sha)
```

## Creating New Fixtures

1. Add function to `create_fixtures.py`:

```python
def create_tXXXX_name_fixture():
    fixture_path = FIXTURES_DIR / "tXXXX-name"
    fixture_path.mkdir(parents=True)
    
    repo = Repo.init(fixture_path)
    # ... setup repository state
    
    return fixture_path
```

2. Add to `create_all_fixtures()` list

3. Add tests to new or existing `test_upstream_*.py`

4. Run `python create_fixtures.py tXXXX-name`

## CI/CD

Tests run automatically:
- Nightly at 2 AM UTC
- On push to `main` or `git-integration`
- On PR to `main`

## See Also

- `LIMITATIONS.md` - Known issues and unsupported features
- `../../../docs/ADRs/ADR-004-Git-Test-Suite-Integration.md` - Architecture decision
- `../../../docs/implementation-guides/git-test-suite-integration.md` - Implementation guide
