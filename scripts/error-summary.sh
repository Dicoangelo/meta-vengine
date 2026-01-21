#!/bin/bash
# Error Summary - Run at session end to summarize errors
# Also provides manual commands: error-log, error-stats, error-analyze

KERNEL_DIR="$HOME/.claude/kernel"
ERROR_TRACKER="$KERNEL_DIR/error-tracker.js"
ERROR_LOG="$HOME/.claude/data/errors.jsonl"
ERRORS_MD="$HOME/.claude/ERRORS.md"

case "${1:-summary}" in
    summary)
        # Count errors from this session
        session_start=$(grep -o '"ts":[0-9]*' ~/.claude/data/session-events.jsonl 2>/dev/null | tail -1 | grep -o '[0-9]*')

        if [[ -z "$session_start" ]]; then
            session_start=$(($(date +%s) - 3600))  # Default to last hour
        fi

        if [[ -f "$ERROR_LOG" ]]; then
            session_errors=$(awk -v start="$session_start" -F'"ts":' '{
                split($2, a, ",");
                if (a[1] > start) count++
            } END {print count+0}' "$ERROR_LOG")

            if [[ "$session_errors" -gt 0 ]]; then
                echo "━━━ Session Errors: $session_errors ━━━"

                # Show last 3 errors
                tail -3 "$ERROR_LOG" | while read -r line; do
                    pattern=$(echo "$line" | grep -o '"pattern":"[^"]*"' | cut -d'"' -f4)
                    tool=$(echo "$line" | grep -o '"tool":"[^"]*"' | cut -d'"' -f4)
                    echo "  [$tool] $pattern"
                done

                echo ""
                echo "Run 'node ~/.claude/kernel/error-tracker.js analyze' for details"
            fi
        fi
        ;;

    log)
        # Manual error logging: error-summary.sh log "context" "message" "cause" "fix"
        shift
        node "$ERROR_TRACKER" log "$@"
        ;;

    stats)
        node "$ERROR_TRACKER" stats
        ;;

    analyze)
        node "$ERROR_TRACKER" analyze
        ;;

    scan)
        node "$ERROR_TRACKER" scan
        ;;

    clear-flag)
        rm -f ~/.claude/data/.last-error-flag ~/.claude/data/.last-error-snippet
        ;;

    *)
        echo "Usage: error-summary.sh [summary|log|stats|analyze|scan]"
        ;;
esac
