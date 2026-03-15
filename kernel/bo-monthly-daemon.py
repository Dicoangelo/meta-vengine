#!/usr/bin/env python3
"""
US-110: Monthly BO Trigger + A/B Infrastructure

Monthly daemon that triggers Bayesian Optimization, manages A/B splits,
and auto-analyzes results after sufficient decisions.

A/B split: 70% current weights, 10% each for 3 candidates (by session ID hash).
After 150 decisions (~3 days), auto-analyze and promote winner or retain baseline.

Usage:
    bo-monthly-daemon.py                # Run BO and create A/B test
    bo-monthly-daemon.py --analyze      # Analyze results and promote/retain
    bo-monthly-daemon.py --status       # Show current A/B test state
    bo-monthly-daemon.py --approve      # Manually approve winning candidate
    bo-monthly-daemon.py --reject       # Manually reject all candidates
    bo-monthly-daemon.py --install      # Install LaunchAgent for monthly trigger
"""

import importlib
import json
import hashlib
import sys
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

BASE_DIR = Path(__file__).parent.parent
AB_TEST_FILE = BASE_DIR / "data" / "bo-ab-test.json"
BANDIT_HISTORY = BASE_DIR / "data" / "bandit-history.jsonl"
BO_REPORTS_DIR = BASE_DIR / "data" / "bo-reports"
LEARNABLE_PARAMS = BASE_DIR / "config" / "learnable-params.json"
LAUNCH_AGENT_DIR = Path.home() / "Library" / "LaunchAgents"
LAUNCH_AGENT_PLIST = LAUNCH_AGENT_DIR / "com.metavengine.bo-monthly.plist"

MIN_DECISIONS = 150
PROMOTION_THRESHOLD = 0.03  # 3% improvement required


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


def load_ab_test() -> dict | None:
    """Load current A/B test configuration."""
    if not AB_TEST_FILE.exists():
        return None
    try:
        return json.loads(AB_TEST_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def save_ab_test(config: dict) -> None:
    """Save A/B test configuration."""
    AB_TEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    AB_TEST_FILE.write_text(json.dumps(config, indent=2))


def get_ab_assignment(session_id: str, ab_config: dict | None = None) -> dict:
    """
    Determine which weight config to use for a given session.

    Uses deterministic hash of session_id for consistent assignment:
    - 0-69:  baseline (70% traffic)
    - 70-79: candidate_0 (10% traffic)
    - 80-89: candidate_1 (10% traffic)
    - 90-99: candidate_2 (10% traffic)

    Returns dict with 'variant' name and 'weights' config.
    """
    if ab_config is None:
        ab_config = load_ab_test()

    if not ab_config or ab_config.get("status") != "running":
        # No active test — use baseline
        return {"variant": "baseline", "weights": ab_config.get("baseline", {}) if ab_config else {}}

    # Deterministic bucket from session ID hash
    hash_val = int(hashlib.sha256(session_id.encode()).hexdigest(), 16)
    bucket = hash_val % 100

    candidates = ab_config.get("candidates", [])

    if bucket < 70:
        return {"variant": "baseline", "weights": ab_config.get("baseline", {})}
    elif bucket < 80 and len(candidates) > 0:
        return {"variant": "candidate_0", "weights": candidates[0]}
    elif bucket < 90 and len(candidates) > 1:
        return {"variant": "candidate_1", "weights": candidates[1]}
    elif len(candidates) > 2:
        return {"variant": "candidate_2", "weights": candidates[2]}
    else:
        # Not enough candidates for this bucket — fall back to baseline
        return {"variant": "baseline", "weights": ab_config.get("baseline", {})}


def get_current_weights() -> dict[str, float]:
    """Extract current weight values from learnable-params.json."""
    data = json.loads(LEARNABLE_PARAMS.read_text())
    return {p["id"]: p["value"] for p in data["parameters"]}


def load_bandit_history(since_ts: float = 0) -> list[dict]:
    """Load bandit decision history from JSONL, optionally since a timestamp."""
    if not BANDIT_HISTORY.exists():
        return []

    decisions = []
    with open(BANDIT_HISTORY) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                if record.get("ts", 0) >= since_ts:
                    decisions.append(record)
            except json.JSONDecodeError:
                continue
    return decisions


def _load_bo_module():
    """Import BayesianWeightOptimizer module (handles hyphenated filename)."""
    import importlib as _importlib
    import importlib.util as _importlib_util
    try:
        return _importlib.import_module("kernel.bayesian-optimizer")
    except (ModuleNotFoundError, ImportError):
        bo_path = BASE_DIR / "kernel" / "bayesian-optimizer.py"
        if not bo_path.exists():
            return None
        spec = _importlib_util.spec_from_file_location("bayesian_optimizer", bo_path)
        mod = _importlib_util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod


def run_bo() -> None:
    """Run Bayesian Optimization and create A/B test with candidates."""
    bo_module = _load_bo_module()
    if bo_module is None:
        print(f"{C.RED}Error: kernel/bayesian-optimizer.py not found.{C.RESET}")
        print(f"{C.DIM}US-109 (Bayesian Optimization) must be implemented first.{C.RESET}")
        sys.exit(1)

    optimizer = bo_module.BayesianWeightOptimizer()

    # Get current baseline
    baseline = get_current_weights()

    # Propose 3 candidates via BO
    candidates = optimizer.propose(n_candidates=3)
    if not candidates or len(candidates) == 0:
        print(f"{C.YELLOW}No candidates proposed by BO. Skipping A/B test.{C.RESET}")
        return

    # Create A/B test config
    now = datetime.now(tz=timezone.utc)
    ab_config = {
        "baseline": baseline,
        "candidates": candidates,
        "start_ts": now.isoformat(),
        "start_epoch": now.timestamp(),
        "decision_count": 0,
        "status": "running",
        "month": now.strftime("%Y-%m"),
        "created_by": "bo-monthly-daemon",
    }

    save_ab_test(ab_config)
    print(f"{C.GREEN}{C.BOLD}A/B test created for {now.strftime('%Y-%m')}{C.RESET}")
    print(f"  Baseline: current weights (70% traffic)")
    print(f"  Candidates: {len(candidates)} proposed configs (10% each)")
    print(f"  Min decisions for analysis: {MIN_DECISIONS}")


def analyze() -> None:
    """Analyze A/B test results and promote winner or retain baseline."""
    ab_config = load_ab_test()
    if not ab_config:
        print(f"{C.YELLOW}No active A/B test found.{C.RESET}")
        return

    if ab_config.get("status") != "running":
        print(f"{C.DIM}A/B test status: {ab_config.get('status')} — not running.{C.RESET}")
        return

    # Load decisions since test start
    start_ts = ab_config.get("start_epoch", 0)
    decisions = load_bandit_history(since_ts=start_ts)

    if len(decisions) < MIN_DECISIONS:
        print(f"{C.YELLOW}Insufficient decisions: {len(decisions)}/{MIN_DECISIONS}{C.RESET}")
        print(f"{C.DIM}Need {MIN_DECISIONS - len(decisions)} more decisions before analysis.{C.RESET}")
        return

    # Group decisions by variant and compute avg reward
    variant_rewards: dict[str, list[float]] = {}
    for d in decisions:
        variant = d.get("variant", "baseline")
        reward = d.get("reward")
        if reward is not None:
            variant_rewards.setdefault(variant, []).append(reward)

    # Compute averages
    variant_avg: dict[str, float] = {}
    for variant, rewards in variant_rewards.items():
        if rewards:
            variant_avg[variant] = sum(rewards) / len(rewards)

    baseline_avg = variant_avg.get("baseline", 0)
    print(f"\n{C.BOLD}A/B Test Analysis — {ab_config.get('month', 'unknown')}{C.RESET}")
    print(f"  Total decisions: {len(decisions)}")
    print(f"  Baseline avg reward: {baseline_avg:.4f} (n={len(variant_rewards.get('baseline', []))})")

    # Find best candidate
    best_candidate = None
    best_improvement = 0.0

    for i in range(3):
        variant_name = f"candidate_{i}"
        avg = variant_avg.get(variant_name)
        n = len(variant_rewards.get(variant_name, []))
        if avg is not None:
            improvement = (avg - baseline_avg) / baseline_avg if baseline_avg > 0 else 0
            print(f"  {variant_name} avg reward: {avg:.4f} (n={n}, {improvement:+.1%} vs baseline)")
            if improvement > best_improvement:
                best_improvement = improvement
                best_candidate = variant_name

    # Promotion decision
    promoted = False
    winner = None
    if best_candidate and best_improvement >= PROMOTION_THRESHOLD:
        candidate_idx = int(best_candidate.split("_")[1])
        winner = ab_config["candidates"][candidate_idx]
        print(f"\n  {C.GREEN}{C.BOLD}PROMOTING {best_candidate}{C.RESET}: "
              f"{best_improvement:+.1%} improvement exceeds {PROMOTION_THRESHOLD:.0%} threshold")
        promoted = True
    else:
        print(f"\n  {C.BLUE}RETAINING baseline{C.RESET}: "
              f"no candidate exceeded {PROMOTION_THRESHOLD:.0%} improvement threshold")

    # Write report
    BO_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    month = ab_config.get("month", datetime.now(tz=timezone.utc).strftime("%Y-%m"))
    report = {
        "month": month,
        "analyzed_at": datetime.now(tz=timezone.utc).isoformat(),
        "total_decisions": len(decisions),
        "variant_stats": {
            variant: {
                "avg_reward": variant_avg.get(variant, 0),
                "n_decisions": len(variant_rewards.get(variant, [])),
            }
            for variant in ["baseline", "candidate_0", "candidate_1", "candidate_2"]
        },
        "baseline_avg": baseline_avg,
        "best_candidate": best_candidate,
        "best_improvement": round(best_improvement, 6),
        "promoted": promoted,
        "winner_weights": winner,
        "promotion_threshold": PROMOTION_THRESHOLD,
    }
    report_path = BO_REPORTS_DIR / f"{month}.json"
    report_path.write_text(json.dumps(report, indent=2))
    print(f"\n  Report written: {report_path}")

    # Update A/B test status
    ab_config["status"] = "promoted" if promoted else "retained"
    ab_config["decision_count"] = len(decisions)
    ab_config["result"] = {
        "promoted": promoted,
        "winner": best_candidate if promoted else None,
        "improvement": round(best_improvement, 6),
    }
    save_ab_test(ab_config)

    # If promoted, apply the winning weights to learnable-params.json
    if promoted and winner:
        _apply_winner(winner)


def _apply_winner(winner_weights: dict) -> None:
    """Apply winning candidate weights to learnable-params.json."""
    data = json.loads(LEARNABLE_PARAMS.read_text())
    for param in data["parameters"]:
        if param["id"] in winner_weights:
            param["value"] = winner_weights[param["id"]]
    data["updated"] = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    data["updatedBy"] = "bo-monthly-daemon (A/B winner)"
    LEARNABLE_PARAMS.write_text(json.dumps(data, indent=2))
    print(f"  {C.GREEN}Weights updated in {LEARNABLE_PARAMS.name}{C.RESET}")


def approve() -> None:
    """Manually approve the winning candidate from the current A/B test."""
    ab_config = load_ab_test()
    if not ab_config:
        print(f"{C.YELLOW}No A/B test found.{C.RESET}")
        return

    result = ab_config.get("result", {})
    winner_name = result.get("winner")
    if not winner_name:
        print(f"{C.YELLOW}No winning candidate to approve.{C.RESET}")
        return

    idx = int(winner_name.split("_")[1])
    winner = ab_config["candidates"][idx]
    _apply_winner(winner)
    ab_config["status"] = "approved"
    save_ab_test(ab_config)
    print(f"{C.GREEN}{C.BOLD}Approved and applied {winner_name}.{C.RESET}")


def reject() -> None:
    """Manually reject all candidates, retain baseline."""
    ab_config = load_ab_test()
    if not ab_config:
        print(f"{C.YELLOW}No A/B test found.{C.RESET}")
        return

    ab_config["status"] = "rejected"
    ab_config["result"] = {"promoted": False, "winner": None, "reason": "manual rejection"}
    save_ab_test(ab_config)
    print(f"{C.YELLOW}All candidates rejected. Baseline retained.{C.RESET}")


def status() -> None:
    """Show current A/B test state."""
    ab_config = load_ab_test()
    if not ab_config:
        print(f"{C.DIM}No A/B test configured.{C.RESET}")
        return

    print(f"\n{C.BOLD}BO A/B Test Status{C.RESET}")
    print(f"  Month:       {ab_config.get('month', 'unknown')}")
    print(f"  Status:      {ab_config.get('status', 'unknown')}")
    print(f"  Started:     {ab_config.get('start_ts', 'unknown')}")
    print(f"  Decisions:   {ab_config.get('decision_count', 0)}/{MIN_DECISIONS}")
    n_candidates = len(ab_config.get("candidates", []))
    print(f"  Candidates:  {n_candidates}")
    print(f"  Split:       70% baseline / {n_candidates}x10% candidates")

    result = ab_config.get("result")
    if result:
        print(f"\n  {C.BOLD}Result:{C.RESET}")
        if result.get("promoted"):
            print(f"    Winner: {C.GREEN}{result.get('winner')}{C.RESET}")
            print(f"    Improvement: {result.get('improvement', 0):+.1%}")
        else:
            print(f"    {C.BLUE}Baseline retained{C.RESET}")
            if result.get("reason"):
                print(f"    Reason: {result['reason']}")
    print()


def install_launch_agent() -> None:
    """Install a macOS LaunchAgent to run BO on the 1st of each month."""
    daemon_path = Path(__file__).resolve()
    python_path = sys.executable

    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.metavengine.bo-monthly</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_path}</string>
        <string>{daemon_path}</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Day</key>
        <integer>1</integer>
        <key>Hour</key>
        <integer>3</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>{BASE_DIR}/data/bo-monthly.log</string>
    <key>StandardErrorPath</key>
    <string>{BASE_DIR}/data/bo-monthly.err</string>
    <key>WorkingDirectory</key>
    <string>{BASE_DIR}</string>
</dict>
</plist>"""

    LAUNCH_AGENT_DIR.mkdir(parents=True, exist_ok=True)
    LAUNCH_AGENT_PLIST.write_text(plist_content)
    print(f"{C.GREEN}LaunchAgent installed: {LAUNCH_AGENT_PLIST}{C.RESET}")
    print(f"  Schedule: 1st of each month at 03:00")
    print(f"  Load with: launchctl load {LAUNCH_AGENT_PLIST}")


def main():
    args = sys.argv[1:]

    if "--analyze" in args:
        analyze()
    elif "--status" in args:
        status()
    elif "--approve" in args:
        approve()
    elif "--reject" in args:
        reject()
    elif "--install" in args:
        install_launch_agent()
    else:
        run_bo()


if __name__ == "__main__":
    main()
