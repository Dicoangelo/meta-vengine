#!/bin/bash
# Git Post-Commit Hook - Track commit activity for CCC dashboard
# Install: ln -sf ~/.claude/hooks/git-post-commit.sh ~/PROJECT/.git/hooks/post-commit

DATA_FILE="$HOME/.claude/data/git-activity.jsonl"
LOG_FILE="$HOME/.claude/logs/git-hooks.log"

# Get commit info
COMMIT_HASH=$(git rev-parse HEAD 2>/dev/null)
COMMIT_MSG=$(git log -1 --format="%s" 2>/dev/null)
COMMIT_DATE=$(git log -1 --format="%ci" 2>/dev/null)
AUTHOR=$(git log -1 --format="%an" 2>/dev/null)
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
REPO_NAME=$(basename "$(git rev-parse --show-toplevel 2>/dev/null)")
FILES_CHANGED=$(git diff-tree --no-commit-id --name-only -r HEAD 2>/dev/null | wc -l | tr -d ' ')

# Get stats
STATS=$(git diff-tree --stat --no-commit-id HEAD 2>/dev/null | tail -1)
INSERTIONS=$(echo "$STATS" | grep -oE '[0-9]+ insertion' | grep -oE '[0-9]+' || echo "0")
DELETIONS=$(echo "$STATS" | grep -oE '[0-9]+ deletion' | grep -oE '[0-9]+' || echo "0")

# Create JSON entry
TIMESTAMP=$(date +%s)
JSON_ENTRY=$(cat << EOF
{"ts":$TIMESTAMP,"type":"commit","repo":"$REPO_NAME","branch":"$BRANCH","hash":"${COMMIT_HASH:0:8}","message":"$(echo "$COMMIT_MSG" | sed 's/"/\\"/g' | head -c 100)","author":"$AUTHOR","files":$FILES_CHANGED,"insertions":${INSERTIONS:-0},"deletions":${DELETIONS:-0},"date":"$COMMIT_DATE"}
EOF
)

# Dual-write to JSONL + SQLite
mkdir -p "$(dirname "$DATA_FILE")"
echo "$JSON_ENTRY" >> "$DATA_FILE"

# Also write to SQLite via dual-write library
python3 << PYEOF
import sys
sys.path.insert(0, '$HOME/.claude/hooks')
from dual_write_lib import log_git_activity

log_git_activity(
    repo="$REPO_NAME",
    commit_hash="${COMMIT_HASH:0:8}",
    message="$(echo "$COMMIT_MSG" | sed 's/"/\\"/g' | head -c 200)"
)
PYEOF

# Log
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Commit tracked: $REPO_NAME ${COMMIT_HASH:0:8}" >> "$LOG_FILE"
