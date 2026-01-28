#!/bin/bash
# Enhanced Post-Tool Hook - Captures full tool details in real-time
# Tracks: file paths, bash commands, success/failure, detailed metadata

KERNEL_DIR="$HOME/.claude/kernel"
DATA_DIR="$HOME/.claude/data"
mkdir -p "$DATA_DIR"

# Get hook data from environment
TOOL_NAME="${CLAUDE_TOOL_NAME:-unknown}"
TOOL_INPUT="${CLAUDE_TOOL_INPUT:-}"
TOOL_OUTPUT="${CLAUDE_TOOL_OUTPUT:-}"
SESSION_ID="${CLAUDE_SESSION_ID:-$(date +%s)}"
MODEL="${CLAUDE_MODEL:-sonnet}"
EXIT_CODE="${CLAUDE_TOOL_EXIT_CODE:-0}"

ts=$(date +%s)

# ═══════════════════════════════════════════════════════════════
# 1. ENHANCED TOOL-USAGE.JSONL - Now with details
# ═══════════════════════════════════════════════════════════════

# Extract file path for Write/Edit/Read tools
file_path=""
case "$TOOL_NAME" in
    Write|Edit|Read)
        # Extract file_path from tool input JSON
        file_path=$(echo "$TOOL_INPUT" | grep -o '"file_path":"[^"]*"' | sed 's/"file_path":"\([^"]*\)"/\1/' | head -1)
        ;;
    Bash)
        # Extract command from tool input
        command=$(echo "$TOOL_INPUT" | grep -o '"command":"[^"]*"' | sed 's/"command":"\([^"]*\)"/\1/' | head -1)
        ;;
esac

# Determine success/failure
success="true"
if [[ "$EXIT_CODE" != "0" ]] || echo "$TOOL_OUTPUT" | grep -qi "error\|failed\|exception"; then
    success="false"
fi

# Log detailed tool usage

# PRIMARY: Write to SQLite (source of truth)
python3 << PYEOF
import sys
sys.path.insert(0, '$HOME/.claude/scripts')
try:
    from sqlite_hooks import log_tool_event

    # Build context JSON
    import json
    context = {
        "file_path": "$file_path",
        "command": "${command:-}",
        "session": "${SESSION_ID:0:8}",
        "model": "$MODEL"
    }

    log_tool_event(
        timestamp=$ts,
        tool_name="$TOOL_NAME",
        success=$([ "$success" == "true" ] && echo 1 || echo 0),
        duration_ms=None,
        error_message=$([ "$success" == "false" ] && echo "\"Exit code $EXIT_CODE\"" || echo "None"),
        context=json.dumps(context)
    )
except Exception as e:
    # Fail silently to not block tool execution
    pass
PYEOF

# BACKUP: Write to JSONL (will be deprecated after 30 days)
entry=$(cat <<EOF
{"ts":$ts,"tool":"$TOOL_NAME","session":"${SESSION_ID:0:8}","model":"$MODEL","source":"hook","file_path":"$file_path","command":"${command:-}","success":$success,"exit_code":$EXIT_CODE}
EOF
)
echo "$entry" >> "$DATA_DIR/tool-usage.jsonl" 2>/dev/null

# ═══════════════════════════════════════════════════════════════
# 2. TOOL-SUCCESS.JSONL - Real-time success tracking
# ═══════════════════════════════════════════════════════════════

success_entry=$(cat <<EOF
{"ts":$ts,"tool":"$TOOL_NAME","success":$success,"exit_code":$EXIT_CODE,"session":"${SESSION_ID:0:8}"}
EOF
)
echo "$success_entry" >> "$DATA_DIR/tool-success.jsonl" 2>/dev/null

# ═══════════════════════════════════════════════════════════════
# 3. COMMAND-USAGE.JSONL - Track bash commands
# ═══════════════════════════════════════════════════════════════

if [[ "$TOOL_NAME" == "Bash" && -n "$command" ]]; then
    # Extract base command (first word)
    base_cmd=$(echo "$command" | awk '{print $1}' | sed 's/[^a-zA-Z0-9_-]//g')

    cmd_entry=$(cat <<EOF
{"ts":$ts,"command":"$base_cmd","full_command":"$command","success":$success,"session":"${SESSION_ID:0:8}"}
EOF
)
    echo "$cmd_entry" >> "$DATA_DIR/command-usage.jsonl" 2>/dev/null
fi

# ═══════════════════════════════════════════════════════════════
# 4. ACTIVITY-EVENTS.JSONL - Enhanced with details
# ═══════════════════════════════════════════════════════════════

# PRIMARY: Write to SQLite (source of truth)
python3 << PYEOF
import sys
sys.path.insert(0, '$HOME/.claude/scripts')
try:
    from sqlite_hooks import log_activity_event_simple
    import json

    # Build activity data JSON
    data = {
        "tool": "$TOOL_NAME",
        "file_path": "$file_path",
        "command": "${command:-}",
        "success": "$success",
        "pwd": "$PWD"
    }

    log_activity_event_simple(
        timestamp=$ts,
        event_type="tool_use",
        data=json.dumps(data),
        session_id="${SESSION_ID:0:8}"
    )
except Exception as e:
    # Fail silently to not block tool execution
    pass
PYEOF

# BACKUP: Write to JSONL (will be deprecated after 30 days)
activity_entry=$(cat <<EOF
{"ts":$ts,"type":"tool_use","tool":"$TOOL_NAME","file_path":"$file_path","command":"${command:-}","success":$success,"pwd":"$PWD"}
EOF
)
echo "$activity_entry" >> "$DATA_DIR/activity-events.jsonl" 2>/dev/null

# ═══════════════════════════════════════════════════════════════
# 5. Legacy activity tracker (keep for compatibility)
# ═══════════════════════════════════════════════════════════════

if [[ -f "$KERNEL_DIR/activity-tracker.js" ]]; then
  node "$KERNEL_DIR/activity-tracker.js" tool "$TOOL_NAME" "$MODEL" 2>/dev/null &
fi

# Feed identity manager for learning
if [[ -f "$KERNEL_DIR/identity-manager.js" && -n "$TOOL_INPUT" ]]; then
  node "$KERNEL_DIR/identity-manager.js" learn "$TOOL_INPUT" "$MODEL" 0.5 2>/dev/null &
fi
