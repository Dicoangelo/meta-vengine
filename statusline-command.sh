#!/bin/bash
# Claude Code Statusline Command - Real-time Context Window Display
# Displays: Model | Progress Bar | % Used | Tokens | Directory | Session ID
# Performance: <50ms cold start, <2ms cache hit

set -euo pipefail

# ════════════════════════════════════════════════════════════════════════════
# CONFIGURATION & DEPENDENCIES
# ════════════════════════════════════════════════════════════════════════════

# Check for jq dependency
if ! command -v jq >/dev/null 2>&1; then
    echo "Statusline unavailable"
    exit 1
fi

# File paths
CACHE_DIR="${HOME}/.claude/tmp"
CACHE_FILE="${CACHE_DIR}/statusline-cache"
STATE_FILE="${HOME}/.claude/kernel/session-state.json"
ACTIVITY_LOG="${HOME}/.claude/activity.log"

# Cache TTL in seconds (10 seconds balances freshness with performance)
CACHE_TTL=10

# Ensure cache directory exists
mkdir -p "$CACHE_DIR" 2>/dev/null || true

# ════════════════════════════════════════════════════════════════════════════
# CACHING LAYER
# ════════════════════════════════════════════════════════════════════════════

is_cache_valid() {
    [[ -f "$CACHE_FILE" ]] || return 1
    local cache_time
    cache_time=$(head -n1 "$CACHE_FILE" 2>/dev/null || echo "0")
    local now
    now=$(date +%s)
    local age=$((now - cache_time))
    [[ $age -lt $CACHE_TTL ]]
}

get_cached_output() {
    tail -n1 "$CACHE_FILE" 2>/dev/null || echo ""
}

set_cache() {
    local output="$1"
    { date +%s; echo "$output"; } > "$CACHE_FILE" 2>/dev/null || true
}

# ════════════════════════════════════════════════════════════════════════════
# INPUT HANDLING - Support multiple data formats
# ════════════════════════════════════════════════════════════════════════════

read_input() {
    local stdin_data

    # Read from stdin (what Claude Code sends)
    # Check if stdin is available without blocking
    if [[ -p /dev/stdin ]] || [[ ! -t 0 ]]; then
        stdin_data=$(cat 2>/dev/null || echo "")
    else
        stdin_data=""
    fi

    # If we got valid JSON from stdin, use it
    if [[ -n "$stdin_data" ]] && echo "$stdin_data" | jq empty 2>/dev/null; then
        echo "$stdin_data"
        return 0
    fi

    # Fallback: construct from available sources
    local model="Sonnet"
    local session_id="unknown"
    local dir="$PWD"

    # Try to get session info from state file
    if [[ -f "$STATE_FILE" ]]; then
        session_id=$(jq -r '.window.id // "unknown"' "$STATE_FILE" 2>/dev/null || echo "unknown")
    fi

    # Try to detect model from activity log (last 100 lines)
    if [[ -f "$ACTIVITY_LOG" ]]; then
        local recent_model
        recent_model=$(tail -100 "$ACTIVITY_LOG" 2>/dev/null | grep -i "model:" | tail -1 | grep -oE "(Opus|Sonnet|Haiku)" || echo "")
        [[ -n "$recent_model" ]] && model="$recent_model"
    fi

    # Construct fallback JSON with estimates
    jq -n \
        --arg model "$model" \
        --arg dir "$dir" \
        --arg session "$session_id" \
        '{
            model: {display_name: $model},
            workspace: {current_dir: $dir},
            session_id: $session,
            context_window: {
                total_input_tokens: 0,
                total_output_tokens: 0,
                context_window_size: 200000,
                used_percentage: 0
            }
        }'
}

# ════════════════════════════════════════════════════════════════════════════
# FORMATTING FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════

# Shorten model name to single word
shorten_model() {
    local full_name="$1"
    case "$full_name" in
        *"Opus"*|*"opus"*)     echo "Opus" ;;
        *"Sonnet"*|*"sonnet"*) echo "Sonnet" ;;
        *"Haiku"*|*"haiku"*)   echo "Haiku" ;;
        *)                     echo "${full_name:0:10}" ;;
    esac
}

# Render progress bar: 20 characters, █ for filled, ░ for empty
render_progress_bar() {
    local percent="$1"
    local width=20

    # Clamp percentage to 0-100
    if (( percent > 100 )); then percent=100; fi
    if (( percent < 0 )); then percent=0; fi

    local filled=$(( (percent * width) / 100 ))
    local empty=$((width - filled))

    # Render filled portion
    if (( filled > 0 )); then
        printf '█%.0s' $(seq 1 $filled)
    fi

    # Render empty portion
    if (( empty > 0 )); then
        printf '░%.0s' $(seq 1 $empty)
    fi
}

# Format tokens with k/M suffix
format_tokens() {
    local tokens="$1"

    # Ensure it's a number
    if ! [[ "$tokens" =~ ^[0-9]+$ ]]; then
        echo "0"
        return
    fi

    if (( tokens >= 1000000 )); then
        # Format as M (millions), one decimal place
        printf "%.1fM" "$(echo "scale=1; $tokens / 1000000" | bc)"
    elif (( tokens >= 1000 )); then
        # Format as k (thousands), one decimal place
        printf "%.1fk" "$(echo "scale=1; $tokens / 1000" | bc)"
    else
        echo "$tokens"
    fi
}

# Shorten directory path for display
shorten_dir() {
    local dir="$1"

    # Replace home directory with ~
    dir="${dir/#$HOME/\~}"

    # Recognize common projects
    case "$dir" in
        *OS-App*)           echo "~/OS-App" ;;
        *CareerCoach*)      echo "~/CareerCoach" ;;
        *researchgravity*)  echo "~/researchgravity" ;;
        *)
            # Just use the basename if path is long
            if (( ${#dir} > 30 )); then
                basename "$dir"
            else
                echo "$dir"
            fi
            ;;
    esac
}

# ════════════════════════════════════════════════════════════════════════════
# MAIN RENDERING FUNCTION
# ════════════════════════════════════════════════════════════════════════════

render_statusline() {
    local json="$1"

    # Parse JSON fields with robust fallbacks
    local model_name
    model_name=$(echo "$json" | jq -r '
        .model.display_name //
        .model.name //
        .model //
        "Sonnet"
    ' 2>/dev/null || echo "Sonnet")

    local current_dir
    current_dir=$(echo "$json" | jq -r '
        .workspace.current_dir //
        .workspace.directory //
        .cwd //
        empty
    ' 2>/dev/null)
    current_dir="${current_dir:-$PWD}"

    local session_id
    session_id=$(echo "$json" | jq -r '
        .session_id //
        .session.id //
        "unknown"
    ' 2>/dev/null || echo "unknown")

    # Parse token usage - try multiple field paths
    local total_input
    total_input=$(echo "$json" | jq -r '
        .context_window.total_input_tokens //
        .usage.input_tokens //
        .tokens.input //
        0
    ' 2>/dev/null || echo "0")

    local total_output
    total_output=$(echo "$json" | jq -r '
        .context_window.total_output_tokens //
        .usage.output_tokens //
        .tokens.output //
        0
    ' 2>/dev/null || echo "0")

    local context_size
    context_size=$(echo "$json" | jq -r '
        .context_window.context_window_size //
        .context_window.size //
        .limits.context_window //
        200000
    ' 2>/dev/null || echo "200000")

    local percent
    percent=$(echo "$json" | jq -r '
        .context_window.used_percentage //
        .usage.percentage //
        0
    ' 2>/dev/null || echo "0")

    # Ensure numeric values
    total_input=${total_input//[!0-9]/}
    total_input=${total_input:-0}
    total_output=${total_output//[!0-9]/}
    total_output=${total_output:-0}
    context_size=${context_size//[!0-9]/}
    context_size=${context_size:-200000}

    # Calculate percentage if not provided
    local total_used=$((total_input + total_output))
    if [[ "$percent" == "0" ]] && [[ $total_used -gt 0 ]]; then
        percent=$(( (total_used * 100) / context_size ))
    fi
    percent=${percent//[!0-9]/}
    percent=${percent:-0}

    # Transform data
    local model
    model=$(shorten_model "$model_name")

    local progress_bar
    progress_bar=$(render_progress_bar "$percent")

    local used_fmt
    used_fmt=$(format_tokens "$total_used")

    local size_fmt
    size_fmt=$(format_tokens "$context_size")

    local dir
    dir=$(shorten_dir "$current_dir")

    local session_short
    session_short="${session_id:0:8}"

    # Render final output
    echo "$model | $progress_bar $percent% ($used_fmt/$size_fmt) | $dir | Session: $session_short"
}

# ════════════════════════════════════════════════════════════════════════════
# MAIN EXECUTION
# ════════════════════════════════════════════════════════════════════════════

main() {
    # Fast path: check cache validity
    if is_cache_valid; then
        get_cached_output
        return 0
    fi

    # Read and parse input
    local input_json
    input_json=$(read_input)

    # Render statusline
    local output
    output=$(render_statusline "$input_json")

    # Cache and return
    set_cache "$output"
    echo "$output"
}

# Silent execution: suppress all errors
main 2>/dev/null || echo "Statusline unavailable"
