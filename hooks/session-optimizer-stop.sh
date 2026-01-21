#!/bin/bash
# Session Optimizer Stop Hook
# Analyzes session, updates patterns, runs feedback loop

set -e

KERNEL_DIR="$HOME/.claude/kernel"
SCRIPTS_DIR="$HOME/.claude/scripts"
OBSERVATORY_DIR="$SCRIPTS_DIR/observatory"
LOGS_DIR="$HOME/.claude/logs"

# Ensure log directory exists
mkdir -p "$LOGS_DIR"

LOG_FILE="$LOGS_DIR/session-optimizer.log"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOG_FILE"
}

log "Session optimizer stop hook started"

# End session in session-engine
if [ -f "$KERNEL_DIR/session-engine.js" ]; then
    node "$KERNEL_DIR/session-engine.js" end 2>/dev/null || true
    log "Session engine end called"
fi

# Run session agents analysis
if [ -d "$OBSERVATORY_DIR/session-agents" ]; then
    # Run each agent and collect results
    for agent in window_pattern budget_efficiency capacity_forecast task_prioritization model_recommendation session_health; do
        agent_file="$OBSERVATORY_DIR/session-agents/${agent}_agent.py"
        if [ -f "$agent_file" ]; then
            python3 "$agent_file" >> "$LOGS_DIR/session-agents.log" 2>&1 || true
        fi
    done
    log "Session agents analysis complete"
fi

# Run feedback loop analysis (but don't auto-apply - just analyze)
if [ -f "$SCRIPTS_DIR/session-optimizer/feedback_loop.py" ]; then
    python3 "$SCRIPTS_DIR/session-optimizer/feedback_loop.py" analyze 7 >> "$LOG_FILE" 2>&1 || true
    log "Feedback loop analysis complete"
fi

# Generate session summary
if [ -f "$KERNEL_DIR/session-engine.js" ]; then
    SUMMARY=$(node "$KERNEL_DIR/session-engine.js" status 2>/dev/null || echo "No summary available")
    log "Session summary: $SUMMARY"
fi

log "Session optimizer stop hook completed"
