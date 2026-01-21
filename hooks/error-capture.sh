#!/bin/bash
# Error Capture Hook
# Detects errors from tool outputs and logs them automatically
#
# Called by PostToolUse hooks with tool output piped to stdin

KERNEL_DIR="$HOME/.claude/kernel"
ERROR_TRACKER="$KERNEL_DIR/error-tracker.js"

# Read tool output from environment or stdin
TOOL_NAME="${CLAUDE_TOOL_NAME:-unknown}"
TOOL_OUTPUT="${CLAUDE_TOOL_OUTPUT:-}"
EXIT_CODE="${CLAUDE_EXIT_CODE:-0}"

# If no output in env, try reading from recent activity
if [[ -z "$TOOL_OUTPUT" ]]; then
    TOOL_OUTPUT=$(tail -5 ~/.claude/activity.log 2>/dev/null | tr '\n' ' ')
fi

# Error patterns to check
ERROR_PATTERNS=(
    "error:"
    "Error:"
    "ERROR"
    "failed"
    "Failed"
    "FAILED"
    "permission denied"
    "not found"
    "No such file"
    "ENOENT"
    "EACCES"
    "fatal:"
    "npm ERR!"
    "SyntaxError"
    "TypeError"
    "ReferenceError"
    "command not found"
    "Cannot find"
    "Module not found"
    "exit code 1"
    "timed out"
)

# Check if output contains error patterns
contains_error=false
matched_pattern=""

for pattern in "${ERROR_PATTERNS[@]}"; do
    if echo "$TOOL_OUTPUT" | grep -qi "$pattern"; then
        contains_error=true
        matched_pattern="$pattern"
        break
    fi
done

# Also check exit code
if [[ "$EXIT_CODE" != "0" && "$EXIT_CODE" != "" ]]; then
    contains_error=true
    matched_pattern="exit_code_$EXIT_CODE"
fi

# If error detected, log it
if $contains_error; then
    # Extract a snippet of the error
    error_snippet=$(echo "$TOOL_OUTPUT" | grep -i -m1 "$matched_pattern" | head -c 200)

    # Log to jsonl immediately
    ts=$(date +%s)
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    entry="{\"ts\":$ts,\"timestamp\":\"$timestamp\",\"tool\":\"$TOOL_NAME\",\"pattern\":\"$matched_pattern\",\"snippet\":\"$(echo "$error_snippet" | tr '"' "'" | tr '\n' ' ')\"}"
    echo "$entry" >> ~/.claude/data/errors.jsonl 2>/dev/null

    # Run full analysis for high-severity errors
    if echo "$TOOL_OUTPUT" | grep -qiE "(fatal|critical|segmentation|permission denied|EACCES)"; then
        node "$ERROR_TRACKER" detect "$TOOL_OUTPUT" 2>/dev/null &
    fi

    # Signal that an error was detected (for other hooks)
    echo "ERROR_DETECTED" > ~/.claude/data/.last-error-flag
    echo "$error_snippet" > ~/.claude/data/.last-error-snippet
fi
