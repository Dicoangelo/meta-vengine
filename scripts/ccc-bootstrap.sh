#!/bin/bash
# CCC Bootstrap - Ensures entire infrastructure is alive
# Called on: login, wake from sleep, manual recovery
#
# This is the nuclear option - loads EVERYTHING unconditionally.

LAUNCH_AGENTS="$HOME/Library/LaunchAgents"
LOG="$HOME/.claude/logs/bootstrap.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG"
}

log "=== BOOTSTRAP START ==="

# All CCC daemons in load order (watchdog last so it doesn't interfere)
DAEMONS=(
    "com.claude.dashboard-refresh"
    "com.claude.supermemory"
    "com.claude.session-analysis"
    "com.claude.autonomous-maintenance"
    "com.claude.self-heal"
    "com.claude.watchdog"
)

loaded=0
for daemon in "${DAEMONS[@]}"; do
    plist="$LAUNCH_AGENTS/$daemon.plist"
    if [[ -f "$plist" ]]; then
        # Unload first (ignore errors)
        launchctl unload "$plist" 2>/dev/null
        # Load
        if launchctl load "$plist" 2>/dev/null; then
            log "LOADED: $daemon"
            ((loaded++))
        else
            log "FAILED: $daemon"
        fi
    else
        log "MISSING: $plist"
    fi
done

log "=== BOOTSTRAP COMPLETE: $loaded daemons loaded ==="

# Verify watchdog is running
sleep 2
if launchctl list | grep -q "com.claude.watchdog"; then
    log "VERIFIED: Watchdog running"
else
    log "WARNING: Watchdog not detected"
fi

# Touch heartbeat
echo "$(date -Iseconds)" > "$HOME/.claude/.watchdog-heartbeat"

exit 0
