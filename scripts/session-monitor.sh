#!/bin/bash
# Session Monitor - Logs unexpected terminations
# Created: 2026-01-31

MONITOR_LOG="$HOME/.claude/logs/session-terminations.log"
mkdir -p "$(dirname "$MONITOR_LOG")"

log_termination() {
    local signal=$1
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local pid=$$
    local ppid=$PPID

    echo "━━━ SESSION TERMINATION ━━━" >> "$MONITOR_LOG"
    echo "Time: $timestamp" >> "$MONITOR_LOG"
    echo "Signal: $signal" >> "$MONITOR_LOG"
    echo "PID: $pid | PPID: $ppid" >> "$MONITOR_LOG"
    echo "Terminal: $TERM_PROGRAM" >> "$MONITOR_LOG"

    # Capture what was running
    echo "Active processes:" >> "$MONITOR_LOG"
    ps aux | grep -E "claude|node" | grep -v grep >> "$MONITOR_LOG" 2>/dev/null

    # Memory state
    echo "Memory:" >> "$MONITOR_LOG"
    vm_stat | head -5 >> "$MONITOR_LOG" 2>/dev/null

    # Parent process info
    echo "Parent:" >> "$MONITOR_LOG"
    ps -p $PPID -o pid,ppid,stat,time,command 2>/dev/null >> "$MONITOR_LOG"

    echo "" >> "$MONITOR_LOG"
}

# Export for use in other scripts
export -f log_termination
export MONITOR_LOG

# Set traps for common termination signals
setup_termination_traps() {
    trap 'log_termination SIGHUP' HUP
    trap 'log_termination SIGINT' INT
    trap 'log_termination SIGTERM' TERM
    trap 'log_termination SIGQUIT' QUIT
    trap 'log_termination EXIT' EXIT
}

# Call to set up
setup_termination_traps
