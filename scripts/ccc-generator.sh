#!/bin/bash
# Claude Command Center - Ultimate Dashboard Generator
# Aggregates all data sources and opens the unified dashboard

set -e

# Parse arguments
NO_OPEN=false
for arg in "$@"; do
  case $arg in
    --no-open) NO_OPEN=true ;;
  esac
done

STATS_FILE="$HOME/.claude/stats-cache.json"
MEMORY_FILE="$HOME/.claude/memory/knowledge.json"
ACTIVITY_LOG="$HOME/.claude/activity.log"
TEMPLATE="$HOME/.claude/scripts/command-center.html"
OUTPUT="$HOME/.claude/dashboard/claude-command-center.html"
mkdir -p "$HOME/.claude/dashboard"

echo "🚀 Building Command Center..."

# Regenerate kernel data from stats-cache (keeps cost/productivity/coevo in sync)
echo "  🔄 Syncing kernel data..."
python3 "$HOME/.claude/scripts/regenerate-kernel-data.py" --quiet 2>/dev/null || true
python3 "$HOME/.claude/scripts/refresh-kernel-data.py" --quiet 2>/dev/null || true

# Default empty data
DEFAULT_STATS='{"totalSessions":0,"totalMessages":0,"dailyActivity":[],"dailyModelTokens":[],"modelUsage":{},"hourCounts":{}}'
DEFAULT_MEMORY='{"facts":[],"decisions":[],"patterns":[],"context":{},"projects":{}}'

# ═══════════════════════════════════════════════════════════════
# GATHER DATA
# ═══════════════════════════════════════════════════════════════

echo "  📊 Loading stats..."
if [[ -f "$STATS_FILE" ]]; then
  STATS_DATA=$(cat "$STATS_FILE")
else
  STATS_DATA="$DEFAULT_STATS"
fi

echo "  🧠 Loading memory..."
if [[ -f "$MEMORY_FILE" ]]; then
  MEMORY_DATA=$(cat "$MEMORY_FILE")
else
  MEMORY_DATA="$DEFAULT_MEMORY"
fi

echo "  📝 Loading activity..."
if [[ -f "$ACTIVITY_LOG" ]]; then
  ACTIVITY_DATA=$(tail -200 "$ACTIVITY_LOG" | python3 -c "
import sys, json
lines = [line.strip() for line in sys.stdin if line.strip()]
print(json.dumps(lines))
" 2>/dev/null || echo '[]')
else
  ACTIVITY_DATA='[]'
fi

echo "  📦 Gathering project stats..."

# Function to get git stats for a project
get_project_stats() {
  local dir="$1"
  local name="$2"
  local stack="$3"
  local class="$4"

  if [[ -d "$dir/.git" ]]; then
    cd "$dir"
    local files=$(find . -type f -name "*.ts" -o -name "*.tsx" -o -name "*.js" -o -name "*.jsx" -o -name "*.py" 2>/dev/null | wc -l | tr -d ' ')
    local commits=$(git rev-list --count HEAD 2>/dev/null || echo "0")
    local lines=$(find . -type f \( -name "*.ts" -o -name "*.tsx" -o -name "*.js" -o -name "*.jsx" -o -name "*.py" \) -exec cat {} + 2>/dev/null | wc -l | tr -d ' ' || echo "0")

    # Format large numbers
    if [[ $lines -gt 1000 ]]; then
      lines="$(echo "scale=1; $lines/1000" | bc)K"
    fi

    echo "{\"name\":\"$name\",\"stack\":\"$stack\",\"status\":\"active\",\"class\":\"$class\",\"files\":\"$files\",\"commits\":\"$commits\",\"lines\":\"$lines\"}"
  else
    echo "{\"name\":\"$name\",\"stack\":\"$stack\",\"status\":\"active\",\"class\":\"$class\",\"files\":\"—\",\"commits\":\"—\",\"lines\":\"—\"}"
  fi
}

# Collect project data - Auto-discover from system.json
PROJECTS_DATA=$(python3 << 'PYPROJECTS'
import json
from pathlib import Path
import subprocess

home = Path.home()
config_file = home / ".claude/config/system.json"

def get_project_stats(path, name, tech, alias):
    """Get stats for a single project."""
    path = Path(str(path).replace("~", str(home)))
    if not path.exists():
        return None

    # Count files
    try:
        result = subprocess.run(
            ["find", str(path), "-type", "f", "-name", "*.ts", "-o", "-name", "*.tsx", "-o", "-name", "*.js", "-o", "-name", "*.py"],
            capture_output=True, text=True, timeout=5
        )
        file_count = len([f for f in result.stdout.strip().split('\n') if f])
    except:
        file_count = 0

    # Get last commit
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "log", "-1", "--format=%cr"],
            capture_output=True, text=True, timeout=5
        )
        last_commit = result.stdout.strip() if result.returncode == 0 else "N/A"
    except:
        last_commit = "N/A"

    return {
        "name": name,
        "path": str(path),
        "tech": tech,
        "alias": alias,
        "files": file_count,
        "lastCommit": last_commit
    }

# Load projects from config
projects = []
if config_file.exists():
    try:
        with open(config_file) as f:
            config = json.load(f)
        for p in config.get("projects", []):
            stats = get_project_stats(p["path"], p["name"], p["tech"], p["alias"])
            if stats:
                projects.append(stats)
    except:
        pass

print(json.dumps(projects))
PYPROJECTS
)

echo "  🎯 Loading proactive suggestions..."
KERNEL_DIR="$HOME/.claude/kernel"
if [[ -f "$KERNEL_DIR/pattern-detector.js" ]]; then
  PROACTIVE_DATA=$(node "$KERNEL_DIR/pattern-detector.js" suggest 2>/dev/null || echo '{"hasContext":false,"suggestions":[]}')
else
  PROACTIVE_DATA='{"hasContext":false,"suggestions":[]}'
fi

echo "  ⚙️ Loading co-evolution data..."
# Load coevo config
COEVO_CONFIG_FILE="$KERNEL_DIR/coevo-config.json"

echo "  💰 Loading subscription value..."
# Prefer fixed data file over JS tracker
if [[ -f "$KERNEL_DIR/subscription-data.json" ]]; then
  SUB_RAW=$(cat "$KERNEL_DIR/subscription-data.json")
  SUBSCRIPTION_DATA=$(python3 -c "
import json
d = json.loads('''$SUB_RAW''')
print(json.dumps({
  'subscription': {'rate': d.get('monthlySubscription', 200)},
  'value': {
    'totalValue': d.get('totalValue', 0),
    'subscriptionMultiplier': d.get('roiMultiplier', 0)
  },
  'current': {
    'messages': d.get('totalMessages', 0),
    'sessions': d.get('totalSessions', 0)
  }
}))
" 2>/dev/null)
elif [[ -f "$KERNEL_DIR/subscription-tracker.js" ]]; then
  SUBSCRIPTION_DATA=$(node "$KERNEL_DIR/subscription-tracker.js" json 2>/dev/null || echo '{"error":"failed"}')
else
  SUBSCRIPTION_DATA='{"subscription":{"rate":200},"value":{"totalValue":0,"subscriptionMultiplier":0}}'
fi

echo "  📦 Loading pack metrics..."
# Generate fresh pack metrics from context-packs infrastructure
python3 "$HOME/.claude/scripts/generate-pack-metrics.py" 2>/dev/null || true

PACK_METRICS_FILE="$HOME/.claude/data/pack-metrics.json"
if [[ -f "$PACK_METRICS_FILE" ]]; then
  PACK_DATA=$(cat "$PACK_METRICS_FILE")
else
  PACK_DATA='{"status":"not_configured","global":{"total_sessions":0},"top_packs":[],"daily_trend":[],"pack_inventory":[]}'
fi

echo "  ⚡ Loading session window data..."
# Get session window data from session-engine.js
SESSION_STATE_FILE="$KERNEL_DIR/session-state.json"
TASK_QUEUE_FILE="$KERNEL_DIR/task-queue.json"

if [[ -f "$SESSION_STATE_FILE" ]]; then
  SESSION_WINDOW_DATA=$(python3 -c "
import json
from pathlib import Path

state_file = Path.home() / '.claude/kernel/session-state.json'
queue_file = Path.home() / '.claude/kernel/task-queue.json'

result = {
    'window': {},
    'budget': {},
    'capacity': {},
    'queue': {'pending': 0},
    'recommendations': []
}

if state_file.exists():
    with open(state_file) as f:
        state = json.load(f)
    result['window'] = state.get('window', {})
    result['budget'] = state.get('budget', {})
    result['capacity'] = state.get('capacity', {})

if queue_file.exists():
    with open(queue_file) as f:
        queue = json.load(f)
    pending = [t for t in queue.get('tasks', []) if t.get('status') == 'pending']
    result['queue'] = {'pending': len(pending)}

# Generate recommendations
tier = result['capacity'].get('tier', 'UNKNOWN')
position = result['window'].get('positionPercent', 0)
budget_used = result['budget'].get('utilizationPercent', 0)

recs = []
if tier == 'CRITICAL':
    recs.append('Switch to Haiku for remaining tasks')
elif tier == 'LOW':
    recs.append('Avoid Opus unless critical')
if position > 80:
    recs.append('Late in window - prioritize completion')
if budget_used > 85:
    recs.append('Budget pressure - consider model downgrade')
if result['queue']['pending'] > 5:
    recs.append('Batch similar tasks for efficiency')

result['recommendations'] = recs if recs else ['Session healthy - proceed normally']

print(json.dumps(result))
" 2>/dev/null || echo '{"window":{},"budget":{},"capacity":{},"queue":{"pending":0},"recommendations":[]}')
else
  SESSION_WINDOW_DATA='{"window":{},"budget":{},"capacity":{},"queue":{"pending":0},"recommendations":[]}'
fi

echo "  🎯 Loading routing metrics..."
# Comprehensive routing metrics from multiple sources
ROUTING_TMP="/tmp/routing-data-$$.json"
python3 << 'ROUTINGEOF' > "$ROUTING_TMP"
import json
from collections import Counter, defaultdict
from pathlib import Path
from datetime import datetime, timedelta

home = Path.home()
dq_file = home / '.claude/kernel/dq-scores.jsonl'
routing_file = home / '.claude/kernel/cognitive-os/routing-decisions.jsonl'
feedback_file = home / '.claude/kernel/routing-feedback.jsonl'
outcomes_file = home / '.claude/data/session-outcomes.jsonl'

# Initialize
scores = []
models = Counter()
latencies = []
routing_decisions = []
feedback_entries = []
daily_queries = defaultdict(int)
daily_accuracy = defaultdict(list)

# Load DQ scores
if dq_file.exists():
    with open(dq_file) as f:
        for line in f:
            try:
                d = json.loads(line)
                if 'dqScore' in d:
                    scores.append(d['dqScore'])
                if 'model' in d:
                    models[d['model']] += 1
                # Track daily
                ts = d.get('ts', 0)
                if ts > 1e12:
                    ts = ts / 1000
                if ts > 0:
                    date = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
                    daily_queries[date] += 1
            except:
                pass

# Load routing decisions for latency and decision tracking
if routing_file.exists():
    try:
        with open(routing_file) as f:
            for line in f:
                try:
                    d = json.loads(line)
                    routing_decisions.append(d)
                except:
                    pass
    except:
        pass

# Calculate latency from routing decisions (time between consecutive decisions)
if len(routing_decisions) > 1:
    for i in range(1, min(100, len(routing_decisions))):
        try:
            t1 = datetime.fromisoformat(routing_decisions[i-1].get('timestamp', ''))
            t2 = datetime.fromisoformat(routing_decisions[i].get('timestamp', ''))
            delta_ms = (t2 - t1).total_seconds() * 1000
            if 0 < delta_ms < 5000:  # Reasonable range
                latencies.append(delta_ms)
        except:
            pass

# Load feedback if exists
if feedback_file.exists():
    try:
        with open(feedback_file) as f:
            for line in f:
                try:
                    feedback_entries.append(json.loads(line))
                except:
                    pass
    except:
        pass

# Calculate accuracy from session outcomes (success rate by model)
model_success = defaultdict(lambda: {'success': 0, 'total': 0})
if outcomes_file.exists():
    try:
        with open(outcomes_file) as f:
            for line in f:
                try:
                    s = json.loads(line)
                    outcome = s.get('outcome', '')
                    models_used = s.get('models_used', {})
                    for model, count in models_used.items():
                        model_success[model]['total'] += 1
                        if outcome == 'success':
                            model_success[model]['success'] += 1
                except:
                    pass
    except:
        pass

# Calculate metrics
total = len(scores)
avg_dq = sum(scores) / total if scores else 0
model_total = sum(models.values()) or 1

# Model distribution
model_dist = {
    'haiku': round(models.get('haiku', 0) / model_total, 3),
    'sonnet': round(models.get('sonnet', 0) / model_total, 3),
    'opus': round(models.get('opus', 0) / model_total, 3)
}

# Cost savings
haiku_pct = model_dist['haiku']
sonnet_pct = model_dist['sonnet']
opus_pct = model_dist['opus']
# Opus 4.5 cost ratios (relative to opus=1.0): sonnet=0.6, haiku=0.16
actual_cost_pct = (haiku_pct * 0.16) + (sonnet_pct * 0.6) + (opus_pct * 1.0)
cost_savings = round((1 - actual_cost_pct) * 100, 1) if opus_pct < 1 else 0

# Latency (p95)
latency_p95 = 42  # default
if latencies:
    latencies.sort()
    p95_idx = int(len(latencies) * 0.95)
    latency_p95 = round(latencies[p95_idx] if p95_idx < len(latencies) else latencies[-1], 1)

# Accuracy from outcomes
total_outcomes = sum(m['total'] for m in model_success.values())
total_success = sum(m['success'] for m in model_success.values())
accuracy = round((total_success / total_outcomes * 100), 1) if total_outcomes > 0 else round(avg_dq * 100, 1)

# Feedback count = sessions with outcomes (implicit feedback)
# Explicit feedback from file, or implicit from session outcomes
feedback_count = len(feedback_entries) if feedback_entries else total_outcomes

# Daily trend (last 14 days)
daily_trend = []
for i in range(14):
    date = (datetime.now() - timedelta(days=13-i)).strftime('%Y-%m-%d')
    daily_trend.append({
        'date': date,
        'queries': daily_queries.get(date, 0)
    })

# Model success rates
model_success_rates = {}
for model, data in model_success.items():
    if data['total'] > 0:
        model_success_rates[model] = {
            'success_rate': round(data['success'] / data['total'] * 100, 1),
            'total': data['total']
        }

routing = {
    'totalQueries': total,
    'avgDqScore': round(avg_dq, 3),
    'dataQuality': round(avg_dq, 2),
    'feedbackCount': feedback_count,
    'costReduction': cost_savings,
    'routingLatency': latency_p95,
    'modelDistribution': model_dist,
    'modelCounts': dict(models),
    'accuracy': accuracy,
    'targetQueries': 100,
    'targetDataQuality': 0.60,
    'targetFeedback': 100,
    'targetAccuracy': 60,
    'productionReady': total >= 100 and avg_dq >= 0.60 and accuracy >= 60,
    'dailyTrend': daily_trend,
    'modelSuccessRates': model_success_rates,
    'routingDecisions': len(routing_decisions),
    'latencyMeasured': len(latencies) > 0
}
print(json.dumps(routing))
ROUTINGEOF

ROUTING_DATA=$(cat "$ROUTING_TMP")
PATTERNS_FILE="$KERNEL_DIR/detected-patterns.json"
MODS_FILE="$KERNEL_DIR/modifications.jsonl"

if [[ -f "$COEVO_CONFIG_FILE" ]]; then
  COEVO_CONFIG=$(cat "$COEVO_CONFIG_FILE")
else
  COEVO_CONFIG='{"enabled":true,"autoApply":false,"minConfidence":0.7}'
fi

echo "  🔄 Loading pattern data..."
# Write patterns to temp file to avoid shell escaping issues
PATTERNS_TMP="/tmp/patterns-data-$$.json"
if [[ -f "$PATTERNS_FILE" ]]; then
  cp "$PATTERNS_FILE" "$PATTERNS_TMP"
else
  echo '{"patterns":[]}' > "$PATTERNS_TMP"
fi

# Load pattern trends
PATTERN_TRENDS_FILE="$KERNEL_DIR/pattern-trends.json"
PATTERN_TRENDS_TMP="/tmp/pattern-trends-$$.json"
if [[ -f "$PATTERN_TRENDS_FILE" ]]; then
  cp "$PATTERN_TRENDS_FILE" "$PATTERN_TRENDS_TMP"
else
  echo '{"daily":{},"weekly":{},"top_patterns":[],"percentages":{}}' > "$PATTERN_TRENDS_TMP"
fi

echo "  🔭 Loading Observatory data..."
# Load Observatory metrics (ALL TIME) - write to temp file to avoid shell escaping issues
OBSERVATORY_TMP="/tmp/observatory-data-$$.json"
python3 "$HOME/.claude/scripts/observatory/analytics-engine.py" export 30 > "$OBSERVATORY_TMP" 2>/dev/null || echo '{}' > "$OBSERVATORY_TMP"

echo "  📋 Loading session outcomes..."
# Load session outcomes to temp file to avoid shell escaping issues
SESSION_OUTCOMES_TMP="/tmp/session-outcomes-data-$$.json"
SESSION_OUTCOMES_FILE="$HOME/.claude/data/session-outcomes.jsonl"
if [[ -f "$SESSION_OUTCOMES_FILE" ]]; then
  python3 -c "
import json
sessions = []
with open('$HOME/.claude/data/session-outcomes.jsonl') as f:
    for line in f:
        if line.strip():
            try:
                s = json.loads(line)
                s['quality'] = min(5, max(1, s.get('messages', 50) / 50))
                s['complexity'] = min(1.0, s.get('tools', 10) / 100)
                s['model_efficiency'] = 0.8
                sessions.append(s)
            except:
                pass
print(json.dumps(sessions[-500:]))
" > "$SESSION_OUTCOMES_TMP" 2>/dev/null || echo '[]' > "$SESSION_OUTCOMES_TMP"
else
  echo '[]' > "$SESSION_OUTCOMES_TMP"
fi

if [[ -f "$MODS_FILE" ]]; then
  MODS_COUNT=$(wc -l < "$MODS_FILE" | tr -d ' ')
else
  MODS_COUNT=0
fi

echo "  🧠 Loading supermemory data..."
# Load supermemory stats from SQLite database
SUPERMEMORY_TMP="/tmp/supermemory-data-$$.json"
python3 << 'SMEOF' > "$SUPERMEMORY_TMP"
import json
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime

home = Path.home()
supermemory_dir = home / ".claude" / "supermemory"
db_path = home / ".claude" / "memory" / "supermemory.db"
hooks_dir = home / ".claude" / "hooks"

result = {
    "status": "not_configured",
    "totals": {"memory_items": 0, "learnings": 0, "error_patterns": 0, "review_items": 0},
    "review": {"due_count": 0, "items": []},
    "recent_learnings": [],
    "error_patterns": [],
    "projects": {},
    "last_sync": None,
    "automations": {"session_sync": False, "error_lookup": False, "daily_cron": False, "weekly_rollup": False}
}

if db_path.exists():
    result["status"] = "active"
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        # Get totals
        result["totals"]["memory_items"] = conn.execute("SELECT COUNT(*) FROM memory_items").fetchone()[0]
        result["totals"]["learnings"] = conn.execute("SELECT COUNT(*) FROM learnings").fetchone()[0]
        result["totals"]["error_patterns"] = conn.execute("SELECT COUNT(*) FROM error_patterns").fetchone()[0]
        result["totals"]["review_items"] = conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]

        # Get project breakdown
        rows = conn.execute("SELECT project, COUNT(*) as cnt FROM memory_items WHERE project IS NOT NULL GROUP BY project").fetchall()
        result["projects"] = {row["project"]: row["cnt"] for row in rows}

        # Get recent learnings (last 10)
        rows = conn.execute("SELECT content, category, project, date FROM learnings ORDER BY date DESC LIMIT 10").fetchall()
        result["recent_learnings"] = [{"content": r["content"], "category": r["category"], "project": r["project"], "date": r["date"]} for r in rows]

        # Get top error patterns
        rows = conn.execute("SELECT category, pattern, count, solution FROM error_patterns ORDER BY count DESC LIMIT 5").fetchall()
        result["error_patterns"] = [{"category": r["category"], "pattern": r["pattern"], "count": r["count"], "solution": r["solution"]} for r in rows]

        # Get due reviews
        today = datetime.now().strftime("%Y-%m-%d")
        result["review"]["due_count"] = conn.execute("SELECT COUNT(*) FROM reviews WHERE next_review <= ?", (today,)).fetchone()[0]
        rows = conn.execute("SELECT id, content, category, next_review FROM reviews WHERE next_review <= ? ORDER BY next_review LIMIT 5", (today,)).fetchall()
        result["review"]["items"] = [{"id": r["id"], "content": r["content"], "category": r["category"], "next_review": r["next_review"]} for r in rows]

        conn.close()
    except Exception as e:
        result["error"] = str(e)

# Check automations
stop_hook = hooks_dir / "session-optimizer-stop.sh"
if stop_hook.exists():
    result["automations"]["session_sync"] = "supermemory" in stop_hook.read_text().lower()

error_hook = hooks_dir / "error-capture.sh"
if error_hook.exists():
    result["automations"]["error_lookup"] = "supermemory" in error_hook.read_text().lower()

cron_script = home / ".claude" / "scripts" / "supermemory-cron.sh"
result["automations"]["daily_cron"] = cron_script.exists()

try:
    cron = subprocess.run(['crontab', '-l'], capture_output=True, text=True, timeout=5)
    result["automations"]["weekly_rollup"] = "supermemory-cron.sh weekly" in cron.stdout
except: pass

print(json.dumps(result))
SMEOF

echo "  🧠 Loading Cognitive OS data..."
# Load Cognitive OS state and metrics
COGNITIVE_TMP="/tmp/cognitive-data-$$.json"
python3 << 'COGEOF' > "$COGNITIVE_TMP"
import json
from pathlib import Path
from datetime import datetime

home = Path.home()
cos_dir = home / ".claude" / "kernel" / "cognitive-os"
cos_script = home / ".claude" / "kernel" / "cognitive-os.py"
flow_state_file = cos_dir / "flow-state.json"
fate_file = cos_dir / "fate-predictions.jsonl"
routing_file = cos_dir / "routing-decisions.jsonl"
energy_file = cos_dir / "weekly-energy.json"
current_state_file = cos_dir / "current-state.json"

# Best tasks by mode
best_for_map = {
    "morning": ["planning", "setup", "reviews"],
    "peak": ["architecture", "complex coding", "debugging"],
    "dip": ["documentation", "emails", "routine tasks"],
    "evening": ["creative work", "design", "exploration"],
    "deep_night": ["deep focus", "research", "refactoring"]
}

# Model recommendations by mode
model_map = {
    "morning": "sonnet",
    "peak": "opus",
    "dip": "haiku",
    "evening": "sonnet",
    "deep_night": "opus"
}

# Initialize result with structure matching renderCognitive()
result = {
    "status": "not_configured",
    "current_state": {
        "mode": "unknown",
        "energy_level": 0.5,
        "recommended_tasks": [],
        "warnings": []
    },
    "flow": {"state": "unknown", "score": 0, "in_flow": False},
    "fate": {"predicted_outcome": "partial"},
    "weekly": {},
    "routing": {"recommended_model": "sonnet"},
    "peak_hours": [20, 19, 3],
    "fate_accuracy": {"total": 0, "correct": 0},
    "flowHistory": [],
    "routingHistory": []
}

if not cos_script.exists():
    print(json.dumps(result))
    exit()

result["status"] = "active"

# Determine cognitive mode from hour
hour = datetime.now().hour
if 5 <= hour < 9:
    mode = "morning"
elif 9 <= hour < 12 or 14 <= hour < 18:
    mode = "peak"
elif 12 <= hour < 14:
    mode = "dip"
elif 18 <= hour < 22:
    mode = "evening"
else:
    mode = "deep_night"

# Load weekly energy for today's energy level
weekly_raw = {}
if energy_file.exists():
    try:
        with open(energy_file) as f:
            weekly_raw = json.load(f)
    except: pass

# Build weekly data with correct structure
days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
today = datetime.now().strftime('%A')
today_energy = weekly_raw.get(today, 0.6)

for day in days:
    level = weekly_raw.get(day, 0.5)
    energy_label = "HIGH" if level >= 0.7 else "MED" if level >= 0.5 else "LOW"
    result["weekly"][day] = {
        "level": level,
        "energy": energy_label,
        "stats": {"success_rate": level}  # Use energy as proxy for success rate
    }

# Set current state
result["current_state"] = {
    "mode": mode,
    "energy_level": today_energy,
    "recommended_tasks": best_for_map.get(mode, []),
    "warnings": []
}

# Add warning if energy is low
if today_energy < 0.5:
    result["current_state"]["warnings"].append("Low energy day - consider lighter tasks")
if mode == "dip":
    result["current_state"]["warnings"].append("Post-lunch dip - avoid complex architecture")

# Set routing recommendation
result["routing"]["recommended_model"] = model_map.get(mode, "sonnet")

# Load flow state from file
if flow_state_file.exists():
    try:
        with open(flow_state_file) as f:
            flow_data = json.load(f)
        result["flow"] = {
            "state": flow_data.get("state", "unknown"),
            "score": flow_data.get("score", 0),
            "in_flow": flow_data.get("in_flow", False)
        }
    except: pass

# Load flow history (last 20 entries)
flow_history_file = cos_dir / "flow-history.jsonl"
if flow_history_file.exists():
    try:
        history = []
        with open(flow_history_file) as f:
            for line in f:
                if line.strip():
                    try:
                        history.append(json.loads(line))
                    except: pass
        result["flow_history"] = [
            {"timestamp": h.get("timestamp", ""), "flow_score": h.get("score", 0), "state": h.get("state", ""), "in_flow": h.get("score", 0) >= 0.75}
            for h in history[-20:]
        ]
    except: pass

# Load routing decisions (last 20)
if routing_file.exists():
    try:
        routing = []
        with open(routing_file) as f:
            for line in f:
                if line.strip():
                    try:
                        routing.append(json.loads(line))
                    except: pass
        result["routing_history"] = [
            {"timestamp": r.get("timestamp", ""), "recommended_model": r.get("recommended_model", ""),
             "cognitive_mode": r.get("cognitive_mode", ""), "dq_score": r.get("dq_score", 0)}
            for r in routing[-20:]
        ]
    except: pass

# Load fate predictions and calculate accuracy
if fate_file.exists():
    try:
        predictions = []
        with open(fate_file) as f:
            for line in f:
                if line.strip():
                    try:
                        predictions.append(json.loads(line))
                    except: pass

        # Get latest prediction for display
        if predictions:
            latest = predictions[-1]
            result["fate"]["predicted_outcome"] = latest.get("predicted", "partial")

        # Calculate accuracy
        correct = sum(1 for p in predictions if p.get("correct", False))
        total = len(predictions)
        result["fate_accuracy"] = {"total": total, "correct": correct}
    except: pass

print(json.dumps(result))
COGEOF

echo "  📂 Loading file activity..."
# Collect recent file changes from git across main projects
FILE_ACTIVITY_TMP="/tmp/file-activity-$$.json"
python3 << 'PYEOF' > "$FILE_ACTIVITY_TMP"
import subprocess
import json
from pathlib import Path
from collections import Counter

projects = [
    ('OS-App', Path.home() / 'OS-App'),
    ('CareerCoach', Path.home() / 'CareerCoachAntigravity'),
    ('ResearchGravity', Path.home() / 'researchgravity'),
]

file_counts = Counter()
for name, path in projects:
    if path.exists() and (path / '.git').exists():
        try:
            result = subprocess.run(
                ['git', 'log', '--oneline', '--name-only', '-50'],
                cwd=path, capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.split('\n'):
                if '.' in line and '/' in line:
                    ext = line.rsplit('.', 1)[-1] if '.' in line else ''
                    if ext in ['ts', 'tsx', 'js', 'jsx', 'py', 'sh', 'json', 'md']:
                        file_counts[f"{name}:{line}"] += 1
        except:
            pass

# Top 15 most modified files
top_files = [{'file': f.split(':', 1)[1], 'project': f.split(':')[0], 'count': c}
             for f, c in file_counts.most_common(15)]
print(json.dumps(top_files))
PYEOF

echo "  🩹 Loading recovery data..."
RECOVERY_TMP="/tmp/recovery-data-$$.json"
python3 << 'RECOVERYEOF' > "$RECOVERY_TMP"
import json
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter, defaultdict

home = Path.home()
outcomes_file = home / ".claude" / "data" / "recovery-outcomes.jsonl"

result = {
    "stats": {"total": 0, "autoFix": 0, "autoFixRate": 0, "successRate": 0},
    "categories": {},
    "outcomes": [],
    "timeline": [],
    "successByCategory": {},
    "matrix": []
}

if not outcomes_file.exists():
    print(json.dumps(result))
    exit()

# Load outcomes
outcomes = []
try:
    with open(outcomes_file) as f:
        for line in f:
            if line.strip():
                try:
                    outcomes.append(json.loads(line))
                except:
                    pass
except:
    pass

if not outcomes:
    print(json.dumps(result))
    exit()

# Calculate stats
total = len(outcomes)
auto_fix = sum(1 for o in outcomes if o.get("auto", False))
success = sum(1 for o in outcomes if o.get("success", False))

result["stats"] = {
    "total": total,
    "autoFix": auto_fix,
    "autoFixRate": round(auto_fix / total * 100, 1) if total > 0 else 0,
    "successRate": round(success / total * 100, 1) if total > 0 else 0
}

# Category distribution
category_counts = Counter(o.get("category", "unknown") for o in outcomes)
result["categories"] = dict(category_counts)

# Recent outcomes (newest first)
result["outcomes"] = sorted(outcomes, key=lambda x: x.get("ts", 0), reverse=True)[:20]

# Timeline (last 7 days)
now = datetime.now()
timeline = defaultdict(lambda: {"autoFix": 0, "suggested": 0})
for o in outcomes:
    ts = o.get("ts", 0)
    if ts:
        date = datetime.fromtimestamp(ts)
        if (now - date).days <= 7:
            day_str = date.strftime("%m/%d")
            if o.get("auto", False):
                timeline[day_str]["autoFix"] += 1
            else:
                timeline[day_str]["suggested"] += 1

# Sort by date and convert to list
sorted_days = sorted(timeline.keys())
result["timeline"] = [{"date": d, "autoFix": timeline[d]["autoFix"], "suggested": timeline[d]["suggested"]} for d in sorted_days]

# Success by category
category_success = defaultdict(lambda: {"success": 0, "total": 0})
for o in outcomes:
    cat = o.get("category", "unknown")
    category_success[cat]["total"] += 1
    if o.get("success", False):
        category_success[cat]["success"] += 1

result["successByCategory"] = {
    cat: round(data["success"] / data["total"] * 100, 1) if data["total"] > 0 else 0
    for cat, data in category_success.items()
}

# Recovery matrix (static + dynamic counts)
matrix_data = {
    "git": {"errors": 560, "autoFix": "username, locks", "suggestOnly": "merge conflicts, force push"},
    "concurrency": {"errors": 55, "autoFix": "stale locks, zombies", "suggestOnly": "parallel sessions"},
    "permissions": {"errors": 40, "autoFix": "safe paths", "suggestOnly": "system paths"},
    "quota": {"errors": 25, "autoFix": "cache", "suggestOnly": "model switch"},
    "crash": {"errors": 15, "autoFix": "corrupt state", "suggestOnly": "restore backup"},
    "recursion": {"errors": 3, "autoFix": "kill runaway", "suggestOnly": "—"},
    "syntax": {"errors": 2, "autoFix": "—", "suggestOnly": "always suggest"}
}

result["matrix"] = [
    {"category": cat.capitalize(), "errors": data["errors"], "autoFix": data["autoFix"], "suggestOnly": data["suggestOnly"]}
    for cat, data in matrix_data.items()
]

print(json.dumps(result))
RECOVERYEOF

echo "  🤖 Loading coordinator data..."
COORDINATOR_TMP="/tmp/coordinator-data-$$.json"
python3 << 'COORDEOF' > "$COORDINATOR_TMP"
import json
from pathlib import Path

home = Path.home()
coord_dir = home / ".claude" / "coordinator" / "data"
agents_file = coord_dir / "active-agents.json"
locks_file = coord_dir / "file-locks.json"
history_file = coord_dir / "coordination-log.jsonl"

result = {
    "registry": {
        "total_agents": 0,
        "by_state": {},
        "by_model": {},
        "total_cost_estimate": 0,
        "active_count": 0,
        "stale_count": 0
    },
    "locks": {
        "total_locks": 0,
        "read_locks": 0,
        "write_locks": 0,
        "files_locked": 0,
        "agents_with_locks": 0
    },
    "agents": [],
    "lockDetails": [],
    "history": []
}

# Load agents
if agents_file.exists():
    try:
        with open(agents_file) as f:
            agents = json.load(f)

        result["registry"]["total_agents"] = len(agents)

        # Count by state
        by_state = {}
        by_model = {}
        total_cost = 0
        active_count = 0
        agent_list = []

        for agent_id, agent in agents.items():
            state = agent.get("state", "unknown")
            model = agent.get("model", "unknown")
            cost = agent.get("cost_estimate", 0)

            by_state[state] = by_state.get(state, 0) + 1
            by_model[model] = by_model.get(model, 0) + 1
            total_cost += cost

            if state in ["pending", "running"]:
                active_count += 1

            agent_list.append({
                "agent_id": agent_id,
                "subtask": agent.get("subtask", ""),
                "state": state,
                "model": model,
                "dq_score": agent.get("dq_score", 0),
                "progress": agent.get("progress", 0)
            })

        result["registry"]["by_state"] = by_state
        result["registry"]["by_model"] = by_model
        result["registry"]["total_cost_estimate"] = total_cost
        result["registry"]["active_count"] = active_count
        result["agents"] = agent_list
    except Exception as e:
        pass

# Load locks
if locks_file.exists():
    try:
        with open(locks_file) as f:
            locks = json.load(f)

        total_locks = sum(len(v) for v in locks.values())
        read_locks = sum(1 for v in locks.values() for l in v if l.get("lock_type") == "read")
        write_locks = total_locks - read_locks

        agents_with_locks = set()
        lock_details = []
        for path, lock_list in locks.items():
            for l in lock_list:
                agents_with_locks.add(l.get("agent_id"))
                lock_details.append({
                    "path": path,
                    "agent_id": l.get("agent_id"),
                    "lock_type": l.get("lock_type")
                })

        result["locks"] = {
            "total_locks": total_locks,
            "read_locks": read_locks,
            "write_locks": write_locks,
            "files_locked": len(locks),
            "agents_with_locks": len(agents_with_locks)
        }
        result["lockDetails"] = lock_details
    except:
        pass

# Load history (last 20)
if history_file.exists():
    try:
        history = []
        with open(history_file) as f:
            for line in f:
                if line.strip():
                    try:
                        history.append(json.loads(line))
                    except:
                        pass
        # Get last 20, newest first
        result["history"] = sorted(history, key=lambda x: x.get("timestamp", ""), reverse=True)[:20]
    except:
        pass

print(json.dumps(result))
COORDEOF

echo "  🛡️ Loading infrastructure status..."
INFRASTRUCTURE_TMP="/tmp/infrastructure-data-$$.json"
python3 << 'INFRAEOF' > "$INFRASTRUCTURE_TMP"
import json
import subprocess
import re
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("America/New_York")
home = Path.home()
launch_agents = home / "Library/LaunchAgents"

# Daemon definitions
DAEMONS = [
    ("com.claude.watchdog", "Watchdog (guardian)", True),
    ("com.claude.dashboard-refresh", "Dashboard Refresh (60s)", True),
    ("com.claude.supermemory", "Supermemory (daily)", True),
    ("com.claude.session-analysis", "Session Analysis (30m)", False),
    ("com.claude.autonomous-maintenance", "Auto Maintenance (1h)", False),
    ("com.claude.self-heal", "Self Heal (6h)", True),
    ("com.claude.bootstrap", "Bootstrap (login)", False),
    ("com.claude.wake-hook", "Wake Hook (sleep)", False),
]

result = {
    "status": "unknown",
    "daemons": [],
    "heartbeat": None,
    "healingEvents": [],
    "dataFreshness": []
}

# Get launchctl list
try:
    ps = subprocess.run(["launchctl", "list"], capture_output=True, text=True, timeout=5)
    launchctl_output = ps.stdout
except:
    launchctl_output = ""

# Check each daemon
for name, desc, critical in DAEMONS:
    plist = launch_agents / f"{name}.plist"
    loaded = name in launchctl_output
    pid = "-"

    # Extract PID if running
    for line in launchctl_output.split('\n'):
        if name in line:
            parts = line.split()
            if len(parts) >= 1 and parts[0] != "-":
                pid = parts[0]
            break

    result["daemons"].append({
        "name": name,
        "description": desc,
        "critical": critical,
        "loaded": loaded,
        "pid": pid,
        "plistExists": plist.exists()
    })

# Determine overall status
critical_daemons = [d for d in result["daemons"] if d["critical"]]
all_critical_loaded = all(d["loaded"] for d in critical_daemons)
result["status"] = "healthy" if all_critical_loaded else "degraded"

# Get heartbeat
heartbeat_file = home / ".claude/.watchdog-heartbeat"
if heartbeat_file.exists():
    try:
        result["heartbeat"] = heartbeat_file.read_text().strip()
    except:
        pass

# Parse watchdog log for healing events
watchdog_log = home / ".claude/logs/watchdog.log"
if watchdog_log.exists():
    try:
        lines = watchdog_log.read_text().strip().split('\n')[-200:]  # Last 200 lines for more history
        for line in reversed(lines):
            # Parse: [2026-01-23 14:30:06 EST] LOADED com.claude.bootstrap
            match = re.match(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
            if match:
                ts = match.group(1)
                if "LOADED" in line:
                    daemon = line.split("LOADED")[-1].strip()
                    result["healingEvents"].append({
                        "timestamp": ts,
                        "daemon": daemon,
                        "action": "reload",
                        "success": True,
                        "message": f"Reloaded {daemon}"
                    })
                elif "DOWN:" in line:
                    daemon = line.split("DOWN:")[-1].strip()
                    result["healingEvents"].append({
                        "timestamp": ts,
                        "daemon": daemon,
                        "action": "detected",
                        "success": False,
                        "message": f"Detected {daemon} down"
                    })
                elif "HEALED" in line:
                    match2 = re.search(r'HEALED (\d+)', line)
                    if match2:
                        count = match2.group(1)
                        result["healingEvents"].append({
                            "timestamp": ts,
                            "daemon": "watchdog",
                            "action": "heal",
                            "success": True,
                            "message": f"Healed {count} daemon(s)"
                        })
    except:
        pass

# Also include self-heal outcomes for deeper history
self_heal_outcomes = home / ".claude/data/self-heal-outcomes.jsonl"
if self_heal_outcomes.exists():
    try:
        for line in self_heal_outcomes.read_text().strip().split('\n')[-50:]:
            if line.strip():
                data = json.loads(line)
                ts = datetime.fromtimestamp(data.get('ts', 0), tz=LOCAL_TZ).strftime('%Y-%m-%d %H:%M:%S')
                fixed = data.get('fixed', 0)
                if fixed > 0:
                    result["healingEvents"].append({
                        "timestamp": ts,
                        "daemon": "self-heal",
                        "action": "deep-heal",
                        "success": True,
                        "message": f"Deep heal fixed {fixed} issue(s)"
                    })
    except:
        pass

# Check data freshness
def check_freshness(path, name, max_hours):
    if not path.exists():
        return {"name": name, "fresh": False, "age": "Missing"}
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=LOCAL_TZ)
    age_hours = (datetime.now(LOCAL_TZ) - mtime).total_seconds() / 3600
    fresh = age_hours <= max_hours
    if age_hours < 1:
        age_str = f"{int(age_hours * 60)}m ago"
    elif age_hours < 24:
        age_str = f"{age_hours:.1f}h ago"
    else:
        age_str = f"{age_hours / 24:.1f}d ago"
    return {"name": name, "fresh": fresh, "age": age_str}

result["dataFreshness"] = [
    check_freshness(home / ".claude/dashboard/claude-command-center.html", "Dashboard", 1),
    check_freshness(home / ".claude/kernel/session-state.json", "Session State", 2),
    check_freshness(home / ".claude/memory/supermemory.db", "Supermemory DB", 24),
    check_freshness(home / ".claude/kernel/cost-data.json", "Cost Data", 24),
    check_freshness(home / ".claude/stats-cache.json", "Stats Cache", 12),
]

print(json.dumps(result))
INFRAEOF

echo "  💻 Loading active Claude sessions..."
SESSIONS_TMP="/tmp/sessions-data-$$.json"
python3 << 'SESSIONSEOF' > "$SESSIONS_TMP"
import json
import subprocess
import re
from datetime import datetime

result = {
    "sessions": [],
    "stats": {
        "total": 0,
        "opus": 0,
        "sonnet": 0,
        "haiku": 0,
        "total_runtime_minutes": 0
    }
}

try:
    # Get Claude processes with detailed info
    ps_result = subprocess.run(
        ['ps', 'aux'],
        capture_output=True, text=True, timeout=5
    )

    sessions = []
    total_runtime = 0

    for line in ps_result.stdout.split('\n'):
        # Match claude processes (not grep, not this script)
        if 'claude' in line.lower() and 'grep' not in line and 'python3' not in line:
            parts = line.split()
            if len(parts) >= 11:
                user = parts[0]
                pid = parts[1]
                cpu = parts[2]
                mem = parts[3]
                # Parse runtime (format: MM:SS or HH:MM:SS or D-HH:MM:SS)
                time_str = parts[9] if len(parts) > 9 else "0:00"

                # Parse the command and find model
                cmd_start = 10
                cmd = ' '.join(parts[cmd_start:]) if len(parts) > cmd_start else ''

                # Detect model from command
                model = 'sonnet'  # default
                if '--model opus' in cmd or 'opus' in cmd.lower():
                    model = 'opus'
                elif '--model sonnet' in cmd or 'sonnet' in cmd.lower():
                    model = 'sonnet'
                elif '--model haiku' in cmd or 'haiku' in cmd.lower():
                    model = 'haiku'

                # Parse runtime to minutes
                runtime_mins = 0
                if '-' in time_str:
                    # Days format: D-HH:MM:SS
                    days, rest = time_str.split('-')
                    runtime_mins = int(days) * 1440
                    time_str = rest

                time_parts = time_str.split(':')
                if len(time_parts) == 3:
                    runtime_mins += int(time_parts[0]) * 60 + int(time_parts[1])
                elif len(time_parts) == 2:
                    runtime_mins += int(time_parts[0])

                # Try to get working directory from lsof
                cwd = '~'
                try:
                    lsof_result = subprocess.run(
                        ['lsof', '-p', pid, '-a', '-d', 'cwd', '-Fn'],
                        capture_output=True, text=True, timeout=2
                    )
                    for l in lsof_result.stdout.split('\n'):
                        if l.startswith('n/'):
                            cwd = l[1:].replace('/Users/dicoangelo', '~')
                            break
                except:
                    pass

                sessions.append({
                    "pid": pid,
                    "model": model,
                    "runtime": time_str,
                    "runtime_mins": runtime_mins,
                    "cpu": cpu,
                    "mem": mem,
                    "cwd": cwd
                })

                total_runtime += runtime_mins
                result["stats"][model] = result["stats"].get(model, 0) + 1

    result["sessions"] = sessions
    result["stats"]["total"] = len(sessions)
    result["stats"]["total_runtime_minutes"] = total_runtime

except Exception as e:
    result["error"] = str(e)

print(json.dumps(result))
SESSIONSEOF

# ═══════════════════════════════════════════════════════════════
# GENERATE DASHBOARD
# ═══════════════════════════════════════════════════════════════

echo "  🎨 Generating dashboard..."

python3 << EOF
import json
import re
import os
from pathlib import Path

# Read template
with open('$TEMPLATE', 'r') as f:
    template = f.read()

# Parse data safely
def safe_parse(data, default):
    try:
        return json.loads(data) if data else default
    except:
        return default

stats = safe_parse('''$STATS_DATA''', {"totalSessions":0,"totalMessages":0,"dailyActivity":[],"dailyModelTokens":[],"modelUsage":{},"hourCounts":{}})
memory = safe_parse('''$MEMORY_DATA''', {"facts":[],"decisions":[],"patterns":[],"context":{},"projects":{}})
activity = safe_parse('''$ACTIVITY_DATA''', [])
projects = safe_parse('''$PROJECTS_DATA''', [])
proactive = safe_parse('''$PROACTIVE_DATA''', {"hasContext":False,"suggestions":[]})
coevo_config = safe_parse('''$COEVO_CONFIG''', {"enabled":True,"autoApply":False,"minConfidence":0.7})
subscription = safe_parse('''$SUBSCRIPTION_DATA''', {"subscription":{"rate":200},"value":{"totalValue":0,"subscriptionMultiplier":0}})

# Load patterns from temp file
with open('$PATTERNS_TMP', 'r') as f:
    patterns_data = safe_parse(f.read(), {"patterns":[]})

# Load pattern trends from temp file
with open('$PATTERN_TRENDS_TMP', 'r') as f:
    pattern_trends = safe_parse(f.read(), {"daily":{},"weekly":{},"top_patterns":[],"percentages":{}})
routing = safe_parse('''$ROUTING_DATA''', {"totalQueries":0,"dataQuality":0.0,"feedbackCount":0,"targetQueries":200,"targetDataQuality":0.80,"targetFeedback":50})

# Calculate cache efficiency from stats
model_usage = stats.get('modelUsage', {})
# Handle both nested token data and simple counts
if model_usage and isinstance(list(model_usage.values())[0], dict):
    model_data = list(model_usage.values())[0]
    cache_read = model_data.get('cacheReadInputTokens', 0)
    cache_create = model_data.get('cacheCreationInputTokens', 0)
    input_tokens = model_data.get('inputTokens', 0)
    total_input = cache_read + cache_create + input_tokens
    cache_efficiency = (cache_read / total_input * 100) if total_input > 0 else 0
else:
    # Simple counts - estimate cache efficiency from session reuse
    cache_efficiency = 95.0  # Estimated based on context reuse

# Calculate real DQ score from dq-scores.jsonl
from datetime import datetime, timedelta
dq_file = Path.home() / '.claude/kernel/dq-scores.jsonl'
avg_dq = 0.750  # fallback

if dq_file.exists():
    scores = []
    cutoff = datetime.now() - timedelta(days=30)

    with open(dq_file) as f:
        for line in f:
            if line.strip():
                try:
                    entry = json.loads(line)
                    ts = entry.get('ts', 0)
                    if ts > 1e12:
                        ts = ts / 1000
                    if datetime.fromtimestamp(ts) > cutoff:
                        dq = entry.get('dqScore', entry.get('dq', 0))
                        if isinstance(dq, dict):
                            dq = dq.get('score', 0)
                        if dq > 0:
                            scores.append(dq)
                except:
                    continue

    if scores:
        avg_dq = sum(scores) / len(scores)

# Build coevo data
# Load coevo-data.json for lastAnalysis (updated more frequently than config)
coevo_data_file = Path.home() / '.claude/kernel/coevo-data.json'
coevo_runtime = {}
if coevo_data_file.exists():
    try:
        with open(coevo_data_file) as f:
            coevo_runtime = json.load(f)
    except:
        pass

coevo_data = {
    "cacheEfficiency": round(cache_efficiency, 2),
    "dqScore": round(avg_dq, 3),
    "dominantPattern": patterns_data.get('patterns', [{}])[0].get('id', 'none') if patterns_data.get('patterns') else 'none',
    "modsApplied": $MODS_COUNT,
    "autoApply": coevo_config.get('autoApply', False),
    "minConfidence": coevo_config.get('minConfidence', 0.7),
    "patterns": patterns_data.get('patterns', []),
    "lastAnalysis": coevo_runtime.get('lastAnalysis') or coevo_config.get('lastAnalysis', 'Never')
}

# Build subscription data for dashboard
sub_value = subscription.get('value', {})
subscription_data = {
    "rate": subscription.get('subscription', {}).get('rate', 200),
    "currency": subscription.get('subscription', {}).get('currency', 'USD'),
    "totalValue": sub_value.get('totalValue', 0),
    "multiplier": sub_value.get('subscriptionMultiplier', 0),
    "savings": sub_value.get('savingsVsApi', 0),
    "utilization": subscription.get('utilization', {}).get('status', 'unknown'),
    "costPerMsg": subscription.get('efficiency', {}).get('costPerMessage', 0)
}

# Inject data - read Observatory from temp file to avoid escaping issues
with open('$OBSERVATORY_TMP', 'r') as f:
    observatory = safe_parse(f.read(), {})
pack_metrics = safe_parse('''$PACK_DATA''', {"status":"not_configured","global":{"total_sessions":0}})

# Supermemory data
with open('$SUPERMEMORY_TMP', 'r') as f:
    supermemory = safe_parse(f.read(), {"status":"not_configured"})

output = template.replace('__STATS_DATA__', json.dumps(stats))
output = output.replace('__MEMORY_DATA__', json.dumps(memory))
output = output.replace('__ACTIVITY_DATA__', json.dumps(activity))
output = output.replace('__PROJECTS_DATA__', json.dumps(projects))
output = output.replace('__PROACTIVE_DATA__', json.dumps(proactive))
output = output.replace('__COEVO_DATA__', json.dumps(coevo_data))
output = output.replace('__PATTERN_TRENDS_DATA__', json.dumps(pattern_trends))
output = output.replace('__SUBSCRIPTION_DATA__', json.dumps(subscription_data))
output = output.replace('__ROUTING_DATA__', json.dumps(routing))
output = output.replace('__OBSERVATORY_DATA__', json.dumps(observatory))
output = output.replace('__PACK_DATA__', json.dumps(pack_metrics))
output = output.replace('__SUPERMEMORY_DATA__', json.dumps(supermemory))

# Session outcomes (embedded) - read from temp file to avoid escaping issues
with open('$SESSION_OUTCOMES_TMP', 'r') as f:
    session_outcomes = safe_parse(f.read(), [])
output = output.replace('__SESSION_OUTCOMES_DATA__', json.dumps(session_outcomes))

# Session window data
session_window = safe_parse('''$SESSION_WINDOW_DATA''', {"window":{},"budget":{},"capacity":{},"queue":{"pending":0},"recommendations":[]})
output = output.replace('__SESSION_WINDOW_DATA__', json.dumps(session_window))

# File activity data
with open('$FILE_ACTIVITY_TMP', 'r') as f:
    file_activity = safe_parse(f.read(), [])
output = output.replace('__FILE_ACTIVITY_DATA__', json.dumps(file_activity))

# Cognitive OS data
with open('$COGNITIVE_TMP', 'r') as f:
    cognitive = safe_parse(f.read(), {"status":"not_configured"})
output = output.replace('__COGNITIVE_DATA__', json.dumps(cognitive))

# Recovery data
with open('$RECOVERY_TMP', 'r') as f:
    recovery = safe_parse(f.read(), {"stats":{"total":0,"autoFixed":0,"suggestions":0,"successRate":0},"categories":{},"outcomes":[],"timeline":[],"successByCategory":{},"matrix":[]})
output = output.replace('__RECOVERY_DATA__', json.dumps(recovery))

# Coordinator data
with open('$COORDINATOR_TMP', 'r') as f:
    coordinator = safe_parse(f.read(), {"registry":{},"locks":{},"agents":[],"lockDetails":[],"history":[]})
output = output.replace('__COORDINATOR_DATA__', json.dumps(coordinator))

# Active sessions data
with open('$SESSIONS_TMP', 'r') as f:
    sessions = safe_parse(f.read(), {"sessions":[],"stats":{"total":0,"opus":0,"sonnet":0,"haiku":0,"total_runtime_minutes":0}})
output = output.replace('__SESSIONS_DATA__', json.dumps(sessions))

# Infrastructure data
with open('$INFRASTRUCTURE_TMP', 'r') as f:
    infrastructure = safe_parse(f.read(), {"status":"unknown","daemons":[],"heartbeat":None,"healingEvents":[],"dataFreshness":[]})
output = output.replace('__INFRASTRUCTURE_DATA__', json.dumps(infrastructure))

# Pricing data from centralized config
pricing_file = os.path.expanduser('~/.claude/config/pricing.json')
if os.path.exists(pricing_file):
    with open(pricing_file, 'r') as f:
        pricing_data = safe_parse(f.read(), {})
else:
    pricing_data = {"models":{"opus":{"input":5,"output":25,"cache_read":0.5},"sonnet":{"input":3,"output":15},"haiku":{"input":0.8,"output":4}}}
output = output.replace('__PRICING_DATA__', json.dumps(pricing_data))

# Write output
with open('$OUTPUT', 'w') as f:
    f.write(output)

print('  ✅ Dashboard ready')
EOF

# ═══════════════════════════════════════════════════════════════
# OPEN DASHBOARD
# ═══════════════════════════════════════════════════════════════

if [[ "$NO_OPEN" == "false" ]]; then
  open "$OUTPUT"
  echo "🎉 Command Center opened!"
  echo ""
  echo "Keyboard shortcuts:"
  echo "  1-9  Switch tabs (7 = Routing, 8 = Co-Evolution)"
  echo "  R    Refresh"
fi

# Cleanup temp files
rm -f "$OBSERVATORY_TMP" "$SESSION_OUTCOMES_TMP" "$FILE_ACTIVITY_TMP" "$SUPERMEMORY_TMP" "$COGNITIVE_TMP" "$RECOVERY_TMP" "$COORDINATOR_TMP" "$SESSIONS_TMP" "$PATTERNS_TMP" "$PATTERN_TRENDS_TMP" "$ROUTING_TMP" "$INFRASTRUCTURE_TMP" 2>/dev/null
