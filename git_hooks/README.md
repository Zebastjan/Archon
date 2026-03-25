# Git Hooks

This directory contains git hooks for Archon development.

## Installation

To install the hooks, run:

```bash
cp git_hooks/* .git/hooks/
chmod +x .git/hooks/*
```

Or use the install script:

```bash
./git_hooks/install.sh
```

## Hooks

- `post-commit` - Auto-syncs code entities and generates embeddings after commits
