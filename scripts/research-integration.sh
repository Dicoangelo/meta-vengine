#!/bin/bash
# ResearchGravity integration for Claude terminal workflow
# Connects Claude sessions with research tracking

RESEARCH_DIR="$HOME/researchgravity"
AGENT_CORE="$HOME/.agent-core"

# Quick research session start
research() {
  local topic="$1"
  if [[ -z "$topic" ]]; then
    echo "Usage: research <topic>"
    echo "  Starts a new research session in researchgravity"
    return 1
  fi

  cd "$RESEARCH_DIR"
  python3 init_session.py "$topic"
  echo "✓ Research session started: $topic"
  echo "  Log URLs with: rlog <url>"
  echo "  Archive with: rarchive"
}

# Log URL to current research session
rlog() {
  local url="$1"
  local tier="${2:-2}"
  local category="${3:-reference}"

  if [[ -z "$url" ]]; then
    echo "Usage: rlog <url> [tier] [category]"
    echo "  tier: 1 (must-read), 2 (important), 3 (reference)"
    echo "  category: paper, code, blog, docs, reference"
    return 1
  fi

  cd "$RESEARCH_DIR"
  python3 log_url.py "$url" --tier "$tier" --category "$category"
  echo "✓ Logged: $url (tier $tier)"
}

# Research status
rstatus() {
  cd "$RESEARCH_DIR"
  python3 status.py 2>/dev/null || echo "No active research session"
}

# Archive current research session
rarchive() {
  cd "$RESEARCH_DIR"
  python3 archive_session.py
  echo "✓ Research session archived"
}

# Quick URL log from clipboard (macOS)
rclip() {
  local url=$(pbpaste)
  if [[ "$url" == http* ]]; then
    rlog "$url" "${1:-2}" "${2:-reference}"
  else
    echo "Clipboard doesn't contain a URL"
  fi
}

# Search research archives
rsearch() {
  local query="$1"
  if [[ -z "$query" ]]; then
    echo "Usage: rsearch <query>"
    return 1
  fi

  echo "═══ RESEARCH ARCHIVES ═══"
  grep -ri "$query" "$AGENT_CORE/research/" 2>/dev/null | head -20

  echo ""
  echo "═══ SESSION ARCHIVES ═══"
  grep -ri "$query" "$AGENT_CORE/sessions/" 2>/dev/null | head -20
}

# List recent research sessions
rlist() {
  echo "═══ RECENT RESEARCH SESSIONS ═══"
  ls -lt "$AGENT_CORE/sessions/" 2>/dev/null | head -10
}

# Load research context into Claude
rcontext() {
  local session="$1"
  if [[ -z "$session" ]]; then
    echo "Recent sessions:"
    ls "$AGENT_CORE/sessions/" 2>/dev/null | head -5
    echo ""
    echo "Usage: rcontext <session-name>"
    return 1
  fi

  local session_file="$AGENT_CORE/sessions/$session"
  if [[ -d "$session_file" ]]; then
    echo "═══ SESSION: $session ═══"
    cat "$session_file"/*.md 2>/dev/null | head -100
  else
    echo "Session not found: $session"
  fi
}

# Start research + Claude together
research-session() {
  local topic="$1"
  if [[ -z "$topic" ]]; then
    echo "Usage: research-session <topic>"
    return 1
  fi

  # Start research tracking
  research "$topic"

  # Start Claude with research context
  echo ""
  echo "Starting Claude with research context..."
  cc "I'm starting a research session on: $topic. Help me explore this topic systematically."
}
