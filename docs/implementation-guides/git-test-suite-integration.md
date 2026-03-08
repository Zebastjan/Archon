# Git Test Suite Integration - Implementation Guide

## Overview

This guide provides step-by-step instructions for integrating Git's official test suite into Archon's testing infrastructure. By the end of this guide, you will have:

- Git test fixtures extracted from the git.git repository
- An adapter layer for running Git tests via pytest
- 50+ Git tests validating `GitRepositoryService` behavior
- CI/CD integration for continuous validation

**Estimated Timeline**: 1-2 weeks (15 days broken into 4 phases)

## Prerequisites

Before starting, ensure you have:

- **Git installed**: For cloning git.git repository
- **Python 3.11+**: With pytest and our existing test infrastructure
- **Docker**: For Supabase testing (already set up)
- **Bash**: For running Sharness test scripts
- **Disk space**: ~500MB for git.git repository and test fixtures

## Directory Structure

You will create the following structure:

```
/home/zebastjan/dev/archon/python/tests/git_integration/
├── fixtures/
│   ├── generators/           # Existing custom generators (KEEP THESE)
│   │   ├── divergent_files.py
│   │   ├── file_deletions.py
│   │   ├── merge_scenarios.py
│   │   └── edge_cases.py
│   └── upstream/             # NEW: Git test fixtures
│       ├── t0000-basic/
│       ├── t1000-read-tree/
│       └── ...
├── upstream/                 # NEW: Git test infrastructure
│   ├── git/                  # Cloned git.git repository
│   ├── extract_fixtures.py   # NEW: Fixture extraction script
│   ├── git_test_adapter.py   # NEW: Adapter layer
│   └── README.md             # NEW: Upstream test documentation
├── test_upstream_basic.py    # NEW: Phase 1 tests
├── test_upstream_files.py    # NEW: Phase 2 tests
├── test_upstream_merges.py   # NEW: Phase 3 tests
└── test_upstream_edge.py     # NEW: Phase 4 tests
```

---

## Phase 1: Setup & Foundation (3 days)

### Step 1.1: Clone Git Repository

Navigate to the test directory and clone git.git:

```bash
cd /home/zebastjan/dev/archon/python/tests/git_integration
mkdir -p upstream
cd upstream

# Clone Git repository (shallow clone for speed)
git clone --depth 1 https://github.com/git/git.git
cd git

# Verify clone
ls t/  # Should see t0000-basic.sh, t1000-read-tree.sh, etc.
```

**Expected output**: Directory listing of 1000+ test scripts in `t/` directory.

### Step 1.2: Understand Git Test Structure

Git's test scripts follow naming conventions:

| Pattern | Description | Example | Relevance |
|---------|-------------|---------|-----------|
| `t0*.sh` | Basic operations | `t0000-basic.sh` | High - repository init, commits |
| `t1*.sh` | Plumbing commands | `t1000-read-tree.sh` | High - low-level file ops |
| `t2*.sh` | Porcelain commands | `t2000-checkout.sh` | Medium - user-facing commands |
| `t3*.sh` | Merging/branching | `t3000-ls-files-others.sh` | High - multi-parent commits |
| `t4*.sh` | Diffs and patches | `t4000-diff-format.sh` | Medium - content comparison |
| `t5*.sh` | Networking | `t5000-clone.sh` | Low - not relevant |
| `t6*.sh` | Advanced features | `t6000-rev-list-misc.sh` | Low - selective use |
| `t7*.sh` | Submodules, large files | `t7000-submodule.sh` | Low - edge cases only |

Explore a test script to understand structure:

```bash
cat t/t0000-basic.sh | head -50
```

**Key observations**:
- Tests use Sharness framework (shell-based)
- Each test creates a "trash directory" with a test repository
- Tests run git commands and assert expected outputs
- Expected outputs are documented inline

### Step 1.3: Extract First Test Fixture

Let's manually extract a simple test fixture to understand the process:

```bash
# Navigate to test directory
cd /home/zebastjan/dev/archon/python/tests/git_integration/upstream/git/t

# Run a basic test to create its repository
bash t0001-init.sh

# The test creates a trash directory
ls -la | grep "trash directory"
# Output: trash directory.t0001-init/

# Copy the trash directory to our fixtures
mkdir -p /home/zebastjan/dev/archon/python/tests/git_integration/fixtures/upstream/
cp -r "trash directory.t0001-init" ../../fixtures/upstream/t0001-init

# Clean up trash directory
rm -rf "trash directory.t0001-init"

echo "Fixture extracted to fixtures/upstream/t0001-init"
```

**Verification**: Check that `fixtures/upstream/t0001-init/.git` exists and contains a valid Git repository.

### Step 1.4: Build Fixture Extraction Script

Now automate this process with a Python script:

Create `/home/zebastjan/dev/archon/python/tests/git_integration/upstream/extract_fixtures.py`:

```python
#!/usr/bin/env python3
"""
Extract test fixtures from Git's test suite.

Usage:
    python extract_fixtures.py t0001-init t1000-read-tree
"""

import subprocess
import shutil
import sys
from pathlib import Path

GIT_TEST_DIR = Path(__file__).parent / "git" / "t"
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "upstream"


def extract_fixture(test_name: str) -> bool:
    """
    Run a Git test script and extract the resulting repository.

    Args:
        test_name: Test name without .sh extension (e.g., "t0001-init")

    Returns:
        True if extraction succeeded, False otherwise
    """
    test_script = GIT_TEST_DIR / f"{test_name}.sh"

    if not test_script.exists():
        print(f"❌ Test script not found: {test_script}")
        return False

    print(f"🏃 Running test: {test_name}")

    # Run test script
    result = subprocess.run(
        ["bash", str(test_script)],
        cwd=GIT_TEST_DIR,
        capture_output=True,
        text=True
    )

    # Find trash directory
    trash_dir = GIT_TEST_DIR / f"trash directory.{test_name}"

    if not trash_dir.exists():
        print(f"⚠️  No trash directory found for {test_name}")
        print(f"Test output:\n{result.stdout}\n{result.stderr}")
        return False

    # Copy to fixtures
    output_dir = FIXTURES_DIR / test_name
    if output_dir.exists():
        print(f"🗑️  Removing existing fixture: {output_dir}")
        shutil.rmtree(output_dir)

    shutil.copytree(trash_dir, output_dir)

    # Clean up trash directory
    shutil.rmtree(trash_dir)

    print(f"✅ Extracted fixture: {test_name} → {output_dir}")
    return True


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_fixtures.py TEST_NAME [TEST_NAME ...]")
        print("Example: python extract_fixtures.py t0001-init t1000-read-tree")
        sys.exit(1)

    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    successes = 0
    failures = 0

    for test_name in sys.argv[1:]:
        # Remove .sh extension if provided
        test_name = test_name.replace(".sh", "")

        if extract_fixture(test_name):
            successes += 1
        else:
            failures += 1

    print(f"\n📊 Results: {successes} succeeded, {failures} failed")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
```

Make it executable and test:

```bash
chmod +x /home/zebastjan/dev/archon/python/tests/git_integration/upstream/extract_fixtures.py
cd /home/zebastjan/dev/archon/python/tests/git_integration/upstream
python extract_fixtures.py t0001-init t0002-gitfile
```

**Expected output**:
```
🏃 Running test: t0001-init
✅ Extracted fixture: t0001-init → .../fixtures/upstream/t0001-init
🏃 Running test: t0002-gitfile
✅ Extracted fixture: t0002-gitfile → .../fixtures/upstream/t0002-gitfile

📊 Results: 2 succeeded, 0 failed
```

### Step 1.5: Build Adapter Layer

Create the adapter that translates Git CLI commands to `GitRepositoryService` calls:

Create `/home/zebastjan/dev/archon/python/tests/git_integration/upstream/git_test_adapter.py`:

```python
"""
Adapter layer to run Git tests against GitRepositoryService.
"""

import subprocess
from pathlib import Path
from typing import List, Optional

from server.services.git.git_repository_service import GitRepositoryService


class GitTestAdapter:
    """
    Adapter layer to run Git tests against GitRepositoryService.

    Translates Git CLI commands to service method calls and validates outputs.
    """

    def __init__(self, repo_path: Path, service: GitRepositoryService, repo_id: str):
        """
        Initialize adapter.

        Args:
            repo_path: Path to test repository
            service: GitRepositoryService instance
            repo_id: Repository ID in database
        """
        self.repo_path = Path(repo_path)
        self.service = service
        self.repo_id = repo_id

        if not self.repo_path.exists():
            raise ValueError(f"Repository path does not exist: {repo_path}")

        if not (self.repo_path / ".git").exists():
            raise ValueError(f"Not a Git repository: {repo_path}")

    def git_command(self, *args: str) -> str:
        """
        Run a git command via CLI for comparison.

        Args:
            *args: Git command arguments (e.g., "log", "--oneline")

        Returns:
            Command output as string
        """
        result = subprocess.run(
            ["git", *args],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode != 0:
            raise RuntimeError(f"Git command failed: git {' '.join(args)}\n{result.stderr}")

        return result.stdout.strip()

    def get_commit_sha(self, ref: str = "HEAD") -> str:
        """
        Get commit SHA for a ref.

        Args:
            ref: Git ref (e.g., "HEAD", "main", "abc123")

        Returns:
            Full commit SHA
        """
        return self.git_command("rev-parse", ref)

    def get_branch_name(self) -> str:
        """Get current branch name."""
        return self.git_command("branch", "--show-current")

    def list_branches(self) -> List[str]:
        """List all branches."""
        output = self.git_command("branch", "--format=%(refname:short)")
        return [line.strip() for line in output.split("\n") if line.strip()]

    def get_file_content_cli(self, file_path: str, ref: str = "HEAD") -> str:
        """Get file content via git CLI."""
        return self.git_command("show", f"{ref}:{file_path}")

    def get_file_content_service(self, file_path: str, commit_sha: str) -> str:
        """Get file content via GitRepositoryService."""
        content = self.service.get_file_content(
            repo_id=self.repo_id,
            file_path=file_path,
            commit_sha=commit_sha
        )
        return content

    def get_file_tree_cli(self, ref: str = "HEAD") -> List[str]:
        """Get file tree via git CLI."""
        output = self.git_command("ls-tree", "-r", "--name-only", ref)
        return [line.strip() for line in output.split("\n") if line.strip()]

    def get_file_tree_service(self, commit_sha: str) -> List[str]:
        """Get file tree via GitRepositoryService."""
        tree = self.service.get_file_tree(
            repo_id=self.repo_id,
            commit_sha=commit_sha
        )
        return [node["path"] for node in tree if node["type"] == "file"]

    def assert_file_content_matches(self, file_path: str, commit_sha: str):
        """Assert that service returns same content as git CLI."""
        cli_content = self.get_file_content_cli(file_path, commit_sha)
        service_content = self.get_file_content_service(file_path, commit_sha)

        assert service_content == cli_content, (
            f"File content mismatch for {file_path} at {commit_sha[:7]}\n"
            f"Expected (git):\n{cli_content}\n"
            f"Got (service):\n{service_content}"
        )

    def assert_file_tree_matches(self, commit_sha: str):
        """Assert that service returns same file tree as git CLI."""
        cli_tree = set(self.get_file_tree_cli(commit_sha))
        service_tree = set(self.get_file_tree_service(commit_sha))

        assert service_tree == cli_tree, (
            f"File tree mismatch at {commit_sha[:7]}\n"
            f"Missing in service: {cli_tree - service_tree}\n"
            f"Extra in service: {service_tree - cli_tree}"
        )
```

### Step 1.6: Write First Adapter Test

Create `/home/zebastjan/dev/archon/python/tests/git_integration/test_upstream_basic.py`:

```python
"""
Test GitRepositoryService against Git's upstream test fixtures (Phase 1: Basic operations).
"""

import pytest
from pathlib import Path

from server.services.git.git_repository_service import GitRepositoryService
from .upstream.git_test_adapter import GitTestAdapter


@pytest.fixture
def upstream_fixture_path():
    """Return path to upstream fixtures directory."""
    return Path(__file__).parent / "fixtures" / "upstream"


@pytest.fixture
def t0001_init_fixture(upstream_fixture_path):
    """Return path to t0001-init test fixture."""
    fixture_path = upstream_fixture_path / "t0001-init"
    if not fixture_path.exists():
        pytest.skip(f"Fixture not found: {fixture_path}. Run extract_fixtures.py first.")
    return fixture_path


def test_t0001_repository_initialization(
    t0001_init_fixture,
    git_repository_service: GitRepositoryService,
    test_project_id: str
):
    """
    Test that GitRepositoryService correctly handles initialized repositories.

    Validates against Git's t0001-init.sh test.
    """
    # Register repository
    repo = git_repository_service.initialize_repository(
        project_id=test_project_id,
        repository_path=str(t0001_init_fixture),
        branch="main"
    )

    # Create adapter
    adapter = GitTestAdapter(
        repo_path=t0001_init_fixture,
        service=git_repository_service,
        repo_id=repo["id"]
    )

    # Test 1: Repository has .git directory
    assert (t0001_init_fixture / ".git").exists()

    # Test 2: Can get current branch
    branch = adapter.get_branch_name()
    assert branch == "main" or branch == "master"

    # Test 3: Repository is registered in database
    assert repo["repository_path"] == str(t0001_init_fixture)
    assert repo["current_branch"] in ["main", "master"]


def test_t0001_commit_history(
    t0001_init_fixture,
    git_repository_service: GitRepositoryService,
    test_project_id: str
):
    """
    Test that GitRepositoryService correctly retrieves commit history.

    Validates against Git's t0001-init.sh test.
    """
    # Register repository
    repo = git_repository_service.initialize_repository(
        project_id=test_project_id,
        repository_path=str(t0001_init_fixture),
        branch="main"
    )

    # Get commits via service
    commits = git_repository_service.get_commit_history(
        repo_id=repo["id"],
        branch=repo["current_branch"]
    )

    # Should have at least one commit (initial commit)
    assert len(commits) > 0

    # First commit should have expected fields
    first_commit = commits[0]
    assert "sha" in first_commit
    assert "message" in first_commit
    assert "author_name" in first_commit
    assert "commit_date" in first_commit


def test_upstream_file_content_matches_cli(
    t0001_init_fixture,
    git_repository_service: GitRepositoryService,
    test_project_id: str
):
    """
    Test that file content retrieved via service matches git CLI output.
    """
    # Register repository
    repo = git_repository_service.initialize_repository(
        project_id=test_project_id,
        repository_path=str(t0001_init_fixture),
        branch="main"
    )

    # Create adapter
    adapter = GitTestAdapter(
        repo_path=t0001_init_fixture,
        service=git_repository_service,
        repo_id=repo["id"]
    )

    # Get HEAD commit
    head_sha = adapter.get_commit_sha("HEAD")

    # Get file tree
    files = adapter.get_file_tree_cli(head_sha)

    if not files:
        pytest.skip("No files in repository")

    # Test first file's content matches
    first_file = files[0]
    adapter.assert_file_content_matches(first_file, head_sha)


def test_upstream_file_tree_matches_cli(
    t0001_init_fixture,
    git_repository_service: GitRepositoryService,
    test_project_id: str
):
    """
    Test that file tree retrieved via service matches git CLI output.
    """
    # Register repository
    repo = git_repository_service.initialize_repository(
        project_id=test_project_id,
        repository_path=str(t0001_init_fixture),
        branch="main"
    )

    # Create adapter
    adapter = GitTestAdapter(
        repo_path=t0001_init_fixture,
        service=git_repository_service,
        repo_id=repo["id"]
    )

    # Get HEAD commit
    head_sha = adapter.get_commit_sha("HEAD")

    # Assert file trees match
    adapter.assert_file_tree_matches(head_sha)
```

### Step 1.7: Run First Tests

```bash
cd /home/zebastjan/dev/archon
pytest python/tests/git_integration/test_upstream_basic.py -v
```

**Expected output**:
```
test_upstream_basic.py::test_t0001_repository_initialization PASSED
test_upstream_basic.py::test_t0001_commit_history PASSED
test_upstream_basic.py::test_upstream_file_content_matches_cli PASSED
test_upstream_basic.py::test_upstream_file_tree_matches_cli PASSED

======================== 4 passed in 2.35s ========================
```

**Phase 1 Complete!** ✅ You now have:
- Git test infrastructure set up
- Fixture extraction script working
- Adapter layer translating Git CLI ↔ Service API
- 4+ passing tests validating basic operations

---

## Phase 2: Core File Operations (4 days)

### Step 2.1: Extract File Operation Fixtures

Extract fixtures from t1*.sh and t2*.sh tests:

```bash
cd /home/zebastjan/dev/archon/python/tests/git_integration/upstream
python extract_fixtures.py \
    t1000-read-tree \
    t1100-commit-tree \
    t1200-checkout-basic \
    t1300-repo-path \
    t2000-checkout \
    t2003-checkout-cache \
    t2004-checkout-cache-tree
```

### Step 2.2: Implement File Operation Tests

Create `/home/zebastjan/dev/archon/python/tests/git_integration/test_upstream_files.py`:

```python
"""
Test GitRepositoryService against Git's upstream test fixtures (Phase 2: File operations).
"""

import pytest
from pathlib import Path

from server.services.git.git_repository_service import GitRepositoryService
from .upstream.git_test_adapter import GitTestAdapter


# Test file tree operations (t1000-read-tree)
def test_t1000_read_tree(upstream_fixture, git_repository_service, test_project_id):
    """Test reading tree objects."""
    # Implementation similar to Phase 1 tests
    pass


# Test commit tree operations (t1100-commit-tree)
def test_t1100_commit_tree(upstream_fixture, git_repository_service, test_project_id):
    """Test commit tree structure."""
    pass


# Test checkout operations (t1200, t2000, etc.)
def test_checkout_file_content_preservation(upstream_fixture, git_repository_service, test_project_id):
    """Test that file content is preserved during branch checkout."""
    pass


# Add 10-15 more file operation tests following same pattern
```

### Step 2.3: Run Phase 2 Tests

```bash
pytest python/tests/git_integration/test_upstream_files.py -v
```

**Goal**: 20+ passing tests covering file operations.

---

## Phase 3: Advanced Scenarios (5 days)

### Step 3.1: Extract Merge & Branch Fixtures

```bash
cd /home/zebastjan/dev/archon/python/tests/git_integration/upstream
python extract_fixtures.py \
    t3000-ls-files-others \
    t3100-ls-tree-restrict \
    t3200-branch \
    t3400-rebase \
    t3600-rm \
    t3701-add-interactive
```

### Step 3.2: Implement Merge Tests

Create `/home/zebastjan/dev/archon/python/tests/git_integration/test_upstream_merges.py`:

```python
"""
Test GitRepositoryService against Git's upstream test fixtures (Phase 3: Merging).
"""

def test_t3400_merge_commit_parents(upstream_fixture, git_repository_service, test_project_id):
    """
    Test that merge commits have multiple parents.
    """
    # Find merge commit
    # Verify parent_shas has 2+ entries
    # Verify file tree at merge point
    pass


def test_t3600_file_deletion_across_branches(upstream_fixture, git_repository_service, test_project_id):
    """
    Test that file deletions are handled correctly.

    Validates against Git's t3600-rm.sh test.
    """
    pass


# Add 15-20 more merge/branch tests
```

### Step 3.3: Run Phase 3 Tests

```bash
pytest python/tests/git_integration/test_upstream_merges.py -v
```

**Goal**: 30+ passing tests covering merge scenarios.

---

## Phase 4: Edge Cases & CI/CD (3 days)

### Step 4.1: Extract Edge Case Fixtures

```bash
cd /home/zebastjan/dev/archon/python/tests/git_integration/upstream
python extract_fixtures.py \
    t3900-i18n-commit \
    t3901-i18n-patch \
    t9600-cvsimport
```

### Step 4.2: Implement Edge Case Tests

Create `/home/zebastjan/dev/archon/python/tests/git_integration/test_upstream_edge.py`:

```python
"""
Test GitRepositoryService against Git's upstream test fixtures (Phase 4: Edge cases).
"""

def test_t3900_unicode_commit_messages(upstream_fixture, git_repository_service, test_project_id):
    """Test handling of unicode in commit messages."""
    pass


def test_t3901_unicode_file_content(upstream_fixture, git_repository_service, test_project_id):
    """Test handling of unicode in file content."""
    pass


def test_binary_file_detection(upstream_fixture, git_repository_service, test_project_id):
    """Test that binary files are detected correctly."""
    pass


# Add 10-15 edge case tests
```

### Step 4.3: CI/CD Integration

Create `.github/workflows/git-upstream-tests.yml`:

```yaml
name: Git Upstream Tests

on:
  push:
    branches: [main, git-integration]
  pull_request:
    branches: [main]
  schedule:
    # Run nightly at 2 AM UTC
    - cron: '0 2 * * *'

jobs:
  upstream-tests:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install uv
          uv pip install -r requirements.txt

      - name: Start Supabase
        run: docker-compose up -d supabase

      - name: Clone Git test suite
        run: |
          cd python/tests/git_integration/upstream
          if [ ! -d "git" ]; then
            git clone --depth 1 https://github.com/git/git.git
          fi

      - name: Extract test fixtures
        run: |
          cd python/tests/git_integration/upstream
          python extract_fixtures.py $(cat fixture_list.txt)

      - name: Run upstream tests
        run: |
          pytest python/tests/git_integration/test_upstream_*.py \
            -v \
            --tb=short \
            --junit-xml=test-results/upstream-tests.xml

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: upstream-test-results
          path: test-results/
```

Create `python/tests/git_integration/upstream/fixture_list.txt`:

```
t0001-init
t0002-gitfile
t1000-read-tree
t1100-commit-tree
t1200-checkout-basic
t2000-checkout
t3000-ls-files-others
t3200-branch
t3400-rebase
t3600-rm
t3900-i18n-commit
```

### Step 4.4: Document Known Limitations

Create `/home/zebastjan/dev/archon/docs/git-integration-limitations.md`:

```markdown
# Git Integration Known Limitations

## Supported Features

- ✅ Repository initialization and registration
- ✅ Commit history retrieval
- ✅ Branch switching
- ✅ File tree navigation
- ✅ File content retrieval
- ✅ Merge commit handling (multi-parent)
- ✅ Binary file detection
- ✅ Unicode filenames and content

## Unsupported Features

- ❌ Git hooks (pre-commit, post-commit, etc.)
- ❌ Git submodules (explicitly rejected)
- ❌ Remote operations (push, pull, fetch)
- ❌ Staging area (we read from commits directly)
- ❌ Interactive rebase
- ❌ Git LFS (Large File Storage)

## Known Failing Tests

| Test | Reason | Priority |
|------|--------|----------|
| t5000-clone.sh | No remote ops | Low |
| t7000-submodule.sh | Submodules rejected | Low |
| t7800-hook.sh | No hook support | Low |

## Performance Limitations

- Large repositories (100k+ commits): May require pagination
- Large files (100MB+): Not optimized for streaming
- Deep nesting (20+ levels): Tested up to 10 levels

## Future Enhancements

- Incremental re-indexing via blob SHA comparison
- Streaming support for large files
- IPFS integration for artifact storage
```

---

## Verification & Success Criteria

Run the full test suite and verify results:

```bash
# Run all upstream tests
pytest python/tests/git_integration/test_upstream_*.py -v --tb=short

# Count results
pytest python/tests/git_integration/test_upstream_*.py --collect-only | grep "test session starts"
```

**Success criteria**:
- [ ] 50+ Git tests running
- [ ] 80%+ pass rate
- [ ] All failures documented in limitations.md
- [ ] CI/CD workflow passing
- [ ] Test results uploaded to GitHub Actions

---

## Maintenance

### Weekly: Check for Git Updates

```bash
cd /home/zebastjan/dev/archon/python/tests/git_integration/upstream/git
git pull origin master
```

If Git has new releases, re-run fixture extraction and tests.

### Monthly: Review Test Coverage

```bash
# Generate coverage report
pytest python/tests/git_integration/ --cov=server.services.git --cov-report=html

# Open report
firefox htmlcov/index.html
```

### On Service Changes: Validate with Git Tests

When modifying `GitRepositoryService`, always run upstream tests:

```bash
pytest python/tests/git_integration/test_upstream_*.py -v
```

---

## Troubleshooting

### Issue: Fixture extraction fails

**Symptom**: `extract_fixtures.py` reports "No trash directory found"

**Solution**: Some tests require setup. Check test script for dependencies:

```bash
cat /home/zebastjan/dev/archon/python/tests/git_integration/upstream/git/t/tXXXX-name.sh | head -20
```

### Issue: Adapter test fails with "output mismatch"

**Symptom**: CLI output doesn't match service output

**Solution**: Check output format differences. Example:

```python
# CLI might return: "commit abc123\nAuthor: ...\n"
# Service returns: {"sha": "abc123", "author": "..."}

# Normalize before comparison
```

### Issue: Tests are slow

**Symptom**: Test suite takes 10+ minutes

**Solution**: Use pytest markers to separate fast/slow tests:

```python
@pytest.mark.slow
def test_large_repository():
    pass
```

Run fast tests only:
```bash
pytest -m "not slow"
```

---

## Next Steps

After completing Phase 4:

1. **Review results**: Analyze pass/fail rates and patterns
2. **Fix bugs**: Address any failures in `GitRepositoryService`
3. **Document limitations**: Update limitations.md with findings
4. **Integrate with Phase 2**: Ensure embeddings/search work with Git fixtures
5. **Expand coverage**: Add more tests for specific edge cases discovered

---

## Resources

- Git Test Suite Documentation: https://github.com/git/git/blob/master/t/README
- Sharness Framework: https://github.com/chriscool/sharness
- GitRepositoryService: `/python/src/server/services/git/git_repository_service.py`
- ADR-003: Git Integration Architecture
- ADR-004: Git Test Suite Integration Decision
