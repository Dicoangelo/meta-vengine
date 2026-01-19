#!/usr/bin/env python3
"""
Claude Observatory - Real-Time Cost Tracker
Tracks actual API costs, budget usage, and ROI
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import glob

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

HOME = Path.home()
DATA_FILE = HOME / ".claude/data/cost-tracking.jsonl"
SESSIONS_DIR = HOME / ".claude/projects"
STATS_CACHE = HOME / ".claude/stats-cache.json"

# Pricing (USD per million tokens) - Opus 4.5
PRICING = {
    "claude-opus-4-5-20251101": {
        "input": 15.00,
        "output": 75.00,
        "cache_read": 1.50,  # 10x cheaper than input
        "cache_create": 18.75  # 1.25x input cost
    },
    "claude-sonnet-4-5-20250929": {
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_create": 3.75
    },
    "claude-haiku-4-0-20250115": {
        "input": 0.25,
        "output": 1.25,
        "cache_read": 0.025,
        "cache_create": 0.3125
    }
}

SUBSCRIPTION_COST = 200.0  # Monthly Pro subscription

# ═══════════════════════════════════════════════════════════════════════════
# COST CALCULATION
# ═══════════════════════════════════════════════════════════════════════════

def calculate_session_cost(session_file: Path) -> Optional[Dict]:
    """Extract tokens and calculate cost for a single session"""
    try:
        with open(session_file) as f:
            lines = [json.loads(line) for line in f if line.strip()]
    except:
        return None

    # Find model usage messages
    tokens = {
        "input": 0,
        "output": 0,
        "cache_read": 0,
        "cache_create": 0
    }
    model = None

    for line in lines:
        if line.get('type') == 'assistant':
            usage = line.get('message', {}).get('usage', {})
            if usage:
                tokens['input'] += usage.get('input_tokens', 0)
                tokens['output'] += usage.get('output_tokens', 0)
                tokens['cache_read'] += usage.get('cache_read_input_tokens', 0)
                tokens['cache_create'] += usage.get('cache_creation_input_tokens', 0)

                if not model:
                    model = line.get('message', {}).get('model', 'claude-opus-4-5-20251101')

    if not model or sum(tokens.values()) == 0:
        return None

    # Calculate cost
    pricing = PRICING.get(model, PRICING['claude-opus-4-5-20251101'])
    cost = (
        (tokens['input'] / 1_000_000) * pricing['input'] +
        (tokens['output'] / 1_000_000) * pricing['output'] +
        (tokens['cache_read'] / 1_000_000) * pricing['cache_read'] +
        (tokens['cache_create'] / 1_000_000) * pricing['cache_create']
    )

    # Get session metadata
    start_msg = next((l for l in lines if l.get('type') == 'user'), None)
    timestamp = start_msg['timestamp'] if start_msg else None
    session_id = session_file.stem

    return {
        "session_id": session_id,
        "timestamp": timestamp,
        "model": model,
        "tokens": tokens,
        "cost_usd": round(cost, 4),
        "cache_efficiency": round(tokens['cache_read'] / sum(tokens.values()) * 100, 2) if sum(tokens.values()) > 0 else 0
    }

def log_session_cost(session_file: Path):
    """Calculate and log cost for a session"""
    result = calculate_session_cost(session_file)
    if not result:
        return

    # Append to cost log
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, 'a') as f:
        entry = {
            "ts": int(datetime.now().timestamp()),
            "event": "session_cost",
            **result
        }
        f.write(json.dumps(entry) + '\n')

    print(f"✅ Logged cost: ${result['cost_usd']:.4f} (session: {result['session_id'][:8]}...)")

# ═══════════════════════════════════════════════════════════════════════════
# BULK PROCESSING
# ═══════════════════════════════════════════════════════════════════════════

def process_all_sessions(days: int = 30):
    """Process all sessions and calculate total costs"""
    cutoff = datetime.now() - timedelta(days=days)

    session_files = list(SESSIONS_DIR.glob("**/*.jsonl"))
    print(f"🔍 Processing {len(session_files)} sessions...")

    costs = []
    for session_file in session_files:
        # Check file modification time
        if datetime.fromtimestamp(session_file.stat().st_mtime) < cutoff:
            continue

        result = calculate_session_cost(session_file)
        if result:
            costs.append(result)

    # Save to cost log
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, 'a') as f:
        for cost in costs:
            entry = {
                "ts": int(datetime.now().timestamp()),
                "event": "bulk_import",
                **cost
            }
            f.write(json.dumps(entry) + '\n')

    total_cost = sum(c['cost_usd'] for c in costs)
    print(f"✅ Processed {len(costs)} sessions")
    print(f"💰 Total cost (last {days} days): ${total_cost:.2f}")

# ═══════════════════════════════════════════════════════════════════════════
# REPORTING
# ═══════════════════════════════════════════════════════════════════════════

def load_costs(days: int = 30) -> List[Dict]:
    """Load cost entries from log"""
    if not DATA_FILE.exists():
        return []

    cutoff = datetime.now() - timedelta(days=days)

    with open(DATA_FILE) as f:
        entries = [json.loads(line) for line in f if line.strip()]

    return [e for e in entries if datetime.fromtimestamp(e['ts']) > cutoff]

def generate_report(days: int = 30, format: str = "text"):
    """Generate cost report"""
    costs = load_costs(days)

    if not costs:
        print(f"No cost data for last {days} days")
        return

    # Aggregate stats
    total_cost = sum(c.get('cost_usd', 0) for c in costs)
    sessions = len(set(c['session_id'] for c in costs if 'session_id' in c))
    avg_cost_per_session = total_cost / sessions if sessions > 0 else 0

    # Daily breakdown
    daily_costs = {}
    for c in costs:
        date = datetime.fromtimestamp(c['ts']).strftime('%Y-%m-%d')
        daily_costs[date] = daily_costs.get(date, 0) + c.get('cost_usd', 0)

    # Model breakdown
    model_costs = {}
    for c in costs:
        model = c.get('model', 'unknown')
        model_costs[model] = model_costs.get(model, 0) + c.get('cost_usd', 0)

    # Budget analysis
    monthly_cost_projected = total_cost / days * 30
    budget_utilization = (total_cost / SUBSCRIPTION_COST) * 100
    roi_multiplier = SUBSCRIPTION_COST / total_cost if total_cost > 0 else 0

    if format == "json":
        report = {
            "period_days": days,
            "total_cost_usd": round(total_cost, 2),
            "sessions": sessions,
            "avg_cost_per_session": round(avg_cost_per_session, 4),
            "monthly_projected": round(monthly_cost_projected, 2),
            "subscription_cost": SUBSCRIPTION_COST,
            "budget_utilization_pct": round(budget_utilization, 2),
            "roi_multiplier": round(roi_multiplier, 2),
            "daily_costs": {k: round(v, 2) for k, v in daily_costs.items()},
            "model_breakdown": {k: round(v, 2) for k, v in model_costs.items()}
        }
        print(json.dumps(report, indent=2))
    else:
        print("═══════════════════════════════════════════════════════════════")
        print(f"  💰 COST REPORT - Last {days} Days")
        print("═══════════════════════════════════════════════════════════════")
        print()
        print(f"  Total Cost:        ${total_cost:.2f}")
        print(f"  Sessions:          {sessions}")
        print(f"  Avg/Session:       ${avg_cost_per_session:.4f}")
        print()
        print(f"  Monthly Projected: ${monthly_cost_projected:.2f}")
        print(f"  Subscription Cost: ${SUBSCRIPTION_COST:.2f}")
        print(f"  Budget Used:       {budget_utilization:.1f}%")
        print(f"  ROI Multiplier:    {roi_multiplier:.1f}x")
        print()
        print("  Model Breakdown:")
        for model, cost in sorted(model_costs.items(), key=lambda x: x[1], reverse=True):
            model_short = model.split('-')[1] if '-' in model else model
            pct = (cost / total_cost * 100) if total_cost > 0 else 0
            print(f"    {model_short:10s} ${cost:8.2f} ({pct:5.1f}%)")
        print()

        # Alert if over budget
        if budget_utilization > 80:
            print("  ⚠️  Warning: Over 80% of monthly budget!")
        elif monthly_cost_projected > SUBSCRIPTION_COST:
            print(f"  ⚠️  Warning: Projected ${monthly_cost_projected:.2f}/mo exceeds subscription!")
        else:
            savings = SUBSCRIPTION_COST - monthly_cost_projected
            print(f"  ✅ On track! Projected savings: ${savings:.2f}/mo")
        print()

def check_budget_status():
    """Quick budget check"""
    costs = load_costs(days=30)
    total = sum(c.get('cost_usd', 0) for c in costs)
    utilization = (total / SUBSCRIPTION_COST) * 100

    if utilization > 90:
        print(f"🔴 Budget: {utilization:.0f}% used (${total:.2f}/${SUBSCRIPTION_COST})")
    elif utilization > 70:
        print(f"🟡 Budget: {utilization:.0f}% used (${total:.2f}/${SUBSCRIPTION_COST})")
    else:
        print(f"🟢 Budget: {utilization:.0f}% used (${total:.2f}/${SUBSCRIPTION_COST})")

# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  cost-tracker.py log <session-file>     - Log cost for session")
        print("  cost-tracker.py process [days]         - Process all sessions")
        print("  cost-tracker.py report [days]          - Generate cost report")
        print("  cost-tracker.py budget                 - Check budget status")
        print("  cost-tracker.py export [days]          - Export as JSON")
        return

    command = sys.argv[1]

    if command == "log" and len(sys.argv) > 2:
        log_session_cost(Path(sys.argv[2]))
    elif command == "process":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        process_all_sessions(days)
    elif command == "report":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        generate_report(days, format="text")
    elif command == "export":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        generate_report(days, format="json")
    elif command == "budget":
        check_budget_status()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()
