#!/usr/bin/env python3
"""
A/B Test Analyzer: Graph Signal vs Keyword Complexity (US-012)

Compares the multi-feature graph signal routing against keyword-based complexity
estimation using data logged during the A/B test period.

Metrics computed per group:
- DQ accuracy (average DQ score)
- Cost per query
- Behavioral outcome (when available)
- ECE (Expected Calibration Error)

Auto-rollback: if graph signal group DQ accuracy is > 5% worse than keyword group,
auto-revert to keyword-only with alert.

Usage:
    ab-test-graph-signal.py                # Show current results
    ab-test-graph-signal.py --days 30      # Last 30 days
    ab-test-graph-signal.py --check        # Check rollback condition only
    ab-test-graph-signal.py --rollback     # Force rollback to keyword-only
    ab-test-graph-signal.py --resume       # Resume A/B test after rollback
"""

import json
import sys
import math
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict

BASE_DIR = Path(__file__).parent.parent
AB_TEST_LOG = BASE_DIR / "data" / "ab-test-graph-signal.jsonl"
AB_TEST_STATE = BASE_DIR / "data" / "ab-test-state.json"
BEHAVIORAL_OUTCOMES = BASE_DIR / "data" / "behavioral-outcomes.jsonl"

# Minimum decisions before analysis is meaningful
MIN_DECISIONS = 200

# ANSI colors
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GREEN = "\033[38;5;82m"
    RED = "\033[38;5;196m"
    YELLOW = "\033[38;5;220m"
    BLUE = "\033[38;5;75m"
    PURPLE = "\033[38;5;183m"
    CYAN = "\033[38;5;87m"


def load_ab_decisions(days=None):
    """Load A/B test decisions from JSONL log."""
    if not AB_TEST_LOG.exists():
        return []

    cutoff_ts = 0
    if days:
        cutoff_ts = int((datetime.now(tz=timezone.utc) - timedelta(days=days)).timestamp())

    decisions = []
    with open(AB_TEST_LOG) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                if record.get("ts", 0) >= cutoff_ts:
                    decisions.append(record)
            except json.JSONDecodeError:
                continue
    return decisions


def load_behavioral_outcomes():
    """Load behavioral outcome scores keyed by timestamp range."""
    if not BEHAVIORAL_OUTCOMES.exists():
        return {}

    outcomes = {}
    with open(BEHAVIORAL_OUTCOMES) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                # Key by session start timestamp (epoch seconds)
                ts = record.get("session_start_ts")
                if ts:
                    outcomes[ts] = record.get("composite_score", 0.5)
            except json.JSONDecodeError:
                continue
    return outcomes


def load_ab_state():
    """Load A/B test state."""
    if AB_TEST_STATE.exists():
        try:
            return json.loads(AB_TEST_STATE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"active": True, "rollback": False, "reason": None, "decisionCount": 0}


def save_ab_state(state):
    """Save A/B test state."""
    AB_TEST_STATE.parent.mkdir(parents=True, exist_ok=True)
    AB_TEST_STATE.write_text(json.dumps(state, indent=2))


def compute_ece(predictions, actuals, n_bins=10):
    """
    Compute Expected Calibration Error.

    Groups predictions into bins and compares average predicted confidence
    with average actual outcome in each bin.
    """
    if not predictions or not actuals or len(predictions) != len(actuals):
        return None

    bins = defaultdict(lambda: {"pred_sum": 0, "actual_sum": 0, "count": 0})
    for pred, actual in zip(predictions, actuals):
        bin_idx = min(int(pred * n_bins), n_bins - 1)
        bins[bin_idx]["pred_sum"] += pred
        bins[bin_idx]["actual_sum"] += actual
        bins[bin_idx]["count"] += 1

    total = len(predictions)
    ece = 0.0
    for b in bins.values():
        if b["count"] > 0:
            avg_pred = b["pred_sum"] / b["count"]
            avg_actual = b["actual_sum"] / b["count"]
            ece += (b["count"] / total) * abs(avg_pred - avg_actual)

    return round(ece, 6)


def analyze_group(decisions, group_name):
    """Compute metrics for one A/B test group."""
    if not decisions:
        return None

    # DQ scores
    dq_key = f"{group_name}_dq"
    model_key = f"{group_name}_model"
    complexity_key = f"{group_name}_complexity"

    dq_scores = [d[dq_key] for d in decisions if d.get(dq_key) is not None]
    models = [d.get(model_key) for d in decisions if d.get(model_key)]
    costs = [d.get("cost_estimate", 0) for d in decisions]

    if not dq_scores:
        return None

    # Model distribution
    model_dist = defaultdict(int)
    for m in models:
        if m:
            model_dist[m] += 1

    avg_dq = sum(dq_scores) / len(dq_scores)
    avg_cost = sum(costs) / len(costs) if costs else 0
    min_dq = min(dq_scores)
    max_dq = max(dq_scores)
    variance = sum((s - avg_dq) ** 2 for s in dq_scores) / len(dq_scores) if len(dq_scores) > 1 else 0

    return {
        "group": group_name,
        "count": len(decisions),
        "avg_dq": round(avg_dq, 4),
        "min_dq": round(min_dq, 4),
        "max_dq": round(max_dq, 4),
        "variance": round(variance, 6),
        "avg_cost": round(avg_cost, 8),
        "model_distribution": dict(model_dist),
        "dq_scores": dq_scores,
    }


def analyze(decisions, behavioral_outcomes=None):
    """Run full A/B test analysis."""
    keyword_group = [d for d in decisions if d.get("ab_group") == "keyword"]
    graph_group = [d for d in decisions if d.get("ab_group") == "graph"]

    keyword_stats = analyze_group(keyword_group, "keyword")
    graph_stats = analyze_group(graph_group, "graph")

    # Compute ECE if behavioral outcomes available
    keyword_ece = None
    graph_ece = None
    if behavioral_outcomes and keyword_stats and graph_stats:
        kw_preds, kw_actuals = [], []
        gr_preds, gr_actuals = [], []
        for d in decisions:
            ts = d.get("ts", 0)
            # Find closest behavioral outcome within 1 hour
            outcome = None
            for ots, oscore in behavioral_outcomes.items():
                if abs(ots - ts) < 3600:
                    outcome = oscore
                    break
            if outcome is not None:
                if d.get("ab_group") == "keyword" and d.get("keyword_dq") is not None:
                    kw_preds.append(d["keyword_dq"])
                    kw_actuals.append(outcome)
                elif d.get("ab_group") == "graph" and d.get("graph_dq") is not None:
                    gr_preds.append(d["graph_dq"])
                    gr_actuals.append(outcome)

        if len(kw_preds) >= 10:
            keyword_ece = compute_ece(kw_preds, kw_actuals)
        if len(gr_preds) >= 10:
            graph_ece = compute_ece(gr_preds, gr_actuals)

    return {
        "total_decisions": len(decisions),
        "min_decisions_required": MIN_DECISIONS,
        "sufficient_data": len(decisions) >= MIN_DECISIONS,
        "keyword": keyword_stats,
        "graph": graph_stats,
        "keyword_ece": keyword_ece,
        "graph_ece": graph_ece,
    }


def check_rollback(results):
    """
    Check if auto-rollback should trigger.
    Condition: graph signal group DQ accuracy is > 5% worse than keyword group.
    Only triggers after MIN_DECISIONS decisions.
    """
    if not results["sufficient_data"]:
        return False, None

    kw = results.get("keyword")
    gr = results.get("graph")

    if not kw or not gr:
        return False, None

    kw_dq = kw["avg_dq"]
    gr_dq = gr["avg_dq"]

    # Rollback if graph DQ is > 5% worse (absolute) than keyword DQ
    diff = kw_dq - gr_dq
    threshold = 0.05

    if diff > threshold:
        reason = (
            f"Graph signal DQ ({gr_dq:.4f}) is {diff:.4f} worse than "
            f"keyword DQ ({kw_dq:.4f}), exceeding {threshold} threshold"
        )
        return True, reason

    return False, None


def print_report(results):
    """Print formatted A/B test report."""
    print(f"\n{C.BOLD}{'='*60}{C.RESET}")
    print(f"{C.BOLD}  A/B Test: Graph Signal vs Keyword Complexity{C.RESET}")
    print(f"{C.BOLD}{'='*60}{C.RESET}\n")

    total = results["total_decisions"]
    required = results["min_decisions_required"]
    sufficient = results["sufficient_data"]

    status_color = C.GREEN if sufficient else C.YELLOW
    print(f"  Total decisions: {C.BOLD}{total}{C.RESET}")
    print(f"  Required:        {required}")
    print(f"  Status:          {status_color}{'Ready for analysis' if sufficient else f'Need {required - total} more'}{C.RESET}\n")

    state = load_ab_state()
    if state.get("rollback"):
        print(f"  {C.RED}{C.BOLD}ROLLBACK ACTIVE{C.RESET}: {state.get('reason', 'manual')}\n")

    for group_name in ["keyword", "graph"]:
        stats = results.get(group_name)
        if not stats:
            print(f"  {C.DIM}{group_name.title()} group: no data{C.RESET}")
            continue

        color = C.BLUE if group_name == "keyword" else C.PURPLE
        print(f"  {color}{C.BOLD}{group_name.title()} Group{C.RESET} (n={stats['count']})")
        print(f"    Avg DQ:      {stats['avg_dq']:.4f}")
        print(f"    DQ Range:    [{stats['min_dq']:.4f}, {stats['max_dq']:.4f}]")
        print(f"    Variance:    {stats['variance']:.6f}")
        print(f"    Avg Cost:    ${stats['avg_cost']:.6f}")

        dist = stats.get("model_distribution", {})
        if dist:
            dist_str = ", ".join(f"{m}: {c}" for m, c in sorted(dist.items()))
            print(f"    Models:      {dist_str}")
        print()

    # ECE comparison
    kw_ece = results.get("keyword_ece")
    gr_ece = results.get("graph_ece")
    if kw_ece is not None or gr_ece is not None:
        print(f"  {C.CYAN}Calibration (ECE){C.RESET}")
        if kw_ece is not None:
            print(f"    Keyword ECE: {kw_ece:.4f}")
        if gr_ece is not None:
            print(f"    Graph ECE:   {gr_ece:.4f}")
        print()

    # Comparison
    kw = results.get("keyword")
    gr = results.get("graph")
    if kw and gr:
        diff = gr["avg_dq"] - kw["avg_dq"]
        pct = (diff / kw["avg_dq"] * 100) if kw["avg_dq"] > 0 else 0
        diff_color = C.GREEN if diff >= 0 else C.RED
        print(f"  {C.BOLD}Comparison{C.RESET}")
        print(f"    DQ Difference:  {diff_color}{diff:+.4f} ({pct:+.1f}%){C.RESET}")

        cost_diff = gr["avg_cost"] - kw["avg_cost"]
        cost_color = C.GREEN if cost_diff <= 0 else C.RED
        print(f"    Cost Difference: {cost_color}{cost_diff:+.8f}{C.RESET}")

        # Rollback check
        should_rollback, reason = check_rollback(results)
        if should_rollback:
            print(f"\n  {C.RED}{C.BOLD}WARNING: Rollback condition met!{C.RESET}")
            print(f"  {C.RED}{reason}{C.RESET}")
        elif sufficient:
            print(f"\n  {C.GREEN}No rollback needed — graph signal performing within tolerance.{C.RESET}")

    print(f"\n{C.DIM}{'='*60}{C.RESET}\n")


def main():
    args = sys.argv[1:]
    days = None
    check_only = False
    force_rollback = False
    resume = False

    i = 0
    while i < len(args):
        if args[i] == "--days" and i + 1 < len(args):
            days = int(args[i + 1])
            i += 2
        elif args[i] == "--check":
            check_only = True
            i += 1
        elif args[i] == "--rollback":
            force_rollback = True
            i += 1
        elif args[i] == "--resume":
            resume = True
            i += 1
        elif args[i] == "--json":
            i += 1
        else:
            i += 1

    # Handle resume
    if resume:
        state = load_ab_state()
        state["active"] = True
        state["rollback"] = False
        state["reason"] = None
        save_ab_state(state)
        print(f"{C.GREEN}A/B test resumed.{C.RESET}")
        return

    # Handle force rollback
    if force_rollback:
        state = load_ab_state()
        state["rollback"] = True
        state["reason"] = "Manual rollback"
        save_ab_state(state)
        print(f"{C.YELLOW}A/B test rolled back to keyword-only.{C.RESET}")
        return

    # Load data
    decisions = load_ab_decisions(days)
    behavioral_outcomes = load_behavioral_outcomes()
    results = analyze(decisions, behavioral_outcomes)

    if check_only:
        should_rollback, reason = check_rollback(results)
        if should_rollback:
            # Auto-rollback
            state = load_ab_state()
            state["rollback"] = True
            state["reason"] = reason
            save_ab_state(state)
            print(f"ROLLBACK: {reason}")
            sys.exit(1)
        else:
            total = results["total_decisions"]
            if not results["sufficient_data"]:
                print(f"PENDING: {total}/{MIN_DECISIONS} decisions collected")
            else:
                print("OK: Graph signal within tolerance")
            sys.exit(0)

    # Check for JSON output
    if "--json" in sys.argv:
        # Strip non-serializable fields
        output = {k: v for k, v in results.items()}
        for g in ["keyword", "graph"]:
            if output.get(g):
                output[g] = {k: v for k, v in output[g].items() if k != "dq_scores"}
        print(json.dumps(output, indent=2))
        return

    # Print report
    print_report(results)

    # Check rollback condition
    should_rollback, reason = check_rollback(results)
    if should_rollback:
        state = load_ab_state()
        if not state.get("rollback"):
            state["rollback"] = True
            state["reason"] = reason
            save_ab_state(state)
            print(f"{C.RED}{C.BOLD}AUTO-ROLLBACK TRIGGERED: Reverting to keyword-only.{C.RESET}")


if __name__ == "__main__":
    main()
