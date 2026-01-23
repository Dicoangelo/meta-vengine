#!/bin/bash
# Smart Session Starter
# Usage:
#   a              → Interactive sonnet (safe default)
#   a "query"      → One-shot with DQ routing
#   a -o           → Interactive opus (complex work)
#   a -q           → Interactive haiku (quick stuff)
#   a -t "task"    → Describe task, get routed to right model

KERNEL_DIR="$HOME/.claude/kernel"
DQ_SCORER="$KERNEL_DIR/dq-scorer.js"

# Parse flags
FORCE_MODEL=""
TASK_DESC=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -o|--opus)   FORCE_MODEL="opus"; shift ;;
    -s|--sonnet) FORCE_MODEL="sonnet"; shift ;;
    -q|--haiku)  FORCE_MODEL="haiku"; shift ;;
    -t|--task)   TASK_DESC="$2"; shift 2 ;;
    -h|--help)
      echo "Smart Session Starter"
      echo ""
      echo "Usage:"
      echo "  a              Interactive sonnet (default)"
      echo "  a \"query\"      One-shot with DQ routing"
      echo "  a -o           Interactive opus"
      echo "  a -q           Interactive haiku"
      echo "  a -t \"task\"    Route based on task description"
      echo ""
      echo "Examples:"
      echo "  a                          # Start sonnet session"
      echo "  a \"what is a monad\"        # Quick answer, routes to haiku"
      echo "  a -o                       # Start opus for complex work"
      echo "  a -t \"architect new auth\"  # Routes to opus (complex)"
      exit 0
      ;;
    *)
      # Treat remaining args as query
      break
      ;;
  esac
done

# Function to route based on task/query
route_query() {
  local query="$1"

  if [[ -f "$DQ_SCORER" ]]; then
    local result=$(node "$DQ_SCORER" route "$query" 2>/dev/null)
    local model=$(echo "$result" | grep -o '"model": *"[^"]*"' | sed 's/"model": *"\([^"]*\)"/\1/')
    local dq=$(echo "$result" | grep -o '"score": *[0-9.]*' | head -1 | sed 's/"score": *//')
    echo "$model:$dq"
  else
    # Fallback: simple heuristics
    local words=$(echo "$query" | wc -w | tr -d ' ')
    local complex=$(echo "$query" | grep -ciE 'architect|design|implement|refactor|complex|system|integrate')

    if [[ $complex -gt 0 || $words -gt 50 ]]; then
      echo "opus:0.8"
    elif [[ $words -lt 15 ]]; then
      echo "haiku:0.6"
    else
      echo "sonnet:0.7"
    fi
  fi
}

# Function to start session
start_session() {
  local model="$1"
  local query="$2"

  echo "[→ $model]"

  case "$model" in
    haiku)
      if [[ -n "$query" ]]; then
        cq -p "$query"
      else
        cq
      fi
      ;;
    opus)
      if [[ -n "$query" ]]; then
        co -p "$query"
      else
        co
      fi
      ;;
    *)
      if [[ -n "$query" ]]; then
        cc -p "$query"
      else
        cc
      fi
      ;;
  esac
}

# Main logic
if [[ -n "$FORCE_MODEL" ]]; then
  # Forced model
  start_session "$FORCE_MODEL" "$*"

elif [[ -n "$TASK_DESC" ]]; then
  # Route based on task description
  result=$(route_query "$TASK_DESC")
  model="${result%%:*}"
  dq="${result##*:}"
  echo "[DQ:$dq] Routing to $model for: $TASK_DESC"
  start_session "$model"

elif [[ $# -gt 0 ]]; then
  # One-shot query - route via DQ
  query="$*"
  result=$(route_query "$query")
  model="${result%%:*}"
  dq="${result##*:}"
  echo "[DQ:$dq → $model]"
  start_session "$model" "$query"

else
  # No args - default to sonnet for interactive
  echo "[Default → sonnet] (use -o for opus, -q for haiku)"
  start_session "sonnet"
fi
