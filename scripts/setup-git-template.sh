#!/bin/bash
# Setup global git template for automatic Archon hooks

set -e

TEMPLATE_DIR="${HOME}/.config/git/templates/archon"
ARCHON_ROOT="${HOME}/dev/archon"

echo "Setting up Git template for Archon integration..."
echo ""

# Create template directories
mkdir -p "$TEMPLATE_DIR/hooks"

# Create the post-commit hook template
cat > "$TEMPLATE_DIR/hooks/post-commit" << 'HOOK_EOF'
#!/bin/bash
# Archon auto-sync hook (auto-installed)
# This hook is automatically installed via git template

REPO_PATH=$(git rev-parse --show-toplevel 2>/dev/null)
[ -z "$REPO_PATH" ] && exit 0

# Check if this is an Archon-tracked repo
if [ -f "$REPO_PATH/.archon/config.yaml" ] || [ -f "$REPO_PATH/.archon" ]; then
    REPO_NAME=$(basename "$REPO_PATH")
    
    # Queue sync (background, non-blocking)
    (
        curl -s -X POST \
            "http://localhost:8181/api/code-repos/sync-by-path" \
            -H "Content-Type: application/json" \
            -d "{\"path\": \"$REPO_PATH\"}" \
            > /dev/null 2>&1 &
    ) &
fi
HOOK_EOF
chmod +x "$TEMPLATE_DIR/hooks/post-commit"

# Create post-checkout hook template
cat > "$TEMPLATE_DIR/hooks/post-checkout" << 'HOOK_EOF'
#!/bin/bash
# Archon branch sync hook (auto-installed)

PREVIOUS_HEAD=$1
NEW_HEAD=$2
BRANCH_SWITCH=$3

REPO_PATH=$(git rev-parse --show-toplevel 2>/dev/null)
[ -z "$REPO_PATH" ] && exit 0

if [ "$BRANCH_SWITCH" = "1" ] && [ -f "$REPO_PATH/.archon/config.yaml" ]; then
    BRANCH_NAME=$(git branch --show-current)
    
    # Update worktree context (background)
    (
        curl -s -X POST \
            "http://localhost:8181/api/worktree/sync" \
            -H "Content-Type: application/json" \
            -d "{\"path\": \"$REPO_PATH\", \"branch\": \"$BRANCH_NAME\"}" \
            > /dev/null 2>&1 &
    ) &
fi
HOOK_EOF
chmod +x "$TEMPLATE_DIR/hooks/post-checkout"

# Create post-merge hook template
cat > "$TEMPLATE_DIR/hooks/post-merge" << 'HOOK_EOF'
#!/bin/bash
# Archon merge sync hook (auto-installed)

REPO_PATH=$(git rev-parse --show-toplevel 2>/dev/null)
[ -z "$REPO_PATH" ] && exit 0

if [ -f "$REPO_PATH/.archon/config.yaml" ]; then
    # Full re-sync on merge
    (
        curl -s -X POST \
            "http://localhost:8181/api/code-repos/sync-by-path?full=true" \
            -H "Content-Type: application/json" \
            -d "{\"path\": \"$REPO_PATH\"}" \
            > /dev/null 2>&1 &
    ) &
fi
HOOK_EOF
chmod +x "$TEMPLATE_DIR/hooks/post-merge"

# Configure git to use this template
git config --global init.templateDir "$TEMPLATE_DIR"

echo "✅ Git template configured at: $TEMPLATE_DIR"
echo ""
echo "Hooks installed:"
ls -la "$TEMPLATE_DIR/hooks/"
echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "  Git Template Configuration Complete!"
echo "═══════════════════════════════════════════════════════════════════"
echo ""
echo "New repositories will automatically have Archon hooks installed."
echo ""
echo "For existing repositories, run:"
echo "  archon-project-init /path/to/repo"
echo ""
echo "Or manually reinitialize:"
echo "  cd /path/to/repo"
echo "  git init  # Re-apply template hooks"
echo ""
