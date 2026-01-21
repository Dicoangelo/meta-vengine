#!/bin/bash
# Claude Code Post-Response Hook
# Auto-captures responses and updates metrics

KERNEL_DIR="$HOME/.claude/kernel"
DATA_DIR="$HOME/.claude/data"

SESSION_ID="${CLAUDE_SESSION_ID:-$(date +%s)}"
MODEL="${CLAUDE_MODEL:-sonnet}"
COST="${CLAUDE_COST:-0}"
TOKENS_IN="${CLAUDE_TOKENS_IN:-0}"
TOKENS_OUT="${CLAUDE_TOKENS_OUT:-0}"

# Log to activity
ACTIVITY_LOG="$HOME/.claude/activity.log"
echo "$(date '+%Y-%m-%d %H:%M:%S') response model=$MODEL tokens_in=$TOKENS_IN tokens_out=$TOKENS_OUT" >> "$ACTIVITY_LOG" 2>/dev/null

# Update subscription tracker
if [[ -f "$KERNEL_DIR/subscription-tracker.js" && "$COST" != "0" ]]; then
  node "$KERNEL_DIR/subscription-tracker.js" add "$COST" "$MODEL" 2>/dev/null &
fi

# Estimate DQ score from model choice
dq_score="0.5"
[[ "$MODEL" == *"haiku"* ]] && dq_score="0.3"
[[ "$MODEL" == *"sonnet"* ]] && dq_score="0.6"
[[ "$MODEL" == *"opus"* ]] && dq_score="0.85"

# Log to DQ scores
DQ_LOG="$KERNEL_DIR/dq-scores.jsonl"
ts=$(date +%s)
echo "{\"ts\":$ts,\"model\":\"$MODEL\",\"dqScore\":$dq_score,\"tokens\":$((TOKENS_IN + TOKENS_OUT)),\"source\":\"hook\"}" >> "$DQ_LOG" 2>/dev/null
