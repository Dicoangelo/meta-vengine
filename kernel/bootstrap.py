#!/usr/bin/env python3
"""
US-204: Production Telemetry Bootstrap — Warm-Start Bandit Seeding

Seeds the Thompson Sampling bandit with informed Beta priors derived from
historical behavioral-outcome data. Also bootstraps LRF clusters and takes
an initial weight snapshot.

Run from project root:
    python3 kernel/bootstrap.py              # normal (skip if state exists)
    python3 kernel/bootstrap.py --force      # overwrite existing state

Pure Python stdlib — zero dependencies.
"""

import argparse
import json
import math
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
OUTCOMES_PATH = DATA_DIR / "behavioral-outcomes.jsonl"
BANDIT_STATE_PATH = DATA_DIR / "bandit-state.json"
LRF_CLUSTERS_PATH = DATA_DIR / "lrf-clusters.json"
SNAPSHOT_DIR = DATA_DIR / "weight-snapshots"
REPORT_PATH = DATA_DIR / "bootstrap-report.json"
PARAMS_PATH = BASE_DIR / "config" / "learnable-params.json"

MIN_ENTRIES = 50

# Session types and time modes from lrf-clustering.py
SESSION_TYPES = [
    "debugging", "research", "architecture", "refactoring",
    "testing", "docs", "exploration", "creative",
]
TIME_MODES = ["morning", "peak", "dip", "evening", "deep_night"]


def _log(msg: str) -> None:
    """Print progress to stderr."""
    print(f"[bootstrap] {msg}", file=sys.stderr)


# ── Data Loading ──────────────────────────────────────────────────────


def load_params() -> dict[str, Any]:
    """Load learnable-params.json."""
    return json.loads(PARAMS_PATH.read_text())


def load_outcomes() -> list[dict[str, Any]]:
    """Load behavioral-outcomes.jsonl, return list of parsed entries."""
    if not OUTCOMES_PATH.exists():
        return []
    entries = []
    with open(OUTCOMES_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


# ── Reward Computation ────────────────────────────────────────────────


def compute_reward(entry: dict, reward_weights: dict[str, float]) -> float:
    """Compute aggregate reward from a behavioral outcome entry.

    Reward = DQ_WEIGHT * dq_proxy + COST_WEIGHT * cost_efficiency + BEHAVIORAL_WEIGHT * behavioral

    Since historical data lacks DQ scores, use completion as DQ proxy.
    Cost efficiency: use efficiency score directly.
    Behavioral: weighted composite of the 5 behavioral components.
    """
    components = entry.get("components", {})

    # DQ proxy: completion score
    dq_proxy = components.get("completion", 0.5)

    # Cost efficiency: efficiency score
    cost_efficiency = components.get("efficiency", 0.5)

    # Behavioral composite from the 5 components using their weights
    beh_weights = entry.get("weights", {
        "completion": 0.30, "tool_success": 0.25,
        "efficiency": 0.20, "no_override": 0.15, "no_followup": 0.10,
    })
    behavioral = sum(
        components.get(k, 0.5) * beh_weights.get(k, 0.0)
        for k in beh_weights
    )
    behavioral = max(0.0, min(1.0, behavioral))

    # Aggregate using reward function weights (default: 40/30/30)
    dq_w = reward_weights.get("dq", 0.40)
    cost_w = reward_weights.get("cost", 0.30)
    beh_w = reward_weights.get("behavioral", 0.30)

    reward = dq_w * dq_proxy + cost_w * cost_efficiency + beh_w * behavioral
    return max(0.0, min(1.0, reward))


# ── Beta Prior Estimation (Method of Moments) ────────────────────────


def estimate_beta_priors(rewards: list[float]) -> tuple[float, float]:
    """Compute Beta distribution priors via method of moments.

    Returns (alpha, beta) clamped to [1.0, 100.0].
    """
    n = len(rewards)
    if n < 2:
        return 1.0, 1.0

    mean = sum(rewards) / n
    var = sum((r - mean) ** 2 for r in rewards) / (n - 1)

    # Avoid degenerate cases
    if var <= 0 or mean <= 0 or mean >= 1:
        return 1.0, 1.0

    # Method of moments for Beta distribution
    common = mean * (1 - mean) / var - 1
    if common <= 0:
        return 1.0, 1.0

    alpha = mean * common
    beta = (1 - mean) * common

    # Clamp to [1.0, 100.0] for stability
    alpha = max(1.0, min(100.0, alpha))
    beta = max(1.0, min(100.0, beta))

    return round(alpha, 4), round(beta, 4)


# ── Bandit State Seeding ─────────────────────────────────────────────


def seed_bandit(params_data: dict, alpha: float, beta: float, n_entries: int) -> dict:
    """Create bandit-state.json with informed priors for all params."""
    beliefs = {}
    for p in params_data["parameters"]:
        beliefs[p["id"]] = {"alpha": alpha, "beta": beta}

    state = {
        "beliefs": beliefs,
        "sampleCounter": 0,
        "lastUpdated": datetime.now().isoformat(),
        "bootstrapped": True,
        "bootstrapEntries": n_entries,
    }
    return state


# ── LRF Clustering ───────────────────────────────────────────────────


def _hour_to_mode(hour: int) -> str:
    """Map hour to cognitive mode (matches lrf-clustering.py)."""
    if 5 <= hour < 9:
        return "morning"
    elif 9 <= hour < 12 or 14 <= hour < 18:
        return "peak"
    elif 12 <= hour < 14:
        return "dip"
    elif 18 <= hour < 22:
        return "evening"
    else:
        return "deep_night"


def _session_type_vector(session_type: str) -> list[float]:
    """One-hot encode session type (8 dims)."""
    vec = [0.0] * len(SESSION_TYPES)
    if session_type in SESSION_TYPES:
        vec[SESSION_TYPES.index(session_type)] = 1.0
    return vec


def _time_mode_vector(mode: str) -> list[float]:
    """One-hot encode time mode (5 dims)."""
    vec = [0.0] * len(TIME_MODES)
    if mode in TIME_MODES:
        vec[TIME_MODES.index(mode)] = 1.0
    return vec


def extract_features(entry: dict) -> list[float]:
    """Extract 14-dim feature vector from a behavioral outcome entry.

    [0]     complexity proxy (behavioral_score as complexity stand-in)
    [1:9]   session type one-hot (uniform since not in historical data)
    [9:14]  time-of-day one-hot (extracted from started_at timestamp)
    """
    # Complexity proxy: use behavioral_score
    complexity = entry.get("behavioral_score", 0.5)

    # Session type: not available in historical data, use uniform
    session_vec = [1.0 / len(SESSION_TYPES)] * len(SESSION_TYPES)

    # Time of day: extract from started_at
    hour = 12  # default noon
    started = entry.get("started_at", "")
    if started:
        try:
            dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
            hour = dt.hour
        except (ValueError, AttributeError):
            pass

    time_vec = _time_mode_vector(_hour_to_mode(hour))

    features = [float(complexity)]
    features.extend(session_vec)
    features.extend(time_vec)
    return features


def _euclidean(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _mean_vector(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        return []
    dim = len(vectors[0])
    return [sum(v[i] for v in vectors) / len(vectors) for i in range(dim)]


def _kmeans_pp_init(features: list[list[float]], k: int) -> list[list[float]]:
    """K-means++ initialization."""
    centroids = [features[random.randint(0, len(features) - 1)]]
    for _ in range(1, k):
        dists = [min(_euclidean(f, c) for c in centroids) for f in features]
        total = sum(d * d for d in dists)
        if total == 0:
            centroids.append(features[random.randint(0, len(features) - 1)])
            continue
        r = random.random() * total
        cumulative = 0.0
        for i, d in enumerate(dists):
            cumulative += d * d
            if cumulative >= r:
                centroids.append(features[i])
                break
    return centroids


def _silhouette_score(features: list[list[float]], assignments: list[int], k: int) -> float:
    """Compute silhouette score (pure Python pairwise Euclidean).

    Returns mean silhouette coefficient in [-1, 1].
    """
    n = len(features)
    if n < 2 or k < 2:
        return 0.0

    silhouettes = []
    for i in range(n):
        ci = assignments[i]

        # a(i) = mean distance to same-cluster points
        same = [j for j in range(n) if j != i and assignments[j] == ci]
        if not same:
            silhouettes.append(0.0)
            continue
        a_i = sum(_euclidean(features[i], features[j]) for j in same) / len(same)

        # b(i) = min over other clusters of mean distance to that cluster
        b_i = float("inf")
        for c in range(k):
            if c == ci:
                continue
            other = [j for j in range(n) if assignments[j] == c]
            if not other:
                continue
            mean_dist = sum(_euclidean(features[i], features[j]) for j in other) / len(other)
            b_i = min(b_i, mean_dist)

        if b_i == float("inf"):
            silhouettes.append(0.0)
            continue

        denom = max(a_i, b_i)
        s_i = (b_i - a_i) / denom if denom > 0 else 0.0
        silhouettes.append(s_i)

    return sum(silhouettes) / len(silhouettes) if silhouettes else 0.0


def run_clustering(
    entries: list[dict], k: int = 5, max_iter: int = 50, sample_limit: int = 500
) -> dict[str, Any]:
    """Run k-means on historical entries and return cluster data.

    For silhouette computation efficiency, subsample if > sample_limit entries.
    """
    if len(entries) < k:
        raise ValueError(f"Need at least {k} entries for clustering, got {len(entries)}")

    all_features = [extract_features(e) for e in entries]
    all_rewards = [e.get("behavioral_score", 0.5) for e in entries]

    # K-means on all features
    centroids = _kmeans_pp_init(all_features, k)
    assignments = [0] * len(all_features)

    for _ in range(max_iter):
        new_assignments = [
            min(range(k), key=lambda c: _euclidean(f, centroids[c]))
            for f in all_features
        ]
        if new_assignments == assignments:
            break
        assignments = new_assignments

        for c in range(k):
            members = [all_features[i] for i in range(len(all_features)) if assignments[i] == c]
            if members:
                centroids[c] = _mean_vector(members)

    # Cluster sizes and avg rewards
    cluster_sizes = [0] * k
    cluster_reward_sums = [0.0] * k
    for i, c in enumerate(assignments):
        cluster_sizes[c] += 1
        cluster_reward_sums[c] += all_rewards[i]

    cluster_avg_rewards = [
        round(cluster_reward_sums[c] / cluster_sizes[c], 4) if cluster_sizes[c] > 0 else 0.0
        for c in range(k)
    ]

    # Silhouette on subsample for efficiency
    if len(all_features) > sample_limit:
        indices = random.sample(range(len(all_features)), sample_limit)
        sub_features = [all_features[i] for i in indices]
        sub_assignments = [assignments[i] for i in indices]
    else:
        sub_features = all_features
        sub_assignments = assignments

    silhouette = round(_silhouette_score(sub_features, sub_assignments, k), 4)

    # Empty cluster weights (no perturbed_weights in historical data)
    cluster_weights = [{}] * k

    cluster_data = {
        "version": "1.0.0",
        "k": k,
        "centroids": [[round(x, 6) for x in c] for c in centroids],
        "cluster_weights": cluster_weights,
        "cluster_sizes": cluster_sizes,
        "cluster_avg_rewards": cluster_avg_rewards,
        "bestSilhouette": silhouette,
        "updated": datetime.now().isoformat(),
        "feature_schema": [
            "graphComplexity",
            *[f"sessionType_{t}" for t in SESSION_TYPES],
            *[f"timeMode_{m}" for m in TIME_MODES],
        ],
        "bootstrapped": True,
    }
    return cluster_data


# ── Snapshot ─────────────────────────────────────────────────────────


def take_snapshot(params_data: dict, bandit_state: dict) -> str:
    """Save weight snapshot to data/weight-snapshots/YYYY-MM-DD.json."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    path = SNAPSHOT_DIR / f"{today}.json"

    weights = {p["id"]: p["value"] for p in params_data["parameters"]}
    snapshot = {
        "date": today,
        "timestamp": datetime.now().isoformat(),
        "weights": weights,
        "bandit_state": {
            "sampleCounter": bandit_state.get("sampleCounter", 0),
            "bootstrapped": bandit_state.get("bootstrapped", False),
            "bootstrapEntries": bandit_state.get("bootstrapEntries", 0),
        },
        "avg_reward": None,
        "promoted": False,
    }
    path.write_text(json.dumps(snapshot, indent=2) + "\n")
    return str(path)


# ── Bootstrap Report ─────────────────────────────────────────────────


def save_report(
    n_entries: int,
    alpha: float,
    beta: float,
    params_data: dict,
    cluster_data: dict,
) -> str:
    """Save bootstrap-report.json."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    priors = {}
    for p in params_data["parameters"]:
        priors[p["id"]] = {"alpha": alpha, "beta": beta}

    report = {
        "entries_used": n_entries,
        "priors": priors,
        "cluster_sizes": cluster_data.get("cluster_sizes", []),
        "silhouette_score": cluster_data.get("bestSilhouette", 0.0),
        "timestamp": datetime.now().isoformat(),
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n")
    return str(REPORT_PATH)


# ── Main ─────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="US-204: Bootstrap bandit with informed priors from historical data"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Overwrite existing bandit state",
    )
    args = parser.parse_args()

    # Idempotency check
    if BANDIT_STATE_PATH.exists() and not args.force:
        _log(f"WARNING: {BANDIT_STATE_PATH} already exists. Use --force to overwrite.")
        print(json.dumps({"status": "skipped", "reason": "state_exists"}))
        return 0

    # Step 1: Load historical data
    _log("Loading behavioral outcomes...")
    entries = load_outcomes()
    n_entries = len(entries)
    _log(f"Found {n_entries} entries")

    if n_entries < MIN_ENTRIES:
        _log(f"ERROR: Need at least {MIN_ENTRIES} entries, got {n_entries}. "
             f"Run 'python3 kernel/behavioral-outcome.py --backfill' first.")
        print(json.dumps({"status": "error", "reason": "insufficient_data",
                          "entries": n_entries, "required": MIN_ENTRIES}))
        return 1

    # Step 2: Load params
    _log("Loading parameter registry...")
    params_data = load_params()
    param_count = len(params_data["parameters"])
    _log(f"Loaded {param_count} learnable parameters")

    # Step 3: Compute rewards
    _log("Computing aggregate rewards...")
    reward_weights = {"dq": 0.40, "cost": 0.30, "behavioral": 0.30}
    rewards = [compute_reward(e, reward_weights) for e in entries]

    mean_reward = sum(rewards) / len(rewards)
    _log(f"Mean reward: {mean_reward:.4f} (n={len(rewards)})")

    # Step 4: Estimate Beta priors
    _log("Estimating Beta priors (method of moments)...")
    alpha, beta_val = estimate_beta_priors(rewards)
    _log(f"Priors: alpha={alpha}, beta={beta_val}")

    # Step 5: Seed bandit state
    _log("Seeding bandit state...")
    bandit_state = seed_bandit(params_data, alpha, beta_val, n_entries)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BANDIT_STATE_PATH.write_text(json.dumps(bandit_state, indent=2) + "\n")
    _log(f"Wrote {BANDIT_STATE_PATH}")

    # Step 6: Seed LRF clusters
    _log("Running LRF clustering...")
    k = 5  # default from param registry
    cluster_data = run_clustering(entries, k=k)
    LRF_CLUSTERS_PATH.write_text(json.dumps(cluster_data, indent=2) + "\n")
    _log(f"Wrote {LRF_CLUSTERS_PATH} (k={k}, silhouette={cluster_data['bestSilhouette']})")

    # Step 7: Take first weight snapshot
    _log("Taking weight snapshot...")
    snap_path = take_snapshot(params_data, bandit_state)
    _log(f"Wrote {snap_path}")

    # Step 8: Save bootstrap report
    _log("Saving bootstrap report...")
    report_path = save_report(n_entries, alpha, beta_val, params_data, cluster_data)
    _log(f"Wrote {report_path}")

    # Structured output
    result = {
        "status": "success",
        "entries_used": n_entries,
        "mean_reward": round(mean_reward, 4),
        "priors": {"alpha": alpha, "beta": beta_val},
        "clusters": {
            "k": k,
            "sizes": cluster_data["cluster_sizes"],
            "silhouette": cluster_data["bestSilhouette"],
        },
        "files_written": [
            str(BANDIT_STATE_PATH),
            str(LRF_CLUSTERS_PATH),
            snap_path,
            report_path,
        ],
    }
    print(json.dumps(result, indent=2))

    _log("Bootstrap complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
