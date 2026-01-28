#!/bin/bash
# Data Architecture Guard - Pre-commit Hook
# Warns about potential data architecture violations before committing

set -e

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
  exit 0
fi

# Get staged files
new_jsonl=$(git diff --cached --name-only --diff-filter=A | grep '\.jsonl$' || true)
new_sync=$(git diff --cached --name-only --diff-filter=A | grep -E '(sync|bridge|replicate|to-.*-to)' || true)

# Check for data duplication patterns in staged changes
duplicate_writes=$(git diff --cached | grep -E '(\.jsonl.*\.db|\.db.*\.jsonl)' || true)

# If any red flags detected, warn the user
if [ -n "$new_jsonl" ] || [ -n "$new_sync" ] || [ -n "$duplicate_writes" ]; then
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "⚠️  DATA ARCHITECTURE WARNING"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  echo "Potential data architecture issues detected:"
  echo ""

  if [ -n "$new_jsonl" ]; then
    echo "🚩 New JSONL files:"
    echo "$new_jsonl" | sed 's/^/   - /'
    echo ""
    echo "   Question: Should this be SQLite instead?"
    echo "   (Structured data with queries → SQLite)"
    echo ""
  fi

  if [ -n "$new_sync" ]; then
    echo "🚩 Potential sync scripts:"
    echo "$new_sync" | sed 's/^/   - /'
    echo ""
    echo "   Question: Can consumers read from source instead?"
    echo "   (Sync scripts create data duplication)"
    echo ""
  fi

  if [ -n "$duplicate_writes" ]; then
    echo "🚩 Possible duplicate writes detected (JSONL + SQLite)"
    echo ""
    echo "   Question: Is this violating Single Source of Truth?"
    echo ""
  fi

  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "See guidance: /data-arch-guard skill"
  echo "Or run: claude -p '/data-arch-guard'"
  echo ""
  echo "Review checklist:"
  echo "  [ ] Is this creating duplicate data?"
  echo "  [ ] Will this need a sync script later?"
  echo "  [ ] Can I use SQLite instead of JSONL?"
  echo "  [ ] Does this data already exist elsewhere?"
  echo ""
  echo "Press Enter to continue or Ctrl+C to abort commit"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  read -r
fi

exit 0
