#!/usr/bin/env python3
"""
US-108: Weekly LRF Update Daemon

Weekly daemon that re-computes LRF clusters and per-cluster optimal weights.
Reads last 7 days of routing decisions with outcomes, re-runs clustering,
updates data/lrf-clusters.json. If any cluster improved >5%, logs promotion.
If total decisions < 200 for the week, skips update.
Outputs weekly report to data/lrf-reports/YYYY-WW.json.

Designed to be run via LaunchAgent on 7-day interval, or manually.
"""

import argparse
import json
import math
import os
import plistlib
import random
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# ─── Paths ───────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent
DQ_SCORES_PATH = Path(os.environ.get("HOME", "~")) / ".claude" / "kernel" / "dq-scores.jsonl"
BANDIT_HISTORY_PATH = BASE_DIR / "data" / "bandit-history.jsonl"
LRF_CLUSTERS_PATH = BASE_DIR / "data" / "lrf-clusters.json"
LRF_REPORTS_DIR = BASE_DIR / "data" / "lrf-reports"
LAUNCHAGENT_LABEL = "com.metavengine.lrf-update"
LAUNCHAGENT_PATH = Path(os.environ.get("HOME", "~")) / "Library" / "LaunchAgents" / f"{LAUNCHAGENT_LABEL}.plist"

MIN_DECISIONS = 200
MIN_DECISIONS_PER_CLUSTER = 50
DEFAULT_K = 5
PROMOTION_THRESHOLD = 0.05  # 5% improvement


# ─── JSONL Reader ────────────────────────────────────────────────────────────

def read_jsonl_since(filepath: Path, since_ts: float) -> list[dict]:
    """Read JSONL entries with timestamp >= since_ts (unix seconds)."""
    entries = []
    if not filepath.exists():
        return entries
    try:
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                # Support both 'ts' (unix seconds) and 'timestamp' (ISO string)
                entry_ts = _extract_timestamp(entry)
                if entry_ts is not None and entry_ts >= since_ts:
                    entries.append(entry)
    except OSError:
        pass
    return entries


def _extract_timestamp(entry: dict) -> float | None:
    """Extract unix timestamp from an entry, supporting ts (int) and timestamp (ISO)."""
    if "ts" in entry:
        ts = entry["ts"]
        if isinstance(ts, (int, float)):
            # Detect milliseconds vs seconds
            return ts / 1000.0 if ts > 1e12 else float(ts)
    if "timestamp" in entry:
        try:
            dt = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))
            return dt.timestamp()
        except (ValueError, AttributeError):
            pass
    return None


# ─── Feature Extraction ─────────────────────────────────────────────────────

SESSION_TYPE_MAP = {
    "debugging": 0, "research": 1, "architecture": 2, "refactoring": 3,
    "testing": 4, "docs": 5, "exploration": 6, "creative": 7,
}

COGNITIVE_MODE_MAP = {
    "morning": 0, "peak": 1, "dip": 2, "evening": 3, "deep_night": 4,
}


def extract_features(decision: dict) -> list[float]:
    """
    Extract context features from a routing decision for clustering.

    Features (5-dimensional):
      [0] complexity (0-1)
      [1] session_type (0-7 normalized to 0-1)
      [2] cognitive_mode (0-4 normalized to 0-1)
      [3] graph_confidence (0-1, or 0.5 if absent)
      [4] dq_score (0-1)
    """
    complexity = float(decision.get("complexity", 0.5))

    session_type = decision.get("session_type", decision.get("sessionType", "exploration"))
    st_idx = SESSION_TYPE_MAP.get(str(session_type).lower(), 6)
    st_norm = st_idx / 7.0

    cog_mode = decision.get("cognitive_mode", decision.get("cognitiveMode", "peak"))
    cm_idx = COGNITIVE_MODE_MAP.get(str(cog_mode).lower(), 1)
    cm_norm = cm_idx / 4.0

    graph_conf = float(decision.get("graph_confidence", decision.get("graphConfidence", 0.5)))

    dq_score = 0.5
    if isinstance(decision.get("dq"), dict):
        dq_score = float(decision["dq"].get("score", 0.5))
    elif isinstance(decision.get("dqScore"), (int, float)):
        dq_score = float(decision["dqScore"])

    return [complexity, st_norm, cm_norm, graph_conf, dq_score]


def extract_reward(decision: dict, bandit_map: dict[str, float]) -> float:
    """
    Get reward for a decision, looking up in bandit history if available.
    Falls back to DQ score as proxy reward.
    """
    # Try to match via bandit sampleId
    bandit_info = decision.get("bandit", {})
    if isinstance(bandit_info, dict):
        sample_id = bandit_info.get("sampleId", "")
        if sample_id and sample_id in bandit_map:
            return bandit_map[sample_id]

    # Fallback: use DQ score as reward proxy
    if isinstance(decision.get("dq"), dict):
        return float(decision["dq"].get("score", 0.5))
    return 0.5


def extract_weights(decision: dict) -> dict[str, float]:
    """Extract perturbed weights from a decision, if present."""
    bandit_info = decision.get("bandit", {})
    if isinstance(bandit_info, dict) and bandit_info.get("perturbedWeights"):
        return dict(bandit_info["perturbedWeights"])
    return {}


# ─── K-Means Clustering ─────────────────────────────────────────────────────

def euclidean_distance(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def kmeans(
    points: list[list[float]],
    k: int = DEFAULT_K,
    max_iter: int = 50,
    seed: int | None = None,
) -> tuple[list[list[float]], list[int]]:
    """
    Simple k-means clustering. Returns (centroids, assignments).
    """
    if not points:
        return [], []

    n = len(points)
    dim = len(points[0])
    k = min(k, n)

    rng = random.Random(seed if seed is not None else 42)

    # Initialize centroids via k-means++ style
    centroids = [list(points[rng.randint(0, n - 1)])]
    for _ in range(1, k):
        dists = []
        for p in points:
            min_d = min(euclidean_distance(p, c) for c in centroids)
            dists.append(min_d * min_d)
        total = sum(dists)
        if total == 0:
            centroids.append(list(points[rng.randint(0, n - 1)]))
            continue
        probs = [d / total for d in dists]
        cum = 0.0
        r = rng.random()
        for i, p_val in enumerate(probs):
            cum += p_val
            if cum >= r:
                centroids.append(list(points[i]))
                break
        else:
            centroids.append(list(points[-1]))

    assignments = [0] * n

    for _ in range(max_iter):
        # Assign points to nearest centroid
        new_assignments = []
        for p in points:
            dists = [euclidean_distance(p, c) for c in centroids]
            new_assignments.append(dists.index(min(dists)))

        if new_assignments == assignments:
            break
        assignments = new_assignments

        # Recompute centroids
        for ci in range(k):
            members = [points[i] for i in range(n) if assignments[i] == ci]
            if members:
                centroids[ci] = [
                    sum(m[d] for m in members) / len(members) for d in range(dim)
                ]

    return centroids, assignments


# ─── Cluster Analysis ────────────────────────────────────────────────────────

def compute_cluster_stats(
    decisions: list[dict],
    features_list: list[list[float]],
    rewards: list[float],
    assignments: list[int],
    centroids: list[list[float]],
    k: int,
) -> list[dict]:
    """Compute per-cluster statistics and optimal weights."""
    clusters = []
    for ci in range(k):
        indices = [i for i, a in enumerate(assignments) if a == ci]
        size = len(indices)

        if size == 0:
            clusters.append({
                "id": ci,
                "size": 0,
                "centroid": centroids[ci] if ci < len(centroids) else [],
                "avgReward": 0.0,
                "bestWeights": {},
                "trusted": False,
            })
            continue

        cluster_rewards = [rewards[i] for i in indices]
        avg_reward = sum(cluster_rewards) / len(cluster_rewards)

        # Find the best weights: aggregate perturbed weights from top-performing decisions
        top_count = max(1, size // 5)  # top 20%
        sorted_indices = sorted(indices, key=lambda i: rewards[i], reverse=True)
        top_indices = sorted_indices[:top_count]

        weight_sums: dict[str, float] = {}
        weight_counts: dict[str, int] = {}
        for idx in top_indices:
            w = extract_weights(decisions[idx])
            for key, val in w.items():
                weight_sums[key] = weight_sums.get(key, 0.0) + val
                weight_counts[key] = weight_counts.get(key, 0) + 1

        best_weights = {
            key: weight_sums[key] / weight_counts[key]
            for key in weight_sums
        }

        clusters.append({
            "id": ci,
            "size": size,
            "centroid": centroids[ci],
            "avgReward": round(avg_reward, 6),
            "bestWeights": best_weights,
            "trusted": size >= MIN_DECISIONS_PER_CLUSTER,
        })

    return clusters


# ─── Promotion Detection ────────────────────────────────────────────────────

def detect_promotions(
    new_clusters: list[dict],
    old_clusters: list[dict],
) -> list[dict]:
    """Detect clusters that improved > 5% vs previous."""
    promotions = []
    old_map = {c["id"]: c for c in old_clusters}

    for nc in new_clusters:
        if nc["size"] == 0 or not nc["trusted"]:
            continue
        oc = old_map.get(nc["id"])
        if not oc or oc["avgReward"] == 0:
            continue
        improvement = (nc["avgReward"] - oc["avgReward"]) / oc["avgReward"]
        if improvement > PROMOTION_THRESHOLD:
            promotions.append({
                "clusterId": nc["id"],
                "previousAvgReward": round(oc["avgReward"], 6),
                "newAvgReward": round(nc["avgReward"], 6),
                "improvementPct": round(improvement * 100, 2),
            })

    return promotions


# ─── Main Update Logic ───────────────────────────────────────────────────────

def run_update(
    dry_run: bool = False,
    dq_scores_path: Path | None = None,
    bandit_history_path: Path | None = None,
    lrf_clusters_path: Path | None = None,
    lrf_reports_dir: Path | None = None,
    k: int = DEFAULT_K,
) -> dict[str, Any]:
    """
    Main update: read last 7 days, cluster, write results.
    Returns the report dict.
    """
    dq_path = dq_scores_path or DQ_SCORES_PATH
    bandit_path = bandit_history_path or BANDIT_HISTORY_PATH
    clusters_path = lrf_clusters_path or LRF_CLUSTERS_PATH
    reports_dir = lrf_reports_dir or LRF_REPORTS_DIR

    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    since_ts = seven_days_ago.timestamp()

    # ── 1. Load data ─────────────────────────────────────────────────────
    decisions = read_jsonl_since(dq_path, since_ts)
    bandit_entries = read_jsonl_since(bandit_path, since_ts)

    # Build sampleId -> reward lookup
    bandit_map: dict[str, float] = {}
    for be in bandit_entries:
        sid = be.get("sampleId", "")
        if sid and "reward" in be:
            bandit_map[sid] = float(be["reward"])

    total = len(decisions)

    # ── 2. Check minimum threshold ───────────────────────────────────────
    if total < MIN_DECISIONS:
        msg = f"Skipping LRF update: {total} decisions < {MIN_DECISIONS} minimum"
        print(msg)
        return {
            "status": "skipped",
            "reason": msg,
            "totalDecisions": total,
            "timestamp": now.isoformat(),
        }

    # ── 3. Extract features and rewards ──────────────────────────────────
    features_list = [extract_features(d) for d in decisions]
    rewards = [extract_reward(d, bandit_map) for d in decisions]

    # ── 4. Cluster ───────────────────────────────────────────────────────
    centroids, assignments = kmeans(features_list, k=k, seed=42)

    # ── 5. Compute per-cluster stats ─────────────────────────────────────
    new_clusters = compute_cluster_stats(
        decisions, features_list, rewards, assignments, centroids, k
    )

    # ── 6. Load previous clusters for promotion detection ────────────────
    old_clusters: list[dict] = []
    if clusters_path.exists():
        try:
            old_data = json.loads(clusters_path.read_text())
            old_clusters = old_data.get("clusters", [])
        except (json.JSONDecodeError, OSError):
            pass

    promotions = detect_promotions(new_clusters, old_clusters)

    # ── 7. Build report ──────────────────────────────────────────────────
    week_label = now.strftime("%Y-W%W")
    report = {
        "weekLabel": week_label,
        "timestamp": now.isoformat(),
        "status": "completed",
        "totalDecisions": total,
        "clusterCount": k,
        "clusters": [
            {
                "id": c["id"],
                "size": c["size"],
                "centroid": [round(v, 6) for v in c["centroid"]] if c["centroid"] else [],
                "avgReward": c["avgReward"],
                "bestWeights": c["bestWeights"],
                "trusted": c["trusted"],
            }
            for c in new_clusters
        ],
        "promotions": promotions,
        "summary": {
            "trustedClusters": sum(1 for c in new_clusters if c["trusted"]),
            "promotionCount": len(promotions),
            "avgRewardOverall": round(sum(rewards) / len(rewards), 6) if rewards else 0,
        },
    }

    # ── 8. Write outputs (unless dry-run) ────────────────────────────────
    if not dry_run:
        # Write lrf-clusters.json
        clusters_data = {
            "version": "1.0.0",
            "updated": now.isoformat(),
            "k": k,
            "clusters": report["clusters"],
        }
        clusters_path.parent.mkdir(parents=True, exist_ok=True)
        clusters_path.write_text(json.dumps(clusters_data, indent=2) + "\n")

        # Write weekly report
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / f"{week_label}.json"
        report_path.write_text(json.dumps(report, indent=2) + "\n")

    # ── 9. Print summary ─────────────────────────────────────────────────
    _print_summary(report, dry_run)

    return report


def _print_summary(report: dict, dry_run: bool) -> None:
    prefix = "[DRY-RUN] " if dry_run else ""
    print(f"{prefix}LRF Weekly Update — {report['weekLabel']}")
    print(f"  Decisions analyzed: {report['totalDecisions']}")
    print(f"  Clusters: {report['clusterCount']} ({report['summary']['trustedClusters']} trusted)")
    print(f"  Overall avg reward: {report['summary']['avgRewardOverall']:.4f}")

    for c in report["clusters"]:
        trust = "trusted" if c["trusted"] else "untrusted"
        print(f"  Cluster {c['id']}: size={c['size']}, avgReward={c['avgReward']:.4f} ({trust})")

    if report["promotions"]:
        print(f"  Promotions ({len(report['promotions'])}):")
        for p in report["promotions"]:
            print(
                f"    Cluster {p['clusterId']}: "
                f"{p['previousAvgReward']:.4f} -> {p['newAvgReward']:.4f} "
                f"(+{p['improvementPct']:.1f}%)"
            )
    else:
        print("  No promotions this week")


# ─── Status ──────────────────────────────────────────────────────────────────

def show_status() -> None:
    """Show info about the last LRF update."""
    if not LRF_CLUSTERS_PATH.exists():
        print("No LRF clusters found. Run the daemon first.")
        return

    try:
        data = json.loads(LRF_CLUSTERS_PATH.read_text())
    except (json.JSONDecodeError, OSError) as e:
        print(f"Error reading clusters: {e}")
        return

    print(f"LRF Clusters — last updated: {data.get('updated', 'unknown')}")
    print(f"  k = {data.get('k', '?')}")
    clusters = data.get("clusters", [])
    for c in clusters:
        trust = "trusted" if c.get("trusted") else "untrusted"
        print(f"  Cluster {c['id']}: size={c['size']}, avgReward={c['avgReward']:.4f} ({trust})")

    # Check for latest report
    if LRF_REPORTS_DIR.exists():
        reports = sorted(LRF_REPORTS_DIR.glob("*.json"))
        if reports:
            latest = reports[-1]
            print(f"\n  Latest report: {latest.name}")
            try:
                rdata = json.loads(latest.read_text())
                promos = rdata.get("promotions", [])
                if promos:
                    print(f"  Promotions: {len(promos)}")
                    for p in promos:
                        print(f"    Cluster {p['clusterId']}: +{p['improvementPct']:.1f}%")
                else:
                    print("  No promotions in latest report")
            except (json.JSONDecodeError, OSError):
                pass


# ─── LaunchAgent Install ─────────────────────────────────────────────────────

def install_launchagent() -> None:
    """Create and load a LaunchAgent plist for weekly execution."""
    script_path = Path(__file__).resolve()
    python_path = sys.executable

    plist = {
        "Label": LAUNCHAGENT_LABEL,
        "ProgramArguments": [python_path, str(script_path)],
        "StartInterval": 7 * 24 * 60 * 60,  # 7 days in seconds
        "StandardOutPath": str(BASE_DIR / "logs" / "lrf-update-daemon.log"),
        "StandardErrorPath": str(BASE_DIR / "logs" / "lrf-update-daemon.err"),
        "RunAtLoad": False,
        "EnvironmentVariables": {
            "HOME": os.environ.get("HOME", ""),
            "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        },
    }

    LAUNCHAGENT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(LAUNCHAGENT_PATH, "wb") as f:
        plistlib.dump(plist, f)

    print(f"LaunchAgent installed: {LAUNCHAGENT_PATH}")

    # Try to load it
    try:
        subprocess.run(
            ["launchctl", "bootout", f"gui/{os.getuid()}", str(LAUNCHAGENT_PATH)],
            capture_output=True,
        )
    except OSError:
        pass
    try:
        result = subprocess.run(
            ["launchctl", "bootstrap", f"gui/{os.getuid()}", str(LAUNCHAGENT_PATH)],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print("LaunchAgent loaded successfully")
        else:
            print(f"LaunchAgent load: {result.stderr.strip() or 'done'}")
    except OSError as e:
        print(f"Could not load LaunchAgent: {e}")
        print("Load manually: launchctl bootstrap gui/$(id -u) " + str(LAUNCHAGENT_PATH))


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="US-108: Weekly LRF Update Daemon — re-cluster routing decisions"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Compute clusters without writing files"
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Show last LRF update info"
    )
    parser.add_argument(
        "--install", action="store_true",
        help="Install LaunchAgent for weekly execution"
    )
    parser.add_argument(
        "--k", type=int, default=DEFAULT_K,
        help=f"Number of clusters (default: {DEFAULT_K})"
    )
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    if args.install:
        install_launchagent()
        return

    run_update(dry_run=args.dry_run, k=args.k)


if __name__ == "__main__":
    main()
