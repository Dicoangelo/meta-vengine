#!/bin/bash
# Update hooks to write directly to SQLite
# Purpose: Ensure new events go to SQLite instead of JSONL
# Created: 2026-01-28

echo "=================================================================="
echo "Updating Hooks for SQLite Direct Writes"
echo "=================================================================="

# Check if hooks directory exists
HOOKS_DIR="$HOME/.claude/hooks"
if [ ! -d "$HOOKS_DIR" ]; then
    echo "⚠️  Hooks directory not found: $HOOKS_DIR"
    exit 1
fi

echo -e "\n📂 Current hooks:"
ls -1 "$HOOKS_DIR"/*.sh 2>/dev/null | sed 's|.*/||' | sed 's|^|  - |'

echo -e "\n🔍 Checking for JSONL writes in hooks..."
echo "----------------------------"

# Find hooks that write to JSONL files
HOOKS_WITH_JSONL=$(grep -l ">> .*\.jsonl" "$HOOKS_DIR"/*.sh 2>/dev/null)

if [ -z "$HOOKS_WITH_JSONL" ]; then
    echo "  ✅ No hooks writing to JSONL files"
else
    echo "  ⚠️  Found hooks writing to JSONL:"
    echo "$HOOKS_WITH_JSONL" | sed 's|.*/||' | sed 's|^|    - |'
fi

echo -e "\n📋 Recommendation:"
echo "----------------------------"
echo "To write directly to SQLite from hooks, use this pattern:"
echo ""
cat << 'EXAMPLE'
# Instead of:
echo "{\"tool\":\"Read\",\"timestamp\":$(date +%s)}" >> ~/.claude/data/tool-usage.jsonl

# Use:
sqlite3 ~/.claude/data/claude.db << SQL
INSERT INTO tool_events (timestamp, tool_name, success, duration_ms)
VALUES ($(date +%s), 'Read', 1, NULL);
SQL
EXAMPLE

echo -e "\n📝 Helper Function (add to hooks):"
echo "----------------------------"
cat << 'HELPER'
# SQLite logging helper
log_tool_event() {
    local tool="$1"
    local success="${2:-1}"
    local duration="${3:-NULL}"
    sqlite3 ~/.claude/data/claude.db << SQL
INSERT INTO tool_events (timestamp, tool_name, success, duration_ms)
VALUES ($(date +%s), '$tool', $success, $duration);
SQL
}

# Usage:
log_tool_event "Read" 1 42
HELPER

echo -e "\n✅ No automatic changes made to hooks"
echo "   Review and update hooks manually as needed"
echo ""
echo "=================================================================="
