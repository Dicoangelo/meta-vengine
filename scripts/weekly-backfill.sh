#!/bin/bash
# Weekly Backfill - Run maintenance scripts
# Triggered by LaunchAgent every Sunday at 3:00 AM

set -e

LOG="$HOME/.claude/logs/weekly-backfill.log"
SCRIPTS="$HOME/.claude/scripts"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG"; }

log "=== Weekly Backfill Started ==="

# 1. Backfill patterns
if [ -f "$SCRIPTS/backfill-patterns.py" ]; then
    log "Running backfill-patterns..."
    python3 "$SCRIPTS/backfill-patterns.py" --days 7 >> "$LOG" 2>&1 || true
fi

# 2. Backfill routing data
if [ -f "$SCRIPTS/backfill-routing.py" ]; then
    log "Running backfill-routing..."
    python3 "$SCRIPTS/backfill-routing.py" >> "$LOG" 2>&1 || true
fi

# 3. Backfill tool usage
if [ -f "$SCRIPTS/backfill-tool-usage.py" ]; then
    log "Running backfill-tool-usage..."
    python3 "$SCRIPTS/backfill-tool-usage.py" >> "$LOG" 2>&1 || true
fi

# 4. Backfill cognitive data
if [ -f "$SCRIPTS/backfill-cognitive-data.py" ]; then
    log "Running backfill-cognitive-data..."
    python3 "$SCRIPTS/backfill-cognitive-data.py" >> "$LOG" 2>&1 || true
fi

# 5. Backfill recovery data
if [ -f "$SCRIPTS/backfill-recovery-data.py" ]; then
    log "Running backfill-recovery-data..."
    python3 "$SCRIPTS/backfill-recovery-data.py" >> "$LOG" 2>&1 || true
fi

# 6. Clean old log files (keep last 7 days)
log "Cleaning old logs..."
find "$HOME/.claude/logs" -name "*.log" -mtime +7 -exec rm {} \; 2>/dev/null || true

# 7. Compact JSONL files (remove duplicates)
if [ -f "$SCRIPTS/clean-jsonl.py" ]; then
    log "Compacting JSONL files..."
    for f in "$HOME/.claude/data"/*.jsonl; do
        python3 "$SCRIPTS/clean-jsonl.py" "$f" >> "$LOG" 2>&1 || true
    done
fi

# 8. Update stats cache
if [ -f "$SCRIPTS/fix-all-dashboard-data.py" ]; then
    log "Updating stats cache..."
    python3 "$SCRIPTS/fix-all-dashboard-data.py" >> "$LOG" 2>&1 || true
fi

# 9. Supermemory weekly rollup
if [ -f "$SCRIPTS/supermemory-cron.sh" ]; then
    log "Running supermemory weekly rollup..."
    bash "$SCRIPTS/supermemory-cron.sh" weekly >> "$LOG" 2>&1 || true
fi

# 10. Backfill capability systems (expertise, predictions, patterns, learning hub)
if [ -f "$SCRIPTS/capability-backfill.py" ]; then
    log "Running capability backfill..."
    python3 "$SCRIPTS/capability-backfill.py" --full --quiet >> "$LOG" 2>&1 || true
fi

log "=== Weekly Backfill Complete ==="
