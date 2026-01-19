#!/bin/bash
# Auto-archive research session on Claude Code stop
# Triggered by: hooks.Stop

cd ~/researchgravity

# Check if there's an active session
if [ -f ~/.agent/research/session.json ] || [ -f .agent/research/session.json ]; then
    python3 archive_session.py 2>/dev/null
    echo "Session auto-archived"
else
    echo "No active session"
fi
