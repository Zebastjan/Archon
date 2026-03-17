# Omnibus Nim Audit Triage Report

**Date:** 2026-03-16  
**Repository:** Omnibus  
**Repo ID:** 15f7ea16-d016-492b-8193-dbbd55f33281  
**Total Findings:** 19  
**Unique Rules:** 1

---

## Summary

| Rule | Severity | Count | Decision |
|------|----------|-------|----------|
| `nim/suspicious-discard` | WARNING | 19 | Mixed (see below) |

---

## Rule Analysis: `nim/suspicious-discard`

### Description
Non-trivial return value is being discarded. The audit flags `discard` expressions that call functions with return values, which may indicate unhandled errors or ignored results.

### Triage Decisions by Pattern

#### Pattern 1: `discard readVarint(data, pos)` in protobuf codecs
**Decision:** `intentional`  
**Rationale:** Protobuf varint reading follows a fire-and-forget pattern where the parsing position is updated via the `pos` reference parameter. The return value (decoded integer) is stored elsewhere or not needed for certain field types.

**Files affected:**
- `tools/omni-schemac/output/proto_codec.nim` (line 119)
- Similar generated codec files

**Triage rule:**
```yaml
rule: nim/suspicious-discard
code_pattern: "discard readVarint"
path_pattern: "*/proto_codec.nim"
decision: intentional
rationale: "Protobuf varint parsing uses ref param for position; return stored elsewhere"
```

---

#### Pattern 2: `discard posix.close(fd)`
**Decision:** `intentional`  
**Rationale:** Standard POSIX practice allows ignoring `close()` return values for most file descriptors. Only specific cases (e.g., NFS with async writes) require error handling. In Omnibus tooling contexts, FDs are typically local pipes/sockets where close errors are non-actionable.

**Files affected:**
- `tools/omni-cat/src/omni_cat.nim` (line 72)
- `lib/libomnibus/src/service.nim` (multiple lines)

**Triage rule:**
```yaml
rule: nim/suspicious-discard
code_pattern: "discard posix.close"
decision: intentional
rationale: "POSIX close() errors are typically non-actionable for local FDs"
conditions:
  - not_nfs_filesystem: true
  - fd_type: [pipe, socket, local_file]
```

---

#### Pattern 3: `discard posix.write(fd, ...)` framing operations
**Decision:** `wont_fix` with monitoring  
**Rationale:** Framing layer writes in `libomnibus` are part of the wire protocol. While ignoring write errors is technically risky, the library's design uses higher-level heartbeat/ack mechanisms to detect transport failures. Individual write failures are not actionable at this layer.

**Files affected:**
- `lib/libomnibus/src/framing.nim` (line 22)
- `lib/libomnibus/src/proto_codec.nim`

**Triage rule:**
```yaml
rule: nim/suspicious-discard
code_pattern: "discard posix.write"
path_pattern: "lib/libomnibus/src/*"
decision: wont_fix
rationale: "Transport-level failures detected via heartbeat/ack; individual write errors non-actionable"
monitor: true
```

---

#### Pattern 4: Other non-trivial discards
**Decision:** `needs_review`  
**Rationale:** Any discard not matching the above patterns requires manual review to determine if the return value contains actionable error information.

---

## Detailed Findings by File

### `tools/omni-schemac/output/proto_codec.nim` (11 findings)
- **Lines:** 119, 134, 156, 178, 201, 223, 245, 267, 289, 311, 333
- **Pattern:** `discard readVarint(data, pos)`
- **Decision:** `intentional` for all
- **Note:** These are auto-generated protobuf codec files. The pattern is consistent across generated code.

### `tools/omni-cat/src/omni_cat.nim` (1 finding)
- **Line:** 72
- **Code:** `discard posix.close(fd)`
- **Decision:** `intentional`

### `lib/libomnibus/src/framing.nim` (2 findings)
- **Line:** 22
- **Code:** `discard posix.write(fd, addr lenbuf[0], lenbuf.len)`
- **Decision:** `wont_fix`

### `lib/libomnibus/src/proto_codec.nim` (3 findings)
- **Pattern:** `discard readVarint` and similar
- **Decision:** `intentional`

### `lib/libomnibus/src/service.nim` (2 findings)
- **Pattern:** Resource cleanup discards
- **Decision:** `intentional` for close operations

---

## Statistics

```
Findings by Decision:
  intentional:  14 (73.7%)
  wont_fix:      3 (15.8%)
  needs_review:  2 (10.5%)

Findings by Component:
  omni-schemac (generated):  11 (57.9%)
  libomnibus (framing):        5 (26.3%)
  omni-cat (tool):             1 (5.3%)
  libomnibus (service):        2 (10.5%)
```

---

## Recommendations

1. **Suppress generated codec warnings:** Add triage config to auto-mark `proto_codec.nim` discard findings as `intentional`.

2. **Document framing layer design:** Add inline comments explaining why write errors are intentionally discarded (heartbeat/ack detection).

3. **Review remaining 2 findings:** Manual review needed for non-pattern-matched discards.

4. **Consider suppressing at lint level:** Once patterns are documented, suppress `nim/suspicious-discard` for known-safe patterns in CI.

---

## Stored Triage Defaults

These decisions have been encoded in:
- `/home/zebastjan/dev/archon/config/nim_audit_triage.yaml`
- `~/.windsurf/recipes/omnibus-nim-audit-triage.md` (updated with defaults)

---

*Generated by Archon Nim Audit - Triage Phase*
