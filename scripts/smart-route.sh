#!/bin/bash
# Sovereign Terminal OS - DQ-Powered Smart Routing
# Based on: Astraea, ACE DQ Framework, ProactiveVA
# Usage: ai "your question"

KERNEL_DIR="$HOME/.claude/kernel"
DQ_SCORER="$KERNEL_DIR/dq-scorer.js"
COMPLEXITY_ANALYZER="$KERNEL_DIR/complexity-analyzer.js"
ACTIVITY_TRACKER="$KERNEL_DIR/activity-tracker.js"
PATTERN_DETECTOR="$KERNEL_DIR/pattern-detector.js"
IDENTITY_MANAGER="$KERNEL_DIR/identity-manager.js"
AI_LOG="$HOME/.claude/data/ai-routing.log"

# ═══════════════════════════════════════════════════════════════════════════
# DQ-POWERED ROUTING (Phase 1 - Sovereign Terminal OS)
# ═══════════════════════════════════════════════════════════════════════════

ai() {
  local query="$*"

  # Check if kernel is available
  if [[ -f "$DQ_SCORER" ]]; then
    # Use DQ-powered routing
    local result=$(node "$DQ_SCORER" route "$query" 2>/dev/null)

    if [[ -n "$result" ]]; then
      local model=$(echo "$result" | grep -o '"model": *"[^"]*"' | sed 's/"model": *"\([^"]*\)"/\1/')
      local dq_score=$(echo "$result" | grep -o '"score": *[0-9.]*' | head -1 | sed 's/"score": *//')
      local complexity=$(echo "$result" | grep -o '"complexity": *[0-9.]*' | head -1 | sed 's/"complexity": *//')

      # Log decision
      echo "$(date '+%H:%M:%S') DQ:$dq_score COMPLEXITY:$complexity → $model" >> "$AI_LOG"

      # Log to activity tracker for ProactiveVA
      if [[ -f "$ACTIVITY_TRACKER" ]]; then
        node "$ACTIVITY_TRACKER" query "$query" "$model" "$dq_score" "$complexity" 2>/dev/null &
      fi

      # Learn from query for Sovereign Identity
      if [[ -f "$IDENTITY_MANAGER" ]]; then
        node "$IDENTITY_MANAGER" learn "$query" "$model" "$dq_score" 2>/dev/null &
      fi

      # Route to model
      case "$model" in
        haiku)
          echo "[DQ:$dq_score] → haiku"
          cq -p "$query"
          ;;
        opus)
          echo "[DQ:$dq_score] → opus"
          co -p "$query"
          ;;
        *)
          echo "[DQ:$dq_score] → sonnet"
          cc -p "$query"
          ;;
      esac
      return
    fi
  fi

  # Fallback to legacy routing if kernel unavailable
  __ai_legacy "$query"
}

# Legacy routing (pre-kernel)
__ai_legacy() {
  local query="$*"
  local word_count=$(echo "$query" | wc -w | tr -d ' ')
  local has_code=$(echo "$query" | grep -cE '(function|class|implement|refactor|architect|design)')

  if [[ $word_count -lt 10 && $has_code -eq 0 ]]; then
    echo "→ haiku (legacy)"
    cq -p "$query"
  elif [[ $has_code -gt 0 || $word_count -gt 50 ]]; then
    echo "→ sonnet (legacy)"
    cc -p "$query"
  else
    echo "→ sonnet (default)"
    cc -p "$query"
  fi
}

# ═══════════════════════════════════════════════════════════════════════════
# DIRECT MODEL SHORTCUTS
# ═══════════════════════════════════════════════════════════════════════════

# Force specific model (bypass DQ routing)
ai-quick() { cq -p "$@"; }
ai-think() { co -p "$@"; }

# ═══════════════════════════════════════════════════════════════════════════
# FEEDBACK & STATS
# ═══════════════════════════════════════════════════════════════════════════

# Record feedback on last routing decision
ai-good() {
  if [[ -f "$DQ_SCORER" ]]; then
    node "$DQ_SCORER" feedback "$1" success
    echo "Feedback recorded: success"
  fi
}

ai-bad() {
  if [[ -f "$DQ_SCORER" ]]; then
    node "$DQ_SCORER" feedback "$1" failure
    echo "Feedback recorded: failure"
  fi
}

# Get routing statistics
ai-stats() {
  if [[ -f "$DQ_SCORER" ]]; then
    echo "═══ DQ ROUTING STATISTICS ═══"
    node "$DQ_SCORER" stats
  else
    echo "Kernel not available. Using legacy routing."
  fi
}

# Analyze a query without routing
ai-analyze() {
  if [[ -f "$COMPLEXITY_ANALYZER" ]]; then
    node "$COMPLEXITY_ANALYZER" "$@"
  else
    echo "Complexity analyzer not available."
  fi
}

# ═══════════════════════════════════════════════════════════════════════════
# KERNEL STATUS
# ═══════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════
# PROACTIVE SUGGESTIONS (Phase 4 - ProactiveVA)
# ═══════════════════════════════════════════════════════════════════════════

# Get proactive suggestions based on activity patterns
ai-suggest() {
  if [[ -f "$PATTERN_DETECTOR" ]]; then
    echo "═══ PROACTIVE SUGGESTIONS ═══"
    echo ""
    local result=$(node "$PATTERN_DETECTOR" suggest 2>/dev/null)

    if echo "$result" | grep -q '"hasContext": *true'; then
      local pattern_name=$(echo "$result" | grep -o '"patternName": *"[^"]*"' | head -1 | sed 's/"patternName": *"\([^"]*\)"/\1/')
      local pattern_icon=$(echo "$result" | grep -o '"patternIcon": *"[^"]*"' | head -1 | sed 's/"patternIcon": *"\([^"]*\)"/\1/')
      echo "$pattern_icon Detected: $pattern_name"
      echo ""
      echo "Suggestions:"
      # Parse and display suggestions
      echo "$result" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for i, s in enumerate(data.get('suggestions', [])[:5], 1):
    print(f\"  {i}. [{s['type']}] {s['label']}\")
    print(f\"     {s['desc']}\")
" 2>/dev/null
    else
      echo "No active patterns detected."
      echo "Keep working and I'll detect patterns in your activity."
    fi
  else
    echo "Pattern detector not available."
  fi
}

# View detected patterns
ai-patterns() {
  if [[ -f "$PATTERN_DETECTOR" ]]; then
    node "$PATTERN_DETECTOR" detect
  else
    echo "Pattern detector not available."
  fi
}

# View activity session
ai-session() {
  if [[ -f "$ACTIVITY_TRACKER" ]]; then
    node "$ACTIVITY_TRACKER" session
  else
    echo "Activity tracker not available."
  fi
}

# ═══════════════════════════════════════════════════════════════════════════
# SOVEREIGN IDENTITY (Phase 5)
# ═══════════════════════════════════════════════════════════════════════════

# View identity card
ai-identity() {
  if [[ -f "$IDENTITY_MANAGER" ]]; then
    echo "═══ SOVEREIGN IDENTITY ═══"
    echo ""
    node "$IDENTITY_MANAGER" card 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"DID: {data['did']}\")
print(f\"Owner: {data['profile'].get('owner', 'Unknown')}\")
print(f\"Org: {data['profile'].get('organization', 'Unknown')}\")
print()
print('Expertise:')
for domain, conf in list(data['expertise']['confidence'].items())[:5]:
    print(f'  {domain}: {conf}')
print()
print('Stats:')
print(f\"  Queries: {data['stats']['queries']}\")
print(f\"  Avg DQ: {data['stats']['avgDQ']}\")
print(f\"  Memories: {data['stats']['memories']}\")
print(f\"  Links: {data['stats']['links']}\")
print()
print(f\"Achievements: {data['achievements']['total']}\")
for a in data['achievements']['recent']:
    print(f\"  ✓ {a['name']}\")
" 2>/dev/null
  else
    echo "Identity manager not available."
  fi
}

# View expertise domains
ai-expertise() {
  if [[ -f "$IDENTITY_MANAGER" ]]; then
    node "$IDENTITY_MANAGER" expertise
  else
    echo "Identity manager not available."
  fi
}

# Check achievements
ai-achievements() {
  if [[ -f "$IDENTITY_MANAGER" ]]; then
    echo "═══ ACHIEVEMENTS ═══"
    echo ""
    node "$IDENTITY_MANAGER" achievements 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"Total: {data['total']}\")
print()
for a in data['all']:
    print(f\"✓ {a['name']}\")
    print(f\"  {a['desc']}\")
    print()
if data['new']:
    print('NEW ACHIEVEMENTS UNLOCKED!')
    for a in data['new']:
        print(f\"  🎉 {a['name']}\")
" 2>/dev/null
  else
    echo "Identity manager not available."
  fi
}

ai-kernel() {
  echo "═══════════════════════════════════════════════════════════"
  echo "  D-ECOSYSTEM :: SOVEREIGN TERMINAL OS"
  echo "  \"Let the invention be hidden in your vision\""
  echo "═══════════════════════════════════════════════════════════"
  echo ""

  if [[ -f "$KERNEL_DIR/state.json" ]]; then
    local version=$(grep '"version"' "$KERNEL_DIR/state.json" | sed 's/.*"\([0-9.]*\)".*/\1/')
    local phase=$(grep '"phase"' "$KERNEL_DIR/state.json" | sed 's/.*: *\([0-9]*\).*/\1/')
    echo "Version: $version (Phase $phase)"
    echo "Status:  Active | Sovereign by design"
  else
    echo "Status:  Not initialized"
  fi

  echo ""
  echo "Components:"
  if [[ -f "$DQ_SCORER" ]]; then
    echo "  ✓ DQ Scorer"
  else
    echo "  ✗ DQ Scorer"
  fi

  if [[ -f "$COMPLEXITY_ANALYZER" ]]; then
    echo "  ✓ Complexity Analyzer"
  else
    echo "  ✗ Complexity Analyzer"
  fi

  if [[ -f "$KERNEL_DIR/memory-graph.json" ]]; then
    echo "  ✓ Memory Graph (Zettelkasten)"
  else
    echo "  ✗ Memory Graph"
  fi

  if [[ -f "$KERNEL_DIR/token-optimizer.js" ]]; then
    echo "  ✓ Token Optimizer (Mem0)"
  else
    echo "  ✗ Token Optimizer"
  fi

  if [[ -f "$PATTERN_DETECTOR" ]]; then
    echo "  ✓ Pattern Detector (ProactiveVA)"
  else
    echo "  ✗ Pattern Detector"
  fi

  if [[ -f "$IDENTITY_MANAGER" ]]; then
    echo "  ✓ Sovereign Identity (D-Ecosystem)"
  else
    echo "  ✗ Sovereign Identity"
  fi

  if [[ -f "$KERNEL_DIR/dq-scores.jsonl" ]]; then
    local count=$(wc -l < "$KERNEL_DIR/dq-scores.jsonl" | tr -d ' ')
    echo "  ✓ Decision History ($count entries)"
  else
    echo "  ○ Decision History (empty)"
  fi

  echo ""
  echo "Commands:"
  echo "  ai \"query\"      - DQ-powered routing"
  echo "  ai-quick        - Force Haiku"
  echo "  ai-think        - Force Opus"
  echo "  ai-analyze      - Analyze complexity"
  echo "  ai-stats        - View statistics"
  echo "  ai-suggest      - Proactive suggestions"
  echo "  ai-patterns     - View detected patterns"
  echo "  ai-session      - View current session"
  echo "  ai-identity     - View sovereign identity"
  echo "  ai-expertise    - View expertise domains"
  echo "  ai-achievements - View achievements"
  echo "  ai-good/bad     - Record feedback"
}
