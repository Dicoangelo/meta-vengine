#!/bin/bash
# CCC Intelligence Advisor Hook
# Runs on session start to provide predictive guidance

INTEL_SCRIPT="$HOME/.claude/scripts/ccc-intelligence-layer.py"

if [ -f "$INTEL_SCRIPT" ]; then
    # Get quick status
    STATUS=$(python3 "$INTEL_SCRIPT" 2>/dev/null)
    
    if [ -n "$STATUS" ]; then
        echo ""
        echo "━━━ Intelligence Advisor ━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "$STATUS"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
    fi
fi
