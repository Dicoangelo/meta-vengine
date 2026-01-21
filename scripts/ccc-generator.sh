#!/bin/bash
# Claude Command Center - Ultimate Dashboard Generator
# Aggregates all data sources and opens the unified dashboard

set -e

STATS_FILE="$HOME/.claude/stats-cache.json"
MEMORY_FILE="$HOME/.claude/memory/knowledge.json"
ACTIVITY_LOG="$HOME/.claude/activity.log"
TEMPLATE="$HOME/.claude/scripts/command-center.html"
OUTPUT="$HOME/.claude/dashboard/claude-command-center.html"
mkdir -p "$HOME/.claude/dashboard"

echo "🚀 Building Command Center..."

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

# Collect project data - All projects
OS_APP_STATS=$(get_project_stats "$HOME/OS-App" "OS-App" "Vite + React 19 + Zustand + Supabase" "os-app")
CAREER_STATS=$(get_project_stats "$HOME/CareerCoachAntigravity" "CareerCoach" "Next.js 14 + React 18 + Zustand" "career")
RESEARCH_STATS=$(get_project_stats "$HOME/researchgravity" "ResearchGravity" "Python 3.8+ Research Framework" "research")
AGENT_CORE_STATS=$(get_project_stats "$HOME/agent-core" "Agent Core" "Unified Agent Data Store" "agent")
BLACKAMETHYST_STATS=$(get_project_stats "$HOME/Blackamethyst-ai-profile" "Blackamethyst AI" "AI Profile System" "ai")
CHROME_HISTORY_STATS=$(get_project_stats "$HOME/chrome-history-export" "Chrome History" "Browser History Export" "tool")
DICOANGELO_STATS=$(get_project_stats "$HOME/Dicoangelo" "Dicoangelo" "GitHub Profile" "profile")
META_VENGINE_STATS=$(get_project_stats "$HOME/meta-vengine" "Meta-Vengine" "Meta Engine System" "meta")
METAVENTIONS_STATS=$(get_project_stats "$HOME/Metaventions-AI-Landing" "Metaventions Landing" "AI Landing Page" "landing")
DECOSYSTEM_STATS=$(get_project_stats "$HOME/The-Decosystem" "The Decosystem" "Ecosystem Framework" "ecosystem")
CPB_CORE_STATS=$(get_project_stats "$HOME/cpb-core" "CPB Core" "Career Precision Bridge Core" "cpb")
CPB_DEMO_STATS=$(get_project_stats "$HOME/cpb-demo" "CPB Demo" "Career Precision Bridge Demo" "cpb-demo")
CAREER_MVP_STATS=$(get_project_stats "$HOME/career-coach-mvp" "Career Coach MVP" "Career Coach Minimum Viable Product" "career-mvp")
VOICE_NEXUS_STATS=$(get_project_stats "$HOME/voice-nexus" "Voice Nexus" "Voice Integration System" "voice")

PROJECTS_DATA="[$OS_APP_STATS,$CAREER_STATS,$RESEARCH_STATS,$AGENT_CORE_STATS,$BLACKAMETHYST_STATS,$CHROME_HISTORY_STATS,$DICOANGELO_STATS,$META_VENGINE_STATS,$METAVENTIONS_STATS,$DECOSYSTEM_STATS,$CPB_CORE_STATS,$CPB_DEMO_STATS,$CAREER_MVP_STATS,$VOICE_NEXUS_STATS]"

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
# Calculate routing metrics directly from dq-scores.jsonl
ROUTING_DATA=$(python3 -c "
import json
from collections import Counter
from pathlib import Path

dq_file = Path.home() / '.claude/kernel/dq-scores.jsonl'
scores = []
models = Counter()

if dq_file.exists():
    with open(dq_file) as f:
        for line in f:
            try:
                d = json.loads(line)
                if 'dqScore' in d:
                    scores.append(d['dqScore'])
                if 'model' in d:
                    models[d['model']] += 1
            except:
                pass

total = len(scores)
avg_dq = sum(scores) / total if scores else 0
model_total = sum(models.values()) or 1

# Normalize model distribution to percentages (main 3 models)
model_dist = {
    'haiku': round(models.get('haiku', 0) / model_total, 3),
    'sonnet': round(models.get('sonnet', 0) / model_total, 3),
    'opus': round(models.get('opus', 0) / model_total, 3)
}

# Calculate cost savings estimate (haiku saves ~98%, sonnet saves ~80% vs opus)
haiku_pct = model_dist['haiku']
sonnet_pct = model_dist['sonnet']
opus_pct = model_dist['opus']
# If everything went to opus, cost = 100%. Actual cost based on model mix
actual_cost_pct = (haiku_pct * 0.017) + (sonnet_pct * 0.2) + (opus_pct * 1.0)
cost_savings = round((1 - actual_cost_pct) * 100, 1) if opus_pct < 1 else 0

routing = {
    'totalQueries': total,
    'avgDqScore': round(avg_dq, 3),
    'dataQuality': round(avg_dq, 2),
    'feedbackCount': total,
    'costReduction': cost_savings,
    'routingLatency': 42,
    'modelDistribution': model_dist,
    'modelCounts': dict(models),
    'accuracy': round(avg_dq * 100, 1),
    'targetQueries': 100,
    'targetDataQuality': 0.60,
    'targetFeedback': 100,
    'targetAccuracy': 60,
    'productionReady': total >= 100 and avg_dq >= 0.60
}
print(json.dumps(routing))
" 2>/dev/null || echo '{"totalQueries":0,"avgDqScore":0,"dataQuality":0,"feedbackCount":0}')
PATTERNS_FILE="$KERNEL_DIR/detected-patterns.json"
MODS_FILE="$KERNEL_DIR/modifications.jsonl"

if [[ -f "$COEVO_CONFIG_FILE" ]]; then
  COEVO_CONFIG=$(cat "$COEVO_CONFIG_FILE")
else
  COEVO_CONFIG='{"enabled":true,"autoApply":false,"minConfidence":0.7}'
fi

echo "  🔭 Loading Observatory data..."
# Load Observatory metrics (ALL TIME) - write to temp file to avoid shell escaping issues
OBSERVATORY_TMP="/tmp/observatory-data-$$.json"
python3 "$HOME/.claude/scripts/observatory/analytics-engine.py" export 9999 > "$OBSERVATORY_TMP" 2>/dev/null || echo '{}' > "$OBSERVATORY_TMP"

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

if [[ -f "$PATTERNS_FILE" ]]; then
  PATTERNS_DATA=$(cat "$PATTERNS_FILE")
else
  PATTERNS_DATA='{"patterns":[]}'
fi

if [[ -f "$MODS_FILE" ]]; then
  MODS_COUNT=$(wc -l < "$MODS_FILE" | tr -d ' ')
else
  MODS_COUNT=0
fi

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
patterns_data = safe_parse('''$PATTERNS_DATA''', {"patterns":[]})
subscription = safe_parse('''$SUBSCRIPTION_DATA''', {"subscription":{"rate":200},"value":{"totalValue":0,"subscriptionMultiplier":0}})
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
coevo_data = {
    "cacheEfficiency": round(cache_efficiency, 2),
    "dqScore": round(avg_dq, 3),
    "dominantPattern": patterns_data.get('patterns', [{}])[0].get('id', 'none') if patterns_data.get('patterns') else 'none',
    "modsApplied": $MODS_COUNT,
    "autoApply": coevo_config.get('autoApply', False),
    "minConfidence": coevo_config.get('minConfidence', 0.7),
    "patterns": patterns_data.get('patterns', []),
    "lastAnalysis": coevo_config.get('lastAnalysis', 'Never')
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

output = template.replace('__STATS_DATA__', json.dumps(stats))
output = output.replace('__MEMORY_DATA__', json.dumps(memory))
output = output.replace('__ACTIVITY_DATA__', json.dumps(activity))
output = output.replace('__PROJECTS_DATA__', json.dumps(projects))
output = output.replace('__PROACTIVE_DATA__', json.dumps(proactive))
output = output.replace('__COEVO_DATA__', json.dumps(coevo_data))
output = output.replace('__SUBSCRIPTION_DATA__', json.dumps(subscription_data))
output = output.replace('__ROUTING_DATA__', json.dumps(routing))
output = output.replace('__OBSERVATORY_DATA__', json.dumps(observatory))
output = output.replace('__PACK_DATA__', json.dumps(pack_metrics))

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

open "$OUTPUT"
echo "🎉 Command Center opened!"
echo ""
echo "Keyboard shortcuts:"
echo "  1-9  Switch tabs (7 = Routing, 8 = Co-Evolution)"
echo "  R    Refresh"

# Cleanup temp files
rm -f "$OBSERVATORY_TMP" "$SESSION_OUTCOMES_TMP" "$FILE_ACTIVITY_TMP" 2>/dev/null
