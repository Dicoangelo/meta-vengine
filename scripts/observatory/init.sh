#!/bin/bash
# Claude Observatory - Master Initialization
# Ties together all metrics collectors and analytics
# Source from ~/.claude/init.sh

OBSERVATORY_DIR="$HOME/.claude/scripts/observatory"
COLLECTORS_DIR="$OBSERVATORY_DIR/collectors"

# ═══════════════════════════════════════════════════════════════════════════
# LOAD COLLECTORS
# ═══════════════════════════════════════════════════════════════════════════

# Load collectors silently
# Disable verbose function printing during load
[[ -n "$ZSH_VERSION" ]] && setopt LOCAL_OPTIONS NO_VERBOSE 2>/dev/null
[[ -f "$COLLECTORS_DIR/session-tracker.sh" ]] && source "$COLLECTORS_DIR/session-tracker.sh" >/dev/null 2>&1
[[ -f "$COLLECTORS_DIR/tool-tracker.sh" ]] && source "$COLLECTORS_DIR/tool-tracker.sh" >/dev/null 2>&1
[[ -f "$COLLECTORS_DIR/git-tracker.sh" ]] && source "$COLLECTORS_DIR/git-tracker.sh" >/dev/null 2>&1
# Note: command-tracker.sh loaded separately to avoid alias conflicts

# ═══════════════════════════════════════════════════════════════════════════
# PASSIVE COMMAND TRACKING (no alias conflicts)
# ═══════════════════════════════════════════════════════════════════════════

COMMAND_LOG="$HOME/.claude/data/command-usage.jsonl"

__elite_track_command() {
  local cmd="$1"
  # Skip internal commands
  [[ "$cmd" == __* ]] && return
  [[ "$cmd" == "source"* ]] && return
  [[ -z "$cmd" ]] && return

  # Extract first word (the command)
  local cmd_name="${cmd%% *}"

  # Log it
  echo "{\"ts\":$(date +%s),\"cmd\":\"$cmd_name\",\"full\":\"${cmd:0:100}\",\"pwd\":\"$PWD\"}" >> "$COMMAND_LOG"
}

# Register passive tracking hook
if [[ -n "$ZSH_VERSION" ]]; then
  autoload -U add-zsh-hook 2>/dev/null
  add-zsh-hook preexec __elite_track_command 2>/dev/null
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

# ═══════════════════════════════════════════════════════════════════════════
# ELITE MODE - Peak Performance Maintenance
# ═══════════════════════════════════════════════════════════════════════════

elite-status() {
  echo "═══════════════════════════════════════════════════════════════"
  echo "  ⚡ ELITE MODE STATUS"
  echo "═══════════════════════════════════════════════════════════════"
  echo ""

  # Check collectors
  local cmd_count=$(wc -l < "$HOME/.claude/data/command-usage.jsonl" 2>/dev/null || echo 0)
  local tool_count=$(wc -l < "$HOME/.claude/data/tool-success.jsonl" 2>/dev/null || echo 0)
  local session_count=$(wc -l < "$HOME/.claude/data/session-outcomes.jsonl" 2>/dev/null || echo 0)
  local git_count=$(wc -l < "$HOME/.claude/data/git-activity.jsonl" 2>/dev/null || echo 0)

  echo "  Data Collectors:"
  [[ $cmd_count -gt 0 ]] && echo "    ✅ command-usage: $cmd_count entries" || echo "    ❌ command-usage: EMPTY"
  [[ $tool_count -gt 0 ]] && echo "    ✅ tool-success: $tool_count entries" || echo "    ❌ tool-success: EMPTY"
  [[ $session_count -gt 0 ]] && echo "    ✅ session-outcomes: $session_count entries" || echo "    ❌ session-outcomes: EMPTY"
  [[ $git_count -gt 0 ]] && echo "    ✅ git-activity: $git_count entries" || echo "    ❌ git-activity: EMPTY"
  echo ""

  # Check co-evolution
  python3 ~/.claude/scripts/meta-analyzer.py dashboard 2>/dev/null | grep -E "(Auto-Apply|Applied|DQ Score)"
  echo ""

  # Check hooks
  echo "  Tracking Hooks:"
  if typeset -f __elite_track_command > /dev/null 2>&1; then
    echo "    ✅ Command tracking: ACTIVE"
  else
    echo "    ❌ Command tracking: NOT LOADED"
  fi
  if typeset -f __observatory_track_bash_result > /dev/null 2>&1; then
    echo "    ✅ Tool tracking: ACTIVE"
  else
    echo "    ❌ Tool tracking: NOT LOADED"
  fi
  echo ""
  echo "═══════════════════════════════════════════════════════════════"
}

elite-backfill() {
  echo "⚡ Backfilling data from session history..."

  # Backfill from Claude session transcripts
  python3 << 'PYEOF'
import json
import os
import glob
from datetime import datetime

data_dir = os.path.expanduser("~/.claude/data")
projects_dir = os.path.expanduser("~/.claude/projects")

# Find all session transcripts
transcripts = glob.glob(f"{projects_dir}/**/*.jsonl", recursive=True)
print(f"  Found {len(transcripts)} session transcripts")

command_log = os.path.join(data_dir, "command-usage.jsonl")
tool_log = os.path.join(data_dir, "tool-success.jsonl")

cmd_entries = []
tool_entries = []

for transcript in transcripts[-50:]:  # Last 50 sessions
    try:
        with open(transcript) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    ts = entry.get("timestamp", 0)
                    if isinstance(ts, str):
                        ts = int(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp())

                    # Extract tool uses
                    if "tool_uses" in str(entry) or "toolUse" in str(entry):
                        content = entry.get("message", {}).get("content", [])
                        if isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "tool_use":
                                    tool_name = block.get("name", "unknown")
                                    tool_entries.append({
                                        "ts": ts,
                                        "tool": tool_name,
                                        "success": True,
                                        "source": "backfill"
                                    })
                except:
                    continue
    except:
        continue

# Write backfilled entries
if tool_entries:
    with open(tool_log, "a") as f:
        for entry in tool_entries[-500:]:  # Cap at 500
            f.write(json.dumps(entry) + "\n")
    print(f"  ✅ Backfilled {min(len(tool_entries), 500)} tool entries")
else:
    print("  ⚠️ No tool entries found to backfill")

print("  Done!")
PYEOF
}

elite-calibrate() {
  echo "⚡ Calibrating co-evolution system..."
  echo ""

  # Run meta-analyzer
  python3 ~/.claude/scripts/meta-analyzer.py analyze 2>/dev/null

  # Check for pending mutations
  echo ""
  echo "Pending mutations:"
  python3 ~/.claude/scripts/meta-analyzer.py propose 2>/dev/null | head -20
}

alias elite='elite-status'
alias elite-fix='source ~/.zshrc && elite-status'

# Auto-trigger feedback loop monthly
if [[ ! -f "$HOME/.claude/data/.last-feedback-loop" ]] || \
   [[ -n "$(find "$HOME/.claude/data/.last-feedback-loop" -mtime +30 2>/dev/null)" ]]; then

    # Run feedback loop in background (non-blocking)
    (
        python3 "$OBSERVATORY_DIR/routing-feedback-loop.py" \
            --auto-apply \
            --days 30 \
            >> "$HOME/.claude/logs/feedback-loop.log" 2>&1

        touch "$HOME/.claude/data/.last-feedback-loop"
    ) &
fi

# ═══════════════════════════════════════════════════════════════════════════
# WEEKLY RESEARCH SYNC
# ═══════════════════════════════════════════════════════════════════════════

__elite_research_sync() {
  local last_sync_file="$HOME/.claude/data/.last-research-sync"
  local today=$(date '+%Y-%m-%d')
  local days_since=999

  if [[ -f "$last_sync_file" ]]; then
    local last_sync=$(cat "$last_sync_file")
    days_since=$(( ($(date +%s) - $(date -j -f "%Y-%m-%d" "$last_sync" +%s 2>/dev/null || echo 0)) / 86400 ))
  fi

  # Run weekly
  if [[ $days_since -ge 7 ]]; then
    echo "🔬 Running weekly research sync..."

    # Update routing research if script exists
    if [[ -f ~/researchgravity/arxiv-sync.py ]]; then
      python3 ~/researchgravity/arxiv-sync.py --quiet >> "$HOME/.claude/logs/research-sync.log" 2>&1 &
    fi

    # Run meta-analyzer to incorporate new insights
    python3 ~/.claude/scripts/meta-analyzer.py analyze --quiet >> "$HOME/.claude/logs/research-sync.log" 2>&1 &

    echo "$today" > "$last_sync_file"
  fi
}

# Run research sync on startup (non-blocking)
(__elite_research_sync &) 2>/dev/null

# Autonomous Analysis Commands
alias session-dashboard='python3 $OBSERVATORY_DIR/dashboard-server.py'
alias session-rename='python3 $OBSERVATORY_DIR/session-naming.py'
alias session-archive='python3 $OBSERVATORY_DIR/session-archival.py'

# ═══════════════════════════════════════════════════════════════════════════
# ELITE AUTO-MAINTENANCE
# ═══════════════════════════════════════════════════════════════════════════

# Run daily elite maintenance at first shell of day
__elite_daily_maintenance() {
  local last_maint_file="$HOME/.claude/data/.last-elite-maint"
  local today=$(date '+%Y-%m-%d')

  if [[ ! -f "$last_maint_file" ]] || [[ "$(cat $last_maint_file)" != "$today" ]]; then
    # Auto-apply high-confidence mutations
    python3 ~/.claude/scripts/meta-analyzer.py propose --auto-apply --min-confidence 0.9 >> "$HOME/.claude/logs/elite-maint.log" 2>&1

    # Evaluate recent modifications
    python3 ~/.claude/scripts/meta-analyzer.py evaluate >> "$HOME/.claude/logs/elite-maint.log" 2>&1

    echo "$today" > "$last_maint_file"
  fi
}

# Run in background
(__elite_daily_maintenance &) 2>/dev/null

# ═══════════════════════════════════════════════════════════════════════════
# AUTO-SYNC ACTIVITY FROM TRANSCRIPTS
# ═══════════════════════════════════════════════════════════════════════════

__auto_activity_sync() {
  local last_sync_file="$HOME/.claude/data/.last-activity-sync"
  local now=$(date +%s)
  local last_sync=0

  if [[ -f "$last_sync_file" ]]; then
    last_sync=$(cat "$last_sync_file" 2>/dev/null || echo 0)
  fi

  # Sync every 5 minutes (300 seconds)
  if [[ $((now - last_sync)) -ge 300 ]]; then
    python3 ~/.claude/scripts/activity-sync.py >> ~/.claude/logs/activity-sync.log 2>&1
    echo "$now" > "$last_sync_file"
  fi
}

# Run activity sync in background
(__auto_activity_sync &) 2>/dev/null

# ═══════════════════════════════════════════════════════════════════════════
# AUTO-RUN PATTERN DETECTION
# ═══════════════════════════════════════════════════════════════════════════

__auto_pattern_detection() {
  local last_detect_file="$HOME/.claude/data/.last-pattern-detect"
  local now=$(date +%s)
  local last_detect=0

  if [[ -f "$last_detect_file" ]]; then
    last_detect=$(cat "$last_detect_file" 2>/dev/null || echo 0)
  fi

  # Run pattern detection every 10 minutes (600 seconds)
  if [[ $((now - last_detect)) -ge 600 ]]; then
    if [[ -f ~/.claude/kernel/pattern-detector.js ]]; then
      node ~/.claude/kernel/pattern-detector.js detect >> ~/.claude/logs/pattern-detect.log 2>&1
    fi
    echo "$now" > "$last_detect_file"
  fi
}

# Run pattern detection in background
(__auto_pattern_detection &) 2>/dev/null

# ═══════════════════════════════════════════════════════════════════════════
# AUTO-ANALYZE NEW SESSIONS
# ═══════════════════════════════════════════════════════════════════════════

__auto_session_analysis() {
  local last_analysis_file="$HOME/.claude/data/.last-auto-analysis"
  local now=$(date +%s)
  local last_analysis=0

  if [[ -f "$last_analysis_file" ]]; then
    last_analysis=$(cat "$last_analysis_file" 2>/dev/null || echo 0)
  fi

  # Analyze new sessions every 30 minutes (1800 seconds)
  if [[ $((now - last_analysis)) -ge 1800 ]]; then
    # Analyze 3 most recent sessions that may not have been analyzed
    python3 "$OBSERVATORY_DIR/post-session-analyzer.py" --recent 3 >> ~/.claude/logs/auto-analysis.log 2>&1
    echo "$now" > "$last_analysis_file"
  fi
}

# Run session analysis in background
(__auto_session_analysis &) 2>/dev/null

# Session analysis aliases
alias session-analyze='python3 $OBSERVATORY_DIR/post-session-analyzer.py --session-id'
alias session-analyze-recent='python3 $OBSERVATORY_DIR/post-session-analyzer.py --recent'
alias session-analyze-all='python3 $OBSERVATORY_DIR/post-session-analyzer.py --all'

# Integrated feedback loop
alias feedback-loop='python3 $OBSERVATORY_DIR/integrated-feedback-loop.py'
alias feedback-loop-auto='python3 $OBSERVATORY_DIR/integrated-feedback-loop.py --auto-apply'
