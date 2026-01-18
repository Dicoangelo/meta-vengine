#!/bin/bash
# Claude Code Dashboard Generator

STATS_FILE="$HOME/.claude/stats-cache.json"
TEMPLATE="$HOME/.claude/scripts/dashboard.html"
OUTPUT="/tmp/claude-dashboard.html"

if [[ ! -f "$STATS_FILE" ]]; then
  echo "No stats found at $STATS_FILE"
  exit 1
fi

# Read stats and escape for JS
STATS=$(cat "$STATS_FILE" | tr -d '\n')

# Build output file
head -n -3 "$TEMPLATE" | sed 's/__STATS_DATA__/{}/' > "$OUTPUT"

# Create the actual HTML with data injected via python for safety
python3 << EOF
import json

with open('$STATS_FILE', 'r') as f:
    stats = json.load(f)

with open('$TEMPLATE', 'r') as f:
    template = f.read()

output = template.replace('__STATS_DATA__', json.dumps(stats))

with open('$OUTPUT', 'w') as f:
    f.write(output)
EOF

# Open in browser
open "$OUTPUT"

echo "✓ Dashboard opened"
