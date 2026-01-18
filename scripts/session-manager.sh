#!/bin/bash
# Session management automation

SESSION_DIR="$HOME/.claude/sessions"
mkdir -p "$SESSION_DIR"

# Start named session with tmux
claude-session() {
  local name="${1:-main}"
  tmux new-session -A -s "claude-$name" "cc"
}

# List active Claude sessions
claude-list() {
  tmux list-sessions 2>/dev/null | grep claude || echo "No active Claude sessions"
}

# Kill all Claude sessions
claude-kill-all() {
  tmux kill-session -t claude-main 2>/dev/null
  echo "Claude sessions terminated"
}

# Quick attach to main session
cx() {
  tmux new-session -A -s claude-main "cc"
}

# Session with project context
cxp() {
  local project="${1:-$(basename $(pwd))}"
  cd ~/"$project" 2>/dev/null || cd ~
  tmux new-session -A -s "claude-$project" "cc"
}
