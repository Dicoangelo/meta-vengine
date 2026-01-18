#!/bin/bash
# Claude Command Center - Full Dashboard Generator
# Aggregates all data and opens unified dashboard

STATS_FILE="$HOME/.claude/stats-cache.json"
MEMORY_FILE="$HOME/.claude/memory/knowledge.json"
ACTIVITY_LOG="$HOME/.claude/activity.log"
TEMPLATE="$HOME/.claude/scripts/dashboard-full.html"
OUTPUT="/tmp/claude-command-center.html"

# Default empty data
DEFAULT_STATS='{"totalSessions":0,"totalMessages":0,"dailyActivity":[],"dailyModelTokens":[],"modelUsage":{},"hourCounts":{}}'
DEFAULT_MEMORY='{"facts":[],"decisions":[],"patterns":[],"context":{},"projects":{}}'

# Read stats
if [[ -f "$STATS_FILE" ]]; then
  STATS_DATA=$(cat "$STATS_FILE")
else
  STATS_DATA="$DEFAULT_STATS"
fi

# Read memory
if [[ -f "$MEMORY_FILE" ]]; then
  MEMORY_DATA=$(cat "$MEMORY_FILE")
else
  MEMORY_DATA="$DEFAULT_MEMORY"
fi

# Read recent activity (last 100 lines)
if [[ -f "$ACTIVITY_LOG" ]]; then
  ACTIVITY_DATA=$(tail -100 "$ACTIVITY_LOG" | python3 -c "
import sys, json
lines = [line.strip() for line in sys.stdin if line.strip()]
print(json.dumps(lines))
")
else
  ACTIVITY_DATA='[]'
fi

# Projects data
PROJECTS_DATA='[
  {"name": "OS-App", "stack": "Vite + React 19 + Zustand + Supabase", "status": "active"},
  {"name": "CareerCoachAntigravity", "stack": "Next.js 14 + React 18 + Zustand", "status": "active"},
  {"name": "researchgravity", "stack": "Python 3.8+", "status": "active"}
]'

# Generate dashboard
python3 << EOF
import json

# Read template
with open('$TEMPLATE', 'r') as f:
    template = f.read()

# Parse data
try:
    stats = json.loads('''$STATS_DATA''')
except:
    stats = json.loads('$DEFAULT_STATS')

try:
    memory = json.loads('''$MEMORY_DATA''')
except:
    memory = json.loads('$DEFAULT_MEMORY')

try:
    activity = json.loads('''$ACTIVITY_DATA''')
except:
    activity = []

projects = json.loads('''$PROJECTS_DATA''')

# Inject data
output = template.replace('__STATS_DATA__', json.dumps(stats))
output = output.replace('__MEMORY_DATA__', json.dumps(memory))
output = output.replace('__ACTIVITY_DATA__', json.dumps(activity))
output = output.replace('__PROJECTS_DATA__', json.dumps(projects))

# Write output
with open('$OUTPUT', 'w') as f:
    f.write(output)

print('✓ Dashboard generated')
EOF

# Open in browser
open "$OUTPUT"
echo "✓ Command Center opened"
