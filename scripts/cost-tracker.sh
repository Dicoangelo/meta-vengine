#!/bin/bash
# Auto cost tracking for Claude sessions
# Logs costs per session and provides summaries

COST_LOG="$HOME/.claude/data/cost-log.jsonl"
COST_SUMMARY="$HOME/.claude/data/cost-summary.json"

# Source centralized pricing
source "$HOME/.claude/config/pricing.sh"

# Initialize if needed
mkdir -p "$(dirname "$COST_LOG")"
touch "$COST_LOG"

# Log a cost entry (called from hooks or manually)
log_cost() {
  local model="$1"
  local input_tokens="$2"
  local output_tokens="$3"
  local cache_read="${4:-0}"
  local cache_write="${5:-0}"

  # Cost per million tokens from centralized config
  local input_cost=0
  local output_cost=0

  case "$model" in
    *haiku*) input_cost=$HAIKU_INPUT; output_cost=$HAIKU_OUTPUT ;;
    *sonnet*) input_cost=$SONNET_INPUT; output_cost=$SONNET_OUTPUT ;;
    *opus*) input_cost=$OPUS_INPUT; output_cost=$OPUS_OUTPUT ;;
  esac

  # Calculate cost in dollars
  local total_input_cost=$(echo "scale=6; $input_tokens * $input_cost / 1000000" | bc)
  local total_output_cost=$(echo "scale=6; $output_tokens * $output_cost / 1000000" | bc)
  local cache_savings=$(echo "scale=6; $cache_read * $input_cost * 0.9 / 1000000" | bc)
  local total_cost=$(echo "scale=6; $total_input_cost + $total_output_cost - $cache_savings" | bc)

  # Log entry
  echo "{\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"model\":\"$model\",\"input\":$input_tokens,\"output\":$output_tokens,\"cache_read\":$cache_read,\"cost\":$total_cost}" >> "$COST_LOG"
}

# Get today's total cost
today_cost() {
  local today=$(date +%Y-%m-%d)
  grep "$today" "$COST_LOG" 2>/dev/null | \
    python3 -c "
import sys, json
total = sum(json.loads(line)['cost'] for line in sys.stdin)
print(f'\${total:.4f}')
" 2>/dev/null || echo "\$0.0000"
}

# Get this week's cost
week_cost() {
  local week_ago=$(date -v-7d +%Y-%m-%d 2>/dev/null || date -d '7 days ago' +%Y-%m-%d)
  python3 << EOF
import json
from datetime import datetime, timedelta

total = 0
week_ago = datetime.now() - timedelta(days=7)

try:
    with open('$COST_LOG', 'r') as f:
        for line in f:
            entry = json.loads(line)
            entry_date = datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00'))
            if entry_date.replace(tzinfo=None) >= week_ago:
                total += entry['cost']
except:
    pass

print(f'\${total:.4f}')
EOF
}

# Show cost dashboard
cost_dashboard() {
  echo "╔══════════════════════════════════════════╗"
  echo "║         CLAUDE COST TRACKER              ║"
  echo "╠══════════════════════════════════════════╣"
  echo "║ Today:     $(today_cost)"
  echo "║ This week: $(week_cost)"
  echo "║ Total entries: $(wc -l < "$COST_LOG" 2>/dev/null | tr -d ' ')"
  echo "╠══════════════════════════════════════════╣"
  echo "║ Recent:"
  tail -5 "$COST_LOG" 2>/dev/null | while read line; do
    local ts=$(echo "$line" | python3 -c "import sys,json; print(json.loads(sys.stdin.read())['timestamp'][:16])" 2>/dev/null)
    local cost=$(echo "$line" | python3 -c "import sys,json; print(f\"\${json.loads(sys.stdin.read())['cost']:.4f}\")" 2>/dev/null)
    echo "║   $ts  $cost"
  done
  echo "╚══════════════════════════════════════════╝"
}

# Export if sourced, run if executed
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  case "${1:-dashboard}" in
    log) shift; log_cost "$@" ;;
    today) today_cost ;;
    week) week_cost ;;
    *) cost_dashboard ;;
  esac
fi
