# ADR-004: Gatekeeper Pre-Commit Code Review

**Status**: Accepted
**Date**: 2026-02-26
**Authors**: zebastjan

## Context

Archon uses CodeRabbit for AI-powered code review. We need a pre-commit workflow that enforces code review quality while being agent-friendly and respecting rate limits.

### Problems with Previous Approach

1. **Auto-commit on issues**: Non-interactive mode auto-committed even when issues were found
2. **Auto-bypass on rate limits**: Rate limits caused automatic bypass without user input
3. **Hook not version-controlled**: Pre-commit hook lived in `.git/hooks/` which isn't tracked

### Requirements

1. Gatekeeper mode: Default `git commit` must block on issues
2. Rate limit handling: Ask user how to proceed (wait/skip/abort)
3. Version-controlled hooks: Hooks should be in the repo
4. Two modes: Gatekeeper (blocks) and Observe-only (never blocks)
5. Agent-friendly: Clear status tags for automation

## Decision

We will implement a two-mode system:

### 1. Gatekeeper Mode (Default)

- Runs via `pre-commit` hook
- **Interactive**: Shows issues with [f/d/v/s/q] options, allows commit anyway or abort
- **Non-interactive**: Blocks on issues (exit 1), asks on rate limits
- Uses state file to skip re-review for unchanged diffs

### 2. Observe-Only Mode

- `bin/cr-review-only -m "message"` wrapper script
- Runs CodeRabbit but always commits regardless of issues
- Uses `--no-verify` to skip pre-commit hook

### Implementation Details

- Hooks stored in `hooks/` directory (version-controlled)
- Install script `bin/install-git-hooks` copies to `.git/hooks/`
- Makefile target `make install-hooks` for convenience
- Environment variables:
  - `SKIP_CODERABBIT=1` - Skip review entirely
  - `FORCE_COMMIT=1` - Skip review and force commit

### Output Tags (for agent consumption)

```
CODERRABBIT_HOOK status=ok                  - Review passed
CODERRABBIT_HOOK status=issues_found         - Review found issues
CODERRABBIT_HOOK status=unchanged            - Diff unchanged, skipped
CODERRABBIT_HOOK status=rate_limited         - API rate limited
CODERRABBIT_INSTRUCTIONS: ...                - Brief guidance when needed
```

## Consequences

### Positive

- Code review is enforced before commits (quality gate)
- Agents get clear signals about how to handle issues
- Rate limits handled gracefully with user input
- Hooks are version-controlled and portable

### Negative

- Requires running `make install-hooks` after clone
- Non-interactive commits will fail if issues found (must use env vars)

## Alternatives Considered

1. **core.hooksPath**: Could use `git config core.hooksPath hooks` but requires git config
2. **Git template directory**: Could add hooks to `.git/template/hooks/` but less discoverable
3. **Only observe-only mode**: Lost the quality gate benefit
