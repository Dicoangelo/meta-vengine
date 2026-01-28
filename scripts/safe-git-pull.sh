#!/bin/bash
# Safe git pull wrapper - protects uncommitted changes
# Usage: bash safe-git-pull.sh [directory]

set -e

DIR="${1:-$PWD}"
cd "$DIR"

echo "🔍 Checking for uncommitted changes in $DIR..."

# Check for uncommitted changes
if ! git diff-index --quiet HEAD -- 2>/dev/null; then
    echo ""
    echo "⚠️  WARNING: You have uncommitted changes!"
    echo ""
    echo "Modified files:"
    git status --short | head -10
    echo ""

    count=$(git status --porcelain | wc -l | tr -d ' ')
    if [[ $count -gt 10 ]]; then
        echo "... and $((count - 10)) more files"
    fi
    echo ""

    # Special warning for dashboard files
    if git status --short | grep -q "command-center.html"; then
        echo "🎨 DASHBOARD CUSTOMIZATION DETECTED"
        echo "    Your command-center.html changes will be preserved"
        echo ""
    fi

    echo "🛡️  PROTECTION OPTIONS:"
    echo "    1. Auto-stash is ENABLED - changes will be stashed and re-applied"
    echo "    2. Manual: Press Ctrl+C now and run 'git stash' yourself"
    echo "    3. Commit: Press Ctrl+C now and commit your changes"
    echo ""
    echo "Proceeding with auto-stash in 3 seconds..."
    sleep 3
fi

# Perform the pull with auto-stash (already configured)
echo "→ Pulling with rebase (auto-stash enabled)..."
git pull --rebase

# Check if stash was created and re-applied
if git stash list | head -1 | grep -q "autostash"; then
    echo ""
    echo "✅ Your changes were auto-stashed and re-applied successfully"
    echo "   If there were conflicts, check: git status"
    echo "   Stash list: git stash list"
fi

echo ""
echo "✅ Pull complete!"
