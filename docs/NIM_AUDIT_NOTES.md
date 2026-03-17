# Nim Audit Notes for Omnibus

This document captures institutional knowledge about Nim code audit findings in the Omnibus repository. It serves as a reference for future triage decisions and onboarding new developers.

---

## Table of Contents

1. [Common Patterns](#common-patterns)
2. [Known-Intentional Discards](#known-intentional-discards)
3. [Won't Fix Patterns](#wont-fix-patterns)
4. [Rules Under Monitoring](#rules-under-monitoring)

---

## Common Patterns

### Protobuf Varint Parsing

**Pattern:** `discard readVarint(data, pos)`

**Context:**
The `readVarint` function in protobuf codecs follows a dual-return pattern:
1. The decoded integer value is returned as the function result
2. The parsing position is updated via the `pos` reference parameter

**Why it's intentional:**
In many protobuf parsing contexts, the varint is being parsed as a length prefix or tag where the value is immediately used for bounds checking or field dispatch, but the return value isn't stored in a named variable. The `discard` makes explicit that we're relying on the side effect (position update).

**Example:**
```nim
# In proto_codec.nim generated code
discard readVarint(data, pos)  # Read and skip length prefix
let fieldData = data[pos..<pos+length]  # pos was updated by readVarint
```

---

### POSIX Resource Cleanup

**Pattern:** `discard posix.close(fd)`

**Context:**
POSIX `close()` can fail if:
- The file descriptor was already closed (EBADF)
- A previous buffered write failed (EIO on NFS with async writes)

**Why it's intentional:**
In local/pipe/socket contexts, close errors are typically non-actionable:
- EBADF indicates a double-close bug, but the FD is closed regardless
- EIO on close indicates a previous write failed, but we can't recover at close-time

The Omnibus codebase uses this pattern in cleanup code where the only recovery option would be logging and continuing anyway.

**Exception:** Network filesystems with `O_SYNC` writes should check close() returns.

---

### Framing Layer Writes

**Pattern:** `discard posix.write(fd, buffer, len)`

**Context:**
The libomnibus framing layer writes length-prefixed messages to sockets/pipes.

**Why it's wont_fix:**
1. **Transport-level detection:** The protocol uses heartbeat/ack messages to detect dead connections
2. **Partial write handling:** The framing layer is designed for non-blocking sockets; partial writes are handled by the event loop retrying
3. **No application-level recovery:** A failed write indicates a dead transport; the application can't "fix" this at the write call site

**Monitoring:**
We monitor connection health via heartbeats, not individual write returns.

---

## Known-Intentional Discards

| Pattern | Location | Rationale |
|---------|----------|-----------|
| `discard readVarint` | `*/proto_codec.nim` | Position updated via ref param |
| `discard posix.close` | `*/service.nim`, `tools/*` | Non-actionable for local FDs |
| `discard Gc_unref` | Various | GC hints, no return value meaning |

---

## Won't Fix Patterns

| Pattern | Location | Rationale | Risk Level |
|---------|----------|-----------|------------|
| `discard posix.write` | `lib/libomnibus/src/framing.nim` | Transport errors detected via heartbeat | Low |

---

## Rules Under Monitoring

### `nim/suspicious-discard`

**Current Status:** Partially suppressed

**Auto-triaged patterns:**
- ✓ Protobuf varint reads
- ✓ POSIX close on local FDs
- ✓ Framing layer writes

**Requires manual review:**
- System calls with error returns (open, read, accept)
- Library calls returning error codes
- Generated code not matching known patterns

---

## Future Improvements

1. **Suppress generated code:** Add lint suppression comments to generated proto_codec.nim files
2. **Document framing layer:** Add architecture docs explaining the heartbeat/ack design
3. **Consider alternatives:** For critical paths, consider using `checkErrno` pattern instead of discard

---

## Related Documentation

- `OMNIBUS_NIM_TRIAGE_REPORT.md` - Specific audit findings and decisions
- `~/.windsurf/recipes/omnibus-nim-audit-triage.md` - Automated triage workflow
- `config/nim_audit_triage.yaml` - Machine-readable triage rules

---

*Last updated: 2026-03-16*
