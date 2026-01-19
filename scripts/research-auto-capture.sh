#!/bin/bash
# Research Auto-Capture - Runs after each Claude session

RESEARCHGRAVITY="$HOME/researchgravity"
LOG="$HOME/.claude/logs/research-capture.log"
mkdir -p "$(dirname "$LOG")"

echo "$(date '+%H:%M:%S') Research auto-capture started" >> "$LOG"

# 1. Extract learnings from latest session
python3 "$HOME/.claude/scripts/research-extract.py" 2>> "$LOG"

# 2. Sync to memory linker
MEMORY_LINKER="$HOME/.claude/kernel/memory-linker.js"
if [[ -f "$MEMORY_LINKER" ]]; then
    # Get latest learning and store
    LATEST=$(tail -20 ~/.agent-core/memory/learnings.md 2>/dev/null | head -5 | tr '\n' ' ' | cut -c1-200)
    if [[ -n "$LATEST" && ${#LATEST} -gt 30 ]]; then
        node "$MEMORY_LINKER" store "$LATEST" insight research auto-capture 2>/dev/null &
    fi
fi

# 3. Archive session if researchgravity available
if [[ -f "$RESEARCHGRAVITY/archive_session.py" ]]; then
    cd "$RESEARCHGRAVITY" && python3 archive_session.py 2>> "$LOG" || true
fi

echo "$(date '+%H:%M:%S') Research auto-capture complete" >> "$LOG"
