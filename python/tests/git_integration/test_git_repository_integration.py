from __future__ import annotations

import json
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from src.server.services.git.git_repository_service import GitRepositoryService
from tests.git_integration.fixtures.generator import generate_fixture, get_fixture_path


def _run_git(repo_path: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Execute a git command in the target repository."""
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo_path),
        check=False,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip() or result.stdout.strip()}")
    return result


def _init_git_repository(base_path: Path) -> Path:
    """Initialise a git repository with a first commit on `main`."""
    repo_path = base_path
    repo_path.mkdir(parents=True, exist_ok=True)

    # Newer git versions support `git init -b`; fall back if not available.
    init_result = _run_git(repo_path, "init", "-b", "main", check=False)
    if init_result.returncode != 0:
        _run_git(repo_path, "init")
        _run_git(repo_path, "checkout", "-b", "main")

    _run_git(repo_path, "config", "user.email", "archon-tests@example.com")
    _run_git(repo_path, "config", "user.name", "Archon Test")

    (repo_path / "README.md").write_text("# Test Repository\n\nInitial content.\n", encoding="utf-8")
    _run_git(repo_path, "add", "README.md")
    _run_git(repo_path, "commit", "-m", "Initial commit")

    return repo_path


@dataclass
class FakeQueryResponse:
    data: list[dict[str, Any]]

    def __init__(self, data: list[dict[str, Any]]) -> None:
        self.data = data

    def execute(self) -> FakeQueryResponse:
        return self


class FakeSupabaseQuery:
    def __init__(
        self,
        table: FakeSupabaseTable,
        action: str,
        payload: Any = None,
        on_conflict: str | None = None,
    ) -> None:
        self.table = table
        self.action = action
        self.payload = payload
        self.on_conflict = on_conflict
        self.filters: list[tuple[str, Any]] = []

    def eq(self, field: str, value: Any) -> FakeSupabaseQuery:
        self.filters.append((field, value))
        return self

    def execute(self) -> FakeQueryResponse:
        if self.action == "select":
            rows = self.table.filter_rows(self.filters)
            return FakeQueryResponse(rows)
        if self.action == "insert":
            rows = self.table.insert_rows(self.payload)
            return FakeQueryResponse(rows)
        if self.action == "upsert":
            rows = self.table.upsert_rows(self.payload, self.on_conflict)
            return FakeQueryResponse(rows)
        if self.action == "update":
            rows = self.table.update_rows(self.filters, self.payload)
            return FakeQueryResponse(rows)
        raise ValueError(f"Unsupported action: {self.action}")


class FakeSupabaseTable:
    def __init__(self, name: str) -> None:
        self.name = name
        self.rows: list[dict[str, Any]] = []

    def select(self, _columns: str = "*") -> FakeSupabaseQuery:
        return FakeSupabaseQuery(self, "select")

    def insert(self, payload: dict[str, Any] | list[dict[str, Any]]) -> FakeSupabaseQuery:
        return FakeSupabaseQuery(self, "insert", payload)

    def upsert(
        self,
        payload: list[dict[str, Any]] | dict[str, Any],
        on_conflict: str | None = None,
    ) -> FakeSupabaseQuery:
        return FakeSupabaseQuery(self, "upsert", payload, on_conflict)

    def update(self, payload: dict[str, Any]) -> FakeSupabaseQuery:
        return FakeSupabaseQuery(self, "update", payload)

    # -- helpers -----------------------------------------------------------------

    def _ensure_list(self, payload: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
        return payload if isinstance(payload, list) else [payload]

    def filter_rows(self, filters: list[tuple[str, Any]]) -> list[dict[str, Any]]:
        if not filters:
            return list(self.rows)
        results = []
        for row in self.rows:
            if all(row.get(field) == value for field, value in filters):
                results.append(dict(row))
        return results

    def insert_rows(self, payload: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows = []
        for record in self._ensure_list(payload):
            row = dict(record)
            row.setdefault("id", str(uuid.uuid4()))
            self.rows.append(row)
            rows.append(dict(row))
        return rows

    def upsert_rows(
        self,
        payload: dict[str, Any] | list[dict[str, Any]],
        on_conflict: str | None,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        conflict_fields = [field.strip() for field in on_conflict.split(",")] if on_conflict else []
        for record in self._ensure_list(payload):
            row = dict(record)
            if conflict_fields:
                existing = None
                for stored in self.rows:
                    if all(stored.get(field) == row.get(field) for field in conflict_fields):
                        existing = stored
                        break
                if existing is not None:
                    # Special handling for branches array - merge instead of replace
                    if "branches" in row and "branches" in existing:
                        merged_branches = list(set(existing["branches"] + row["branches"]))
                        existing["branches"] = merged_branches
                        # Update other fields normally
                        for field_key, value in row.items():
                            if field_key != "branches":
                                existing[field_key] = value
                    else:
                        existing.update(row)
                    rows.append(dict(existing))
                    continue
            row.setdefault("id", str(uuid.uuid4()))
            self.rows.append(row)
            rows.append(dict(row))
        return rows

    def update_rows(
        self,
        filters: list[tuple[str, Any]],
        payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        updated: list[dict[str, Any]] = []
        for row in self.rows:
            if all(row.get(field) == value for field, value in filters):
                row.update(payload)
                updated.append(dict(row))
        return updated


class FakeSupabaseClient:
    def __init__(self) -> None:
        self.tables: dict[str, FakeSupabaseTable] = {}

    def table(self, name: str) -> FakeSupabaseTable:
        if name not in self.tables:
            self.tables[name] = FakeSupabaseTable(name)
        return self.tables[name]

    def rpc(self, function_name: str, params: dict[str, Any]) -> FakeQueryResponse:
        """Mock RPC function - returns success for branch merge upserts."""
        if function_name == "upsert_git_commit_with_branch_merge":
            commits_table = self.table("archon_git_commits")
            existing = None
            p_branches = params.get("p_branches", [])
            for row in commits_table.rows:
                if row.get("repo_id") == params.get("p_repo_id") and row.get("commit_sha") == params.get(
                    "p_commit_sha"
                ):
                    existing = row
                    break
            if existing:
                # Merge branches
                existing_branches = existing.get("branches", [])
                if isinstance(existing_branches, list):
                    existing["branches"] = list(set(existing_branches + p_branches))
            else:
                commits_table.rows.append(
                    {
                        "id": str(uuid.uuid4()),
                        "repo_id": params.get("p_repo_id"),
                        "commit_sha": params.get("p_commit_sha"),
                        "author_name": params.get("p_author_name"),
                        "author_email": params.get("p_author_email"),
                        "commit_date": params.get("p_commit_date"),
                        "message": params.get("p_message"),
                        "branches": p_branches,
                    }
                )
            return FakeQueryResponse([{"success": True}])
        return FakeQueryResponse([{"success": False}])


@pytest.fixture
def supabase_client() -> FakeSupabaseClient:
    return FakeSupabaseClient()


@pytest.fixture
def git_service(supabase_client: FakeSupabaseClient) -> GitRepositoryService:
    return GitRepositoryService(supabase_client=supabase_client)


def test_register_repository_records_metadata(
    tmp_path: Path, git_service: GitRepositoryService, supabase_client: FakeSupabaseClient
) -> None:
    repo_path = _init_git_repository(tmp_path / "basic-repo")

    success, result = git_service.register_repository(str(repo_path), source_id="source-basic")

    assert success is True
    assert result["default_branch"] == "main"

    repo_rows = supabase_client.table("archon_git_repositories").rows
    assert len(repo_rows) == 1
    stored_repo = repo_rows[0]
    assert stored_repo["repo_url"] == str(repo_path)
    assert stored_repo["current_head_sha"] == result["current_head_sha"]


def test_sync_commits_persists_history(
    tmp_path: Path, git_service: GitRepositoryService, supabase_client: FakeSupabaseClient
) -> None:
    repo_path = _init_git_repository(tmp_path / "history-repo")

    # Create an additional commit on main.
    (repo_path / "README.md").write_text("# Test Repository\n\nSecond commit.\n", encoding="utf-8")
    _run_git(repo_path, "add", "README.md")
    _run_git(repo_path, "commit", "-m", "Second commit")

    success, result = git_service.register_repository(str(repo_path), source_id="source-history")
    assert success is True
    repo_id = result["repo_id"]

    sync_success, sync_result = git_service.sync_commits(repo_id, "main", max_commits=10)

    assert sync_success is True
    assert sync_result["commit_count"] == 2

    commit_rows = supabase_client.table("archon_git_commits").rows
    assert len(commit_rows) == 2
    assert all(row["repo_id"] == repo_id for row in commit_rows)
    assert all("main" in row["branches"] for row in commit_rows)


def test_get_file_tree_includes_binary_flags(
    tmp_path: Path, git_service: GitRepositoryService, supabase_client: FakeSupabaseClient
) -> None:
    repo_path = _init_git_repository(tmp_path / "file-tree-repo")

    src_dir = repo_path / "src"
    src_dir.mkdir()
    (src_dir / "app.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (repo_path / "notes.txt").write_text("Some plain text", encoding="utf-8")

    binary_path = repo_path / "assets"
    binary_path.mkdir()
    (binary_path / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\x00")

    _run_git(repo_path, "add", ".")
    _run_git(repo_path, "commit", "-m", "Add text and binary files")

    success, result = git_service.register_repository(str(repo_path), source_id="source-files")
    assert success is True
    repo_id = result["repo_id"]

    head_sha = _run_git(repo_path, "rev-parse", "HEAD").stdout.strip()

    tree_success, tree_result = git_service.get_file_tree(repo_id, head_sha)

    assert tree_success is True
    files = tree_result["files"]
    assert {file["file_path"] for file in files} >= {"README.md", "src/app.py", "notes.txt", "assets/logo.png"}

    binary_entry = next(file for file in files if file["file_path"] == "assets/logo.png")
    assert binary_entry["is_binary"] is True

    text_entry = next(file for file in files if file["file_path"] == "src/app.py")
    assert text_entry["is_binary"] is False
    assert text_entry["language"] == "Python"


def test_sync_commits_merges_branches_on_upsert(
    tmp_path: Path, git_service: GitRepositoryService, supabase_client: FakeSupabaseClient
) -> None:
    """Test that syncing from multiple branches merges the branches array."""
    repo_path = _init_git_repository(tmp_path / "multi-branch-repo")

    # Create a second commit on main
    (repo_path / "feature.txt").write_text("Feature implementation\n", encoding="utf-8")
    _run_git(repo_path, "add", "feature.txt")
    _run_git(repo_path, "commit", "-m", "Add feature")

    # Register repository
    success, result = git_service.register_repository(str(repo_path), source_id="source-multi")
    assert success is True
    repo_id = result["repo_id"]

    # Sync from main branch
    sync_success, sync_result = git_service.sync_commits(repo_id, "main", max_commits=10)
    assert sync_success is True
    assert sync_result["commit_count"] >= 2

    # Get the first commit SHA (shared between main and develop)
    commits_table = supabase_client.table("archon_git_commits")
    initial_commits = [row for row in commits_table.rows if row.get("repo_id") == repo_id]
    assert len(initial_commits) >= 2
    # Get the oldest commit (should be shared across branches)
    test_commit = min(initial_commits, key=lambda c: c["commit_date"])
    test_commit_sha = test_commit["commit_sha"]
    assert test_commit["branches"] == ["main"]

    # Create develop branch from main (shares commits)
    _run_git(repo_path, "checkout", "-b", "develop")

    # Sync from develop branch
    sync_success_dev, sync_result_dev = git_service.sync_commits(repo_id, "develop", max_commits=10)
    assert sync_success_dev is True

    # Verify shared commit now has both branches
    commits_after = [row for row in commits_table.rows if row.get("commit_sha") == test_commit_sha]
    assert len(commits_after) == 1
    assert set(commits_after[0]["branches"]) == {"main", "develop"}

    # Verify querying for main still returns commits
    main_commits = [row for row in commits_table.rows if "main" in row.get("branches", [])]
    assert len(main_commits) >= 2

    # Verify querying for develop returns commits
    develop_commits = [row for row in commits_table.rows if "develop" in row.get("branches", [])]
    assert len(develop_commits) >= 2


@pytest.fixture
def fixture_repo_simple_commits(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    """Load the simple-commits fixture and return repo path and expected data."""
    fixture_path = get_fixture_path("simple-commits")
    repo_path = generate_fixture(fixture_path, tmp_path / "fixtures")

    expected_path = fixture_path / "EXPECTED.json"
    with open(expected_path) as f:
        expected = json.load(f)

    return repo_path, expected


@pytest.fixture
def fixture_repo_multi_branch(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    """Load the multi-branch fixture and return repo path and expected data."""
    fixture_path = get_fixture_path("multi-branch")
    repo_path = generate_fixture(fixture_path, tmp_path / "fixtures")

    expected_path = fixture_path / "EXPECTED.json"
    with open(expected_path) as f:
        expected = json.load(f)

    return repo_path, expected


@pytest.fixture
def fixture_repo_file_structure(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    """Load the file-structure fixture and return repo path and expected data."""
    fixture_path = get_fixture_path("file-structure")
    repo_path = generate_fixture(fixture_path, tmp_path / "fixtures")

    expected_path = fixture_path / "EXPECTED.json"
    with open(expected_path) as f:
        expected = json.load(f)

    return repo_path, expected


def test_fixture_simple_commits_matches_expected(
    fixture_repo_simple_commits: tuple[Path, dict[str, Any]],
    git_service: GitRepositoryService,
    supabase_client: FakeSupabaseClient,
) -> None:
    """Test that simple-commits fixture matches expected data."""
    repo_path, expected = fixture_repo_simple_commits

    # Register repository
    success, result = git_service.register_repository(str(repo_path), source_id="source-simple")
    assert success is True
    assert result["default_branch"] == expected["default_branch"]

    # Sync commits
    repo_id = result["repo_id"]
    sync_success, sync_result = git_service.sync_commits(repo_id, "main", max_commits=10)
    assert sync_success is True
    assert sync_result["commit_count"] == len(expected["commits"])

    # Verify commit count matches expected
    commit_rows = supabase_client.table("archon_git_commits").rows
    assert len(commit_rows) == len(expected["commits"])


def test_fixture_multi_branch_has_correct_branches(
    fixture_repo_multi_branch: tuple[Path, dict[str, Any]],
    git_service: GitRepositoryService,
    supabase_client: FakeSupabaseClient,
) -> None:
    """Test that multi-branch fixture correctly captures branches."""
    repo_path, expected = fixture_repo_multi_branch

    # Register and sync main branch
    success, result = git_service.register_repository(str(repo_path), source_id="source-multi")
    assert success is True

    repo_id = result["repo_id"]
    sync_success, _ = git_service.sync_commits(repo_id, "main", max_commits=10)
    assert sync_success is True

    # Verify all expected branches exist in the repo
    branch_result = subprocess.run(
        ["git", "branch", "--format=%(refname:short)"],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
    )
    actual_branches = [b.strip() for b in branch_result.stdout.strip().split("\n") if b.strip()]
    assert set(actual_branches) == set(expected["branches"])


def test_fixture_file_structure_binary_detection(
    fixture_repo_file_structure: tuple[Path, dict[str, Any]],
    git_service: GitRepositoryService,
    supabase_client: FakeSupabaseClient,
) -> None:
    """Test that file-structure fixture correctly detects binary files."""
    repo_path, expected = fixture_repo_file_structure

    # Register and sync
    success, result = git_service.register_repository(str(repo_path), source_id="source-files")
    assert success is True

    repo_id = result["repo_id"]
    head_sha = result["current_head_sha"]

    # Get file tree
    tree_success, tree_result = git_service.get_file_tree(repo_id, head_sha)
    assert tree_success is True

    files = tree_result["files"]
    expected_files = {f["path"]: f for f in expected["files"]}

    # Verify binary detection
    for file in files:
        expected_file = expected_files.get(file["file_path"])
        if expected_file:
            assert file["is_binary"] == expected_file["is_binary"], (
                f"Binary mismatch for {file['file_path']}: "
                f"got {file['is_binary']}, expected {expected_file['is_binary']}"
            )

    # Verify binary files are correctly identified
    binary_files = [f for f in files if f["is_binary"]]
    expected_binary = [f for f in expected["files"] if f["is_binary"]]
    assert len(binary_files) == len(expected_binary)

    # Check specific binary files
    binary_paths = {f["file_path"] for f in binary_files}
    expected_binary_paths = {f["path"] for f in expected_binary}
    assert binary_paths == expected_binary_paths
