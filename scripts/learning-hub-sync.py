#!/usr/bin/env python3
"""
Learning Hub Sync - Aggregate learnings from all systems weekly.

Reads from:
- learned-weights.json (Cognitive OS)
- baselines.json (Routing)
- detected-patterns.json (Patterns)
- supermemory.db (Memory)
- identity.json (Identity)
- recovery-outcomes.jsonl (Recovery)

Produces:
- Cross-domain correlations
- Weekly summary
- Improvement suggestions
"""

import json
import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import Counter

# Paths
CLAUDE_DIR = Path.home() / ".claude"
KERNEL_DIR = CLAUDE_DIR / "kernel"
DATA_DIR = CLAUDE_DIR / "data"
MEMORY_DIR = CLAUDE_DIR / "memory"

LEARNING_HUB = KERNEL_DIR / "learning-hub.json"
COS_WEIGHTS = KERNEL_DIR / "cognitive-os" / "learned-weights.json"
BASELINES = KERNEL_DIR / "baselines.json"
PATTERNS = KERNEL_DIR / "detected-patterns.json"
SUPERMEMORY_DB = MEMORY_DIR / "supermemory.db"
IDENTITY = KERNEL_DIR / "identity.json"
RECOVERY_OUTCOMES = DATA_DIR / "recovery-outcomes.jsonl"
DQ_SCORES = KERNEL_DIR / "dq-scores.jsonl"
ACTIVITY_EVENTS = DATA_DIR / "activity-events.jsonl"


def load_json(path: Path) -> Dict:
    """Load JSON file safely."""
    if path.exists():
        try:
            return json.loads(path.read_text())
        except:
            pass
    return {}


def load_jsonl(path: Path, since_days: int = 7) -> List[Dict]:
    """Load JSONL file, optionally filtering by date."""
    results = []
    if not path.exists():
        return results

    cutoff = (datetime.now() - timedelta(days=since_days)).timestamp()

    for line in path.read_text().strip().split('\n'):
        if line:
            try:
                d = json.loads(line)
                ts = d.get('ts', d.get('timestamp', 0))
                if isinstance(ts, str):
                    ts = datetime.fromisoformat(ts).timestamp()
                if ts > cutoff:
                    results.append(d)
            except:
                pass

    return results


def get_supermemory_stats() -> Dict:
    """Get stats from supermemory SQLite database."""
    if not SUPERMEMORY_DB.exists():
        return {"available": False}

    try:
        conn = sqlite3.connect(str(SUPERMEMORY_DB))
        cursor = conn.cursor()

        # Get memory counts
        cursor.execute("SELECT COUNT(*) FROM memories")
        memory_count = cursor.fetchone()[0]

        # Get recent memories
        cursor.execute("""
            SELECT COUNT(*) FROM memories
            WHERE created_at > datetime('now', '-7 days')
        """)
        recent_memories = cursor.fetchone()[0]

        # Get topic distribution
        cursor.execute("""
            SELECT topic, COUNT(*) FROM memories
            GROUP BY topic ORDER BY COUNT(*) DESC LIMIT 5
        """)
        top_topics = cursor.fetchall()

        conn.close()

        return {
            "available": True,
            "total_memories": memory_count,
            "recent_memories": recent_memories,
            "top_topics": [{"topic": t[0], "count": t[1]} for t in top_topics]
        }
    except Exception as e:
        return {"available": False, "error": str(e)}


def aggregate_cognitive_os() -> Dict:
    """Aggregate Cognitive OS learnings."""
    weights = load_json(COS_WEIGHTS)

    accuracy_history = weights.get("accuracy_history", [])
    if accuracy_history:
        recent = accuracy_history[-20:]  # Last 20 predictions
        correct = sum(1 for a in recent if a.get("correct", False))
        accuracy = correct / len(recent) if recent else 0
    else:
        accuracy = 0

    return {
        "fate_weights": weights.get("fate_weights", {}),
        "prediction_count": len(accuracy_history),
        "recent_accuracy": round(accuracy, 3),
        "model_routes": weights.get("model_routes", {})
    }


def aggregate_routing() -> Dict:
    """Aggregate routing decisions."""
    baselines = load_json(BASELINES)
    dq_scores = load_jsonl(DQ_SCORES, since_days=7)

    model_dist = {"haiku": 0, "sonnet": 0, "opus": 0}
    dq_values = []

    for d in dq_scores:
        model = d.get("model", "sonnet")
        if model in model_dist:
            model_dist[model] += 1
        if "dqScore" in d:
            dq_values.append(d["dqScore"])

    avg_dq = sum(dq_values) / len(dq_values) if dq_values else 0

    return {
        "version": baselines.get("version", "unknown"),
        "decisions_this_week": len(dq_scores),
        "model_distribution": model_dist,
        "average_dq": round(avg_dq, 3)
    }


def aggregate_patterns() -> Dict:
    """Aggregate detected patterns."""
    patterns = load_json(PATTERNS)
    activity = load_jsonl(ACTIVITY_EVENTS, since_days=7)

    session_types = Counter()
    for a in activity:
        st = a.get("session_type", "unknown")
        session_types[st] += 1

    return {
        "current_session_type": patterns.get("current_session_type", "unknown"),
        "session_type_distribution": dict(session_types.most_common(5)),
        "total_events": len(activity)
    }


def aggregate_recovery() -> Dict:
    """Aggregate recovery outcomes."""
    outcomes = load_jsonl(RECOVERY_OUTCOMES, since_days=7)

    if not outcomes:
        return {"total": 0}

    success_count = sum(1 for o in outcomes if o.get("success", False))
    auto_count = sum(1 for o in outcomes if o.get("auto", False))

    categories = Counter()
    for o in outcomes:
        categories[o.get("category", "unknown")] += 1

    return {
        "total": len(outcomes),
        "success_rate": round(success_count / len(outcomes), 3) if outcomes else 0,
        "auto_fix_rate": round(auto_count / len(outcomes), 3) if outcomes else 0,
        "categories": dict(categories.most_common(5))
    }


def aggregate_identity() -> Dict:
    """Aggregate identity and expertise."""
    identity = load_json(IDENTITY)

    expertise = identity.get("expertise", {})
    confidence = expertise.get("confidence", {})

    # Get top expertise domains
    top_domains = sorted(
        confidence.items(),
        key=lambda x: x[1],
        reverse=True
    )[:5]

    stats = identity.get("statistics", {})

    return {
        "top_expertise": [{"domain": d, "confidence": round(c, 3)} for d, c in top_domains],
        "total_queries": stats.get("totalQueries", 0),
        "avg_dq": round(stats.get("avgDQScore", 0), 3),
        "model_usage": stats.get("modelUsage", {})
    }


def find_correlations(aggregated: Dict) -> List[Dict]:
    """Find cross-domain correlations."""
    correlations = []

    # Correlation: High DQ score + high expertise
    routing = aggregated.get("routing", {})
    identity = aggregated.get("identity", {})

    if routing.get("average_dq", 0) > 0.7 and identity.get("top_expertise"):
        top_exp = identity["top_expertise"][0] if identity["top_expertise"] else {}
        if top_exp.get("confidence", 0) > 0.6:
            correlations.append({
                "type": "positive",
                "domains": ["routing", "identity"],
                "insight": f"High DQ ({routing['average_dq']}) correlates with strong {top_exp.get('domain', '')} expertise",
                "strength": "strong"
            })

    # Correlation: Recovery failures + time of day patterns
    recovery = aggregated.get("recovery", {})
    cognitive = aggregated.get("cognitive_os", {})

    if recovery.get("success_rate", 1) < 0.7:
        correlations.append({
            "type": "negative",
            "domains": ["recovery", "cognitive_os"],
            "insight": f"Recovery success rate ({recovery.get('success_rate', 0):.0%}) is low - check if occurring during low-energy periods",
            "strength": "moderate"
        })

    # Correlation: Pattern detection + model usage
    patterns = aggregated.get("patterns", {})
    if patterns.get("session_type_distribution"):
        top_type = list(patterns["session_type_distribution"].keys())[0] if patterns["session_type_distribution"] else None
        if top_type == "architecture" and routing.get("model_distribution", {}).get("opus", 0) > 0:
            correlations.append({
                "type": "positive",
                "domains": ["patterns", "routing"],
                "insight": "Architecture sessions properly using Opus for complex reasoning",
                "strength": "moderate"
            })

    return correlations


def generate_suggestions(aggregated: Dict, correlations: List[Dict]) -> List[Dict]:
    """Generate improvement suggestions based on aggregated data."""
    suggestions = []

    # Suggestion: Low DQ score
    routing = aggregated.get("routing", {})
    if routing.get("average_dq", 1) < 0.6:
        suggestions.append({
            "priority": "high",
            "domain": "routing",
            "suggestion": f"DQ score is low ({routing['average_dq']:.2f}). Consider reviewing query patterns or adjusting thresholds.",
            "action": "Review dq-scores.jsonl for patterns of low scores"
        })

    # Suggestion: Low prediction accuracy
    cognitive = aggregated.get("cognitive_os", {})
    if cognitive.get("prediction_count", 0) > 10 and cognitive.get("recent_accuracy", 1) < 0.5:
        suggestions.append({
            "priority": "high",
            "domain": "cognitive_os",
            "suggestion": f"Fate prediction accuracy is low ({cognitive['recent_accuracy']:.0%}). Weights may need retuning.",
            "action": "Run cos tune to adjust prediction weights"
        })

    # Suggestion: Heavy Opus usage
    model_usage = routing.get("model_distribution", {})
    total_usage = sum(model_usage.values())
    if total_usage > 0:
        opus_pct = model_usage.get("opus", 0) / total_usage
        if opus_pct > 0.5:
            suggestions.append({
                "priority": "medium",
                "domain": "routing",
                "suggestion": f"Opus usage is high ({opus_pct:.0%}). Consider if all tasks require this capability.",
                "action": "Review recent sessions for over-provisioning"
            })

    # Suggestion: Low memory usage
    memory = aggregated.get("supermemory", {})
    if memory.get("available") and memory.get("recent_memories", 0) < 5:
        suggestions.append({
            "priority": "medium",
            "domain": "supermemory",
            "suggestion": "Few new memories added recently. Consider logging more insights.",
            "action": "Run sm context to review memory utilization"
        })

    # Suggestion: High recovery failures
    recovery = aggregated.get("recovery", {})
    if recovery.get("total", 0) > 5 and recovery.get("success_rate", 1) < 0.7:
        suggestions.append({
            "priority": "high",
            "domain": "recovery",
            "suggestion": f"Recovery success rate is low ({recovery['success_rate']:.0%}). Check for recurring issues.",
            "action": "Run meta-analyzer analyze to identify patterns"
        })

    return suggestions


def generate_weekly_summary(aggregated: Dict, correlations: List[Dict], suggestions: List[Dict]) -> Dict:
    """Generate weekly summary."""
    return {
        "week_ending": datetime.now().isoformat(),
        "key_metrics": {
            "routing_dq": aggregated.get("routing", {}).get("average_dq", 0),
            "prediction_accuracy": aggregated.get("cognitive_os", {}).get("recent_accuracy", 0),
            "recovery_success": aggregated.get("recovery", {}).get("success_rate", 0),
            "memories_added": aggregated.get("supermemory", {}).get("recent_memories", 0),
            "total_decisions": aggregated.get("routing", {}).get("decisions_this_week", 0)
        },
        "correlations_found": len(correlations),
        "suggestions_count": len(suggestions),
        "top_suggestion": suggestions[0] if suggestions else None
    }


def sync() -> Dict:
    """Main sync function - aggregate all learnings."""
    print("Syncing learning hub...")

    # Aggregate from all sources
    aggregated = {
        "cognitive_os": aggregate_cognitive_os(),
        "routing": aggregate_routing(),
        "patterns": aggregate_patterns(),
        "supermemory": get_supermemory_stats(),
        "identity": aggregate_identity(),
        "recovery": aggregate_recovery()
    }

    # Find correlations
    correlations = find_correlations(aggregated)

    # Generate suggestions
    suggestions = generate_suggestions(aggregated, correlations)

    # Generate weekly summary
    summary = generate_weekly_summary(aggregated, correlations, suggestions)

    # Update learning hub
    hub = load_json(LEARNING_HUB)
    hub["last_sync"] = datetime.now().isoformat()
    hub["aggregated_data"] = aggregated
    hub["cross_domain_insights"] = correlations
    hub["improvement_suggestions"] = suggestions

    # Keep last 4 weekly summaries
    weekly_summaries = hub.get("weekly_summaries", [])
    weekly_summaries.append(summary)
    hub["weekly_summaries"] = weekly_summaries[-4:]

    # Save
    LEARNING_HUB.write_text(json.dumps(hub, indent=2))

    return {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "aggregated": aggregated,
        "correlations": correlations,
        "suggestions": suggestions,
        "summary": summary
    }


def print_report(result: Dict):
    """Print formatted report."""
    print(f"\n{'='*60}")
    print("  Learning Hub Weekly Sync Report")
    print(f"{'='*60}")

    summary = result.get("summary", {})
    metrics = summary.get("key_metrics", {})

    print(f"\n  Key Metrics:")
    print(f"    Routing DQ Score:     {metrics.get('routing_dq', 0):.3f}")
    print(f"    Prediction Accuracy:  {metrics.get('prediction_accuracy', 0):.1%}")
    print(f"    Recovery Success:     {metrics.get('recovery_success', 0):.1%}")
    print(f"    Memories Added:       {metrics.get('memories_added', 0)}")
    print(f"    Total Decisions:      {metrics.get('total_decisions', 0)}")

    correlations = result.get("correlations", [])
    if correlations:
        print(f"\n  Cross-Domain Insights ({len(correlations)}):")
        for c in correlations[:3]:
            icon = "+" if c["type"] == "positive" else "-"
            print(f"    [{icon}] {c['insight']}")

    suggestions = result.get("suggestions", [])
    if suggestions:
        print(f"\n  Improvement Suggestions ({len(suggestions)}):")
        for s in suggestions[:3]:
            print(f"    [{s['priority'].upper()}] {s['suggestion']}")
            print(f"          Action: {s['action']}")

    print(f"\n{'='*60}\n")


# CLI Interface
if __name__ == "__main__":
    args = sys.argv[1:]

    if not args:
        print("Learning Hub Sync")
        print("")
        print("Commands:")
        print("  sync        - Run weekly sync and generate report")
        print("  status      - Show current hub status")
        print("  insights    - Show cross-domain insights")
        print("  suggestions - Show improvement suggestions")
        sys.exit(0)

    command = args[0]

    if command == 'sync':
        result = sync()
        print_report(result)

    elif command == 'status':
        hub = load_json(LEARNING_HUB)
        print(json.dumps({
            "last_sync": hub.get("last_sync"),
            "sources": list(hub.get("sources", {}).keys()),
            "insights_count": len(hub.get("cross_domain_insights", [])),
            "suggestions_count": len(hub.get("improvement_suggestions", []))
        }, indent=2))

    elif command == 'insights':
        hub = load_json(LEARNING_HUB)
        print(json.dumps(hub.get("cross_domain_insights", []), indent=2))

    elif command == 'suggestions':
        hub = load_json(LEARNING_HUB)
        print(json.dumps(hub.get("improvement_suggestions", []), indent=2))

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
