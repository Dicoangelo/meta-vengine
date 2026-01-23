#!/bin/bash
# Session Optimizer Stop Hook
# Analyzes session, updates patterns, runs feedback loop

set -e

KERNEL_DIR="$HOME/.claude/kernel"
SCRIPTS_DIR="$HOME/.claude/scripts"
OBSERVATORY_DIR="$SCRIPTS_DIR/observatory"
LOGS_DIR="$HOME/.claude/logs"

# Ensure log directory exists
mkdir -p "$LOGS_DIR"

LOG_FILE="$LOGS_DIR/session-optimizer.log"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOG_FILE"
}

log "Session optimizer stop hook started"

# End session in session-engine
if [ -f "$KERNEL_DIR/session-engine.js" ]; then
    node "$KERNEL_DIR/session-engine.js" end 2>/dev/null || true
    log "Session engine end called"
fi

# Run session agents analysis
if [ -d "$OBSERVATORY_DIR/session-agents" ]; then
    # Run each agent and collect results
    for agent in window_pattern budget_efficiency capacity_forecast task_prioritization model_recommendation session_health; do
        agent_file="$OBSERVATORY_DIR/session-agents/${agent}_agent.py"
        if [ -f "$agent_file" ]; then
            python3 "$agent_file" >> "$LOGS_DIR/session-agents.log" 2>&1 || true
        fi
    done
    log "Session agents analysis complete"
fi

# Run feedback loop analysis (but don't auto-apply - just analyze)
if [ -f "$SCRIPTS_DIR/session-optimizer/feedback_loop.py" ]; then
    python3 "$SCRIPTS_DIR/session-optimizer/feedback_loop.py" analyze 7 >> "$LOG_FILE" 2>&1 || true
    log "Feedback loop analysis complete"
fi

# Generate session summary
if [ -f "$KERNEL_DIR/session-engine.js" ]; then
    SUMMARY=$(node "$KERNEL_DIR/session-engine.js" status 2>/dev/null || echo "No summary available")
    log "Session summary: $SUMMARY"
fi

log "Session optimizer stop hook completed"

# ══════════════════════════════════════════════════════════════
# PATTERN DETECTION: Auto-detect session patterns
# ══════════════════════════════════════════════════════════════

detect_pattern() {
    local detector="$HOME/.claude/scripts/detect-session-pattern.py"
    if [ -f "$detector" ]; then
        python3 "$detector" 2>/dev/null || true
        log "Pattern detection completed"
    fi
}

detect_pattern

# ══════════════════════════════════════════════════════════════
# ROUTING METRICS: Auto-track session routing data
# ══════════════════════════════════════════════════════════════

track_routing() {
    python3 << 'ROUTINGTRACK' 2>/dev/null || true
import json
import hashlib
from pathlib import Path
from datetime import datetime

home = Path.home()
outcomes_file = home / ".claude/data/session-outcomes.jsonl"
dq_file = home / ".claude/kernel/dq-scores.jsonl"

if not outcomes_file.exists():
    exit()

# Get last session
try:
    with open(outcomes_file) as f:
        lines = f.readlines()
        if not lines:
            exit()
        session = json.loads(lines[-1])
except:
    exit()

# Skip if trivial
if (session.get('messages', 0) or 0) < 3:
    exit()
if 'warmup' in (session.get('title', '') or '').lower():
    exit()

# Check if already tracked
session_id = session.get('session_id', '')
query_hash = hashlib.md5(f"{session_id}{session.get('title', '')}".encode()).hexdigest()

if dq_file.exists():
    with open(dq_file) as f:
        for line in f:
            try:
                d = json.loads(line)
                if d.get('query_hash') == query_hash or d.get('session_id') == session_id:
                    exit()  # Already tracked
            except:
                pass

# Estimate complexity and DQ
title = session.get('title', '') or ''
intent = session.get('intent', '') or ''
messages = session.get('messages', 0) or 0
tools = session.get('tools', 0) or 0
outcome = session.get('outcome', '')
models_used = session.get('models_used', {})

text = f"{title} {intent}".lower()
high_kw = ["architect", "design", "system", "complex", "implement", "build"]
complexity = 0.3 + sum(0.1 for kw in high_kw if kw in text) + min(0.3, messages/200) + min(0.2, tools/100)
complexity = max(0.0, min(1.0, complexity))

dq = 0.4 + (complexity * 0.4)
if outcome == "success": dq += 0.15
elif outcome == "abandoned": dq -= 0.1
dq = max(0.1, min(1.0, dq))

model = max(models_used.keys(), key=lambda m: models_used.get(m, 0)) if models_used else ("opus" if complexity > 0.7 else "sonnet" if complexity > 0.4 else "haiku")

entry = {
    "ts": datetime.now().timestamp(),
    "session_id": session_id,
    "query_hash": query_hash,
    "query_preview": title[:80] if title else intent[:80],
    "model": model,
    "dqScore": round(dq, 3),
    "complexity": round(complexity, 3),
    "outcome": outcome,
    "source": "auto"
}

with open(dq_file, "a") as f:
    f.write(json.dumps(entry) + "\n")
ROUTINGTRACK
    log "Routing metrics tracked"
}

track_routing

# ══════════════════════════════════════════════════════════════
# SUPERMEMORY: Incremental sync on session end
# ══════════════════════════════════════════════════════════════

supermemory_sync() {
    local supermemory="$HOME/.claude/supermemory/cli.py"
    if [ -f "$supermemory" ]; then
        # Background sync to not block session end
        (python3 "$supermemory" sync &) 2>/dev/null
        log "Supermemory sync triggered"
    fi

    # Update snapshot timestamp
    echo "$(date +%Y-%m-%d)" > "$HOME/.claude/data/.last-snapshot"
    log "Snapshot timestamp updated"
}

supermemory_sync

# ══════════════════════════════════════════════════════════════
# AUTOMATED MITIGATIONS: Cleanup
# ══════════════════════════════════════════════════════════════

cleanup_session() {
    [ -f "$HOME/.claude/scripts/session-lock.sh" ] && source "$HOME/.claude/scripts/session-lock.sh"
    release_session_lock "$$" 2>/dev/null
}

cleanup_session

# ══════════════════════════════════════════════════════════════
# INCREMENTAL TOKEN TRACKING: Update stats-cache with session tokens
# ══════════════════════════════════════════════════════════════

track_session_tokens() {
    python3 << 'TOKENTRACK' 2>/dev/null || true
import json
from pathlib import Path
from datetime import datetime
import os

home = Path.home()
stats_file = home / ".claude/stats-cache.json"
projects_dir = home / ".claude/projects"

if not stats_file.exists():
    exit()

# Find most recently modified transcript (current session)
latest_transcript = None
latest_mtime = 0

for transcript in projects_dir.glob("**/*.jsonl"):
    mtime = transcript.stat().st_mtime
    if mtime > latest_mtime:
        latest_mtime = mtime
        latest_transcript = transcript

if not latest_transcript:
    exit()

# Only process if modified in last 5 minutes (current session)
if (datetime.now().timestamp() - latest_mtime) > 300:
    exit()

# Extract tokens from current session
session_tokens = {
    "cache_read": 0,
    "input": 0,
    "cache_create": 0,
    "output": 0
}

try:
    with open(latest_transcript) as f:
        for line in f:
            try:
                d = json.loads(line)
                usage = d.get('message', {}).get('usage', {})
                if usage:
                    session_tokens["cache_read"] += usage.get('cache_read_input_tokens', 0)
                    session_tokens["input"] += usage.get('input_tokens', 0)
                    session_tokens["cache_create"] += usage.get('cache_creation_input_tokens', 0)
                    session_tokens["output"] += usage.get('output_tokens', 0)
            except:
                pass
except:
    exit()

# Skip if no meaningful tokens
if session_tokens["cache_read"] + session_tokens["input"] < 1000:
    exit()

# Load current stats
try:
    with open(stats_file) as f:
        stats = json.load(f)
except:
    exit()

# Check if already processed (use a marker file)
marker_file = home / ".claude/kernel/.last-token-update"
marker_key = f"{latest_transcript}:{latest_mtime}"

if marker_file.exists():
    try:
        last_marker = marker_file.read_text().strip()
        if last_marker == marker_key:
            exit()  # Already processed this session
    except:
        pass

# Update modelUsage totals incrementally
opus_usage = stats.get("modelUsage", {}).get("opus", {})
opus_usage["cacheReadInputTokens"] = opus_usage.get("cacheReadInputTokens", 0) + session_tokens["cache_read"]
opus_usage["inputTokens"] = opus_usage.get("inputTokens", 0) + session_tokens["input"]
opus_usage["cacheCreationInputTokens"] = opus_usage.get("cacheCreationInputTokens", 0) + session_tokens["cache_create"]
opus_usage["outputTokens"] = opus_usage.get("outputTokens", 0) + session_tokens["output"]

stats["modelUsage"]["opus"] = opus_usage
stats["lastComputedDate"] = datetime.now().strftime("%Y-%m-%d")

# Write updated stats
with open(stats_file, "w") as f:
    json.dump(stats, f, indent=2)

# Write marker
marker_file.parent.mkdir(parents=True, exist_ok=True)
marker_file.write_text(marker_key)

TOKENTRACK
    log "Incremental token tracking completed"
}

track_session_tokens
