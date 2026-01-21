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
# Note: cq, cc defined in .zshrc; co() function in .zshrc with Black Panther art

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

# Multi-repo test/lint runner
ccheck() {
  echo "═══ MULTI-REPO CHECK ═══"
  local failed=0

  echo -e "\n▶ OS-App (npm test + lint)"
  (cd ~/OS-App && npm run test:run && npm run lint) || ((failed++))

  echo -e "\n▶ CareerCoachAntigravity (npm test)"
  (cd ~/CareerCoachAntigravity && npm test -- --run) || ((failed++))

  echo -e "\n▶ cpb-core (npm test + lint)"
  (cd ~/cpb-core && npm run test:run && npm run lint) || ((failed++))

  echo -e "\n▶ voice-nexus (npm test + lint)"
  (cd ~/voice-nexus && npm run test:run && npm run lint) || ((failed++))

  echo -e "\n▶ researchgravity (ruff)"
  (cd ~/researchgravity && source .venv/bin/activate && ruff check .) || ((failed++))

  echo -e "\n═══ SUMMARY ═══"
  if [[ $failed -eq 0 ]]; then
    echo "✅ All 5 projects passed"
  else
    echo "❌ $failed project(s) failed"
  fi
  return $failed
}
alias lint-all='ccheck'
alias ruff-check='cd ~/researchgravity && source .venv/bin/activate && ruff check .'
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

# A/B Test: HSRGS vs Keyword DQ
alias ab-test='python3 ~/.claude/scripts/ab-test-analyzer.py'
alias ab-test-detailed='python3 ~/.claude/scripts/ab-test-analyzer.py --detailed'

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

# Check feedback status (has access to shell variables)
ai-feedback-status() {
  if [[ " ${precmd_functions[@]} " =~ " __ai_feedback_auto " ]]; then
    echo "✓ Automated feedback is ACTIVE"
    echo ""
    echo "How it works:"
    echo "  - Monitors command exit codes after AI queries"
    echo "  - Records failures within 30 seconds of query"
    echo "  - Automatically improves routing decisions"
    echo "  - Logs to: ~/.claude/data/ai-routing.log"
    echo ""
    echo "To disable: ai-feedback-disable"
  else
    echo "✗ Automated feedback is NOT active"
    echo ""
    echo "To enable: ai-feedback-enable"
  fi
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
# SESSION OPTIMIZER (Sovereign Session Management)
# ══════════════════════════════════════════════════════════════

# Session status and dashboard
alias session-status='node ~/.claude/kernel/session-engine.js compact 2>/dev/null || python3 ~/.claude/scripts/session-optimizer/cli.py status'
alias session-dash='node ~/.claude/kernel/session-engine.js dashboard 2>/dev/null || python3 ~/.claude/scripts/session-optimizer/cli.py status'
alias session-full='python3 ~/.claude/scripts/session-optimizer/cli.py dashboard'

# Window operations
alias session-window='python3 ~/.claude/scripts/session-optimizer/cli.py window status'
alias session-predict='python3 ~/.claude/scripts/session-optimizer/cli.py window predict'
alias session-history='python3 ~/.claude/scripts/session-optimizer/cli.py window history --days'
alias session-analyze='python3 ~/.claude/scripts/session-optimizer/cli.py window analyze --days'

# Budget management
alias session-budget='python3 ~/.claude/scripts/session-optimizer/cli.py budget status'
alias session-reserve='python3 ~/.claude/scripts/session-optimizer/cli.py budget reserve'
alias session-simulate='python3 ~/.claude/scripts/session-optimizer/cli.py budget simulate'
alias session-api-value='python3 ~/.claude/scripts/session-optimizer/cli.py budget api-value'

# Task queue
alias session-queue-add='python3 ~/.claude/scripts/session-optimizer/cli.py queue add'
alias session-queue-list='python3 ~/.claude/scripts/session-optimizer/cli.py queue list'
alias session-queue-next='python3 ~/.claude/scripts/session-optimizer/cli.py queue next'
alias session-queue-batch='python3 ~/.claude/scripts/session-optimizer/cli.py queue batch'

# Optimization
alias session-optimize='python3 ~/.claude/scripts/session-optimizer/cli.py optimize'
alias session-optimize-dry='python3 ~/.claude/scripts/session-optimizer/cli.py optimize --dry-run'
alias session-optimize-apply='python3 ~/.claude/scripts/session-optimizer/cli.py optimize --apply'

# Feedback loop
alias session-feedback='python3 ~/.claude/scripts/session-optimizer/feedback_loop.py'
alias session-proposals='python3 ~/.claude/scripts/session-optimizer/feedback_loop.py propose'
alias session-auto-apply='python3 ~/.claude/scripts/session-optimizer/feedback_loop.py auto-apply'

# Quick shortcut
session() {
  if [[ $# -eq 0 ]]; then
    session-status
  else
    python3 ~/.claude/scripts/session-optimizer/cli.py "$@"
  fi
}

# ══════════════════════════════════════════════════════════════
# OBSERVATORY (Comprehensive Metrics & Analytics)
# ══════════════════════════════════════════════════════════════

[[ -f ~/.claude/scripts/observatory/init.sh ]] && source ~/.claude/scripts/observatory/init.sh

# ══════════════════════════════════════════════════════════════
# STARTUP
# ══════════════════════════════════════════════════════════════

# Show status on shell start
__sovereign_startup() {
  local kernel_status=$(__kernel_check)

  # Colors: Purple/Magenta
  local PURPLE='\033[38;5;129m'
  local BRIGHT_PURPLE='\033[38;5;165m'
  local RESET='\033[0m'

  echo ""
  echo -e "${PURPLE}⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣶⣄⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀${RESET}"
  echo -e "${PURPLE}⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⡿⢩⣇⠙⠻⣛⡒⠒⠶⠤⢤⣄⣀⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀${RESET}"
  echo -e "${PURPLE}⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣰⣿⢃⡟⠛⡆⠀⣈⣉⠻⣦⣍⠲⢤⣈⠉⠛⠶⣄⡀⠀⠀⠀⠀⠀⠀⠀${RESET}"
  echo -e "${PURPLE}⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣼⣿⡟⠸⠀⠀⢻⡀⢹⠀⠉⠙⠛⠷⣀⠹⢷⣦⡀⠈⠙⢦⡀⠀⠀⠀⠀⠀${RESET}"
  echo -e "${PURPLE}⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⠞⢸⣩⣇⣀⠀⠀⠈⢷⡀⢣⠀⠀⠀⠀⠀⠙⢶⣿⣟⢷⣄⠀⠻⡄⠀⠀⠀⠀${RESET}"
  echo -e "${BRIGHT_PURPLE}⠀⠀⠀⠀⠀⠀⠀⠀⠀⡞⣠⢻⣇⠹⣾⣄⠀⠀⠀⢳⡀⠳⡀⠀⠀⠀⠀⠀⠙⢿⣷⡙⢷⡄⠹⡄⠀⠀⠀${RESET}"
  echo -e "${BRIGHT_PURPLE}⠀⠀⠀⠀⠀⠀⠀⠀⢸⣷⠁⠀⢻⣆⠈⠻⢇⠀⠀⠀⠹⣦⡈⢦⡀⠀⠀⠀⠀⠈⠻⣿⣦⠹⣦⣿⠀⠀⠀${RESET}"
  echo -e "${BRIGHT_PURPLE}⠀⠀⠀⠀⠀⠀⠀⠀⡾⢻⠀⠀⠀⢻⢦⡀⠀⠑⢄⠀⠀⠀⠑⢄⠙⠢⣀⠀⠀⠀⠀⠈⠙⠻⣿⣿⡆⠀⠀${RESET}"
  echo -e "${BRIGHT_PURPLE}⠀⠀⠀⠀⠀⠀⠀⠀⡇⠸⣇⠀⠀⠀⠳⢍⠢⣀⠀⠑⠦⡀⠀⠀⢱⡆⠈⠑⠲⠒⣲⣄⡀⠀⠈⣿⣧⠀⠀${RESET}"
  echo -e "${BRIGHT_PURPLE}⠀⠀⠀⠀⠀⠀⠀⠀⡇⠀⢿⡄⠀⠀⠀⠀⠙⠪⣷⣄⡀⠈⠳⢄⣈⣇⠀⣠⣶⣾⠿⠽⡿⣦⣠⢿⣿⡄⠀${RESET}"
  echo -e "${BRIGHT_PURPLE}⠀⠀⠀⠀⠀⠀⠀⠀⣿⠀⠈⢿⣆⠀⠀⠀⠀⠀⠀⠙⠿⣶⣄⡀⠙⠻⣦⣈⠙⠿⣖⣖⣁⡀⢹⠿⠛⣷⠀${RESET}"
  echo -e "${PURPLE}⠀⠀⠀⠀⠀⠀⠀⠀⢸⣷⡀⠈⢫⡑⢄⡀⠀⠀⠀⠀⠀⠀⠙⠻⢷⡦⣼⠙⠷⣦⡀⠉⠉⣹⠷⡶⠚⠛⣧${RESET}"
  echo -e "${PURPLE}⠀⠀⠀⠀⠀⠀⠀⠀⠀⢿⠑⢄⠀⠑⢄⣸⠿⢶⣤⣀⡀⠀⠀⠀⠀⠈⢻⡆⠀⠈⢻⠢⢴⡉⠒⢌⣆⢠⡟${RESET}"
  echo -e "${PURPLE}⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⢧⣌⣀⣀⣀⣉⣷⣀⣈⡉⠛⠷⡆⠀⢀⣠⠾⢃⣤⠤⢤⣳⡀⢱⡀⠀⣿⡿⠀${RESET}"
  echo -e "${PURPLE}⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⠃⠀⠀⠀⠀⠀⠀⠈⠏⡓⢦⣠⠶⢋⡥⣾⠭⠊⠀⠀⠘⣷⡀⢡⣰⣽⠁⠀${RESET}"
  echo -e "${PURPLE}⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣼⠀⠀⠀⠀⠀⠀⠀⢠⡇⡇⠀⢹⣿⣅⢲⠃⠀⠀⠀⢀⣴⣿⡵⠁⣿⡏⠀⠀${RESET}"
  echo -e "${PURPLE}⠀⠀⠀⠀⠀⠀⠀⠀⠀⢠⡇⠀⠀⠀⠀⠀⠀⠀⣾⢧⠀⠀⢸⢣⠈⢷⡀⠀⠀⣰⣿⣿⠊⠀⣠⣿⠁⠀⠀${RESET}"
  echo -e "${PURPLE}⠀⠀⠀⠀⠀⠀⠀⠀⠀⣸⠁⠀⠀⠀⠀⠀⠀⠀⠘⠢⣷⣄⣈⣿⣆⠀⠹⣦⣼⣿⠟⠁⢀⠔⢁⡏⠀⠀⠀${RESET}"
  echo -e "${PURPLE}⠀⠀⠀⠀⠀⠀⢀⣤⣶⣿⡟⠳⣄⡀⣀⡄⠀⠀⠀⠀⠀⠉⠛⠫⠬⣑⢶⣿⣿⡏⢀⡔⠀⢀⡼⠁⠀⠀⠀${RESET}"
  echo -e "${PURPLE}⠀⠀⠀⠀⢀⣾⣿⣿⣿⠟⣁⡔⢛⣿⡿⠈⢲⡤⣀⣀⣤⠀⠀⠀⠀⠈⠻⣿⡀⠉⠛⠒⠚⠋⠀⠀⠀⠀⠀${RESET}"
  echo -e "${PURPLE}⠀⠀⠀⢠⣿⡿⢯⡿⡣⠚⠉⢡⡿⠟⣡⠶⠽⠿⢿⢠⠋⣳⠄⣀⠀⠀⠀⢸⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀${RESET}"
  echo -e "${PURPLE}⠀⠀⢀⣿⠟⢡⡾⠋⠉⠀⢠⠟⣡⠞⠁⠀⠀⠀⣇⡎⣴⣁⡀⣙⡿⠖⣦⣈⣿⣤⠀⠀⠀⠀⠀⠀⠀⠀⠀${RESET}"
  echo -e "${PURPLE}⠀⢠⡾⣡⠞⠁⠀⠀⠀⠀⣼⠞⠁⠀⠀⠀⠀⢰⣿⡟⢩⠈⠋⢻⡃⢠⡿⠽⣻⠟⢳⣄⠀⠀⠀⠀⠀⠀⠀${RESET}"
  echo -e "${PURPLE}⢀⣿⡟⠁⠀⠀⠀⣀⣠⣴⣷⣖⠒⠾⠿⠷⠶⣾⡿⠤⢼⠀⠀⢸⢀⡟⠀⠤⠃⠀⠀⠙⠀⠀⠀⠀⠀⠀⠀${RESET}"
  echo -e "${PURPLE}⣼⠋⠀⢀⣠⡶⠟⠋⠉⠁⠀⠀⠀⠀⠀⠀⠀⠈⢳⠀⠈⡇⠀⢸⡞⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀${RESET}"
  echo -e "${PURPLE}⠋⠀⠀⠉⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⣇⠀⢇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀${RESET}"
  echo -e "${PURPLE}⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠸⡄⠸⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀${RESET}"
  echo -e "${PURPLE}⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢳⡀⠇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀${RESET}"
  echo ""
  echo -e "  ${BRIGHT_PURPLE}D-ECOSYSTEM${RESET} :: SOVEREIGN TERMINAL OS v1.5.0"
  echo -e "  ${PURPLE}\"Let the invention be hidden in your vision\"${RESET}"
  echo ""

  if [[ "$kernel_status" == "active" ]]; then
    echo -e "  Kernel: ${BRIGHT_PURPLE}✓ Active${RESET} | ai cq cc co | ccc gsave"
  else
    echo -e "  Kernel: ⚠ Degraded | ai cq cc co | ccc gsave"
  fi
  echo ""
}

__sovereign_startup
alias gsave="~/.claude/scripts/session-save.sh"

# ══════════════════════════════════════════════════════════════
# META-VENGINE EXTENSIONS (v2.0)
# Addressing Top 5 Pain Points
# ══════════════════════════════════════════════════════════════

# Phase 1: Adversarial ACE Agent (ContrarianAgent)
# Already integrated into observatory/agents/

# Phase 2: Prompt/Agent Versioning
alias prompt-version='~/.claude/scripts/version-manager.sh version'
alias prompt-bump='~/.claude/scripts/version-manager.sh bump'
alias prompt-rollback='~/.claude/scripts/version-manager.sh rollback'
alias prompt-diff='~/.claude/scripts/version-manager.sh diff'
alias prompt-list='~/.claude/scripts/version-manager.sh list'
alias prompt-status='~/.claude/scripts/version-manager.sh status'

# Phase 3: Persistent Vector Memory
alias mem-query='python3 ~/.claude/kernel/memory-api.py query'
alias mem-persist='python3 ~/.claude/kernel/memory-api.py persist'
alias mem-rebuild='python3 ~/.claude/kernel/memory-api.py rebuild'
alias mem-stats='python3 ~/.claude/kernel/memory-api.py stats'
alias mem-link='python3 ~/.claude/kernel/memory-api.py link'

# Phase 4: Background Agent Daemon
alias daemon-start='~/.claude/daemon/agent-daemon.sh start'
alias daemon-stop='~/.claude/daemon/agent-daemon.sh stop'
alias daemon-status='~/.claude/daemon/agent-daemon.sh status'
alias daemon-restart='~/.claude/daemon/agent-daemon.sh restart'
alias brief='~/.claude/daemon/agent-daemon.sh brief'
alias daemon-log='~/.claude/daemon/agent-daemon.sh log'
alias daemon-test='~/.claude/daemon/agent-daemon.sh test'

# Phase 5: Smart Context Compression
alias context-compress='python3 ~/.claude/kernel/context-compressor.py compress'
alias context-estimate='python3 ~/.claude/kernel/context-compressor.py estimate'

# Meta-Vengine help
meta-vengine-help() {
  cat << 'EOF'
═══════════════════════════════════════════════════════════════
  META-VENGINE v2.0 - Self-Improving System
═══════════════════════════════════════════════════════════════

PROMPT VERSIONING:
  prompt-version         Show current CLAUDE.md version
  prompt-bump [type]     Bump version (major|minor|patch)
  prompt-rollback <ver>  Rollback to specific version
  prompt-diff <v1> [v2]  Diff between versions
  prompt-list            List all archived versions
  prompt-status          Full version status

VECTOR MEMORY:
  mem-query "text"       Semantic search across knowledge
  mem-persist <content> <cat> <tags...>  Add knowledge
  mem-rebuild            Rebuild all embeddings
  mem-stats              Memory system statistics

BACKGROUND DAEMON:
  daemon-start           Start background agents
  daemon-stop            Stop daemon
  daemon-status          Check daemon status
  brief [date]           View daily brief

CONTEXT COMPRESSION:
  context-compress <file>  Compress JSON context
  context-estimate <file>  Estimate tokens in file

ADVERSARIAL ANALYSIS:
  - ContrarianAgent integrated into ACE consensus
  - Provides minority opinions in session analysis
  - Run: session-analyze <session-id>

═══════════════════════════════════════════════════════════════
EOF
}

alias mvhelp='meta-vengine-help'

# ══════════════════════════════════════════════════════════════
# CHIEF OF STAFF INFRASTRUCTURE (v1.0)
# Pattern 4: Infrastructure Over Tools
# ══════════════════════════════════════════════════════════════

# API Surface (REST endpoints for cross-application queries)
alias api-start='cd ~/researchgravity && python3 -m api.server --port 3847'
alias api-docs='open http://localhost:3847/docs 2>/dev/null || echo "Start API first: api-start"'

# Writer-Critic Validation System
alias critic-archive='python3 -m critic.archive_critic --session'
alias critic-evidence='python3 -m critic.evidence_critic --session'
alias critic-pack='python3 -m critic.pack_critic --pack'
alias critic-all='python3 -m critic.archive_critic --all --verbose'
alias critic-stats='python3 -m critic.evidence_critic --stats'

# Reinvigoration System (Session Resume)
alias reinvigorate='python3 ~/researchgravity/reinvigorate.py'
alias resume='python3 ~/researchgravity/reinvigorate.py'
alias resume-list='python3 ~/researchgravity/reinvigorate.py --list'
alias resume-inject='python3 ~/researchgravity/reinvigorate.py --inject'
alias resume-verify='python3 ~/researchgravity/reinvigorate.py --verify'

# Checkpoint System
alias checkpoint='python3 ~/researchgravity/checkpoint.py'
alias checkpoint-create='python3 ~/researchgravity/checkpoint.py create'
alias checkpoint-list='python3 ~/researchgravity/checkpoint.py list'
alias checkpoint-restore='python3 ~/researchgravity/checkpoint.py restore'
alias checkpoint-auto='python3 ~/researchgravity/checkpoint.py auto'

# Principle Injection
alias principles='python3 ~/researchgravity/principle_injector.py'
alias principles-inject='python3 ~/researchgravity/principle_injector.py --inject'
alias principles-list='cat ~/.agent-core/principles/manifest.yaml'

# Evidence Layer
alias evidence-extract='python3 ~/researchgravity/evidence_extractor.py'
alias evidence-validate='python3 ~/researchgravity/evidence_validator.py'
alias evidence-score='python3 ~/researchgravity/confidence_scorer.py'

# Chief of Staff Help
chief-help() {
  cat << 'EOF'
═══════════════════════════════════════════════════════════════
  CHIEF OF STAFF INFRASTRUCTURE v1.0
  Pattern 4: Infrastructure Over Tools
═══════════════════════════════════════════════════════════════

API SURFACE (REST endpoints):
  api-start              Start API server on port 3847
  api-docs               Open API documentation

WRITER-CRITIC VALIDATION:
  critic-archive <sid>   Validate archive completeness
  critic-evidence <sid>  Validate evidence quality
  critic-pack <pid>      Validate context pack
  critic-all             Validate all sessions

REINVIGORATION (Session Resume):
  resume <session-id>    Get reinvigoration context
  resume-list            List resumable sessions
  resume-inject <sid>    Inject context into CLAUDE.md
  resume-verify <sid>    Verify reinvigoration readiness

CHECKPOINTS:
  checkpoint create "desc"  Create restore point
  checkpoint list           List all checkpoints
  checkpoint restore <id>   Get checkpoint context
  checkpoint auto           Auto-checkpoint current session

EVIDENCE LAYER:
  evidence-extract --all    Extract citations from findings
  evidence-validate <sid>   Validate evidence quality
  evidence-score --stats    Show confidence statistics

PRINCIPLES:
  principles                Show active principles
  principles-inject         Inject into prefetch
  principles-list           List all defined principles

═══════════════════════════════════════════════════════════════
EOF
}

alias chiefhelp='chief-help'
