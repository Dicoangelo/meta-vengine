#!/bin/bash
# Session lock management - prevents parallel Claude sessions corrupting data
# Non-blocking: warns but doesn't prevent work

LOCK_FILE="$HOME/.claude/.session.lock"
LOCK_TTL=3600  # 1 hour max lock

acquire_session_lock() {
    local session_id="${1:-$$}"

    # Check for existing lock
    if [ -f "$LOCK_FILE" ]; then
        local lock_age=$(($(date +%s) - $(stat -f %m "$LOCK_FILE" 2>/dev/null || stat -c %Y "$LOCK_FILE" 2>/dev/null || echo 0)))
        local lock_pid=$(cat "$LOCK_FILE" 2>/dev/null | head -1)

        # Stale lock (>1 hour)
        if [ $lock_age -gt $LOCK_TTL ]; then
            echo "🔓 Clearing stale session lock (${lock_age}s old)"
            rm -f "$LOCK_FILE"
        # Active lock from different session
        elif [ "$lock_pid" != "$session_id" ] && kill -0 "$lock_pid" 2>/dev/null; then
            echo ""
            echo "━━━ ⚠️  Parallel Session Detected ━━━"
            echo "Another Claude session is active (PID: $lock_pid)"
            echo "Parallel sessions can cause race conditions."
            echo ""
            echo "Options:"
            echo "  1. Close the other session first"
            echo "  2. Continue anyway (risk data corruption)"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo ""
            # Don't block - just warn
        fi
    fi

    # Acquire lock
    echo "$session_id" > "$LOCK_FILE"
    echo "$(date +%s)" >> "$LOCK_FILE"
}

release_session_lock() {
    local session_id="${1:-$$}"
    if [ -f "$LOCK_FILE" ]; then
        local lock_pid=$(cat "$LOCK_FILE" 2>/dev/null | head -1)
        if [ "$lock_pid" = "$session_id" ]; then
            rm -f "$LOCK_FILE"
        fi
    fi
}

check_parallel_sessions() {
    local count=$(pgrep -f "claude" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$count" -gt 2 ]; then  # Allow for current + 1 parent
        echo "⚠️  Multiple Claude processes detected ($count)"
    fi
}

export -f acquire_session_lock release_session_lock check_parallel_sessions
