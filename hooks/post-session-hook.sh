#!/bin/bash
#
# Post-Session Hook
# Triggers session analysis when a Claude Code session completes.
#
# Usage:
#   - Manually: post-session-hook.sh [session-id]
#   - As trap: trap 'post-session-hook.sh "$CLAUDE_SESSION_ID"' EXIT
#   - Via cron: 0 */4 * * * ~/.claude/hooks/post-session-hook.sh batch
#

SCRIPT_DIR="$(dirname "$0")"
LOG_DIR="$HOME/.claude/logs"
LOG_FILE="$LOG_DIR/post-session.log"
ANALYZER="$HOME/.claude/scripts/observatory/post-session-analyzer.py"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# Get latest session transcript
get_latest_session() {
    ls -t ~/.claude/projects/*/transcripts/*.jsonl 2>/dev/null | head -1
}

# Analyze a specific session
analyze_session() {
    local session="$1"

    if [[ ! -f "$session" ]]; then
        log "Session file not found: $session"
        return 1
    fi

    log "Analyzing session: $session"

    # Run post-session analyzer in background
    python3 "$ANALYZER" "$session" >> "$LOG_FILE" 2>&1 &

    log "Analysis started (pid: $!)"
}

# Batch analyze recent sessions
analyze_batch() {
    local count="${1:-5}"

    log "Batch analyzing $count recent sessions..."

    # Get recent transcripts
    for session in $(ls -t ~/.claude/projects/*/transcripts/*.jsonl 2>/dev/null | head -$count); do
        analyze_session "$session"
        sleep 1  # Don't overload
    done

    log "Batch analysis queued"
}

# Main dispatch
case "${1:-}" in
    batch)
        analyze_batch "${2:-5}"
        ;;
    "")
        # No argument - analyze most recent session
        LATEST=$(get_latest_session)
        if [[ -n "$LATEST" ]]; then
            analyze_session "$LATEST"
        else
            log "No sessions found"
        fi
        ;;
    *)
        # Specific session ID or path provided
        if [[ -f "$1" ]]; then
            analyze_session "$1"
        else
            # Try to find session by ID
            SESSION_FILE=$(find ~/.claude/projects/*/transcripts -name "*$1*" -type f 2>/dev/null | head -1)
            if [[ -n "$SESSION_FILE" ]]; then
                analyze_session "$SESSION_FILE"
            else
                log "Session not found: $1"
                exit 1
            fi
        fi
        ;;
esac
