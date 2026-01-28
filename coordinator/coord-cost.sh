#!/bin/bash
# coord-cost.sh - Estimate costs for coordinated multi-agent tasks
# Usage: coord-cost <strategy> "task description"

set -euo pipefail

# Pricing per message estimate (USD)
HAIKU_COST=0.004
SONNET_COST=0.017
OPUS_COST=0.027

# Color codes for output
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

show_usage() {
    cat <<EOF
Usage: coord-cost <strategy> "task description"

Strategies:
  research   - 3 haiku agents for research
  implement  - 2 sonnet agents for implementation (default)
  review     - 2 agents (1 sonnet builder + 1 haiku reviewer)
  full       - 5 agents (2 haiku research + 1 sonnet build + 2 haiku review)

Example:
  coord-cost research "How does routing work?"
  coord-cost implement "Add cost tracking to orchestrator"
EOF
    exit 1
}

# Validate arguments
if [ $# -lt 2 ]; then
    show_usage
fi

STRATEGY="$1"
TASK_DESC="$2"

# Calculate costs based on strategy
calculate_cost() {
    local strategy="$1"
    local haiku_count=0
    local sonnet_count=0
    local opus_count=0
    local agent_details=""

    case "$strategy" in
        research)
            haiku_count=3
            agent_details="    3× haiku  @ \$${HAIKU_COST}/msg = \$$(printf "%.3f" $(echo "$haiku_count * $HAIKU_COST" | bc -l))"
            ;;
        implement)
            sonnet_count=2
            agent_details="    2× sonnet @ \$${SONNET_COST}/msg = \$$(printf "%.3f" $(echo "$sonnet_count * $SONNET_COST" | bc -l))"
            ;;
        review)
            sonnet_count=1
            haiku_count=1
            agent_details="    1× sonnet @ \$${SONNET_COST}/msg = \$$(printf "%.3f" $(echo "$sonnet_count * $SONNET_COST" | bc -l))
    1× haiku  @ \$${HAIKU_COST}/msg = \$$(printf "%.3f" $(echo "$haiku_count * $HAIKU_COST" | bc -l))"
            ;;
        full)
            haiku_count=4
            sonnet_count=1
            agent_details="    2× haiku  @ \$${HAIKU_COST}/msg (research) = \$$(printf "%.3f" $(echo "2 * $HAIKU_COST" | bc -l))
    1× sonnet @ \$${SONNET_COST}/msg (build)    = \$$(printf "%.3f" $(echo "$SONNET_COST" | bc -l))
    2× haiku  @ \$${HAIKU_COST}/msg (review)    = \$$(printf "%.3f" $(echo "2 * $HAIKU_COST" | bc -l))"
            ;;
        *)
            echo "Error: Unknown strategy '$strategy'"
            echo ""
            show_usage
            ;;
    esac

    # Calculate total
    local total=$(echo "$haiku_count * $HAIKU_COST + $sonnet_count * $SONNET_COST + $opus_count * $OPUS_COST" | bc -l)

    # Format output box
    cat <<EOF

╔══════════════════════════════════════════════════╗
║  COORD COST ESTIMATE                             ║
╠══════════════════════════════════════════════════╣
║  Strategy: $(printf "%-38s" "$strategy")║
║  Task: $(printf "%-42s" "${TASK_DESC:0:42}")║
╠══════════════════════════════════════════════════╣
║  Agents:                                         ║
$(echo "$agent_details" | while IFS= read -r line; do printf "║  %-46s║\n" "$line"; done)
║  ────────────────────────────────────            ║
║  TOTAL ESTIMATE: \$$(printf "%-32.3f" "$total")║
╚══════════════════════════════════════════════════╝

${DIM}Note: Estimate is per message. Actual cost depends on conversation length.${RESET}
${DIM}Multi-turn conversations multiply this base cost.${RESET}

EOF
}

# Main execution
calculate_cost "$STRATEGY"

# Only show prompt if running in interactive terminal
if [ -t 0 ]; then
    echo -e "${DIM}Tip: Add --dry-run to skip this prompt${RESET}"
    echo ""
    read -p "Proceed with coordination? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Starting coordination with strategy: $STRATEGY"
        echo "Task: $TASK_DESC"
        # TODO: Call actual coordinator here
        # python3 ~/.claude/coordinator/orchestrator.py "$STRATEGY" "$TASK_DESC"
    else
        echo "Cancelled."
        exit 0
    fi
else
    echo "Non-interactive mode - estimation only."
fi
