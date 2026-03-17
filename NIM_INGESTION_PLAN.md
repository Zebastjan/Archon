# Nim Ingestion Plan (P0)

**Status:** Draft  
**Priority:** P0 - Strategic Core  
**Scope:** Omnibus-first, then Syllablaze  

---

## 1. Strategic Context

### Why Nim/Omnibus is P0

| Priority | Item | Rationale |
|----------|------|-----------|
| P0 | Nim ingestion (Omnibus) | Omnibus and Syllablaze are strategic cores. Archon and Syllablaze are intended to become Omnibus-native Nim apps. |
| P1 | Audit sophistication on Nim | Only after Nim entities are indexed. |
| P2 | New audit rules (non-Nim) | Deprioritized until Nim ingestion is confirmed working. |

**Decision:** All agent work on Archon/Omnibus now follows this order:
1. Infra and MCP sanity (locked - no changes unless broken)
2. Nim/Omnibus ingestion (current focus)
3. Only then, deeper audits and rules

---

## 2. Infra Lock

The following are now **canonical and frozen** unless explicitly broken:

- `make health-check` flow
- MCP server behavior
- Repo lifecycle states (not_known → created → indexing → ready)
- `POST /api/code_repos/create-and-index` endpoint
- `archon code-repos add` CLI

**Rule:** Do not add new ways to create/index repos. Use the existing "create and index" API/CLI only.

---

## 3. Nim Ingestion Design

### 3.1 Hook Location

The language-specific indexing plugs in at:

```python
# src/server/services/languages/__init__.py
# get_language_for_file(file_path: str) -> LanguageSupport | None
```

Current support: Python, TypeScript, JavaScript.

**Add:** `nim_support.py` following the same pattern.

### 3.2 Nim Entities to Index

| Entity Type | Examples | Priority |
|-------------|----------|----------|
| Files | `.nim`, `.nims` files | Must have |
| Procs | `proc name(args): RetType` | Must have |
| Types | `type Foo = object`, `enum`, `distinct` | Must have |
| Modules | `import`, `export` statements | Should have |
| Services | HTTP handlers, RPC procs | Nice to have |
| Schemas | DB models, DTOs | Nice to have |

### 3.3 Parser/Tooling Options

| Option | Pros | Cons |
|--------|------|------|
| Tree-sitter (nim grammar) | Fast, incremental, fits existing pipeline | Grammar may need validation |
| Nim compiler JSON output | Authoritative, complete | Slower, requires compiler |
| Custom Omnibus helpers | Domain-aware | Tight coupling, maintenance |

**Decision:** Start with Tree-sitter nim grammar. If incomplete, fallback to Nim compiler JSON for edge cases.

---

## 4. Implementation Plan

### Step 1: Nim Language Support Module

Create `src/server/services/languages/nim_support.py`:

```python
class NimLanguageSupport(LanguageSupport):
    language_id = "nim"
    file_extensions = [".nim", "nims"]
    
    def parse(self, content: str) -> Tree:
        # Use tree-sitter-nim
        pass
    
    def extract_entities(self, tree: Tree, file_path: str) -> list[CodeEntity]:
        # Extract: procs, types, modules
        pass
```

### Step 2: Register Nim Support

Update `src/server/services/languages/__init__.py`:

```python
_language_registry = {
    "python": PythonLanguageSupport,
    "typescript": TypeScriptLanguageSupport,
    "javascript": JavaScriptLanguageSupport,
    "nim": NimLanguageSupport,  # ADD
}
```

### Step 3: Test with Omnibus

```bash
# Reindex Omnibus
archon code-repos add --name Omnibus --root-path /home/zebastjan/dev/Omnibus --wait

# Verify
curl http://localhost:8181/api/code_repos
# Expected: Omnibus status=ready, entities_count > 0
```

---

## 5. Success Criteria

| Check | Expected |
|-------|----------|
| `reindex Omnibus` | Status transitions to `ready` |
| Entity count | Non-zero (at minimum: files + procs) |
| No errors in logs | `tree_sitter` import success for Nim |
| MCP `audit_get_context` | Returns grouped findings with entity references |

---

## 6. Post-Ingestion: Resume Audits

Once Nim ingestion is confirmed:

1. Use `audit_get_context(repo_name="Omnibus")` for batched triage
2. Group findings by Nim module/service
3. Iterate on Nim-specific rules:
   - varint discards
   - Missing doc comments
   - DB rule violations

---

## 7. Agent Alignment

All Archon/Omnibus recipes and prompts must reflect:

```
Priority Order:
1. Infra and MCP sanity (locked)
2. Nim/Omnibus ingestion (current)
3. Audit sophistication (future)
```

**Forbidden until Nim ingestion works:**
- Adding new non-Nim audit rules
- Schema changes unrelated to Nim entities
- Alternative repo creation methods

---

## Appendix: Current State

- [x] Health checks: Working
- [x] MCP server: Working
- [x] Repo lifecycle: Working
- [x] Create+index API: Working
- [ ] Nim ingestion: Not implemented (shows 0 entities for Omnibus)
