#!/bin/bash
# Sovereign Terminal OS - Master Init
# Based on: AIOS, Astraea, ACE DQ Framework
# Add to .zshrc: source ~/.claude/init.sh

# ══════════════════════════════════════════════════════════════
# KERNEL INITIALIZATION
# ══════════════════════════════════════════════════════════════

KERNEL_DIR="$HOME/.claude/kernel"
KERNEL_STATE="$KERNEL_DIR/state.json"

# Verify kernel components
__kernel_check() {
  local kernel_state="active"
  [[ ! -f "$KERNEL_DIR/dq-scorer.js" ]] && kernel_state="degraded"
  [[ ! -f "$KERNEL_DIR/complexity-analyzer.js" ]] && kernel_state="degraded"
  echo "$kernel_state"
}

# ══════════════════════════════════════════════════════════════
# CORE AUTOMATION
# ══════════════════════════════════════════════════════════════

# Only source scripts that define functions (not executables)
# smart-route.sh contains the ai() function and related commands
[[ -f ~/.claude/scripts/smart-route.sh ]] && source ~/.claude/scripts/smart-route.sh
[[ -f ~/.claude/scripts/git-auto.sh ]] && source ~/.claude/scripts/git-auto.sh

# ══════════════════════════════════════════════════════════════
# ALIASES
# ══════════════════════════════════════════════════════════════

# Intercept claude command for DQ-powered routing
export CLAUDE_REAL_BIN="/Users/dicoangelo/.local/bin/claude"
alias claude='~/.claude/scripts/claude-wrapper.sh'

# Model shortcuts - now act as explicit overrides to DQ routing
alias cq='claude --model haiku'               # Quick/cheap (explicit override)
alias cc='claude --model sonnet'              # Standard (explicit override)
alias co='claude --model opus'                # Heavy thinking (explicit override)

# Session management
alias cx='tmux new-session -A -s claude-main "cc"'
alias cl='tail -f ~/.claude/activity.log'     # Live activity
alias clog='cat ~/.claude/activity.log'       # Full log
alias cstats='claude --stats 2>/dev/null || echo "Run inside claude for stats"'

# Quick actions
alias cgit='cc "/pr"'                         # PR workflow
alias ctest='cc "run tests and fix failures"'
alias cbuild='cc "run build and fix errors"'
alias cfix='cc "fix the last error"'
alias cterm='~/.claude/scripts/cterm.sh'   # Terminal dashboard
alias ccost='~/.claude/scripts/cost-tracker.sh' # Cost tracker
alias ccc='~/.claude/scripts/ccc-generator.sh'  # Command Center (ultimate dashboard)

# Routing system (new)
alias routing-dash='~/.claude/scripts/routing-dashboard.sh'
alias routing-report='python3 ~/researchgravity/routing-metrics.py report --days'
alias routing-targets='python3 ~/researchgravity/routing-metrics.py check-targets'
alias routing-cron='~/.claude/scripts/routing-cron-setup.sh'
alias routing-auto='~/.claude/scripts/routing-auto-update.sh'
alias routing-docs='cat ~/.claude/ROUTING_DOCS_INDEX.md'
alias routing-help='cat ~/.claude/ROUTING_QUICK_REFERENCE.md'
alias ai-feedback-status='~/.claude/scripts/feedback-status.sh'

# ══════════════════════════════════════════════════════════════
# CO-EVOLUTION SYSTEM (Bidirectional Learning)
# ══════════════════════════════════════════════════════════════

alias meta-analyzer='python3 ~/.claude/scripts/meta-analyzer.py'
alias coevo-analyze='python3 ~/.claude/scripts/meta-analyzer.py analyze'
alias coevo-propose='python3 ~/.claude/scripts/meta-analyzer.py propose'
alias coevo-apply='python3 ~/.claude/scripts/meta-analyzer.py apply'
alias coevo-rollback='python3 ~/.claude/scripts/meta-analyzer.py rollback'
alias coevo-dashboard='python3 ~/.claude/scripts/meta-analyzer.py dashboard'
alias coevo-config='python3 ~/.claude/scripts/meta-analyzer.py config'

# Pattern-aware prefetch
alias prefetch-pattern='python3 ~/researchgravity/prefetch.py --pattern'
alias prefetch-proactive='python3 ~/researchgravity/prefetch.py --proactive'
alias prefetch-suggest='python3 ~/researchgravity/prefetch.py --suggest'

# Learned suggestions (co-evolution enhanced)
alias suggest-learned='node ~/.claude/kernel/pattern-detector.js learned'

# ══════════════════════════════════════════════════════════════
# FUNCTIONS
# ══════════════════════════════════════════════════════════════

# Quick question (stays in shell, no session)
q() {
  cq -p "$*"
}

# Explain anything
explain() {
  cq -p "explain concisely: $*"
}

# Fix command
fixcmd() {
  local last_cmd=$(fc -ln -1)
  cc -p "this command failed: $last_cmd. Error: $*. Give me only the corrected command."
}

# Today's activity summary
today() {
  echo "═══ TODAY'S CLAUDE ACTIVITY ═══"
  grep "$(date '+%Y-%m-%d')" ~/.claude/activity.log 2>/dev/null || echo "No activity today"
}

# Clear context reminder
__claude_msg_reminder() {
  local count=$(wc -l < ~/.claude/activity.log 2>/dev/null | tr -d ' ')
  if [[ $count -gt 100 ]]; then
    echo "💡 Activity log has $count entries. Consider: clog-clear"
  fi
}

# Clear old logs
clog-clear() {
  local backup="$HOME/.claude/activity.log.$(date '+%Y%m%d')"
  mv ~/.claude/activity.log "$backup"
  echo "✓ Log archived to $backup"
}

# ══════════════════════════════════════════════════════════════
# STARTUP
# ══════════════════════════════════════════════════════════════

# Show status on shell start
__sovereign_startup() {
  local kernel_status=$(__kernel_check)

  echo ""
  echo "  ╔═══════════════════════════════════════════════════════════╗"
  echo "  ║     D-ECOSYSTEM :: SOVEREIGN TERMINAL OS v1.5.0           ║"
  echo "  ║     \"Let the invention be hidden in your vision\"          ║"
  echo "  ╚═══════════════════════════════════════════════════════════╝"
  echo ""

  if [[ "$kernel_status" == "active" ]]; then
    echo "  Kernel: ✓ Active | Sovereign by design"
  else
    echo "  Kernel: ⚠ Degraded (using legacy routing)"
  fi

  echo ""
  echo "  Core:"
  echo "    ai \"query\"    DQ-powered routing (haiku/sonnet/opus)"
  echo "    ai-kernel     Full kernel status"
  echo "    ai-identity   Sovereign identity card"
  echo "    ai-suggest    Proactive suggestions"
  echo ""
  echo "  Co-Evolution (Bidirectional Learning):"
  echo "    coevo-analyze    Analyze patterns & generate insights"
  echo "    coevo-propose    Generate modification proposals"
  echo "    coevo-dashboard  View effectiveness over time"
  echo ""
  echo "  Dashboard: ccc | Models: cq, cc, co | Git: gsave, gsync"
  echo ""
}

__sovereign_startup
