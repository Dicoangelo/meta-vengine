#!/bin/bash
# Centralized pricing configuration for shell scripts
# Source this file: source ~/.claude/config/pricing.sh

PRICING_FILE="$HOME/.claude/config/pricing.json"

# Extract values using jq (falls back to defaults if jq unavailable)
if command -v jq &> /dev/null && [ -f "$PRICING_FILE" ]; then
    OPUS_INPUT=$(jq -r '.models.opus.input' "$PRICING_FILE")
    OPUS_OUTPUT=$(jq -r '.models.opus.output' "$PRICING_FILE")
    SONNET_INPUT=$(jq -r '.models.sonnet.input' "$PRICING_FILE")
    SONNET_OUTPUT=$(jq -r '.models.sonnet.output' "$PRICING_FILE")
    HAIKU_INPUT=$(jq -r '.models.haiku.input' "$PRICING_FILE")
    HAIKU_OUTPUT=$(jq -r '.models.haiku.output' "$PRICING_FILE")
    PRICING_VERSION=$(jq -r '._meta.version' "$PRICING_FILE")
else
    # Fallback defaults (Opus 4.5 Jan 2026)
    OPUS_INPUT=5
    OPUS_OUTPUT=25
    SONNET_INPUT=3
    SONNET_OUTPUT=15
    HAIKU_INPUT=0.80
    HAIKU_OUTPUT=4
    PRICING_VERSION="fallback"
fi

# Helper function to get rates by model name
get_model_rates() {
    local model="$1"
    case "$model" in
        *haiku*) echo "$HAIKU_INPUT $HAIKU_OUTPUT" ;;
        *sonnet*) echo "$SONNET_INPUT $SONNET_OUTPUT" ;;
        *opus*) echo "$OPUS_INPUT $OPUS_OUTPUT" ;;
        *) echo "$SONNET_INPUT $SONNET_OUTPUT" ;;  # Default to sonnet
    esac
}

# Export for subprocesses
export OPUS_INPUT OPUS_OUTPUT SONNET_INPUT SONNET_OUTPUT HAIKU_INPUT HAIKU_OUTPUT PRICING_VERSION
