#!/bin/bash
# Permission pre-check - validates file access before operations
# Non-blocking: caches results, warns on issues

check_permissions() {
    local path="$1"
    local operation="${2:-read}"  # read, write, execute

    [ -z "$path" ] && return 0
    path=$(eval echo "$path")

    case "$operation" in
        read)
            if [ -e "$path" ] && [ ! -r "$path" ]; then
                echo "⚠️  No read permission: $path"
                echo "   Fix: chmod +r \"$path\""
                return 1
            fi
            ;;
        write)
            if [ -e "$path" ]; then
                if [ ! -w "$path" ]; then
                    echo "⚠️  No write permission: $path"
                    echo "   Fix: chmod +w \"$path\""
                    return 1
                fi
            else
                local parent=$(dirname "$path")
                if [ ! -w "$parent" ]; then
                    echo "⚠️  Cannot create file (no write permission in $parent)"
                    return 1
                fi
            fi
            ;;
        execute)
            if [ -e "$path" ] && [ ! -x "$path" ]; then
                echo "⚠️  Not executable: $path"
                echo "   Fix: chmod +x \"$path\""
                return 1
            fi
            ;;
    esac
    return 0
}

check_claude_paths() {
    local paths=(
        "$HOME/.claude/data"
        "$HOME/.claude/logs"
        "$HOME/.claude/memory"
        "$HOME/.claude/cache"
    )

    local issues=0
    for p in "${paths[@]}"; do
        if [ -d "$p" ] && [ ! -w "$p" ]; then
            echo "⚠️  No write access to: $p"
            ((issues++))
        fi
    done

    if [ $issues -gt 0 ]; then
        echo "   Fix: chmod -R u+w ~/.claude/"
    fi
}

export -f check_permissions check_claude_paths
