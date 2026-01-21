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

    # ══════════════════════════════════════════════════════════════
    # SUPERMEMORY: Auto-suggest solutions for errors
    # ══════════════════════════════════════════════════════════════
    suggest_error_solution() {
        local error_text="$1"
        local supermemory="$HOME/.claude/supermemory/cli.py"

        if [ -f "$supermemory" ] && [ -n "$error_text" ]; then
            local solution=$(python3 "$supermemory" errors "$error_text" 2>/dev/null | head -5)
            if [ -n "$solution" ]; then
                echo ""
                echo "━━━ Supermemory Suggestion ━━━"
                echo "$solution"
                echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            fi
        fi
    }

    # Auto-suggest solution for detected error
    suggest_error_solution "$error_snippet"

    # ══════════════════════════════════════════════════════════════
    # AUTO-RECOVERY: Trigger recovery engine for high-severity errors
    # ══════════════════════════════════════════════════════════════
    trigger_recovery() {
        local error_snippet="$1"
        local category="$2"
        local recovery_engine="$HOME/.claude/kernel/recovery-engine.py"

        # Run recovery engine in background (non-blocking)
        if [ -f "$recovery_engine" ]; then
            (
                python3 "$recovery_engine" \
                    recover \
                    --error "$error_snippet" \
                    ${category:+--category "$category"} \
                    2>/dev/null
            ) &
        fi
    }

    # Detect category for targeted recovery
    detect_category() {
        local snippet="$1"
        if echo "$snippet" | grep -qiE "(fatal:|git|repository|merge)"; then
            echo "git"
        elif echo "$snippet" | grep -qiE "(lock|race|parallel|session)"; then
            echo "concurrency"
        elif echo "$snippet" | grep -qiE "(permission denied|EACCES|chmod)"; then
            echo "permissions"
        elif echo "$snippet" | grep -qiE "(quota|rate limit|exceeded)"; then
            echo "quota"
        elif echo "$snippet" | grep -qiE "(SIGKILL|segfault|killed)"; then
            echo "crash"
        elif echo "$snippet" | grep -qiE "(overflow|recursion|maximum call)"; then
            echo "recursion"
        elif echo "$snippet" | grep -qiE "(SyntaxError|TypeError|parse)"; then
            echo "syntax"
        fi
    }

    # Only trigger for high-severity errors
    if echo "$error_snippet" | grep -qiE "(fatal|permission denied|race condition|lock|SIGKILL|EACCES|index\.lock|another.*process)"; then
        detected_category=$(detect_category "$error_snippet")
        trigger_recovery "$error_snippet" "$detected_category"
    fi
fi
