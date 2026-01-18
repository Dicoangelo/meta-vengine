#!/bin/bash
# Claude Terminal Dashboard - Quick status overview

clear
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║               CLAUDE TERMINAL DASHBOARD                      ║"
echo "╠══════════════════════════════════════════════════════════════╣"

# Current directory context
PROJECT=$(basename "$(pwd)")
echo "║ 📂 Project: $PROJECT"
echo "║ 📍 Path: $(pwd)"
echo "╠══════════════════════════════════════════════════════════════╣"

# Active sessions
echo "║ 🖥️  ACTIVE SESSIONS:"
SESSIONS=$(tmux list-sessions 2>/dev/null | grep -c claude || echo "0")
echo "║    Claude sessions: $SESSIONS"
echo "╠══════════════════════════════════════════════════════════════╣"

# Today's activity
echo "║ 📊 TODAY'S ACTIVITY:"
TODAY_COUNT=$(grep "$(date '+%Y-%m-%d')" ~/.claude/activity.log 2>/dev/null | wc -l | tr -d ' ')
WRITES=$(grep "$(date '+%Y-%m-%d')" ~/.claude/activity.log 2>/dev/null | grep -c WRITE || echo "0")
EDITS=$(grep "$(date '+%Y-%m-%d')" ~/.claude/activity.log 2>/dev/null | grep -c EDIT || echo "0")
BASH_CMDS=$(grep "$(date '+%Y-%m-%d')" ~/.claude/activity.log 2>/dev/null | grep -c BASH || echo "0")
echo "║    Total actions: $TODAY_COUNT"
echo "║    Writes: $WRITES | Edits: $EDITS | Bash: $BASH_CMDS"
echo "╠══════════════════════════════════════════════════════════════╣"

# Recent activity
echo "║ 🕐 RECENT (last 5):"
tail -5 ~/.claude/activity.log 2>/dev/null | while read line; do
  echo "║    $line"
done
echo "╠══════════════════════════════════════════════════════════════╣"

# Checkpoints
CHECKPOINTS=$(ls ~/.claude/checkpoints/*.md 2>/dev/null | wc -l | tr -d ' ')
echo "║ 💾 Checkpoints saved: $CHECKPOINTS"
echo "╠══════════════════════════════════════════════════════════════╣"

# Quick commands
echo "║ ⚡ QUICK COMMANDS:"
echo "║    cx        → Start Claude session"
echo "║    q \"...\"   → Quick question (no session)"
echo "║    checkpoint→ Save checkpoint"
echo "║    today     → Today's activity"
echo "║    cl        → Live activity log"
echo "╚══════════════════════════════════════════════════════════════╝"
