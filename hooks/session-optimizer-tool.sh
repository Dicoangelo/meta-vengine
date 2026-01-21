#!/bin/bash
# Session Optimizer Tool Hook
# Updates consumption tracking after tool use

set -e

KERNEL_DIR="$HOME/.claude/kernel"

# Update context message count
if [ -f "$KERNEL_DIR/session-engine.js" ]; then
    # Increment message count in context tracking
    node "$KERNEL_DIR/session-engine.js" context 2>/dev/null || true
fi

# Check if capacity thresholds are breached
if [ -f "$KERNEL_DIR/session-state.json" ]; then
    UTILIZATION=$(python3 -c "
import json
try:
    with open('$KERNEL_DIR/session-state.json') as f:
        state = json.load(f)
    print(state.get('budget', {}).get('utilizationPercent', 0))
except:
    print(0)
" 2>/dev/null || echo "0")

    # Alert if utilization is high
    if [ "${UTILIZATION%.*}" -ge 85 ] 2>/dev/null; then
        echo "[SESSION] Budget utilization at ${UTILIZATION}% - consider model downgrade" >&2
    fi
fi
