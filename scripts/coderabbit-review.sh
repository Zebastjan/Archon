#!/usr/bin/env bash
set -euo pipefail

# Run a CodeRabbit review on uncommitted changes and print a concise prompt
coderabbit review --prompt-only --type uncommitted
