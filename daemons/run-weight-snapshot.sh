#!/usr/bin/env bash
# run-weight-snapshot.sh — Daily weight snapshot daemon
# Calls WeightSafety.take_snapshot() to record current learnable weights.

set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

PROJECT_ROOT="$HOME/projects/core/meta-vengine"
DAEMON_NAME="weight-snapshot"
LOG_DIR="$PROJECT_ROOT/data/daemon-logs"
LOG_FILE="$LOG_DIR/${DAEMON_NAME}.log"
MAX_LOG_BYTES=10485760  # 10 MB

# --- Defensive checks ---
if ! command -v python3 &>/dev/null; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) [$DAEMON_NAME] ERROR: python3 not found" >&2
    exit 1
fi

if [ ! -d "$PROJECT_ROOT" ]; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) [$DAEMON_NAME] ERROR: project root not found: $PROJECT_ROOT" >&2
    exit 1
fi

mkdir -p "$LOG_DIR"

# --- Log rotation ---
if [ -f "$LOG_FILE" ]; then
    log_size=$(stat -f%z "$LOG_FILE" 2>/dev/null || echo 0)
    if [ "$log_size" -gt "$MAX_LOG_BYTES" ]; then
        mv "$LOG_FILE" "${LOG_FILE}.1"
    fi
fi

# --- banditEnabled gate ---
BANDIT_ENABLED=$(python3 -c "
import json, pathlib
cfg = json.loads(pathlib.Path('$PROJECT_ROOT/config/learnable-params.json').read_text())
print('true' if cfg.get('banditEnabled') else 'false')
")

if [ "$BANDIT_ENABLED" = "false" ]; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) [$DAEMON_NAME] banditEnabled=false, skipping"
    exit 0
fi

# --- Run ---
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) [$DAEMON_NAME] START"

cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT"

python3 kernel/weight-snapshot-daemon.py
EXIT_CODE=$?

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) [$DAEMON_NAME] END exit=$EXIT_CODE"
exit $EXIT_CODE
