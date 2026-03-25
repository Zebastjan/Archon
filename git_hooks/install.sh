#!/bin/bash
# Install git hooks for Archon development

HOOKS_DIR=$(git rev-parse --show-toplevel)/.git/hooks
SOURCE_DIR=$(git rev-parse --show-toplevel)/git_hooks

if [ ! -d "$SOURCE_DIR" ]; then
    echo "Error: git_hooks directory not found"
    exit 1
fi

echo "Installing git hooks..."
for hook in "$SOURCE_DIR"/*; do
    if [ -f "$hook" ] && [ "$(basename "$hook")" != "README.md" ] && [ "$(basename "$hook")" != "install.sh" ]; then
        cp "$hook" "$HOOKS_DIR/"
        chmod +x "$HOOKS_DIR/$(basename "$hook")"
        echo "  Installed: $(basename "$hook")"
    fi
done

echo "Done!"
