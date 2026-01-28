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

# PRIMARY: Write to SQLite
python3 << PYEOF >> "$HOME/.claude/logs/post-tool-sqlite.log" 2>&1 || true
import sys
import time
sys.path.insert(0, '$HOME/.claude/scripts')
try:
    from sqlite_hooks import log_tool_event, log_activity_event_simple
    import json

    # Log tool event
    result1 = log_tool_event(
        timestamp=$ts,
        tool_name="$TOOL_NAME",
        success=1,
        duration_ms=None,
        error_message=None,
        context='{"session":"${SESSION_ID:0:8}","model":"$MODEL","source":"hook"}'
    )

    # Log activity event
    result2 = log_activity_event_simple(
        timestamp=$ts,
        event_type="tool_use",
        data='{"tool":"$TOOL_NAME","model":"$MODEL"}',
        session_id="${SESSION_ID:0:8}"
    )

    print(f"[{time.strftime('%H:%M:%S')}] SQLite: tool={result1}, activity={result2}, name=$TOOL_NAME")
except Exception as e:
    print(f"[{time.strftime('%H:%M:%S')}] ERROR: {e}")
    import traceback
    traceback.print_exc()
PYEOF

# BACKUP: Write to JSONL (will be deprecated after 30 days)
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
