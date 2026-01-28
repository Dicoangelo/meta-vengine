#!/bin/bash
# Git pre-flight validator - runs before git operations
# Non-blocking: caches results for 5 minutes

CACHE_DIR="$HOME/.claude/cache"
CACHE_TTL=300  # 5 minutes

mkdir -p "$CACHE_DIR"

preflight_git() {
    local operation="$1"
    local target="$2"
    local cache_file="$CACHE_DIR/preflight-$(echo "$target" | md5 -q 2>/dev/null || echo "$target" | md5sum | cut -d' ' -f1).cache"

    # Fast path: use cached result if fresh
    if [ -f "$cache_file" ]; then
        local age=$(($(date +%s) - $(stat -f %m "$cache_file" 2>/dev/null || stat -c %Y "$cache_file" 2>/dev/null || echo 0)))
        if [ $age -lt $CACHE_TTL ]; then
            return 0  # Cached success
        fi
    fi

    case "$operation" in
        clone|fetch|pull|push)
            # Check if remote exists (background, non-blocking)
            if echo "$target" | grep -qi "github.com"; then
                local repo=$(echo "$target" | sed 's|.*github.com[:/]||' | sed 's|\.git$||')
                if ! gh repo view "$repo" &>/dev/null; then
                    echo "⚠️  Repository may not exist: $repo"
                    echo "   Check: gh repo view $repo"
                    return 1
                fi
            fi
            ;;
        tag)
            # Check if tag already exists
            if git tag -l | grep -q "^$target$"; then
                echo "⚠️  Tag already exists: $target"
                return 1
            fi
            ;;
        checkout|branch)
            # Check if branch exists
            if ! git rev-parse --verify "$target" &>/dev/null; then
                if ! git ls-remote --heads origin "$target" 2>/dev/null | grep -q "$target"; then
                    echo "ℹ️  Branch doesn't exist locally or remotely: $target"
                fi
            fi
            ;;
    esac

    # Cache success
    touch "$cache_file"
    return 0
}
