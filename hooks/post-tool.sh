#!/bin/bash
# Claude Code Post-Tool Hook
# Auto-captures tool usage and feeds kernel systems

KERNEL_DIR="$HOME/.claude/kernel"
DATA_DIR="$HOME/.claude/data"

# Get hook data from environment/stdin
TOOL_NAME="${CLAUDE_TOOL_NAME:-unknown}"
TOOL_INPUT="${CLAUDE_TOOL_INPUT:-}"
SESSION_ID="${CLAUDE_SESSION_ID:-$(date +%s)}"
MODEL="${CLAUDE_MODEL:-sonnet}"

# Log tool usage
TOOL_LOG="$DATA_DIR/tool-usage.jsonl"
mkdir -p "$DATA_DIR"

ts=$(date +%s)
entry="{\"ts\":$ts,\"tool\":\"$TOOL_NAME\",\"session\":\"${SESSION_ID:0:8}\",\"model\":\"$MODEL\",\"source\":\"hook\"}"
echo "$entry" >> "$TOOL_LOG" 2>/dev/null

# Update activity tracker
if [[ -f "$KERNEL_DIR/activity-tracker.js" ]]; then
  node "$KERNEL_DIR/activity-tracker.js" tool "$TOOL_NAME" "$MODEL" 2>/dev/null &
fi

# Feed identity manager for learning
if [[ -f "$KERNEL_DIR/identity-manager.js" && -n "$TOOL_INPUT" ]]; then
  # Extract query context from tool input
  node "$KERNEL_DIR/identity-manager.js" learn "$TOOL_INPUT" "$MODEL" 0.5 2>/dev/null &
fi
