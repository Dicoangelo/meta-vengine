#!/bin/bash
# Claude Command Center - Ultimate Dashboard Generator
# Aggregates all data sources and opens the unified dashboard

set -e

STATS_FILE="$HOME/.claude/stats-cache.json"
MEMORY_FILE="$HOME/.claude/memory/knowledge.json"
ACTIVITY_LOG="$HOME/.claude/activity.log"
TEMPLATE="$HOME/.claude/scripts/command-center.html"
OUTPUT="/tmp/claude-command-center.html"

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

# Collect project data
OS_APP_STATS=$(get_project_stats "$HOME/OS-App" "OS-App" "Vite + React 19 + Zustand + Supabase" "os-app")
CAREER_STATS=$(get_project_stats "$HOME/CareerCoachAntigravity" "CareerCoach" "Next.js 14 + React 18 + Zustand" "career")
RESEARCH_STATS=$(get_project_stats "$HOME/researchgravity" "ResearchGravity" "Python 3.8+ Research Framework" "research")

PROJECTS_DATA="[$OS_APP_STATS,$CAREER_STATS,$RESEARCH_STATS]"

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
if [[ -f "$KERNEL_DIR/subscription-tracker.js" ]]; then
  SUBSCRIPTION_DATA=$(node "$KERNEL_DIR/subscription-tracker.js" json 2>/dev/null || echo '{"error":"failed"}')
else
  SUBSCRIPTION_DATA='{"subscription":{"rate":200},"value":{"totalValue":0,"subscriptionMultiplier":0}}'
fi

echo "  🎯 Loading routing metrics..."
RESEARCHGRAVITY_DIR="$HOME/researchgravity"
if [[ -f "$RESEARCHGRAVITY_DIR/routing-metrics.py" ]]; then
  # Get all-time report (use days 9999 for all data)
  ROUTING_REPORT=$(python3 "$RESEARCHGRAVITY_DIR/routing-metrics.py" report --days 9999 --format json 2>/dev/null || echo '{"error":"failed"}')

  # Get data quality
  DATA_QUALITY=$(python3 "$RESEARCHGRAVITY_DIR/routing-metrics.py" check-data-quality --all-time 2>/dev/null || echo "0.0")

  # Get feedback count
  FEEDBACK_COUNT=$(wc -l < "$KERNEL_DIR/dq-scores.jsonl" 2>/dev/null | tr -d ' ' || echo "0")

  # Calculate production readiness
  TOTAL_QUERIES=$(echo "$ROUTING_REPORT" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('total_queries', 0))" 2>/dev/null || echo "0")

  # Build routing data using Python
  ROUTING_DATA=$(python3 -c "
import json
import sys

report_json = '''$ROUTING_REPORT'''
try:
    report = json.loads(report_json)
except:
    report = {}

routing = {
  'totalQueries': $TOTAL_QUERIES,
  'dataQuality': float('$DATA_QUALITY'),
  'feedbackCount': $FEEDBACK_COUNT,
  'targetQueries': 200,
  'targetDataQuality': 0.80,
  'targetFeedback': 50,
  'avgDqScore': report.get('avg_dq_score', 0.0),
  'costReduction': report.get('cost_reduction', 0.0),
  'routingLatency': (report.get('routing_latency', {}) or {}).get('p95') or 0,
  'modelDistribution': report.get('model_distribution', {}),
  'accuracy': report.get('accuracy') or 0.0,
  'productionReady': $TOTAL_QUERIES >= 200 and float('$DATA_QUALITY') >= 0.80 and $FEEDBACK_COUNT >= 50
}
print(json.dumps(routing))
")
else
  ROUTING_DATA='{"error":"routing-metrics.py not found","totalQueries":0,"dataQuality":0.0,"feedbackCount":0}'
fi
PATTERNS_FILE="$KERNEL_DIR/detected-patterns.json"
MODS_FILE="$KERNEL_DIR/modifications.jsonl"

if [[ -f "$COEVO_CONFIG_FILE" ]]; then
  COEVO_CONFIG=$(cat "$COEVO_CONFIG_FILE")
else
  COEVO_CONFIG='{"enabled":true,"autoApply":false,"minConfidence":0.7}'
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

# ═══════════════════════════════════════════════════════════════
# GENERATE DASHBOARD
# ═══════════════════════════════════════════════════════════════

echo "  🎨 Generating dashboard..."

python3 << EOF
import json
import re

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
model_data = list(stats.get('modelUsage', {}).values())[0] if stats.get('modelUsage') else {}
cache_read = model_data.get('cacheReadInputTokens', 0)
cache_create = model_data.get('cacheCreationInputTokens', 0)
input_tokens = model_data.get('inputTokens', 0)
total_input = cache_read + cache_create + input_tokens
cache_efficiency = (cache_read / total_input * 100) if total_input > 0 else 0

# Build coevo data
coevo_data = {
    "cacheEfficiency": round(cache_efficiency, 2),
    "dqScore": 0.839,
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

# Inject data
output = template.replace('__STATS_DATA__', json.dumps(stats))
output = output.replace('__MEMORY_DATA__', json.dumps(memory))
output = output.replace('__ACTIVITY_DATA__', json.dumps(activity))
output = output.replace('__PROJECTS_DATA__', json.dumps(projects))
output = output.replace('__PROACTIVE_DATA__', json.dumps(proactive))
output = output.replace('__COEVO_DATA__', json.dumps(coevo_data))
output = output.replace('__SUBSCRIPTION_DATA__', json.dumps(subscription_data))
output = output.replace('__ROUTING_DATA__', json.dumps(routing))

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
