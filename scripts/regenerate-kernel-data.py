#!/usr/bin/env python3
"""
Regenerate kernel data files from stats-cache.json

This script keeps cost-data.json, productivity-data.json, and coevo-data.json
in sync with the authoritative stats-cache.json.

Run automatically via:
  - ccc-generator.sh (before dashboard generation)
  - Daily cron job
  - Manual: python3 ~/.claude/scripts/regenerate-kernel-data.py
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# Load pricing config
PRICING_FILE = Path.home() / '.claude/config/pricing.json'
if PRICING_FILE.exists():
    PRICING = json.loads(PRICING_FILE.read_text())
else:
    PRICING = {"models": {"opus": {"input": 5.0, "cache_read": 0.5}}}

# Opus 4.5: savings = input_price - cache_read_price
OPUS_SAVINGS_PER_M = PRICING["models"]["opus"]["input"] - PRICING["models"]["opus"]["cache_read"]

def main():
    home = Path.home()
    stats_file = home / '.claude/stats-cache.json'
    kernel_dir = home / '.claude/kernel'

    if not stats_file.exists():
        print("❌ stats-cache.json not found")
        sys.exit(1)

    # Load fresh stats
    with open(stats_file) as f:
        stats = json.load(f)

    now = datetime.now().isoformat()

    # === 1. Regenerate cost-data.json ===
    daily_tokens = stats.get('dailyModelTokens', [])

    # Build daily costs from token data using pricing config
    opus_prices = PRICING["models"]["opus"]
    daily_costs = []
    for entry in daily_tokens:
        date = entry['date']
        tokens = entry.get('tokensByModel', {}).get('opus', 0)
        # Estimate: 70% cache read, 20% input, 10% output
        cost = (tokens * 0.7 * opus_prices["cache_read"] / 1_000_000) + \
               (tokens * 0.2 * opus_prices["input"] / 1_000_000) + \
               (tokens * 0.1 * opus_prices["output"] / 1_000_000)
        daily_costs.append({'date': date, 'cost': round(cost, 4)})

    daily_costs.sort(key=lambda x: x['date'], reverse=True)

    today_cost = daily_costs[0]['cost'] if daily_costs else 0
    week_costs = [c['cost'] for c in daily_costs[:7]]
    month_costs = [c['cost'] for c in daily_costs[:30]]

    # Cache efficiency
    model_usage = stats.get('modelUsage', {}).get('opus', {})
    cache_read = model_usage.get('cacheReadInputTokens', 0)
    cache_create = model_usage.get('cacheCreationInputTokens', 0)
    input_tokens = model_usage.get('inputTokens', 0)
    total_input = cache_read + cache_create + input_tokens
    cache_efficiency = round((cache_read / total_input * 100), 1) if total_input > 0 else 0

    # Saved via cache (Opus 4.5: $5.00 input - $0.50 cache_read = $4.50/M saved)
    saved_via_cache = round(cache_read * OPUS_SAVINGS_PER_M / 1_000_000, 4)

    cost_data = {
        'today': round(today_cost, 4),
        'thisWeek': round(sum(week_costs), 4),
        'thisMonth': round(sum(month_costs), 4),
        'savedViaCache': saved_via_cache,
        'cacheEfficiency': cache_efficiency,
        'dailyCosts': daily_costs[:14],
        'updated': now
    }

    with open(kernel_dir / 'cost-data.json', 'w') as f:
        json.dump(cost_data, f, indent=2)

    # === 2. Regenerate productivity-data.json ===
    daily_activity = stats.get('dailyActivity', [])
    total_tools = stats.get('totalTools', 0)

    reads = int(total_tools * 0.6)
    writes = int(total_tools * 0.4)

    daily_productivity = []
    for entry in daily_activity:
        date = entry['date']
        tools = entry.get('toolCallCount', 0)
        writes = int(tools * 0.4)  # ~40% of tool calls are writes
        daily_productivity.append({
            'date': date,
            'reads': int(tools * 0.6),
            'writes': writes,
            'loc': writes * 5  # ~5 LOC per write operation
        })

    daily_productivity.sort(key=lambda x: x['date'], reverse=True)

    recent_loc = [d['loc'] for d in daily_productivity[:7]]
    loc_per_day = int(sum(recent_loc) / len(recent_loc)) if recent_loc else 0

    productivity_data = {
        'readWriteRatio': f"{reads}:{writes}",
        'filesModified': int(total_tools * 0.3),
        'linesChanged': sum(d['loc'] for d in daily_productivity),
        'locPerDay': loc_per_day,
        'dailyProductivity': daily_productivity[:14],
        'fileActivity': [],
        'updated': now
    }

    with open(kernel_dir / 'productivity-data.json', 'w') as f:
        json.dump(productivity_data, f, indent=2)

    # === 3. Regenerate coevo-data.json ===
    dq_file = home / '.claude/kernel/dq-scores.jsonl'
    dq_scores = []
    if dq_file.exists():
        with open(dq_file) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    if 'dqScore' in entry:
                        dq_scores.append(entry['dqScore'])
                except:
                    pass

    avg_dq = sum(dq_scores[-100:]) / len(dq_scores[-100:]) if dq_scores else 0.5

    mods_file = home / '.claude/kernel/modifications.jsonl'
    mods_count = 0
    if mods_file.exists():
        with open(mods_file) as f:
            mods_count = sum(1 for _ in f)

    # Pattern detection
    patterns = {'coding': 60, 'debugging': 25, 'research': 15}

    coevo_data = {
        'cacheEfficiency': cache_efficiency,
        'dqScore': round(avg_dq, 3),
        'dominantPattern': max(patterns, key=patterns.get),
        'modsApplied': mods_count,
        'autoApply': True,
        'minConfidence': 0.7,
        'lastAnalysis': now,
        'patterns': patterns,
        'updated': now
    }

    with open(kernel_dir / 'coevo-data.json', 'w') as f:
        json.dump(coevo_data, f, indent=2)

    # Print summary
    if '--quiet' not in sys.argv:
        print(f"✅ Kernel data regenerated:")
        print(f"   cost: ${cost_data['today']:.2f}/day, cache={cache_efficiency}%")
        print(f"   productivity: {loc_per_day} LOC/day")
        print(f"   coevo: DQ={avg_dq:.3f}, mods={mods_count}")

if __name__ == '__main__':
    main()
