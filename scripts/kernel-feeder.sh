#!/bin/bash
# Kernel Feeder - Bulk data injection to all kernel systems
# Sources: transcripts, git, shell history, activity logs

KERNEL_DIR="$HOME/.claude/kernel"
DATA_DIR="$HOME/.claude/data"
LOG="$HOME/.claude/logs/kernel-feeder.log"

mkdir -p "$DATA_DIR" "$(dirname "$LOG")"

log() { echo "$(date '+%H:%M:%S') $1" >> "$LOG"; }

# ═══════════════════════════════════════════════════════════════════════════
# ACTIVITY TRACKER FEED
# ═══════════════════════════════════════════════════════════════════════════
feed_activity() {
    log "Feeding activity tracker..."

    local activity_file="$KERNEL_DIR/activity.json"
    local sessions=()

    # Count recent sessions from transcripts
    local session_count=$(find ~/.claude/projects -name "*.jsonl" -mtime -7 2>/dev/null | wc -l | tr -d ' ')

    # Update activity.json
    python3 << EOF
import json
from datetime import datetime
from pathlib import Path

activity_file = Path("$activity_file")
data = json.loads(activity_file.read_text()) if activity_file.exists() else {"sessions": []}

# Add today's session count
today = datetime.now().strftime('%Y-%m-%d')
data['sessions'] = [s for s in data.get('sessions', []) if s.get('date') != today]
data['sessions'].append({
    "date": today,
    "count": $session_count,
    "timestamp": datetime.now().isoformat()
})
data['lastUpdated'] = datetime.now().isoformat()

# Keep last 30 days
data['sessions'] = data['sessions'][-30:]

activity_file.write_text(json.dumps(data, indent=2))
print(f"Updated activity: {len(data['sessions'])} days tracked")
EOF
}

# ═══════════════════════════════════════════════════════════════════════════
# SUBSCRIPTION TRACKER FEED
# ═══════════════════════════════════════════════════════════════════════════
feed_subscription() {
    log "Feeding subscription tracker..."

    local sub_file="$KERNEL_DIR/subscription-data.json"

    # Calculate value from tool usage and sessions
    python3 << EOF
import json
from datetime import datetime
from pathlib import Path

sub_file = Path("$sub_file")
tool_file = Path("$DATA_DIR/tool-usage.jsonl")
dq_file = Path("$KERNEL_DIR/dq-scores.jsonl")

# Count tools and estimate value
tool_count = 0
if tool_file.exists():
    tool_count = sum(1 for _ in open(tool_file))

# Count DQ entries
dq_count = 0
if dq_file.exists():
    dq_count = sum(1 for _ in open(dq_file))

# Estimate value: each tool call ~$0.50, each DQ query ~$2
estimated_value = (tool_count * 0.5) + (dq_count * 2)

data = {
    "totalValue": round(estimated_value, 2),
    "toolCalls": tool_count,
    "dqQueries": dq_count,
    "monthlySubscription": 200,
    "roiMultiplier": round(estimated_value / 200, 1) if estimated_value > 0 else 0,
    "lastUpdated": datetime.now().isoformat()
}

sub_file.write_text(json.dumps(data, indent=2))
print(f"Subscription value: \${data['totalValue']:.0f} ({data['roiMultiplier']}x ROI)")
EOF
}

# ═══════════════════════════════════════════════════════════════════════════
# COMPLEXITY ANALYZER FEED
# ═══════════════════════════════════════════════════════════════════════════
feed_complexity() {
    log "Feeding complexity analyzer..."

    local complexity_file="$KERNEL_DIR/complexity-data.json"

    python3 << EOF
import json
from datetime import datetime
from pathlib import Path
from collections import Counter

complexity_file = Path("$complexity_file")
dq_file = Path("$KERNEL_DIR/dq-scores.jsonl")

analyses = []
model_counts = Counter()

if dq_file.exists():
    with open(dq_file) as f:
        for line in f:
            try:
                entry = json.loads(line)
                model = entry.get('model', 'unknown')
                complexity = entry.get('complexity', entry.get('dqScore', 0.5))
                model_counts[model] += 1

                # Categorize complexity
                if complexity < 0.3:
                    level = "simple"
                elif complexity < 0.7:
                    level = "moderate"
                else:
                    level = "complex"

            except:
                pass

# Calculate distribution
total = sum(model_counts.values()) or 1
distribution = {
    "haiku": model_counts.get('haiku', 0) / total,
    "sonnet": model_counts.get('sonnet', 0) / total,
    "opus": model_counts.get('opus', 0) / total
}

data = {
    "totalQueries": sum(model_counts.values()),
    "modelDistribution": {k: round(v, 3) for k, v in distribution.items()},
    "modelCounts": dict(model_counts),
    "avgComplexity": round(
        (distribution.get('haiku', 0) * 0.2 +
         distribution.get('sonnet', 0) * 0.5 +
         distribution.get('opus', 0) * 0.85), 3
    ),
    "lastUpdated": datetime.now().isoformat()
}

complexity_file.write_text(json.dumps(data, indent=2))
print(f"Complexity: avg={data['avgComplexity']:.2f}, queries={data['totalQueries']}")
EOF
}

# ═══════════════════════════════════════════════════════════════════════════
# CONTEXT BUDGET FEED
# ═══════════════════════════════════════════════════════════════════════════
feed_context_budget() {
    log "Feeding context budget..."

    local budget_file="$KERNEL_DIR/context-budget.json"

    python3 << EOF
import json
from datetime import datetime
from pathlib import Path

budget_file = Path("$budget_file")
session_file = Path("$DATA_DIR/session-events.jsonl")

# Estimate context usage from session events
total_messages = 0
if session_file.exists():
    with open(session_file) as f:
        for line in f:
            try:
                entry = json.loads(line)
                total_messages += entry.get('messages', 0)
            except:
                pass

# Estimate tokens (avg 500 tokens per message exchange)
estimated_tokens = total_messages * 500
daily_budget = 1000000  # 1M tokens/day estimate

data = {
    "estimatedTokensUsed": estimated_tokens,
    "dailyBudget": daily_budget,
    "utilizationPercent": round((estimated_tokens / daily_budget) * 100, 1),
    "totalMessages": total_messages,
    "lastUpdated": datetime.now().isoformat()
}

budget_file.write_text(json.dumps(data, indent=2))
print(f"Context budget: {data['utilizationPercent']}% utilized ({total_messages} messages)")
EOF
}

# ═══════════════════════════════════════════════════════════════════════════
# TOKEN OPTIMIZER FEED
# ═══════════════════════════════════════════════════════════════════════════
feed_token_optimizer() {
    log "Feeding token optimizer..."

    local cache_file="$KERNEL_DIR/token-cache.json"

    python3 << EOF
import json
from datetime import datetime
from pathlib import Path

cache_file = Path("$cache_file")
memory_file = Path("$KERNEL_DIR/memory-graph.json")

# Build cache from memory graph
cache = {}
if memory_file.exists():
    try:
        memory = json.loads(memory_file.read_text())
        for node in memory.get('nodes', []):
            content = node.get('content', '')
            if len(content) > 20:
                # Create cache key from first 50 chars
                key = content[:50].lower().replace(' ', '_')
                cache[key] = {
                    "content": content,
                    "type": node.get('type', 'unknown'),
                    "tokens": len(content.split()) * 1.3,  # Rough token estimate
                    "lastUsed": datetime.now().isoformat()
                }
    except:
        pass

data = {
    "cache": cache,
    "cacheSize": len(cache),
    "totalTokensCached": sum(int(v.get('tokens', 0)) for v in cache.values()),
    "hits": 0,
    "misses": 0,
    "lastUpdated": datetime.now().isoformat()
}

cache_file.write_text(json.dumps(data, indent=2))
print(f"Token cache: {len(cache)} entries, ~{data['totalTokensCached']:.0f} tokens")
EOF
}

# ═══════════════════════════════════════════════════════════════════════════
# GIT TRACKER FEED
# ═══════════════════════════════════════════════════════════════════════════
feed_git_tracker() {
    log "Feeding git tracker..."

    local git_file="$DATA_DIR/git-activity.jsonl"

    # Scan repos for recent commits
    for repo in ~/OS-App ~/CareerCoachAntigravity ~/researchgravity ~/.agent-core; do
        if [[ -d "$repo/.git" ]]; then
            cd "$repo"
            git log --oneline --since="7 days ago" --format='{"ts":%ct,"repo":"'$(basename "$repo")'","hash":"%h","msg":"%s"}' 2>/dev/null >> "$git_file"
        fi
    done

    # Dedupe
    if [[ -f "$git_file" ]]; then
        sort -u "$git_file" -o "$git_file"
        echo "Git activity: $(wc -l < "$git_file" | tr -d ' ') commits tracked"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════
main() {
    echo "═══════════════════════════════════════════════════════════════"
    echo "KERNEL FEEDER - Bulk Data Injection"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""

    feed_activity
    feed_subscription
    feed_complexity
    feed_context_budget
    feed_token_optimizer
    feed_git_tracker

    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "All kernel systems fed successfully"
    echo "═══════════════════════════════════════════════════════════════"
}

main "$@"
