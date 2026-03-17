#!/usr/bin/env bash
# uninstall.sh — Remove meta-vengine LaunchAgent daemons

set -euo pipefail

LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"

PLISTS=(
    "com.metavengine.weight-snapshot.plist"
    "com.metavengine.lrf-update.plist"
    "com.metavengine.bo-monthly.plist"
)

echo "Uninstalling meta-vengine daemons..."

for plist in "${PLISTS[@]}"; do
    dst="$LAUNCH_AGENTS_DIR/$plist"

    if [ ! -f "$dst" ]; then
        echo "  Not found: $plist (skipping)"
        continue
    fi

    launchctl unload "$dst" 2>/dev/null || true
    rm "$dst"
    echo "  Removed: $plist"
done

echo "Done. Daemon log files in data/daemon-logs/ were not removed."
