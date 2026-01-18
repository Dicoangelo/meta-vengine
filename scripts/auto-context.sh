#!/bin/bash
# Auto-load project context when entering directories
# Source this in .zshrc

RESEARCHGRAVITY_DIR="$HOME/researchgravity"
AGENT_CORE="$HOME/.agent-core"

__claude_auto_context() {
  local project=""
  local cwd="$(pwd)"

  case "$cwd" in
    *OS-App*) project="os-app" ;;
    *CareerCoach*) project="careercoach" ;;
    *researchgravity*) project="researchgravity" ;;
    *antigravity*) project="metaventions" ;;
    *metaventions*) project="metaventions" ;;
  esac

  if [[ -n "$project" && "$project" != "$__CLAUDE_CURRENT_PROJECT" ]]; then
    export __CLAUDE_CURRENT_PROJECT="$project"
    echo "📂 Context: $project"

    # Optional: Auto-prefetch on project change
    if [[ -n "$CLAUDE_AUTO_PREFETCH" ]]; then
      python3 "$RESEARCHGRAVITY_DIR/prefetch.py" --project "$project" --days 7 --limit 3 --quiet
    fi
  fi
}

# Hook into cd
cd() {
  builtin cd "$@" && __claude_auto_context
}

# ============================================================
# PREFETCH FUNCTIONS - Memory Injection for Claude Sessions
# ============================================================

# Main prefetch command
# Usage: prefetch [project] [days]
prefetch() {
  local project="${1:-$__CLAUDE_CURRENT_PROJECT}"
  local days="${2:-14}"

  if [[ -z "$project" ]]; then
    echo "Usage: prefetch [project] [days]"
    echo "  Or: cd to a project directory first"
    echo ""
    echo "Available projects:"
    python3 "$RESEARCHGRAVITY_DIR/project_context.py" --list 2>/dev/null | grep -E "^[✓○]" || echo "  (none detected)"
    return 1
  fi

  python3 "$RESEARCHGRAVITY_DIR/prefetch.py" --project "$project" --days "$days" --papers
}

# Prefetch to clipboard
# Usage: prefetch-clip [project]
prefetch-clip() {
  local project="${1:-$__CLAUDE_CURRENT_PROJECT}"

  if [[ -z "$project" ]]; then
    echo "Usage: prefetch-clip [project]"
    return 1
  fi

  python3 "$RESEARCHGRAVITY_DIR/prefetch.py" --project "$project" --papers --clipboard
  echo "✓ Context copied to clipboard"
}

# Prefetch and inject into CLAUDE.md
# Usage: prefetch-inject [project]
prefetch-inject() {
  local project="${1:-$__CLAUDE_CURRENT_PROJECT}"

  if [[ -z "$project" ]]; then
    echo "Usage: prefetch-inject [project]"
    return 1
  fi

  python3 "$RESEARCHGRAVITY_DIR/prefetch.py" --project "$project" --papers --inject
}

# Quick research context for current topic
# Usage: prefetch-topic "multi-agent"
prefetch-topic() {
  local topic="$1"

  if [[ -z "$topic" ]]; then
    echo "Usage: prefetch-topic <topic>"
    return 1
  fi

  python3 "$RESEARCHGRAVITY_DIR/prefetch.py" --topic "$topic" --days 30 --papers
}

# Backfill learnings from archived sessions
# Usage: backfill-learnings [--since N]
backfill-learnings() {
  python3 "$RESEARCHGRAVITY_DIR/backfill_learnings.py" "$@"
}
