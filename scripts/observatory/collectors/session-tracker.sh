#!/bin/bash
# Claude Observatory - Session Outcome Tracker
# Tracks session outcomes, quality, and completion status

# Clear conflicting aliases (prevents parse errors on re-source)
unalias session-start session-complete session-rate session-stats 2>/dev/null

OBSERVATORY_DIR="$HOME/.claude/scripts/observatory"
CONFIG_FILE="$OBSERVATORY_DIR/config.json"
DATA_FILE="$HOME/.claude/data/session-outcomes.jsonl"

# Ensure data directory exists
mkdir -p "$(dirname "$DATA_FILE")"

# ═══════════════════════════════════════════════════════════════════════════
# SESSION OUTCOME TRACKING
# ═══════════════════════════════════════════════════════════════════════════

session-start() {
  export OBSERVATORY_SESSION_START=$(date +%s)
  export OBSERVATORY_SESSION_ID="${CLAUDE_SESSION_ID:-$(uuidgen | tr '[:upper:]' '[:lower:]')}"
  export OBSERVATORY_SESSION_PWD="$PWD"
  export OBSERVATORY_SESSION_MODEL="${CLAUDE_MODEL:-unknown}"

  # Log session start
  echo "{\"ts\":$OBSERVATORY_SESSION_START,\"event\":\"session_start\",\"session_id\":\"$OBSERVATORY_SESSION_ID\",\"pwd\":\"$PWD\",\"model\":\"$OBSERVATORY_SESSION_MODEL\"}" >> "$DATA_FILE"
}

session-complete() {
  local outcome="${1:-unknown}"  # success, partial, abandoned, error, research
  local note="${2:-}"
  local quality="${3:-}"  # 1-5 rating

  if [[ -z "$OBSERVATORY_SESSION_START" ]]; then
    echo "⚠️  No active session tracked. Run session-start first."
    return 1
  fi

  local end_time=$(date +%s)
  local duration=$((end_time - OBSERVATORY_SESSION_START))

  # Auto-detect quality if not provided
  if [[ -z "$quality" ]]; then
    case "$outcome" in
      success) quality=5 ;;
      partial) quality=3 ;;
      error) quality=1 ;;
      abandoned) quality=2 ;;
      research) quality=4 ;;
      *) quality=3 ;;
    esac
  fi

  # Build entry (single-line JSON for JSONL format)
  local entry="{\"ts\":$end_time,\"event\":\"session_complete\",\"session_id\":\"$OBSERVATORY_SESSION_ID\",\"outcome\":\"$outcome\",\"quality\":$quality,\"duration_sec\":$duration,\"note\":\"$note\",\"pwd\":\"$OBSERVATORY_SESSION_PWD\",\"model\":\"$OBSERVATORY_SESSION_MODEL\"}"

  echo "$entry" >> "$DATA_FILE"

  # Also write to SQLite via dual-write library
  python3 << PYEOF 2>/dev/null || true
import sys
sys.path.insert(0, '$HOME/.claude/hooks')
from dual_write_lib import log_session_outcome

log_session_outcome(
    session_id="$OBSERVATORY_SESSION_ID",
    messages=0,  # Not tracked in observatory
    tools=0,     # Not tracked in observatory
    title="$note",
    intent="$outcome",
    outcome="$outcome",
    model_efficiency=0.0,  # Not tracked in observatory
    models_used={"$OBSERVATORY_SESSION_MODEL": 1},
    quality=$quality
)
PYEOF

  # Store in memory-linker if there's a meaningful note
  local MEMORY_LINKER="$HOME/.claude/kernel/memory-linker.js"
  if [[ -n "$note" && -f "$MEMORY_LINKER" && ${#note} -gt 10 ]]; then
    local note_type="insight"
    [[ "$outcome" == "error" ]] && note_type="pattern"
    [[ "$outcome" == "success" ]] && note_type="fact"
    node "$MEMORY_LINKER" store "$note" "$note_type" "session" "$outcome" 2>/dev/null &
  fi

  # Show summary
  local duration_min=$((duration / 60))
  echo "✅ Session completed: $outcome (${duration_min}m, quality: $quality/5)"

  # Clear tracking vars
  unset OBSERVATORY_SESSION_START
  unset OBSERVATORY_SESSION_ID
  unset OBSERVATORY_SESSION_PWD
  unset OBSERVATORY_SESSION_MODEL
}

session-abandon() {
  session-complete "abandoned" "$1" "2"
}

session-error() {
  session-complete "error" "$1" "1"
}

session-success() {
  session-complete "success" "$1" "5"
}

# ═══════════════════════════════════════════════════════════════════════════
# AUTO-DETECTION HELPERS
# ═══════════════════════════════════════════════════════════════════════════

# Detect outcome from recent activity
session-auto-complete() {
  if [[ -z "$OBSERVATORY_SESSION_START" ]]; then
    echo "⚠️  No active session"
    return 1
  fi

  # Check recent git commits (success indicator)
  local recent_commits=$(git log --since="$OBSERVATORY_SESSION_START seconds ago" --oneline 2>/dev/null | wc -l | tr -d ' ')

  # Check recent errors in activity log
  local recent_errors=$(tail -50 ~/.claude/activity.log 2>/dev/null | grep -c "ERROR\|FAIL" || echo 0)

  # Determine outcome
  local outcome="partial"
  local quality=3

  if [[ $recent_commits -gt 0 && $recent_errors -eq 0 ]]; then
    outcome="success"
    quality=5
  elif [[ $recent_errors -gt 5 ]]; then
    outcome="error"
    quality=2
  elif [[ $recent_commits -gt 0 ]]; then
    outcome="partial"
    quality=4
  fi

  session-complete "$outcome" "auto-detected" "$quality"
}

# ═══════════════════════════════════════════════════════════════════════════
# QUALITY RATING HELPER
# ═══════════════════════════════════════════════════════════════════════════

session-rate() {
  local rating=$1
  local note="${2:-}"

  if [[ -z "$rating" ]] || [[ $rating -lt 1 ]] || [[ $rating -gt 5 ]]; then
    echo "Usage: session-rate [1-5] [optional note]"
    echo "  1 = Terrible, wasted time"
    echo "  2 = Poor, little progress"
    echo "  3 = OK, some progress"
    echo "  4 = Good, solid progress"
    echo "  5 = Excellent, major breakthrough"
    return 1
  fi

  # Determine outcome from rating
  local outcome="partial"
  if [[ $rating -ge 4 ]]; then
    outcome="success"
  elif [[ $rating -le 2 ]]; then
    outcome="error"
  fi

  session-complete "$outcome" "$note" "$rating"
}

# ═══════════════════════════════════════════════════════════════════════════
# QUERY INTERFACE
# ═══════════════════════════════════════════════════════════════════════════

session-stats() {
  local days="${1:-7}"

  echo "📊 Session Outcomes (Last $days days)"
  echo "════════════════════════════════════════"

  python3 << EOF
import json
from datetime import datetime, timedelta
from collections import Counter

cutoff = datetime.now() - timedelta(days=$days)

with open("$DATA_FILE") as f:
    events = [json.loads(line) for line in f if line.strip()]

# Filter to time range and completed sessions
completed = [e for e in events
             if e.get('event') == 'session_complete'
             and datetime.fromtimestamp(e['ts']) > cutoff]

if not completed:
    print("  No completed sessions in last $days days")
    exit()

# Stats
total = len(completed)
outcomes = Counter(e['outcome'] for e in completed)
avg_quality = sum(e.get('quality', 3) for e in completed) / total
avg_duration = sum(e.get('duration_sec', 0) for e in completed) / total / 60

print(f"  Total Sessions: {total}")
print(f"  Avg Quality: {avg_quality:.1f}/5")
print(f"  Avg Duration: {avg_duration:.0f}m")
print()
print("  Outcomes:")
for outcome, count in outcomes.most_common():
    pct = count / total * 100
    print(f"    {outcome:12s}: {count:3d} ({pct:5.1f}%)")
EOF
}

# ═══════════════════════════════════════════════════════════════════════════
# INTEGRATION HOOKS
# ═══════════════════════════════════════════════════════════════════════════

# Auto-start tracking on shell prompt
__observatory_session_init() {
  if [[ -z "$OBSERVATORY_SESSION_START" ]] && [[ -n "$CLAUDE_SESSION_ID" ]]; then
    session-start
  fi
}

# Note: export -f removed for zsh compatibility (bash-only feature)
