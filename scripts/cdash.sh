#!/bin/bash
# Claude Code Dashboard Generator with Co-Evolution

STATS_FILE="$HOME/.claude/stats-cache.json"
COEVO_CONFIG="$HOME/.claude/kernel/coevo-config.json"
PATTERNS_FILE="$HOME/.claude/kernel/detected-patterns.json"
MODS_FILE="$HOME/.claude/kernel/modifications.jsonl"
TEMPLATE="$HOME/.claude/scripts/dashboard.html"
OUTPUT="/tmp/claude-dashboard.html"

if [[ ! -f "$STATS_FILE" ]]; then
  echo "No stats found at $STATS_FILE"
  exit 1
fi

# Create the actual HTML with data injected via python
python3 << 'PYTHON_EOF'
import json
import os
from pathlib import Path

home = Path.home()

# Load main stats
with open(home / '.claude/stats-cache.json', 'r') as f:
    stats = json.load(f)

# Load coevo config
coevo_config = {"enabled": True, "autoApply": False, "minConfidence": 0.7}
coevo_config_path = home / '.claude/kernel/coevo-config.json'
if coevo_config_path.exists():
    with open(coevo_config_path, 'r') as f:
        coevo_config = json.load(f)

# Load patterns
patterns = {"patterns": []}
patterns_path = home / '.claude/kernel/detected-patterns.json'
if patterns_path.exists():
    with open(patterns_path, 'r') as f:
        patterns = json.load(f)

# Count modifications
mods_count = 0
mods_path = home / '.claude/kernel/modifications.jsonl'
if mods_path.exists():
    with open(mods_path, 'r') as f:
        mods_count = sum(1 for line in f if line.strip())

# Calculate cache efficiency
model_data = list(stats.get('modelUsage', {}).values())[0] if stats.get('modelUsage') else {}
cache_read = model_data.get('cacheReadInputTokens', 0)
cache_create = model_data.get('cacheCreationInputTokens', 0)
input_tokens = model_data.get('inputTokens', 0)
total_input = cache_read + cache_create + input_tokens
cache_efficiency = (cache_read / total_input * 100) if total_input > 0 else 0

# Build coevo data
coevo_data = {
    "cacheEfficiency": round(cache_efficiency, 2),
    "dqScore": 0.839,  # From DQ scorer
    "dominantPattern": patterns.get('patterns', [{}])[0].get('id', 'none') if patterns.get('patterns') else 'none',
    "modsApplied": mods_count,
    "autoApply": coevo_config.get('autoApply', False),
    "minConfidence": coevo_config.get('minConfidence', 0.7),
    "patterns": patterns.get('patterns', [])
}

# Combine all data
combined = {
    "stats": stats,
    "coevo": coevo_data
}

# Load template
with open(home / '.claude/scripts/dashboard.html', 'r') as f:
    template = f.read()

# Inject both datasets
output = template.replace('__STATS_DATA__', json.dumps(stats))
output = output.replace('__COEVO_DATA__', json.dumps(coevo_data))

# Write output
with open('/tmp/claude-dashboard.html', 'w') as f:
    f.write(output)

print(f"✓ Dashboard generated with Co-Evolution data")
print(f"  Cache Efficiency: {cache_efficiency:.1f}%")
print(f"  Dominant Pattern: {coevo_data['dominantPattern']}")
print(f"  Mods Applied: {mods_count}")
PYTHON_EOF

# Open in browser
open "$OUTPUT"
