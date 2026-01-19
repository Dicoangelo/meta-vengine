#!/bin/bash
# Autonomous DQ Router - Makes smart routing the default
# Part of: Sovereign Terminal OS v1.5.0
# Based on: ACE DQ Framework, Astraea

KERNEL_DIR="$HOME/.claude/kernel"
DQ_SCORER="$KERNEL_DIR/dq-scorer.js"
CLAUDE_BIN="/Users/dicoangelo/.local/bin/claude"
METRICS_LOG="$HOME/.claude/data/routing-metrics.jsonl"

# ═══════════════════════════════════════════════════════════════════════════
# ROUTING INTERCEPTOR
# ═══════════════════════════════════════════════════════════════════════════

# Check for manual model override
if [[ "$*" == *"--model"* ]]; then
  # User explicitly chose model, bypass routing
  exec "$CLAUDE_BIN" "$@"
fi

# Extract query from arguments
query=""
for ((i=1; i<=$#; i++)); do
  if [[ "${!i}" == "-p" ]]; then
    next=$((i+1))
    query="${!next}"
    break
  fi
done

# If no query detected or kernel unavailable, pass through
if [[ -z "$query" ]] || [[ ! -f "$DQ_SCORER" ]]; then
  exec "$CLAUDE_BIN" "$@"
fi

# ═══════════════════════════════════════════════════════════════════════════
# DQ-POWERED ROUTING
# ═══════════════════════════════════════════════════════════════════════════

# Measure routing latency (milliseconds)
if [[ "$OSTYPE" == "darwin"* ]]; then
  # macOS: use python for microsecond precision
  start_time=$(python3 -c 'import time; print(int(time.time() * 1000))')
else
  # Linux: date +%s%3N works
  start_time=$(date +%s%3N)
fi

# Route via DQ scorer
result=$(node "$DQ_SCORER" route "$query" 2>/dev/null)

# Calculate latency
if [[ "$OSTYPE" == "darwin"* ]]; then
  end_time=$(python3 -c 'import time; print(int(time.time() * 1000))')
else
  end_time=$(date +%s%3N)
fi
routing_latency=$((end_time - start_time))

# Parse routing decision
if command -v jq &> /dev/null && [[ -n "$result" ]]; then
  # Use jq if available
  model=$(echo "$result" | jq -r '.model // "sonnet"')
  dq_score=$(echo "$result" | jq -r '.dq.score // 0.5')
  complexity=$(echo "$result" | jq -r '.complexity // 0.5')
else
  # Fallback: grep parsing
  model=$(echo "$result" | grep -o '"model": *"[^"]*"' | sed 's/"model": *"\([^"]*\)"/\1/' | head -1)
  dq_score=$(echo "$result" | grep -o '"score": *[0-9.]*' | sed 's/"score": *//' | head -1)
  complexity=$(echo "$result" | grep -o '"complexity": *[0-9.]*' | sed 's/"complexity": *//' | head -1)

  # Defaults if parsing failed
  model=${model:-sonnet}
  dq_score=${dq_score:-0.5}
  complexity=${complexity:-0.5}
fi

# Log metrics (append to JSONL)
if [[ -w "$METRICS_LOG" ]] || [[ ! -e "$METRICS_LOG" ]]; then
  # Generate query hash (md5 or fallback)
  if command -v md5 &> /dev/null; then
    query_hash=$(echo -n "$query" | md5 | cut -d' ' -f1)
  elif command -v md5sum &> /dev/null; then
    query_hash=$(echo -n "$query" | md5sum | cut -d' ' -f1)
  else
    query_hash=$(echo -n "$query" | cksum | cut -d' ' -f1)
  fi

  echo "{\"ts\":$(date +%s),\"query_hash\":\"$query_hash\",\"complexity\":$complexity,\"model\":\"$model\",\"dq\":$dq_score,\"latency_ms\":$routing_latency}" >> "$METRICS_LOG"
fi

# Show decision to user (stderr so it doesn't interfere with output)
echo "[DQ:$dq_score C:$complexity] → $model" >&2

# ═══════════════════════════════════════════════════════════════════════════
# FEEDBACK TRACKING (for automated learning)
# ═══════════════════════════════════════════════════════════════════════════

# Export variables for feedback hook to detect failures
export __AI_LAST_QUERY="$query"
export __AI_LAST_MODEL="$model"
export __AI_LAST_DQ="$dq_score"
export __AI_LAST_TIMESTAMP=$(date +%s)

# ═══════════════════════════════════════════════════════════════════════════
# INVOKE CLAUDE WITH SELECTED MODEL
# ═══════════════════════════════════════════════════════════════════════════

# Reconstruct arguments with selected model
args=()
skip_next=false

for ((i=1; i<=$#; i++)); do
  if [[ "$skip_next" == "true" ]]; then
    skip_next=false
    continue
  fi

  arg="${!i}"

  # Skip -p and its value (will be re-added)
  if [[ "$arg" == "-p" ]]; then
    skip_next=true
    continue
  fi

  args+=("$arg")
done

# Invoke with selected model
exec "$CLAUDE_BIN" --model "$model" -p "$query" "${args[@]}"
