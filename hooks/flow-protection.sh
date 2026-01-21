#!/bin/bash
# Flow Protection Hook
# Checks if user is in flow state before allowing interrupts
#
# Usage in hooks:
#   bash ~/.claude/hooks/flow-protection.sh && <interrupt-command>
#
# Returns:
#   0 (success) = NOT in flow, allow interrupt
#   1 (failure) = IN flow, suppress interrupt

FLOW_STATE_FILE="$HOME/.claude/kernel/cognitive-os/flow-state.json"
COS_SCRIPT="$HOME/.claude/kernel/cognitive-os.py"

# Fast path: check quick-access flow state file
if [[ -f "$FLOW_STATE_FILE" ]]; then
    # Check if file is recent (less than 5 minutes old)
    if [[ $(find "$FLOW_STATE_FILE" -mmin -5 2>/dev/null) ]]; then
        # Parse in_flow from JSON
        in_flow=$(grep -o '"in_flow": *[a-z]*' "$FLOW_STATE_FILE" | sed 's/"in_flow": *//')
        if [[ "$in_flow" == "true" ]]; then
            # In flow - suppress interrupt
            exit 1
        else
            # Not in flow - allow interrupt
            exit 0
        fi
    fi
fi

# Slow path: compute flow state if file is stale or missing
if [[ -f "$COS_SCRIPT" ]]; then
    python3 "$COS_SCRIPT" check-flow --quiet 2>/dev/null
    # check-flow returns 0 when IN flow, 1 when NOT in flow
    if [[ $? -eq 0 ]]; then
        exit 1  # In flow - suppress
    else
        exit 0  # Not in flow - allow
    fi
fi

# No cognitive OS available, allow all interrupts
exit 0
