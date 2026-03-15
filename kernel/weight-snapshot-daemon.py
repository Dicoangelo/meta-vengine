#!/usr/bin/env python3
"""
US-106: Weight Snapshot Daemon

Daily daemon that snapshots all 19 learnable params + bandit state + avg reward.
Computes epoch metrics: avg reward, variance, exploration rate, drift from baseline.
If improvement > 3%, marks as promoted (new baseline).
Prunes snapshots older than 90 days (keeps promoted forever).

Designed to be run via LaunchAgent on 24h interval, or manually.
"""

import argparse
import json
import math
import os
import plistlib
import statistics
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Resolve paths relative to repo root
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
SNAPSHOT_DIR = DATA_DIR / "weight-snapshots"
BANDIT_STATE_PATH = DATA_DIR / "bandit-state.json"
BANDIT_HISTORY_PATH = DATA_DIR / "bandit-history.jsonl"
PLIST_LABEL = "com.metaventions.weight-snapshot"
PROMOTION_THRESHOLD = 0.03  # 3% improvement triggers promotion
PRUNE_DAYS = 90


def load_registry():
    """Load param registry, importing from sibling module."""
    sys.path.insert(0, str(REPO_ROOT / "kernel"))
    from param_registry import ParamRegistry
    return ParamRegistry()


def load_bandit_state() -> dict | None:
    """Load bandit state if it exists."""
    if not BANDIT_STATE_PATH.exists():
        return None
    try:
        return json.loads(BANDIT_STATE_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def load_bandit_history() -> list[dict]:
    """Load bandit history entries from JSONL."""
    if not BANDIT_HISTORY_PATH.exists():
        return []
    entries = []
    try:
        for line in BANDIT_HISTORY_PATH.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return entries


def compute_epoch_metrics(history: list[dict], params: list[dict]) -> dict:
    """Compute epoch-level metrics from bandit history."""
    rewards = [e.get("reward", 0.0) for e in history if "reward" in e]

    avg_reward = statistics.mean(rewards) if rewards else 0.0
    reward_variance = statistics.variance(rewards) if len(rewards) >= 2 else 0.0

    # Exploration rate: fraction of history entries flagged as exploration
    explore_count = sum(1 for e in history if e.get("explored", False))
    exploration_rate = explore_count / len(history) if history else 0.0

    # Drift from baseline: RMS of (current - baseline) / range for each param
    drift_terms = []
    for p in params:
        baseline = p.get("value", 0.0)
        current = p.get("value", 0.0)  # current IS the registry value
        param_range = p["max"] - p["min"]
        if param_range > 0:
            drift_terms.append(((current - baseline) / param_range) ** 2)
    drift_from_baseline = math.sqrt(statistics.mean(drift_terms)) if drift_terms else 0.0

    return {
        "avg_reward": round(avg_reward, 6),
        "reward_variance": round(reward_variance, 6),
        "exploration_rate": round(exploration_rate, 4),
        "drift_from_baseline": round(drift_from_baseline, 6),
        "history_entries": len(history),
        "reward_samples": len(rewards),
    }


def get_previous_snapshot() -> dict | None:
    """Get the most recent existing snapshot."""
    if not SNAPSHOT_DIR.exists():
        return None
    snapshots = sorted(SNAPSHOT_DIR.glob("*.json"), reverse=True)
    for snap_path in snapshots:
        try:
            return json.loads(snap_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
    return None


def check_promotion(current_metrics: dict, previous: dict | None) -> bool:
    """Check if current epoch shows > 3% improvement over previous."""
    if previous is None:
        return False
    prev_reward = previous.get("epoch_metrics", {}).get("avg_reward", 0.0)
    curr_reward = current_metrics.get("avg_reward", 0.0)

    if prev_reward <= 0:
        # Can't compute relative improvement from zero/negative baseline
        return curr_reward > PROMOTION_THRESHOLD

    improvement = (curr_reward - prev_reward) / abs(prev_reward)
    return improvement >= PROMOTION_THRESHOLD


def create_snapshot(registry, bandit_state: dict | None,
                    history: list[dict], today: str | None = None) -> dict:
    """Create a weight snapshot dict."""
    today = today or datetime.now().strftime("%Y-%m-%d")
    params = registry.get_all_params()

    # Build param values map
    param_values = {}
    for p in params:
        param_values[p["id"]] = {
            "value": p["value"],
            "min": p["min"],
            "max": p["max"],
            "group": p["group"],
        }

    # Extract bandit beliefs (alpha/beta per param) if available
    bandit_beliefs = {}
    if bandit_state and isinstance(bandit_state.get("beliefs"), dict):
        bandit_beliefs = bandit_state["beliefs"]
    elif bandit_state and isinstance(bandit_state.get("arms"), dict):
        for arm_id, arm_data in bandit_state["arms"].items():
            bandit_beliefs[arm_id] = {
                "alpha": arm_data.get("alpha", 1.0),
                "beta": arm_data.get("beta", 1.0),
            }

    epoch_metrics = compute_epoch_metrics(history, params)
    previous = get_previous_snapshot()
    promoted = check_promotion(epoch_metrics, previous)

    snapshot = {
        "date": today,
        "version": "1.0.0",
        "param_count": len(params),
        "params": param_values,
        "bandit_beliefs": bandit_beliefs,
        "bandit_enabled": registry.is_bandit_enabled(),
        "epoch_metrics": epoch_metrics,
        "promoted": promoted,
        "created_at": datetime.now().isoformat(),
    }

    return snapshot


def save_snapshot(snapshot: dict) -> Path:
    """Save snapshot to data/weight-snapshots/YYYY-MM-DD.json."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOT_DIR / f"{snapshot['date']}.json"
    path.write_text(json.dumps(snapshot, indent=2) + "\n")
    return path


def prune_snapshots(dry_run: bool = False) -> list[str]:
    """Remove snapshots older than 90 days, keeping promoted ones."""
    if not SNAPSHOT_DIR.exists():
        return []

    cutoff = datetime.now() - timedelta(days=PRUNE_DAYS)
    pruned = []

    for snap_path in sorted(SNAPSHOT_DIR.glob("*.json")):
        stem = snap_path.stem  # YYYY-MM-DD
        try:
            snap_date = datetime.strptime(stem, "%Y-%m-%d")
        except ValueError:
            continue

        if snap_date >= cutoff:
            continue

        # Check if promoted
        try:
            data = json.loads(snap_path.read_text())
            if data.get("promoted", False):
                continue
        except (json.JSONDecodeError, OSError):
            pass

        if not dry_run:
            snap_path.unlink()
        pruned.append(stem)

    return pruned


def show_status():
    """Print status of last snapshot."""
    previous = get_previous_snapshot()
    if previous is None:
        print("No snapshots found.")
        return

    print(f"Last snapshot: {previous['date']}")
    print(f"  Params: {previous['param_count']}")
    print(f"  Promoted: {previous.get('promoted', False)}")
    print(f"  Bandit enabled: {previous.get('bandit_enabled', False)}")

    metrics = previous.get("epoch_metrics", {})
    print(f"  Avg reward: {metrics.get('avg_reward', 'N/A')}")
    print(f"  Reward variance: {metrics.get('reward_variance', 'N/A')}")
    print(f"  Exploration rate: {metrics.get('exploration_rate', 'N/A')}")
    print(f"  Drift from baseline: {metrics.get('drift_from_baseline', 'N/A')}")
    print(f"  History entries: {metrics.get('history_entries', 0)}")

    # Count total snapshots
    if SNAPSHOT_DIR.exists():
        total = len(list(SNAPSHOT_DIR.glob("*.json")))
        promoted = 0
        for sp in SNAPSHOT_DIR.glob("*.json"):
            try:
                d = json.loads(sp.read_text())
                if d.get("promoted"):
                    promoted += 1
            except (json.JSONDecodeError, OSError):
                pass
        print(f"  Total snapshots: {total} ({promoted} promoted)")


def install_launchagent():
    """Create a LaunchAgent plist for daily execution."""
    plist = {
        "Label": PLIST_LABEL,
        "ProgramArguments": [
            sys.executable,
            str(REPO_ROOT / "kernel" / "weight-snapshot-daemon.py"),
        ],
        "StartInterval": 86400,  # 24 hours
        "StandardOutPath": str(DATA_DIR / "weight-snapshot-daemon.log"),
        "StandardErrorPath": str(DATA_DIR / "weight-snapshot-daemon-error.log"),
        "RunAtLoad": True,
    }

    launch_agents_dir = Path.home() / "Library" / "LaunchAgents"
    launch_agents_dir.mkdir(parents=True, exist_ok=True)
    plist_path = launch_agents_dir / f"{PLIST_LABEL}.plist"
    with open(plist_path, "wb") as f:
        plistlib.dump(plist, f)

    print(f"LaunchAgent installed: {plist_path}")
    print(f"  Load: launchctl load {plist_path}")
    print(f"  Unload: launchctl unload {plist_path}")


def main():
    parser = argparse.ArgumentParser(description="Weight Snapshot Daemon (US-106)")
    parser.add_argument("--status", action="store_true", help="Show last snapshot info")
    parser.add_argument("--install", action="store_true", help="Install LaunchAgent plist")
    parser.add_argument("--prune-only", action="store_true", help="Only prune old snapshots")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be pruned")
    parser.add_argument("--date", type=str, default=None, help="Override snapshot date (YYYY-MM-DD)")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    if args.install:
        install_launchagent()
        return

    if args.prune_only:
        pruned = prune_snapshots(dry_run=args.dry_run)
        if pruned:
            action = "Would prune" if args.dry_run else "Pruned"
            print(f"{action} {len(pruned)} snapshots: {', '.join(pruned)}")
        else:
            print("Nothing to prune.")
        return

    # --- Main snapshot flow ---
    registry = load_registry()
    bandit_state = load_bandit_state()
    history = load_bandit_history()

    today = args.date or datetime.now().strftime("%Y-%m-%d")
    snapshot = create_snapshot(registry, bandit_state, history, today=today)
    path = save_snapshot(snapshot)

    # Prune old snapshots
    pruned = prune_snapshots()

    # Summary
    print(f"Snapshot saved: {path}")
    print(f"  Date: {snapshot['date']}")
    print(f"  Params: {snapshot['param_count']}")
    print(f"  Promoted: {snapshot['promoted']}")

    metrics = snapshot["epoch_metrics"]
    print(f"  Avg reward: {metrics['avg_reward']}")
    print(f"  Reward variance: {metrics['reward_variance']}")
    print(f"  Exploration rate: {metrics['exploration_rate']}")
    print(f"  Drift: {metrics['drift_from_baseline']}")
    print(f"  History entries: {metrics['history_entries']}")

    if pruned:
        print(f"  Pruned {len(pruned)} old snapshots")


if __name__ == "__main__":
    main()
