#!/bin/bash
# Claude Observatory - Command Usage Tracker
# Tracks which aliases, skills, and commands are actually used

# Clear conflicting aliases (prevents parse errors on re-source)
unalias command-stats cq cc co claude ccc routing-dash cterm gsave gsync ai-good ai-bad 2>/dev/null

DATA_FILE="$HOME/.claude/data/command-usage.jsonl"
mkdir -p "$(dirname "$DATA_FILE")"

# ═══════════════════════════════════════════════════════════════════════════
# COMMAND TRACKING
# ═══════════════════════════════════════════════════════════════════════════

__track_command() {
  local cmd="$1"
  local args="$2"
  local context="${3:-shell}"

  # Build entry
  local entry=$(cat <<EOF
{"ts":$(date +%s),"cmd":"$cmd","args":"$args","context":"$context","pwd":"$PWD"}
EOF
)

  echo "$entry" >> "$DATA_FILE"
}

# Wrapper function for tracked commands
__wrap_command() {
  local cmd_name="$1"
  shift
  __track_command "$cmd_name" "$*" "alias"
}

# ═══════════════════════════════════════════════════════════════════════════
# KERNEL INTEGRATION HOOK
# ═══════════════════════════════════════════════════════════════════════════

# Notify all kernel systems of Claude invocation
# This ensures activity tracker, identity manager get data regardless of entry point
__kernel_hook() {
  local model="$1"
  local query="$2"
  local dq_score="${3:-0.5}"  # Default for direct model calls

  local KERNEL_DIR="$HOME/.claude/kernel"
  local ACTIVITY_TRACKER="$KERNEL_DIR/activity-tracker.js"
  local IDENTITY_MANAGER="$KERNEL_DIR/identity-manager.js"
  local DQ_SCORES="$KERNEL_DIR/dq-scores.jsonl"
  local AI_LOG="$HOME/.claude/data/ai-routing.log"

  # Skip if called from ai() function (it handles kernel logging itself)
  [[ -n "$__AI_KERNEL_ACTIVE" ]] && return

  # Skip if no query (interactive session start)
  [[ -z "$query" ]] && return

  # Calculate complexity based on model choice (heuristic)
  local complexity="0.3"
  [[ "$model" == "sonnet" ]] && complexity="0.5"
  [[ "$model" == "opus" ]] && complexity="0.8"

  # Estimate DQ score based on model (users choose appropriate model)
  # Higher DQ for opus (complex queries), lower for haiku (simple queries)
  local estimated_dq="0.5"
  [[ "$model" == "haiku" ]] && estimated_dq="0.3"
  [[ "$model" == "sonnet" ]] && estimated_dq="0.6"
  [[ "$model" == "opus" ]] && estimated_dq="0.85"

  # Log to DQ scores for routing metrics (background)
  local ts=$(date +%s)
  local dq_entry="{\"ts\":$ts,\"query\":\"${query:0:100}\",\"model\":\"$model\",\"dqScore\":$estimated_dq,\"complexity\":$complexity,\"source\":\"direct\"}"
  echo "$dq_entry" >> "$DQ_SCORES" 2>/dev/null &

  # Log to activity tracker (background)
  if [[ -f "$ACTIVITY_TRACKER" ]]; then
    node "$ACTIVITY_TRACKER" query "$query" "$model" "$estimated_dq" "$complexity" 2>/dev/null &
  fi

  # Update identity manager (background)
  if [[ -f "$IDENTITY_MANAGER" ]]; then
    node "$IDENTITY_MANAGER" learn "$query" "$model" "$estimated_dq" 2>/dev/null &
  fi

  # Log decision
  echo "$(date '+%H:%M:%S') DIRECT:$model DQ:$estimated_dq C:$complexity query:${query:0:50}" >> "$AI_LOG"
}

# Claude wrapper functions (not aliases) to capture queries
__claude_with_kernel() {
  local model="$1"
  shift
  local args="$*"

  # Track the command
  __track_command "c${model:0:1}" "$args" "alias"

  # Extract query if using -p flag
  local query=""
  if [[ "$args" == *"-p"* ]]; then
    # Parse query after -p flag
    query=$(echo "$args" | sed -n 's/.*-p[[:space:]]*["'\'']\{0,1\}\([^"'\'']*\)["'\'']\{0,1\}.*/\1/p')
    if [[ -z "$query" ]]; then
      # Try without quotes
      query=$(echo "$args" | sed 's/.*-p[[:space:]]*//')
    fi
  fi

  # Notify kernel systems
  __kernel_hook "$model" "$query"

  # Run Claude
  claude --model "$model" $args
}

# Note: export -f is bash-only and causes function dumps in zsh
# Functions are available in sourced context without export

# ═══════════════════════════════════════════════════════════════════════════
# TRACKED ALIASES (wrap existing aliases)
# ═══════════════════════════════════════════════════════════════════════════

# Model selection - now with kernel integration
cq() { __claude_with_kernel haiku "$@"; }
cc() { __claude_with_kernel sonnet "$@"; }
co() { __claude_with_kernel opus "$@"; }
alias claude='__track_command claude "$*" alias && ~/.claude/scripts/claude-wrapper.sh'

# Dashboards
alias ccc='__track_command ccc "" alias && ~/.claude/scripts/ccc-generator.sh'
alias routing-dash='__track_command routing-dash "" alias && ~/.claude/scripts/routing-dashboard.sh'
alias cterm='__track_command cterm "" alias && ~/.claude/scripts/cterm.sh'

# Routing
alias routing-report='__track_command routing-report "$*" alias && python3 ~/researchgravity/routing-metrics.py report --days'
alias routing-targets='__track_command routing-targets "" alias && python3 ~/researchgravity/routing-metrics.py check-targets'

# Co-evolution
alias coevo-analyze='__track_command coevo-analyze "" alias && python3 ~/.claude/scripts/meta-analyzer.py analyze'
alias coevo-propose='__track_command coevo-propose "" alias && python3 ~/.claude/scripts/meta-analyzer.py propose'
alias coevo-dashboard='__track_command coevo-dashboard "" alias && python3 ~/.claude/scripts/meta-analyzer.py dashboard'

# Git shortcuts
alias cgit='__track_command cgit "" alias && cc "/pr"'
alias gsave='__track_command gsave "$*" alias && git add -A && git commit -m'
alias gsync='__track_command gsync "$*" alias && git pull --rebase && git push'

# Quick commands
alias ctest='__track_command ctest "" alias && cc "run tests and fix failures"'
alias cbuild='__track_command cbuild "" alias && cc "run build and fix errors"'
alias cfix='__track_command cfix "" alias && cc "fix the last error"'

# Feedback
alias ai-good='__track_command ai-good "$*" alias && node ~/.claude/kernel/dq-scorer.js feedback'
alias ai-bad='__track_command ai-bad "$*" alias && node ~/.claude/kernel/dq-scorer.js feedback'
alias ai-feedback-enable='__track_command ai-feedback-enable "" alias && source ~/.claude/scripts/smart-route.sh && precmd_functions+=(__ai_feedback_auto)'
alias ai-feedback-status='__track_command ai-feedback-status "" alias && ai-feedback-status'

# ═══════════════════════════════════════════════════════════════════════════
# SKILL TRACKING
# ═══════════════════════════════════════════════════════════════════════════

__track_skill() {
  local skill="$1"
  __track_command "$skill" "" "skill"
}

# Note: export -f is bash-only, removed for zsh compatibility

# ═══════════════════════════════════════════════════════════════════════════
# ANALYTICS
# ═══════════════════════════════════════════════════════════════════════════

command-stats() {
  local days="${1:-7}"

  echo "📊 Command Usage (Last $days days)"
  echo "════════════════════════════════════════"

  python3 << EOF
import json
from datetime import datetime, timedelta
from collections import Counter

cutoff = datetime.now() - timedelta(days=$days)

try:
    with open("$DATA_FILE") as f:
        events = [json.loads(line) for line in f if line.strip()]
except FileNotFoundError:
    print("  No command usage data yet")
    exit()

# Filter to time range
recent = [e for e in events if datetime.fromtimestamp(e['ts']) > cutoff]

if not recent:
    print(f"  No commands in last $days days")
    exit()

# Stats
total = len(recent)
commands = Counter(e['cmd'] for e in recent)
contexts = Counter(e.get('context', 'unknown') for e in recent)

print(f"  Total Commands: {total}")
print()
print("  Top Commands:")
for cmd, count in commands.most_common(15):
    pct = count / total * 100
    print(f"    {cmd:20s}: {count:4d} ({pct:5.1f}%)")
print()
print("  By Context:")
for ctx, count in contexts.most_common():
    pct = count / total * 100
    print(f"    {ctx:12s}: {count:4d} ({pct:5.1f}%)")
EOF
}

# Note: export -f removed for zsh compatibility
