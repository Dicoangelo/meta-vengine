#!/bin/bash
# Supermemory scheduled tasks
# Usage: supermemory-cron.sh {daily|weekly|monthly}

set -e
SUPERMEMORY="python3 $HOME/.claude/supermemory/cli.py"
LOG="$HOME/.claude/logs/supermemory-cron.log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG"; }

case "$1" in
  daily)
    log "Starting daily sync"
    $SUPERMEMORY sync >> "$LOG" 2>&1
    python3 "$HOME/.claude/scripts/daily-memory-log.py" >> "$LOG" 2>&1
    log "Daily sync complete"
    ;;
  weekly)
    log "Starting weekly rollup"
    $SUPERMEMORY rollup >> "$LOG" 2>&1
    # Refresh memory links
    python3 "$HOME/.claude/scripts/populate-memory-links.py" >> "$LOG" 2>&1 || true
    log "Weekly rollup complete"
    ;;
  monthly)
    log "Starting monthly tasks"
    $SUPERMEMORY rollup --month "$(date +%Y-%m)" >> "$LOG" 2>&1
    # Generate all project memories
    for proj in os-app career research claude-system; do
      $SUPERMEMORY project "$proj" > "$HOME/.claude/memory/projects/${proj}.md" 2>/dev/null || true
    done
    log "Monthly tasks complete"
    ;;
  *)
    echo "Usage: supermemory-cron.sh {daily|weekly|monthly}"
    exit 1
    ;;
esac
