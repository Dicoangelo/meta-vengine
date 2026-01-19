#!/usr/bin/env python3
"""
Claude Observatory - Unified Analytics Engine
Combines all data sources for comprehensive insights and predictions
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List
from collections import Counter, defaultdict

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

HOME = Path.home()
DATA_DIR = HOME / ".claude/data"

# All data sources
SOURCES = {
    "sessions": DATA_DIR / "session-outcomes.jsonl",
    "costs": DATA_DIR / "cost-tracking.jsonl",
    "commands": DATA_DIR / "command-usage.jsonl",
    "tools": DATA_DIR / "tool-success.jsonl",
    "productivity": DATA_DIR / "productivity.jsonl",
    "git": DATA_DIR / "git-activity.jsonl",
    "routing": DATA_DIR / "routing-metrics.jsonl",
    "dq_scores": HOME / ".claude/kernel/dq-scores.jsonl"
}

# ═══════════════════════════════════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════════════════════════════════

def load_data_source(source_name: str, days: int = 30) -> List[Dict]:
    """Load data from a source file"""
    source_file = SOURCES.get(source_name)
    if not source_file or not source_file.exists():
        return []

    cutoff = datetime.now() - timedelta(days=days)
    data = []

    with open(source_file) as f:
        for line in f:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                # Handle both ms and seconds timestamps
                ts = entry.get('ts', 0)
                if ts > 1e12:  # Milliseconds
                    ts = ts / 1000
                if datetime.fromtimestamp(ts) > cutoff:
                    data.append(entry)
            except:
                continue

    return data

def load_all_data(days: int = 30) -> Dict[str, List]:
    """Load all data sources"""
    return {source: load_data_source(source, days) for source in SOURCES.keys()}

# ═══════════════════════════════════════════════════════════════════════════
# COMPREHENSIVE ANALYTICS
# ═══════════════════════════════════════════════════════════════════════════

def calculate_comprehensive_metrics(days: int = 30) -> Dict:
    """Calculate metrics across all data sources"""
    data = load_all_data(days)

    metrics = {}

    # Session metrics
    if data['sessions']:
        completed = [s for s in data['sessions'] if s.get('event') == 'session_complete']
        if completed:
            outcomes = Counter(s['outcome'] for s in completed)
            avg_quality = sum(s.get('quality', 3) for s in completed) / len(completed)
            avg_duration = sum(s.get('duration_sec', 0) for s in completed) / len(completed) / 60

            metrics['sessions'] = {
                "total": len(completed),
                "success_rate": outcomes.get('success', 0) / len(completed) if completed else 0,
                "avg_quality": round(avg_quality, 2),
                "avg_duration_min": round(avg_duration, 1),
                "outcomes": dict(outcomes)
            }

    # Cost metrics
    if data['costs']:
        total_cost = sum(c.get('cost_usd', 0) for c in data['costs'])
        sessions_count = len(set(c['session_id'] for c in data['costs'] if 'session_id' in c))

        metrics['costs'] = {
            "total_cost": round(total_cost, 2),
            "sessions_tracked": sessions_count,
            "avg_per_session": round(total_cost / sessions_count, 4) if sessions_count > 0 else 0,
            "monthly_projected": round(total_cost / days * 30, 2),
            "budget_utilization": round(total_cost / 200 * 100, 1)
        }

    # Command usage metrics
    if data['commands']:
        commands = Counter(c['cmd'] for c in data['commands'])
        total = len(data['commands'])

        metrics['commands'] = {
            "total_commands": total,
            "unique_commands": len(commands),
            "top_commands": dict(commands.most_common(10)),
            "commands_per_day": round(total / days, 1)
        }

    # Tool success metrics
    if data['tools']:
        successful = sum(1 for t in data['tools'] if t.get('success', False))
        total = len(data['tools'])

        metrics['tools'] = {
            "total_operations": total,
            "success_rate": round(successful / total, 3) if total > 0 else 0,
            "failure_rate": round((total - successful) / total, 3) if total > 0 else 0
        }

    # Git metrics
    if data['git']:
        commits = [g for g in data['git'] if g.get('event') == 'commit']
        prs = [g for g in data['git'] if g.get('event') == 'pr_created']

        metrics['git'] = {
            "commits": len(commits),
            "prs_created": len(prs),
            "avg_commits_per_day": round(len(commits) / days, 2)
        }

    # Productivity metrics
    if data['productivity']:
        latest = data['productivity'][-1] if data['productivity'] else {}
        reads = latest.get('reads', 0)
        writes = latest.get('writes', 0)
        edits = latest.get('edits', 0)
        total_writes = writes + edits

        metrics['productivity'] = {
            "reads": reads,
            "writes": total_writes,
            "read_write_ratio": {"reads": reads, "writes": max(total_writes, 1)},
            "files_modified": latest.get('files_changed', 0),
            "lines_changed": latest.get('net_loc', 0),
            "loc_per_day": round(latest.get('productivity_velocity', 0), 1),
            "productivity_score": round(total_writes / max(reads, 1), 3) if reads > 0 else 0
        }

    # Routing metrics
    if data['routing'] or data['dq_scores']:
        routing_data = data['routing'] if data['routing'] else data['dq_scores']
        models = Counter(r.get('model', 'unknown') for r in routing_data)
        avg_dq = sum(r.get('dq', 0) for r in routing_data if 'dq' in r) / len(routing_data) if routing_data else 0

        metrics['routing'] = {
            "total_queries": len(routing_data),
            "avg_dq_score": round(avg_dq, 3),
            "model_distribution": dict(models)
        }

    return metrics

# ═══════════════════════════════════════════════════════════════════════════
# INSIGHT GENERATION
# ═══════════════════════════════════════════════════════════════════════════

def generate_insights(metrics: Dict) -> List[str]:
    """Generate actionable insights from metrics"""
    insights = []

    # Session insights
    if 'sessions' in metrics:
        success_rate = metrics['sessions'].get('success_rate', 0)
        if success_rate < 0.5:
            insights.append(f"⚠️  Low session success rate ({success_rate:.0%}). Consider breaking down complex tasks.")
        elif success_rate > 0.8:
            insights.append(f"✅ Excellent session success rate ({success_rate:.0%})!")

        avg_quality = metrics['sessions'].get('avg_quality', 0)
        if avg_quality < 3:
            insights.append(f"⚠️  Sessions averaging low quality ({avg_quality:.1f}/5). Focus on clearer objectives.")

    # Cost insights
    if 'costs' in metrics:
        utilization = metrics['costs'].get('budget_utilization', 0)
        if utilization > 80:
            insights.append(f"🔴 Using {utilization:.0f}% of budget! Consider model optimization.")
        elif utilization < 20:
            insights.append(f"💡 Only using {utilization:.0f}% of subscription. You can do more!")

    # Command insights
    if 'commands' in metrics:
        top_cmd = list(metrics['commands']['top_commands'].keys())[0] if metrics['commands']['top_commands'] else None
        if top_cmd and top_cmd in ['co', 'claude-opus']:
            insights.append("💡 You're using Opus frequently. DQ routing could reduce costs.")

    # Tool insights
    if 'tools' in metrics:
        success_rate = metrics['tools'].get('success_rate', 0)
        if success_rate < 0.7:
            insights.append(f"⚠️  Tool success rate is {success_rate:.0%}. Review recent failures.")

    # Git insights
    if 'git' in metrics:
        commits_per_day = metrics['git'].get('avg_commits_per_day', 0)
        if commits_per_day < 0.5:
            insights.append(f"💡 Low commit rate ({commits_per_day:.1f}/day). Create more checkpoints.")
        elif commits_per_day > 5:
            insights.append(f"✨ High velocity ({commits_per_day:.1f} commits/day)!")

    # Routing insights
    if 'routing' in metrics:
        total_queries = metrics['routing'].get('total_queries', 0)
        if total_queries < 50:
            insights.append(f"📊 Only {total_queries} routed queries. More data needed for optimization.")

    return insights

# ═══════════════════════════════════════════════════════════════════════════
# UNIFIED REPORTING
# ═══════════════════════════════════════════════════════════════════════════

def generate_unified_report(days: int = 7, format: str = "text"):
    """Generate comprehensive report across all data sources"""
    metrics = calculate_comprehensive_metrics(days)
    insights = generate_insights(metrics)

    if format == "json":
        report = {
            "period_days": days,
            "generated_at": datetime.now().isoformat(),
            "metrics": metrics,
            "insights": insights
        }
        print(json.dumps(report, indent=2))
        return

    # Text format
    print("═══════════════════════════════════════════════════════════════")
    print(f"  🔭 CLAUDE OBSERVATORY - UNIFIED REPORT")
    print(f"  Period: Last {days} days | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("═══════════════════════════════════════════════════════════════")
    print()

    # Sessions
    if 'sessions' in metrics:
        print("  📊 SESSIONS")
        s = metrics['sessions']
        print(f"    Total:        {s['total']}")
        print(f"    Success Rate: {s['success_rate']:.0%}")
        print(f"    Avg Quality:  {s['avg_quality']:.1f}/5")
        print(f"    Avg Duration: {s['avg_duration_min']:.0f}m")
        print()

    # Costs
    if 'costs' in metrics:
        print("  💰 COSTS")
        c = metrics['costs']
        print(f"    Total Cost:   ${c['total_cost']:.2f}")
        print(f"    Per Session:  ${c['avg_per_session']:.4f}")
        print(f"    Monthly Proj: ${c['monthly_projected']:.2f}")
        print(f"    Budget Used:  {c['budget_utilization']:.1f}%")
        print()

    # Commands
    if 'commands' in metrics:
        print("  ⌨️  COMMANDS")
        cmd = metrics['commands']
        print(f"    Total:        {cmd['total_commands']}")
        print(f"    Per Day:      {cmd['commands_per_day']:.1f}")
        print(f"    Top 3:")
        for c, count in list(cmd['top_commands'].items())[:3]:
            print(f"      {c:15s} {count:3d}")
        print()

    # Tools
    if 'tools' in metrics:
        print("  🔧 TOOLS")
        t = metrics['tools']
        print(f"    Operations:   {t['total_operations']}")
        print(f"    Success Rate: {t['success_rate']:.0%}")
        print()

    # Git
    if 'git' in metrics:
        print("  📝 GIT ACTIVITY")
        g = metrics['git']
        print(f"    Commits:      {g['commits']}")
        print(f"    PRs Created:  {g['prs_created']}")
        print(f"    Per Day:      {g['avg_commits_per_day']:.1f}")
        print()

    # Routing
    if 'routing' in metrics:
        print("  🎯 ROUTING")
        r = metrics['routing']
        print(f"    Queries:      {r['total_queries']}")
        print(f"    Avg DQ Score: {r['avg_dq_score']:.3f}")
        print()

    # Insights
    if insights:
        print("  💡 INSIGHTS")
        for insight in insights:
            print(f"    {insight}")
        print()

def generate_daily_digest():
    """Generate daily digest email/notification"""
    metrics = calculate_comprehensive_metrics(days=1)
    insights = generate_insights(metrics)

    print("═══════════════════════════════════════════════════════════════")
    print("  📬 DAILY DIGEST")
    print("═══════════════════════════════════════════════════════════════")
    print()

    # Quick summary
    sessions = metrics.get('sessions', {}).get('total', 0)
    cost = metrics.get('costs', {}).get('total_cost', 0)
    commits = metrics.get('git', {}).get('commits', 0)

    print(f"  Yesterday: {sessions} sessions, ${cost:.2f} spent, {commits} commits")
    print()

    # Top insights
    if insights:
        print("  Key Insights:")
        for insight in insights[:3]:
            print(f"    {insight}")
        print()

# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  analytics-engine.py report [days]   - Unified report")
        print("  analytics-engine.py digest          - Daily digest")
        print("  analytics-engine.py export [days]   - Export as JSON")
        return

    command = sys.argv[1]

    if command == "report":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        generate_unified_report(days, format="text")
    elif command == "digest":
        generate_daily_digest()
    elif command == "export":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        generate_unified_report(days, format="json")
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()
