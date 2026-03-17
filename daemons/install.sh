#!/usr/bin/env bash
# install.sh — Install meta-vengine LaunchAgent daemons
# Copies plists to ~/Library/LaunchAgents/ and loads them.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="$PROJECT_ROOT/data/daemon-logs"

PLISTS=(
    "com.metavengine.weight-snapshot.plist"
    "com.metavengine.lrf-update.plist"
    "com.metavengine.bo-monthly.plist"
)

# Ensure directories exist
mkdir -p "$LAUNCH_AGENTS_DIR"
mkdir -p "$LOG_DIR"

echo "Installing meta-vengine daemons..."

for plist in "${PLISTS[@]}"; do
    src="$SCRIPT_DIR/$plist"
    dst="$LAUNCH_AGENTS_DIR/$plist"

    if [ ! -f "$src" ]; then
        echo "  ERROR: $src not found, skipping"
        continue
    fi

    # Unload first if already loaded (ignore errors)
    if [ -f "$dst" ]; then
        launchctl unload "$dst" 2>/dev/null || true
    fi

    cp "$src" "$dst"
    launchctl load "$dst"
    echo "  Loaded: $plist"
done

echo "Done. Daemon logs will be written to: $LOG_DIR"
echo ""
echo "Schedules:"
echo "  weight-snapshot  — daily at 03:00"
echo "  lrf-update       — weekly Sunday at 04:00"
echo "  bo-monthly       — 1st of month at 05:00"
