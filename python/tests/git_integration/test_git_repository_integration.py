from __future__ import annotations

import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from src.server.services.git.git_repository_service import GitRepositoryService


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
        raise RuntimeError(
            f"git {' '.join(args)} failed: {result.stderr.strip() or result.stdout.strip()}"
        )
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

    def insert_rows(
        self, payload: dict[str, Any] | list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
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
