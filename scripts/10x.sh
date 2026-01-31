#!/bin/bash
# 10x Power Dashboard - Unified Claude Code Command
# Usage: 10x [quick|full|boost]

set -e

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color
BOLD='\033[1m'

divider() {
  echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

header() {
  echo ""
  divider
  echo -e "${BOLD}${MAGENTA}  $1${NC}"
  divider
}

MODE="${1:-quick}"

header "🚀 10X POWER DASHBOARD"
echo -e "  Mode: ${YELLOW}$MODE${NC} | $(date '+%Y-%m-%d %H:%M')"

# 1. Cognitive State
header "🧠 COGNITIVE STATE"
if command -v cos &> /dev/null; then
  cos state 2>/dev/null || echo "  Cognitive OS not responding"
else
  # Fallback: determine time-based state
  HOUR=$(date +%H)
  if [ $HOUR -ge 5 ] && [ $HOUR -lt 9 ]; then
    echo -e "  Mode: ${GREEN}morning${NC} | Energy: High | Best for: Planning"
  elif [ $HOUR -ge 9 ] && [ $HOUR -lt 12 ]; then
    echo -e "  Mode: ${GREEN}peak${NC} | Energy: Maximum | Best for: Complex coding"
  elif [ $HOUR -ge 12 ] && [ $HOUR -lt 14 ]; then
    echo -e "  Mode: ${YELLOW}dip${NC} | Energy: Low | Best for: Reviews, docs"
  elif [ $HOUR -ge 14 ] && [ $HOUR -lt 18 ]; then
    echo -e "  Mode: ${GREEN}peak${NC} | Energy: High | Best for: Implementation"
  elif [ $HOUR -ge 18 ] && [ $HOUR -lt 22 ]; then
    echo -e "  Mode: ${CYAN}evening${NC} | Energy: Medium | Best for: Creative work"
  else
    echo -e "  Mode: ${MAGENTA}deep_night${NC} | Energy: Variable | Best for: Deep focus"
  fi
fi

# 2. Session Status
header "📊 SESSION STATUS"
if [ -f ~/.claude/kernel/session-state.json ]; then
  session-status 2>/dev/null || echo "  Run 'session-status' for details"
else
  echo "  No active session tracking"
fi

# 3. Supermemory Check
header "🧬 SUPERMEMORY"
if command -v sm &> /dev/null; then
  SM_STATS=$(sm stats 2>/dev/null | head -5) || SM_STATS="  Database ready"
  echo "$SM_STATS"

  # Check due reviews
  DUE=$(sm-due 2>/dev/null | head -3) || DUE=""
  if [ -n "$DUE" ]; then
    echo -e "\n  ${YELLOW}Reviews due:${NC}"
    echo "$DUE"
  fi
else
  echo "  Supermemory not configured"
fi

# 4. Error Prevention (quick mode skips this)
if [ "$MODE" = "full" ] || [ "$MODE" = "boost" ]; then
  header "🛡️ ERROR PREVENTION"
  if command -v predict-dry &> /dev/null; then
    predict-dry 2>/dev/null | head -10 || echo "  No predictions available"
  else
    echo "  Predictive system not configured"
  fi
fi

# 5. Observatory (7-day report)
if [ "$MODE" = "full" ] || [ "$MODE" = "boost" ]; then
  header "🔭 OBSERVATORY (7 days)"
  if command -v obs &> /dev/null; then
    obs 7 2>/dev/null | head -15 || echo "  Run 'obs 7' for full report"
  else
    echo "  Observatory not configured"
  fi
fi

# 6. Active Tasks (Ralph TUI)
header "🤖 AUTONOMOUS AGENTS"
# Check for running ralph-tui
if pgrep -f "ralph-tui" > /dev/null 2>&1; then
  echo -e "  ${GREEN}●${NC} Ralph TUI: Running"
  if [ -f ".ralph-tui/session.json" ]; then
    ralph-tui status 2>/dev/null | head -5 || echo "    Check terminal for status"
  fi
else
  echo -e "  ${YELLOW}○${NC} Ralph TUI: Not running"
fi

# Check for background Claude agents
BG_AGENTS=$(ps aux | grep -E "claude.*Task" | grep -v grep | wc -l | tr -d ' ')
if [ "$BG_AGENTS" -gt 0 ]; then
  echo -e "  ${GREEN}●${NC} Background agents: $BG_AGENTS active"
else
  echo -e "  ${YELLOW}○${NC} Background agents: None"
fi

# 7. Quick Context (boost mode)
if [ "$MODE" = "boost" ]; then
  header "📦 LOADING CONTEXT PACKS"
  if command -v prefetch &> /dev/null; then
    prefetch 2>/dev/null | tail -5 || echo "  Context loaded"
  else
    echo "  Prefetch not configured"
  fi

  header "🎯 MODEL ROUTING SUGGESTION"
  if command -v cos &> /dev/null; then
    cos route "current task" 2>/dev/null || echo "  Use 'cos route \"task\"' for suggestions"
  fi
fi

# 8. Recommendations
header "💡 RECOMMENDATIONS"
HOUR=$(date +%H)
if [ $HOUR -ge 9 ] && [ $HOUR -lt 12 ]; then
  echo -e "  ${GREEN}Peak hours${NC} - tackle complex architecture"
elif [ $HOUR -ge 20 ] || [ $HOUR -lt 2 ]; then
  echo -e "  ${MAGENTA}Your peak: 20:00, 02:00${NC} - deep work time"
else
  echo -e "  ${CYAN}Consider batching small tasks${NC}"
fi

# Cost check
if [ -f ~/.claude/stats-cache.json ]; then
  echo -e "  Run ${YELLOW}/cost${NC} to check daily spend"
fi

echo ""
divider
echo -e "${BOLD}  Commands: ${NC}${CYAN}10x quick${NC} | ${CYAN}10x full${NC} | ${CYAN}10x boost${NC}"
echo -e "  ${YELLOW}boost${NC} = full + context packs + model routing"
divider
echo ""
