#!/bin/bash
# Session Optimizer Start Hook - Meta-Vengine Enhanced
# Initializes window, loads budget, injects status, queries memory

set -e

KERNEL_DIR="$HOME/.claude/kernel"
DATA_DIR="$HOME/.claude/data"
SCRIPTS_DIR="$HOME/.claude/scripts"
MEMORY_DIR="$HOME/.claude/memory"

# Ensure directories exist
mkdir -p "$KERNEL_DIR" "$DATA_DIR" "$MEMORY_DIR"

# ══════════════════════════════════════════════════════════════
# 1. INITIALIZE SESSION ENGINE
# ══════════════════════════════════════════════════════════════

if [ -f "$KERNEL_DIR/session-engine.js" ]; then
    node "$KERNEL_DIR/session-engine.js" start 2>/dev/null || true
    node "$KERNEL_DIR/session-engine.js" sync 2>/dev/null || true
fi

# ══════════════════════════════════════════════════════════════
# 2. DETECT PROJECT CONTEXT
# ══════════════════════════════════════════════════════════════

detect_project() {
    local pwd="$PWD"

    case "$pwd" in
        *OS-App*) echo "os-app" ;;
        *CareerCoach*) echo "career" ;;
        *researchgravity*|*research*) echo "research" ;;
        *Metaventions*) echo "metaventions" ;;
        *agent-core*) echo "agent-core" ;;
        *.claude*) echo "claude-system" ;;
        *) echo "general" ;;
    esac
}

PROJECT=$(detect_project)

# ══════════════════════════════════════════════════════════════
# 3. SEMANTIC MEMORY QUERY
# ══════════════════════════════════════════════════════════════

query_relevant_memory() {
    local project="$1"
    local context_file="$DATA_DIR/session-context.md"

    # Build query based on project
    local query=""
    case "$project" in
        "os-app") query="agentic kernel react zustand 3D visualization" ;;
        "career") query="career coaching AI agents resume" ;;
        "research") query="research workflow papers arxiv sessions" ;;
        "metaventions") query="metaventions landing page AI" ;;
        "claude-system") query="routing system observatory ACE agents" ;;
        *) query="recent work patterns productivity" ;;
    esac

    # Query vector memory if available
    if [ -f "$KERNEL_DIR/memory-api.py" ]; then
        local results=$(python3 "$KERNEL_DIR/memory-api.py" query "$query" all 5 2>/dev/null)

        if [ -n "$results" ] && [ "$results" != "No results found" ]; then
            echo "## Relevant Context (from Memory)" > "$context_file"
            echo "" >> "$context_file"
            echo "$results" | head -20 >> "$context_file"
            echo "" >> "$context_file"
        fi
    fi
}

# Query memory in background to not slow down startup
(query_relevant_memory "$PROJECT" &) 2>/dev/null

# ══════════════════════════════════════════════════════════════
# 3b. SUPERMEMORY INJECTION
# ══════════════════════════════════════════════════════════════

inject_supermemory() {
    local project="$1"
    local supermemory="$HOME/.claude/supermemory/cli.py"

    if [ -f "$supermemory" ]; then
        # Inject context in background
        python3 "$supermemory" inject --project "$project" > "$DATA_DIR/session-context.md" 2>/dev/null &
    fi
}

# Run supermemory injection in background
(inject_supermemory "$PROJECT" &) 2>/dev/null

# ══════════════════════════════════════════════════════════════
# 4. CHECK TODAY'S BRIEF
# ══════════════════════════════════════════════════════════════

inject_daily_brief() {
    local today=$(date +%Y-%m-%d)
    local brief_file="$HOME/.claude/briefs/brief-$today.md"

    if [ -f "$brief_file" ]; then
        # Extract key stats from brief
        local sessions=$(grep "Sessions:" "$brief_file" 2>/dev/null | head -1)
        local pattern=$(grep "Top Pattern:" "$brief_file" 2>/dev/null | head -1)

        if [ -n "$sessions" ]; then
            echo "Today: $sessions | $pattern"
        fi
    fi
}

# ══════════════════════════════════════════════════════════════
# 5. OUTPUT SESSION STATUS
# ══════════════════════════════════════════════════════════════

# Compact status from session engine
if [ -f "$KERNEL_DIR/session-engine.js" ]; then
    node "$KERNEL_DIR/session-engine.js" compact 2>/dev/null || echo "Session optimizer initialized"
fi

# Show brief excerpt if available
BRIEF_STATUS=$(inject_daily_brief)
if [ -n "$BRIEF_STATUS" ]; then
    echo "$BRIEF_STATUS"
fi

# Show flow state if available
FLOW_STATE_FILE="$KERNEL_DIR/cognitive-os/flow-state.json"
if [ -f "$FLOW_STATE_FILE" ]; then
    FLOW_STATE=$(grep -o '"state": *"[^"]*"' "$FLOW_STATE_FILE" 2>/dev/null | sed 's/"state": *"\([^"]*\)"/\1/')
    FLOW_SCORE=$(grep -o '"score": *[0-9.]*' "$FLOW_STATE_FILE" 2>/dev/null | sed 's/"score": *//')
    if [ -n "$FLOW_STATE" ]; then
        echo "Project: $PROJECT | Memory: queried"
        echo "Flow: $FLOW_STATE ($FLOW_SCORE)"
    else
        echo "Project: $PROJECT | Memory: queried"
    fi
else
    echo "Project: $PROJECT | Memory: queried"
fi

# ══════════════════════════════════════════════════════════════
# AUTOMATED MITIGATIONS: Non-blocking pre-flight checks
# ══════════════════════════════════════════════════════════════

run_preflight_checks() {
    [ -f "$HOME/.claude/scripts/session-lock.sh" ] && source "$HOME/.claude/scripts/session-lock.sh"
    [ -f "$HOME/.claude/scripts/permission-check.sh" ] && source "$HOME/.claude/scripts/permission-check.sh"

    # Run checks in background to not block session start
    (
        acquire_session_lock "$$" 2>/dev/null
        check_claude_paths 2>/dev/null
        check_parallel_sessions 2>/dev/null
    ) &
}

run_preflight_checks
