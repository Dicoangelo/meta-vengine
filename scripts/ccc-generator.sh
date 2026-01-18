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

# Inject data
output = template.replace('__STATS_DATA__', json.dumps(stats))
output = output.replace('__MEMORY_DATA__', json.dumps(memory))
output = output.replace('__ACTIVITY_DATA__', json.dumps(activity))
output = output.replace('__PROJECTS_DATA__', json.dumps(projects))
output = output.replace('__PROACTIVE_DATA__', json.dumps(proactive))

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
echo "  1-6  Switch tabs"
echo "  R    Refresh"
