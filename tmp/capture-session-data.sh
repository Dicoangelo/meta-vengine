#!/bin/bash
# Capture what Claude Code sends to statusline
{
    echo "=== $(date) ==="
    echo "PWD: $PWD"
    echo "ENV VARS:"
    env | grep -i claude || echo "  (none)"
    echo ""
    echo "STDIN:"
    timeout 0.5 cat || echo "  (no stdin)"
    echo ""
} >> ~/.claude/tmp/statusline-capture.log 2>&1
echo "Sonnet | ████░░░░░░░░░░░░░░░░ 35% (70k/200k) | ~/OS-App | Session: test"
