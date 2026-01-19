#!/bin/bash
# Claude Observatory - Master Initialization
# Ties together all metrics collectors and analytics
# Source from ~/.claude/init.sh

OBSERVATORY_DIR="$HOME/.claude/scripts/observatory"
COLLECTORS_DIR="$OBSERVATORY_DIR/collectors"

# ═══════════════════════════════════════════════════════════════════════════
# LOAD COLLECTORS
# ═══════════════════════════════════════════════════════════════════════════

echo "🔭 Initializing Claude Observatory..."

# Session tracking
if [[ -f "$COLLECTORS_DIR/session-tracker.sh" ]]; then
  source "$COLLECTORS_DIR/session-tracker.sh"
  echo "  ✓ Session tracker loaded"
fi

# Command tracking (must be loaded before redefining aliases)
if [[ -f "$COLLECTORS_DIR/command-tracker.sh" ]]; then
  source "$COLLECTORS_DIR/command-tracker.sh"
  echo "  ✓ Command tracker loaded"
fi

# Tool tracking
if [[ -f "$COLLECTORS_DIR/tool-tracker.sh" ]]; then
  source "$COLLECTORS_DIR/tool-tracker.sh"
  echo "  ✓ Tool tracker loaded"
fi

# Git tracking
if [[ -f "$COLLECTORS_DIR/git-tracker.sh" ]]; then
  source "$COLLECTORS_DIR/git-tracker.sh"
  echo "  ✓ Git tracker loaded"
fi

# ═══════════════════════════════════════════════════════════════════════════
# PYTHON TOOLS SETUP
# ═══════════════════════════════════════════════════════════════════════════

# Make Python scripts executable
chmod +x "$COLLECTORS_DIR/cost-tracker.py" 2>/dev/null
chmod +x "$COLLECTORS_DIR/productivity-analyzer.py" 2>/dev/null
chmod +x "$OBSERVATORY_DIR/analytics-engine.py" 2>/dev/null

# ═══════════════════════════════════════════════════════════════════════════
# ALIASES - Analytics & Reporting
# ═══════════════════════════════════════════════════════════════════════════

# Session management
alias session-complete='session-complete'
alias session-rate='session-rate'
alias session-stats='session-stats'

# Cost tracking
alias cost-report='python3 $COLLECTORS_DIR/cost-tracker.py report'
alias cost-budget='python3 $COLLECTORS_DIR/cost-tracker.py budget'
alias cost-process='python3 $COLLECTORS_DIR/cost-tracker.py process'

# Productivity
alias productivity-report='python3 $COLLECTORS_DIR/productivity-analyzer.py report'
alias productivity-log='python3 $COLLECTORS_DIR/productivity-analyzer.py log'

# Tool analytics
alias tool-stats='tool-stats'

# Command analytics
alias command-stats='command-stats'

# Git analytics
alias git-stats='git-stats'

# Unified analytics
alias observatory-report='python3 $OBSERVATORY_DIR/analytics-engine.py report'
alias observatory-digest='python3 $OBSERVATORY_DIR/analytics-engine.py digest'
alias observatory-export='python3 $OBSERVATORY_DIR/analytics-engine.py export'

# Quick alias
alias obs='observatory-report'

# ═══════════════════════════════════════════════════════════════════════════
# AUTOMATED TRACKING
# ═══════════════════════════════════════════════════════════════════════════

# Auto-start session tracking when Claude session detected
if [[ -n "$CLAUDE_SESSION_ID" ]] && [[ -z "$OBSERVATORY_SESSION_START" ]]; then
  session-start 2>/dev/null
fi

# Daily productivity snapshot (run once per day)
__observatory_daily_snapshot() {
  local last_snapshot_file="$HOME/.claude/data/.last-snapshot"
  local today=$(date '+%Y-%m-%d')

  if [[ ! -f "$last_snapshot_file" ]] || [[ "$(cat $last_snapshot_file)" != "$today" ]]; then
    echo "📸 Taking daily Observatory snapshot..."
    python3 "$COLLECTORS_DIR/productivity-analyzer.py" log 2>/dev/null
    python3 "$COLLECTORS_DIR/cost-tracker.py" process 1 2>/dev/null
    echo "$today" > "$last_snapshot_file"
  fi
}

# Run daily snapshot on shell startup (non-blocking)
(__observatory_daily_snapshot &)

# ═══════════════════════════════════════════════════════════════════════════
# HELP
# ═══════════════════════════════════════════════════════════════════════════

observatory-help() {
  cat << 'EOF'
═══════════════════════════════════════════════════════════════
  🔭 CLAUDE OBSERVATORY - HELP
═══════════════════════════════════════════════════════════════

Session Tracking:
  session-complete <outcome> [note] [quality]  - Complete session
    outcomes: success, partial, error, abandoned, research
    quality: 1-5 (optional, auto-detected if omitted)
  session-rate <1-5> [note]                    - Rate session quality
  session-stats [days]                         - View session statistics

Cost Tracking:
  cost-report [days]      - Cost report (default: 30 days)
  cost-budget             - Quick budget check
  cost-process [days]     - Process all sessions for costs

Productivity:
  productivity-report [days]  - Productivity metrics
  productivity-log            - Log daily snapshot

Analytics:
  tool-stats [days]       - Tool success rates
  command-stats [days]    - Command usage statistics
  git-stats [days]        - Git activity
  obs [days]              - Unified Observatory report (all metrics)
  observatory-digest      - Daily digest

Examples:
  session-rate 5 "Implemented routing system"
  cost-report 7
  obs 30
  productivity-report 7

Integration:
  • Bash commands auto-tracked (exit codes, duration)
  • Git commits auto-logged (via gcommit, gsave)
  • Session tracking auto-starts in Claude sessions
  • Daily snapshots run automatically

Dashboard:
  ccc                     - Open Command Center (includes Observatory)

═══════════════════════════════════════════════════════════════
EOF
}

alias obs-help='observatory-help'

echo "  ✓ Observatory initialized"
echo "  Type 'obs-help' for usage guide"
