#!/bin/bash
#
# Auto-trigger Script for Session Analysis
#
# Automatically runs post-session analysis when a Claude Code session ends.
# Integration options:
#   1. Shell exit trap (add to ~/.claude/init.sh)
#   2. File watcher daemon (run in background)
#   3. Cron job (periodic batch analysis)
#

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
LOG_FILE="$HOME/.claude/logs/auto-analysis.log"
ANALYZER="$SCRIPT_DIR/post-session-analyzer.py"

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

#
# Option 1: Post-session hook (called on session exit)
#
post_session_hook() {
    local session_id="$1"

    # Only run if session_id is provided
    if [[ -z "$session_id" ]]; then
        return 0
    fi

    # Run analysis in background (non-blocking)
    (
        sleep 5  # Give session time to write final entries

        echo "[$(date -Iseconds)] Auto-analyzing session: $session_id" >> "$LOG_FILE"

        python3 "$ANALYZER" \
            --session-id "$session_id" \
            >> "$LOG_FILE" 2>&1

        if [[ $? -eq 0 ]]; then
            echo "[$(date -Iseconds)] ✅ Analysis complete for $session_id" >> "$LOG_FILE"
        else
            echo "[$(date -Iseconds)] ❌ Analysis failed for $session_id" >> "$LOG_FILE"
        fi
    ) &
}

#
# Option 2: Analyze recent sessions (batch mode)
#
analyze_recent_sessions() {
    local count="${1:-5}"

    echo "[$(date -Iseconds)] Analyzing $count most recent sessions..." >> "$LOG_FILE"

    python3 "$ANALYZER" \
        --recent "$count" \
        >> "$LOG_FILE" 2>&1

    if [[ $? -eq 0 ]]; then
        echo "[$(date -Iseconds)] ✅ Batch analysis complete" >> "$LOG_FILE"
    else
        echo "[$(date -Iseconds)] ❌ Batch analysis failed" >> "$LOG_FILE"
    fi
}

#
# Option 3: Feedback loop (monthly)
#
run_feedback_loop() {
    local days="${1:-30}"

    echo "[$(date -Iseconds)] Running feedback loop (${days} days)..." >> "$LOG_FILE"

    python3 "$SCRIPT_DIR/routing-feedback-loop.py" \
        --auto-apply \
        --days "$days" \
        >> "$LOG_FILE" 2>&1

    if [[ $? -eq 0 ]]; then
        echo "[$(date -Iseconds)] ✅ Feedback loop complete" >> "$LOG_FILE"
    else
        echo "[$(date -Iseconds)] ❌ Feedback loop failed" >> "$LOG_FILE"
    fi
}

#
# Main command dispatch
#
case "${1:-}" in
    hook)
        post_session_hook "$2"
        ;;
    batch)
        analyze_recent_sessions "${2:-5}"
        ;;
    feedback)
        run_feedback_loop "${2:-30}"
        ;;
    *)
        echo "Auto-trigger Script for Session Analysis"
        echo ""
        echo "Usage:"
        echo "  $0 hook <session-id>     Run post-session analysis"
        echo "  $0 batch [count]         Analyze N recent sessions (default: 5)"
        echo "  $0 feedback [days]       Run feedback loop (default: 30 days)"
        echo ""
        echo "Integration:"
        echo "  Add to ~/.claude/init.sh:"
        echo "    trap '$0 hook \$CLAUDE_SESSION_ID' EXIT"
        echo ""
        echo "  Or run periodically via cron:"
        echo "    0 2 * * * $0 batch 10"
        echo "    0 3 1 * * $0 feedback 30"
        ;;
esac
