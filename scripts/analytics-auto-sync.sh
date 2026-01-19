#!/bin/bash
# Analytics Auto-Sync - Keeps all dashboard data sources updated

KERNEL_DIR="$HOME/.claude/kernel"
DATA_DIR="$HOME/.claude/data"
LOG="$HOME/.claude/logs/analytics-sync.log"

mkdir -p "$(dirname "$LOG")"
log() { echo "$(date '+%H:%M:%S') $1" >> "$LOG"; }

log "Analytics sync started"

# ═══════════════════════════════════════════════════════════════════════════
# 1. UPDATE STATS CACHE (for ccc dashboard)
# ═══════════════════════════════════════════════════════════════════════════

update_stats_cache() {
    python3 << 'EOF'
import json
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

stats_file = Path.home() / ".claude" / "stats-cache.json"
projects_dir = Path.home() / ".claude" / "projects"

# Load existing or create new
stats = {"version": 1, "dailyActivity": []}
if stats_file.exists():
    try:
        stats = json.loads(stats_file.read_text())
    except:
        pass

# Calculate daily activity from transcripts
daily = defaultdict(lambda: {"messages": 0, "sessions": 0, "tools": 0})

for transcript in projects_dir.glob("**/*.jsonl"):
    try:
        mtime = datetime.fromtimestamp(transcript.stat().st_mtime)
        date_str = mtime.strftime('%Y-%m-%d')
        daily[date_str]["sessions"] += 1

        with open(transcript) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    if entry.get('type') in ['user', 'assistant']:
                        daily[date_str]["messages"] += 1
                    if entry.get('type') == 'assistant':
                        msg = entry.get('message', {})
                        content = msg.get('content', [])
                        if isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict) and item.get('type') == 'tool_use':
                                    daily[date_str]["tools"] += 1
                except:
                    pass
    except:
        pass

# Update stats
stats['lastComputedDate'] = datetime.now().strftime('%Y-%m-%d')
stats['dailyActivity'] = [
    {"date": d, "messageCount": v["messages"], "sessionCount": v["sessions"], "toolCallCount": v["tools"]}
    for d, v in sorted(daily.items(), reverse=True)[:30]
]

stats_file.write_text(json.dumps(stats, indent=2))
print(f"Stats cache updated: {len(stats['dailyActivity'])} days")
EOF
}

# ═══════════════════════════════════════════════════════════════════════════
# 2. UPDATE DETECTED PATTERNS
# ═══════════════════════════════════════════════════════════════════════════

update_patterns() {
    if [[ -f "$KERNEL_DIR/pattern-detector.js" ]]; then
        node "$KERNEL_DIR/pattern-detector.js" detect >> "$LOG" 2>&1 || true
        log "Patterns updated"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════
# 3. SYNC ROUTING METRICS
# ═══════════════════════════════════════════════════════════════════════════

sync_routing_metrics() {
    if [[ -f ~/researchgravity/routing-metrics.py ]]; then
        python3 ~/researchgravity/routing-metrics.py report --days 7 --format json >> "$LOG" 2>&1 || true
        log "Routing metrics synced"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════
# 4. CONSOLIDATE TOOL SUCCESS DATA
# ═══════════════════════════════════════════════════════════════════════════

consolidate_tool_data() {
    python3 << 'EOF'
import json
from pathlib import Path
from collections import Counter

tool_usage = Path.home() / ".claude" / "data" / "tool-usage.jsonl"
tool_success = Path.home() / ".claude" / "data" / "tool-success.jsonl"

if not tool_usage.exists():
    exit()

# Count tools
tools = Counter()
with open(tool_usage) as f:
    for line in f:
        try:
            entry = json.loads(line)
            tools[entry.get('tool', 'unknown')] += 1
        except:
            pass

# Update summary
summary_file = Path.home() / ".claude" / "kernel" / "tool-summary.json"
summary = {
    "totalCalls": sum(tools.values()),
    "uniqueTools": len(tools),
    "topTools": tools.most_common(20),
    "updated": __import__('datetime').datetime.now().isoformat()
}
summary_file.write_text(json.dumps(summary, indent=2))
print(f"Tool summary: {sum(tools.values())} calls, {len(tools)} unique tools")
EOF
}

# ═══════════════════════════════════════════════════════════════════════════
# 5. UPDATE ACTIVITY TIMELINE FOR DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════

update_activity_timeline() {
    python3 << 'EOF'
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

kernel_dir = Path.home() / ".claude" / "kernel"
data_dir = Path.home() / ".claude" / "data"

# Aggregate from all sources
activity = defaultdict(lambda: {"tools": 0, "sessions": 0, "messages": 0, "commits": 0})

# From tool usage
tool_file = data_dir / "tool-usage.jsonl"
if tool_file.exists():
    with open(tool_file) as f:
        for line in f:
            try:
                entry = json.loads(line)
                ts = entry.get('ts', 0)
                if ts:
                    day = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
                    activity[day]["tools"] += 1
            except:
                pass

# From git activity
git_file = data_dir / "git-activity.jsonl"
if git_file.exists():
    with open(git_file) as f:
        for line in f:
            try:
                entry = json.loads(line)
                ts = entry.get('ts', 0)
                if ts:
                    day = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
                    activity[day]["commits"] += 1
            except:
                pass

# From session events
session_file = data_dir / "session-events.jsonl"
if session_file.exists():
    with open(session_file) as f:
        for line in f:
            try:
                entry = json.loads(line)
                ts = entry.get('ts', 0)
                if ts:
                    day = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
                    activity[day]["sessions"] += 1
                    activity[day]["messages"] += entry.get('messages', 0)
            except:
                pass

# Write timeline
timeline = {
    "generated": datetime.now().isoformat(),
    "days": [(d, v) for d, v in sorted(activity.items(), reverse=True)[:30]],
    "totals": {
        "tools": sum(d["tools"] for d in activity.values()),
        "sessions": sum(d["sessions"] for d in activity.values()),
        "messages": sum(d["messages"] for d in activity.values()),
        "commits": sum(d["commits"] for d in activity.values())
    }
}

(kernel_dir / "activity-timeline.json").write_text(json.dumps(timeline, indent=2))
print(f"Activity timeline: {len(activity)} days, {timeline['totals']['tools']} tools, {timeline['totals']['commits']} commits")
EOF
}

# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

main() {
    echo "═══════════════════════════════════════════════════════════════"
    echo "ANALYTICS AUTO-SYNC"
    echo "═══════════════════════════════════════════════════════════════"

    update_stats_cache
    update_patterns
    sync_routing_metrics
    consolidate_tool_data
    update_activity_timeline

    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    log "Analytics sync complete"
}

main "$@"
