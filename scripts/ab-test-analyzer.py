#!/usr/bin/env python3
"""
A/B Test Analyzer for HSRGS vs Keyword DQ Routing

Analyzes routing decisions from the coevo data pipeline to compare:
- HSRGS (Homeomorphic Self-Routing Gödel System)
- Keyword DQ (original keyword-based Decision Quality scoring)

Usage:
    ab-test-analyzer.py              # Show current results
    ab-test-analyzer.py --days 7     # Last 7 days
    ab-test-analyzer.py --detailed   # Show per-query breakdown
    ab-test-analyzer.py --feedback   # Include feedback signals
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional

# Import timestamp normalization
sys.path.insert(0, str(Path.home() / ".claude/scripts"))
from lib.timestamps import normalize_ts

COEVO_DQ_FILE = Path.home() / ".claude" / "kernel" / "dq-scores.jsonl"
FEEDBACK_FILE = Path.home() / ".claude" / "data" / "ai-routing.log"

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


def load_routing_decisions(days: int = 30) -> List[Dict]:
    """Load routing decisions from coevo data pipeline"""
    if not COEVO_DQ_FILE.exists():
        return []

    cutoff = datetime.now() - timedelta(days=days)
    cutoff_ts = int(cutoff.timestamp())  # Use seconds

    decisions = []
    with open(COEVO_DQ_FILE) as f:
        for line in f:
            try:
                record = json.loads(line)
                # Normalize timestamp for comparison
                record_ts = normalize_ts(record.get("ts", 0)) or 0
                if record_ts >= cutoff_ts:
                    # Only include A/B test records
                    if record.get("ab_test_mode") or record.get("ab_variant"):
                        decisions.append(record)
            except json.JSONDecodeError:
                continue

    return decisions


def load_feedback() -> Dict[str, bool]:
    """Load feedback signals (ai-good/ai-bad) mapped by query hash"""
    feedback = {}
    if not FEEDBACK_FILE.exists():
        return feedback

    with open(FEEDBACK_FILE) as f:
        for line in f:
            try:
                record = json.loads(line)
                query_hash = record.get("query_hash")
                if query_hash:
                    # True = positive feedback, False = negative
                    feedback[query_hash] = record.get("feedback") == "good"
            except json.JSONDecodeError:
                continue

    return feedback


def analyze_ab_test(decisions: List[Dict], feedback: Dict[str, bool]) -> Dict:
    """Analyze A/B test results"""

    variants = defaultdict(lambda: {
        "count": 0,
        "models": defaultdict(int),
        "complexity_sum": 0,
        "feedback_positive": 0,
        "feedback_negative": 0,
        "feedback_total": 0,
        "queries": []
    })

    for d in decisions:
        variant = d.get("ab_variant", "unknown")
        v = variants[variant]

        v["count"] += 1
        v["models"][d.get("model", "unknown")] += 1
        v["complexity_sum"] += d.get("complexity", 0)

        query_hash = d.get("query_hash")
        if query_hash in feedback:
            v["feedback_total"] += 1
            if feedback[query_hash]:
                v["feedback_positive"] += 1
            else:
                v["feedback_negative"] += 1

        v["queries"].append({
            "query": d.get("query_preview", ""),
            "model": d.get("model"),
            "complexity": d.get("complexity"),
            "ts": d.get("ts")
        })

    # Calculate metrics
    results = {}
    for variant, data in variants.items():
        count = data["count"]
        if count == 0:
            continue

        results[variant] = {
            "total_queries": count,
            "avg_complexity": round(data["complexity_sum"] / count, 3),
            "model_distribution": dict(data["models"]),
            "feedback": {
                "total": data["feedback_total"],
                "positive": data["feedback_positive"],
                "negative": data["feedback_negative"],
                "rate": round(data["feedback_positive"] / data["feedback_total"], 3) if data["feedback_total"] > 0 else None
            },
            "queries": data["queries"]
        }

    return results


def print_results(results: Dict, detailed: bool = False):
    """Print A/B test results"""

    print(f"\n{C.BOLD}{'='*60}{C.RESET}")
    print(f"{C.BOLD}  A/B TEST: HSRGS vs Keyword DQ{C.RESET}")
    print(f"{C.BOLD}{'='*60}{C.RESET}\n")

    if not results:
        print(f"{C.YELLOW}No A/B test data found.{C.RESET}")
        print(f"{C.DIM}Run queries with ab_test_mode=true to collect data.{C.RESET}\n")
        return

    # Summary table
    print(f"{C.BOLD}Variant Summary:{C.RESET}\n")
    print(f"  {'Variant':<15} {'Queries':<10} {'Avg Complexity':<15} {'Feedback Rate':<15}")
    print(f"  {'-'*55}")

    for variant, data in sorted(results.items()):
        queries = data["total_queries"]
        avg_c = data["avg_complexity"]
        fb = data["feedback"]
        fb_rate = f"{fb['rate']:.1%}" if fb["rate"] is not None else "N/A"

        color = C.PURPLE if variant == "hsrgs" else C.BLUE
        print(f"  {color}{variant:<15}{C.RESET} {queries:<10} {avg_c:<15} {fb_rate:<15}")

    print()

    # Model distribution
    print(f"{C.BOLD}Model Distribution:{C.RESET}\n")
    for variant, data in sorted(results.items()):
        color = C.PURPLE if variant == "hsrgs" else C.BLUE
        print(f"  {color}{variant}:{C.RESET}")
        total = data["total_queries"]
        for model, count in sorted(data["model_distribution"].items(), key=lambda x: -x[1]):
            pct = count / total * 100
            bar = "█" * int(pct / 5)
            print(f"    {model:<12} {count:>4} ({pct:>5.1f}%) {C.DIM}{bar}{C.RESET}")
        print()

    # Statistical comparison
    if "hsrgs" in results and "keyword_dq" in results:
        print(f"{C.BOLD}Comparison:{C.RESET}\n")
        h = results["hsrgs"]
        k = results["keyword_dq"]

        # Complexity comparison
        c_diff = h["avg_complexity"] - k["avg_complexity"]
        c_color = C.GREEN if abs(c_diff) < 0.05 else C.YELLOW
        print(f"  Avg Complexity: HSRGS {h['avg_complexity']:.3f} vs Keyword {k['avg_complexity']:.3f} ({c_color}{c_diff:+.3f}{C.RESET})")

        # Feedback comparison
        if h["feedback"]["rate"] is not None and k["feedback"]["rate"] is not None:
            fb_diff = h["feedback"]["rate"] - k["feedback"]["rate"]
            fb_color = C.GREEN if fb_diff > 0 else C.RED if fb_diff < 0 else C.YELLOW
            print(f"  Feedback Rate:  HSRGS {h['feedback']['rate']:.1%} vs Keyword {k['feedback']['rate']:.1%} ({fb_color}{fb_diff:+.1%}{C.RESET})")

            # Winner
            if fb_diff > 0.05:
                print(f"\n  {C.GREEN}→ HSRGS is performing better{C.RESET}")
            elif fb_diff < -0.05:
                print(f"\n  {C.RED}→ Keyword DQ is performing better{C.RESET}")
            else:
                print(f"\n  {C.YELLOW}→ No significant difference yet{C.RESET}")
        else:
            print(f"\n  {C.DIM}Need more feedback data for comparison.{C.RESET}")
            print(f"  {C.DIM}Use 'ai-good' after successful queries, 'ai-bad' after failures.{C.RESET}")

        # Sample size warning
        min_queries = min(h["total_queries"], k["total_queries"])
        if min_queries < 30:
            print(f"\n  {C.YELLOW}⚠ Small sample size ({min_queries} queries). Need 30+ per variant for significance.{C.RESET}")

    print()

    # Detailed query breakdown
    if detailed:
        print(f"{C.BOLD}Recent Queries:{C.RESET}\n")
        for variant, data in sorted(results.items()):
            color = C.PURPLE if variant == "hsrgs" else C.BLUE
            print(f"  {color}{variant}:{C.RESET}")
            for q in data["queries"][-5:]:  # Last 5
                ts = datetime.fromtimestamp(q["ts"] / 1000).strftime("%H:%M")
                print(f"    [{ts}] {q['model']:<10} c={q['complexity']:.2f} {C.DIM}{q['query'][:40]}...{C.RESET}")
            print()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="A/B Test Analyzer for HSRGS vs Keyword DQ")
    parser.add_argument("--days", type=int, default=30, help="Days of data to analyze")
    parser.add_argument("--detailed", action="store_true", help="Show detailed query breakdown")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    decisions = load_routing_decisions(args.days)
    feedback = load_feedback()
    results = analyze_ab_test(decisions, feedback)

    if args.json:
        # Remove queries list for cleaner JSON output
        for v in results.values():
            del v["queries"]
        print(json.dumps(results, indent=2))
    else:
        print_results(results, args.detailed)


if __name__ == "__main__":
    main()
