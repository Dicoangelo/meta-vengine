#!/usr/bin/env python3
"""
Predictive Error Prevention - Fix errors BEFORE they occur.

Analyzes recovery-outcomes.jsonl to identify recurring patterns
and takes preemptive action at session start.

Example: If 2+ git lock errors in last day → preemptively clear locks
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

# Paths
DATA_DIR = Path.home() / ".claude" / "data"
KERNEL_DIR = Path.home() / ".claude" / "kernel"
RECOVERY_OUTCOMES = DATA_DIR / "recovery-outcomes.jsonl"
PREDICTION_LOG = DATA_DIR / "predictive-recovery.jsonl"
PREDICTION_STATE = KERNEL_DIR / "predictive-state.json"

# Pattern thresholds (occurrences in time window to trigger prevention)
THRESHOLDS = {
    "git_lock": {"count": 2, "hours": 24, "action": "clear_git_locks"},
    "permission": {"count": 3, "hours": 48, "action": "fix_permissions"},
    "stale_cache": {"count": 2, "hours": 24, "action": "clear_cache"},
    "concurrent_session": {"count": 2, "hours": 12, "action": "warn_concurrency"},
    "quota": {"count": 3, "hours": 48, "action": "warn_quota"}
}

# Preemptive action definitions
PREEMPTIVE_ACTIONS = {
    "clear_git_locks": {
        "description": "Clear stale git locks before they cause issues",
        "command": "find ~ -name '*.lock' -path '*/.git/*' -mmin +5 -delete 2>/dev/null || true",
        "auto": True
    },
    "fix_permissions": {
        "description": "Fix common permission issues",
        "command": "chmod -R u+rw ~/.claude 2>/dev/null || true",
        "auto": True
    },
    "clear_cache": {
        "description": "Clear potentially stale caches",
        "command": "rm -f ~/.claude/stats-cache.json 2>/dev/null || true",
        "auto": True
    },
    "warn_concurrency": {
        "description": "Warn about concurrent session issues",
        "command": None,  # Warning only
        "auto": False,
        "message": "Concurrent session issues detected recently. Ensure only one session is active."
    },
    "warn_quota": {
        "description": "Warn about quota issues",
        "command": None,
        "auto": False,
        "message": "Quota limits hit recently. Consider cost-efficient model selection."
    }
}


def load_recovery_outcomes(hours: int = 48) -> List[Dict]:
    """Load recent recovery outcomes."""
    outcomes = []
    if not RECOVERY_OUTCOMES.exists():
        return outcomes

    cutoff = datetime.now() - timedelta(hours=hours)
    cutoff_ts = cutoff.timestamp()

    for line in RECOVERY_OUTCOMES.read_text().strip().split('\n'):
        if line:
            try:
                o = json.loads(line)
                ts = o.get('ts', 0)
                if ts > cutoff_ts:
                    outcomes.append(o)
            except:
                pass

    return outcomes


def analyze_patterns(outcomes: List[Dict]) -> List[Dict]:
    """Analyze outcomes to find recurring patterns that warrant prevention."""
    predictions = []
    now = datetime.now()

    # Group by category + action
    patterns = {}
    for o in outcomes:
        cat = o.get('category', 'unknown')
        action = o.get('action', 'unknown')
        success = o.get('success', True)

        # Only count failures as patterns to prevent
        if not success:
            key = f"{cat}_{action}"
            if key not in patterns:
                patterns[key] = {"count": 0, "timestamps": [], "category": cat, "action": action}
            patterns[key]["count"] += 1
            patterns[key]["timestamps"].append(o.get('ts', 0))

    # Check against thresholds
    for pattern_key, pattern_data in patterns.items():
        cat = pattern_data["category"]

        # Map category to threshold key
        threshold_key = None
        if cat == "git" and "lock" in pattern_key.lower():
            threshold_key = "git_lock"
        elif cat == "permissions":
            threshold_key = "permission"
        elif cat == "cache":
            threshold_key = "stale_cache"
        elif cat == "concurrency":
            threshold_key = "concurrent_session"
        elif cat == "quota":
            threshold_key = "quota"

        if threshold_key and threshold_key in THRESHOLDS:
            threshold = THRESHOLDS[threshold_key]
            if pattern_data["count"] >= threshold["count"]:
                # Check if within time window
                recent_ts = [t for t in pattern_data["timestamps"]
                           if t > (now - timedelta(hours=threshold["hours"])).timestamp()]

                if len(recent_ts) >= threshold["count"]:
                    action_def = PREEMPTIVE_ACTIONS.get(threshold["action"], {})
                    predictions.append({
                        "pattern": pattern_key,
                        "occurrences": len(recent_ts),
                        "threshold": threshold["count"],
                        "action": threshold["action"],
                        "auto": action_def.get("auto", False),
                        "description": action_def.get("description", ""),
                        "probability": min(0.95, 0.5 + (len(recent_ts) - threshold["count"]) * 0.1)
                    })

    return predictions


def execute_prevention(predictions: List[Dict], dry_run: bool = False) -> List[Dict]:
    """Execute preemptive actions for high-probability predictions."""
    results = []

    for pred in predictions:
        action_name = pred["action"]
        action_def = PREEMPTIVE_ACTIONS.get(action_name, {})

        result = {
            "timestamp": datetime.now().isoformat(),
            "pattern": pred["pattern"],
            "action": action_name,
            "probability": pred["probability"],
            "auto": pred["auto"],
            "dry_run": dry_run
        }

        if pred["auto"] and action_def.get("command"):
            if dry_run:
                result["status"] = "would_execute"
                result["command"] = action_def["command"]
            else:
                try:
                    subprocess.run(
                        action_def["command"],
                        shell=True,
                        capture_output=True,
                        timeout=10
                    )
                    result["status"] = "executed"
                except Exception as e:
                    result["status"] = "failed"
                    result["error"] = str(e)
        elif action_def.get("message"):
            result["status"] = "warning"
            result["message"] = action_def["message"]
        else:
            result["status"] = "skipped"

        results.append(result)

        # Log the action
        log_prediction(result)

    return results


def log_prediction(result: Dict):
    """Log prediction and action to file."""
    PREDICTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(PREDICTION_LOG, 'a') as f:
        f.write(json.dumps(result) + '\n')


def save_state(predictions: List[Dict]):
    """Save current prediction state."""
    state = {
        "timestamp": datetime.now().isoformat(),
        "predictions": predictions,
        "prevented_count": len([p for p in predictions if p.get("auto")])
    }
    PREDICTION_STATE.write_text(json.dumps(state, indent=2))


def run_predictions(dry_run: bool = False) -> Dict:
    """Main prediction flow - analyze and optionally prevent."""
    # Load recent recovery outcomes
    outcomes = load_recovery_outcomes(hours=48)

    # Analyze for patterns
    predictions = analyze_patterns(outcomes)

    # Execute prevention (or dry run)
    results = []
    if predictions:
        results = execute_prevention(predictions, dry_run=dry_run)

    # Save state
    save_state(predictions)

    summary = {
        "timestamp": datetime.now().isoformat(),
        "outcomes_analyzed": len(outcomes),
        "patterns_detected": len(predictions),
        "actions_taken": len([r for r in results if r["status"] == "executed"]),
        "warnings_issued": len([r for r in results if r["status"] == "warning"]),
        "predictions": predictions,
        "results": results
    }

    return summary


def get_stats(days: int = 7) -> Dict:
    """Get predictive recovery statistics."""
    if not PREDICTION_LOG.exists():
        return {"total": 0}

    cutoff = datetime.now() - timedelta(days=days)

    predictions = []
    for line in PREDICTION_LOG.read_text().strip().split('\n'):
        if line:
            try:
                p = json.loads(line)
                if datetime.fromisoformat(p['timestamp']) > cutoff:
                    predictions.append(p)
            except:
                pass

    if not predictions:
        return {"total": 0, "errors_prevented": 0}

    statuses = {"executed": 0, "warning": 0, "skipped": 0, "failed": 0}
    patterns = {}

    for p in predictions:
        s = p.get("status", "unknown")
        if s in statuses:
            statuses[s] += 1

        pattern = p.get("pattern", "unknown")
        patterns[pattern] = patterns.get(pattern, 0) + 1

    return {
        "total": len(predictions),
        "errors_prevented": statuses["executed"],
        "warnings_issued": statuses["warning"],
        "status_breakdown": statuses,
        "top_patterns": sorted(patterns.items(), key=lambda x: x[1], reverse=True)[:5],
        "prevention_rate": round(statuses["executed"] / len(predictions), 2) if predictions else 0
    }


def print_summary(summary: Dict):
    """Print formatted summary."""
    print(f"\n{'='*50}")
    print("  Predictive Error Prevention")
    print(f"{'='*50}")
    print(f"  Outcomes analyzed: {summary['outcomes_analyzed']}")
    print(f"  Patterns detected: {summary['patterns_detected']}")
    print(f"  Actions taken: {summary['actions_taken']}")
    print(f"  Warnings issued: {summary['warnings_issued']}")

    if summary['predictions']:
        print(f"\n  Predictions:")
        for p in summary['predictions']:
            status = "AUTO" if p['auto'] else "WARN"
            print(f"    [{status}] {p['pattern']}: {p['description']} (prob: {p['probability']:.0%})")

    for r in summary.get('results', []):
        if r['status'] == 'warning' and 'message' in r:
            print(f"\n  Warning: {r['message']}")

    print(f"{'='*50}\n")


# CLI Interface
if __name__ == "__main__":
    args = sys.argv[1:]

    if not args:
        print("Predictive Error Prevention")
        print("")
        print("Commands:")
        print("  run [--dry-run]    - Analyze patterns and prevent errors")
        print("  predict            - Show predictions without acting")
        print("  stats [days]       - Get prevention statistics")
        print("  state              - Show current prediction state")
        sys.exit(0)

    command = args[0]

    if command == 'run':
        dry_run = '--dry-run' in args
        summary = run_predictions(dry_run=dry_run)
        print_summary(summary)

    elif command == 'predict':
        outcomes = load_recovery_outcomes()
        predictions = analyze_patterns(outcomes)
        print(json.dumps({
            "outcomes_analyzed": len(outcomes),
            "predictions": predictions
        }, indent=2))

    elif command == 'stats':
        days = int(args[1]) if len(args) > 1 else 7
        print(json.dumps(get_stats(days), indent=2))

    elif command == 'state':
        if PREDICTION_STATE.exists():
            print(PREDICTION_STATE.read_text())
        else:
            print("{}")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
