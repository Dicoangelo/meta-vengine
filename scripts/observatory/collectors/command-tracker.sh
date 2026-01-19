#!/bin/bash
# Claude Observatory - Command Usage Tracker
# Tracks which aliases, skills, and commands are actually used

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
# TRACKED ALIASES (wrap existing aliases)
# ═══════════════════════════════════════════════════════════════════════════

# Model selection
alias cq='__track_command cq "$*" alias && claude --model haiku'
alias cc='__track_command cc "$*" alias && claude --model sonnet'
alias co='__track_command co "$*" alias && claude --model opus'
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

# Export tracking function
export -f __track_command
export -f __track_skill

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

# Export analytics function
export -f command-stats
