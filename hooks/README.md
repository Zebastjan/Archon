# Git Hooks

This directory contains git hooks that are version-controlled and installed to `.git/hooks/`.

## Installation

Run the install script to copy hooks to `.git/hooks/`:

```bash
bin/install-git-hooks
```

Or use the Makefile target:

```bash
make install-hooks
```

## Available Hooks

### pre-commit

Runs CodeRabbit AI code review on staged changes before each commit.

**Features:**
- Interactive review with [f/d/v/s/q] options: Fix, Dismiss, View, Skip, Quit
- Blocks commit on issues (gatekeeper mode)
- Handles rate limits with user prompt
- Skips re-review for unchanged diffs
- Respects `SKIP_CODERABBIT=1` and `FORCE_COMMIT=1` env vars

**Output Tags (for agents):**
- `CODERRABBIT_HOOK status=ok` - Review passed
- `CODERRABBIT_HOOK status=issues_found` - Issues need attention
- `CODERRABBIT_HOOK status=unchanged` - No new changes since last review
- `CODERRABBIT_HOOK status=rate_limited` - API rate limited
- `CODERRABBIT_INSTRUCTIONS: ...` - Guidance when action needed

**Usage:**
```bash
git commit -m "message"                    # Normal (blocks on issues)
SKIP_CODERABBIT=1 git commit -m "message"   # Skip review
FORCE_COMMIT=1 git commit -m "message"      # Force commit
```

## Two Modes

1. **Gatekeeper mode** (default): Runs via pre-commit hook, blocks on issues
2. **Observe-only mode**: Use `bin/cr-review-only` to run review without blocking

See CLAUDE.md and AGENTS.md for full documentation.
