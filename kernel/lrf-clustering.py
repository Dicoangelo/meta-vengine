#!/usr/bin/env python3
"""
US-107: Contextual LRF — Query Context Clustering

Clusters routing decisions by context so each cluster can have locally
optimized weights (Optimas Local Reward Function).

Context features: graphComplexity, sessionType (8 types), timeOfDay (5 modes), domain.
K-means clustering with k=5.
Per-cluster weight preferences: which configs produced highest rewards.
"""

import json
import math
import random
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).parent.parent
CLUSTERS_PATH = BASE_DIR / "data" / "lrf-clusters.json"
HISTORY_PATH = BASE_DIR / "data" / "bandit-history.jsonl"
DQ_SCORES_PATH = BASE_DIR / "kernel" / "dq-scores.jsonl"
LRF_REPORTS_DIR = BASE_DIR / "data" / "lrf-reports"

# Silhouette guard: reject new k if score drops more than this fraction
SILHOUETTE_DROP_THRESHOLD = 0.15

# Session types from pattern-detector.js
SESSION_TYPES = [
    "debugging", "research", "architecture", "refactoring",
    "testing", "docs", "exploration", "creative"
]

# Cognitive OS time-of-day modes
TIME_MODES = ["morning", "peak", "dip", "evening", "deep_night"]


def _session_type_vector(session_type: str) -> list[float]:
    """One-hot encode session type."""
    vec = [0.0] * len(SESSION_TYPES)
    if session_type in SESSION_TYPES:
        vec[SESSION_TYPES.index(session_type)] = 1.0
    return vec


def _time_mode_vector(mode: str) -> list[float]:
    """One-hot encode time mode."""
    vec = [0.0] * len(TIME_MODES)
    if mode in TIME_MODES:
        vec[TIME_MODES.index(mode)] = 1.0
    return vec


def _hour_to_mode(hour: int) -> str:
    """Map hour to cognitive mode."""
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


def extract_features(decision: dict) -> list[float]:
    """Extract feature vector from a routing decision record.

    Returns a 14-dimensional vector:
      [0]     graphComplexity (float, 0-1)
      [1:9]   sessionType one-hot (8 dims)
      [9:14]  timeOfDay one-hot (5 dims)
    """
    complexity = decision.get("adjusted_complexity", decision.get("complexity", 0.5))
    session_type = decision.get("session_type", "exploration")
    ts = decision.get("ts", 0)

    if ts > 1e12:
        ts = ts / 1000  # Convert ms to seconds
    hour = datetime.fromtimestamp(ts).hour if ts > 0 else 12

    features = [float(complexity)]
    features.extend(_session_type_vector(session_type))
    features.extend(_time_mode_vector(_hour_to_mode(hour)))
    return features


def _euclidean(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _mean_vector(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        return []
    dim = len(vectors[0])
    return [sum(v[i] for v in vectors) / len(vectors) for i in range(dim)]


def _get_k_from_registry() -> int:
    """Load kClusters from param registry, defaulting to 5 if unavailable."""
    try:
        from kernel.param_registry import get_registry
        p = get_registry().get_param('kClusters')
        return int(p['value'])
    except Exception:
        return 5


def silhouette_score(features: list[list[float]], assignments: list[int], k: int) -> float:
    """Pure Python silhouette score (no external deps).

    For each point: compute mean intra-cluster distance (a) and mean
    nearest-cluster distance (b). Silhouette = (b - a) / max(a, b).
    Average over all points. Subsamples to 500 if dataset > 500.
    """
    n = len(features)
    if n <= 1 or k <= 1:
        return 0.0

    # Subsample for performance
    if n > 500:
        indices = random.sample(range(n), 500)
    else:
        indices = list(range(n))

    # Build cluster membership index
    cluster_members: dict[int, list[int]] = {}
    for i in range(n):
        cluster_members.setdefault(assignments[i], []).append(i)

    total = 0.0
    count = 0
    for idx in indices:
        ci = assignments[idx]
        same = [j for j in cluster_members.get(ci, []) if j != idx]

        # Mean intra-cluster distance (a)
        if not same:
            a = 0.0
        else:
            a = sum(_euclidean(features[idx], features[j]) for j in same) / len(same)

        # Mean nearest-cluster distance (b)
        b = float('inf')
        for ck in range(k):
            if ck == ci:
                continue
            members = cluster_members.get(ck, [])
            if not members:
                continue
            mean_dist = sum(_euclidean(features[idx], features[j]) for j in members) / len(members)
            if mean_dist < b:
                b = mean_dist

        if b == float('inf'):
            b = 0.0

        denom = max(a, b)
        if denom > 0:
            total += (b - a) / denom
        count += 1

    return total / count if count > 0 else 0.0


class ContextualLRF:
    """K-means clustering of routing decisions for per-context weight optimization."""

    def __init__(self, k: int | None = None, clusters_path: Path | None = None):
        self.k = k if k is not None else _get_k_from_registry()
        self.clusters_path = clusters_path or CLUSTERS_PATH
        self.centroids: list[list[float]] = []
        self.cluster_weights: list[dict[str, float]] = []
        self.cluster_sizes: list[int] = []
        self.cluster_avg_rewards: list[float] = []
        self.best_silhouette: float | None = None
        self._loaded = False
        self._try_load()

    def _try_load(self) -> None:
        """Load existing clusters if available."""
        if self.clusters_path.exists():
            try:
                data = json.loads(self.clusters_path.read_text())
                self.centroids = data.get("centroids", [])
                self.cluster_weights = data.get("cluster_weights", [])
                self.cluster_sizes = data.get("cluster_sizes", [])
                self.cluster_avg_rewards = data.get("cluster_avg_rewards", [])
                self.best_silhouette = data.get("bestSilhouette")
                self.k = len(self.centroids) if self.centroids else self.k
                self._loaded = bool(self.centroids)
            except (json.JSONDecodeError, KeyError):
                pass

    def fit(self, decisions: list[dict], max_iter: int = 50) -> dict[str, Any]:
        """Run k-means on routing decisions.

        Args:
            decisions: list of routing decision dicts with features + reward
            max_iter: maximum k-means iterations

        Returns:
            dict with cluster info, or rejection info if silhouette guard triggered
        """
        if len(decisions) < self.k:
            raise ValueError(f"Need at least {self.k} decisions, got {len(decisions)}")

        features = [extract_features(d) for d in decisions]
        rewards = [d.get("reward", 0.5) for d in decisions]
        weights_used = [d.get("perturbed_weights", {}) for d in decisions]

        # Save previous state for potential rollback
        prev_centroids = list(self.centroids)
        prev_k = len(prev_centroids) if prev_centroids else self.k
        prev_cluster_weights = list(self.cluster_weights)
        prev_cluster_sizes = list(self.cluster_sizes)
        prev_cluster_avg_rewards = list(self.cluster_avg_rewards)
        prev_best_silhouette = self.best_silhouette

        # Run k-means with current k
        centroids, assignments = self._run_kmeans(features, self.k, max_iter)

        # Compute silhouette score
        score = silhouette_score(features, assignments, self.k)

        # Silhouette guard: reject if score drops >15% from best known
        if self.best_silhouette is not None and self.best_silhouette > 0:
            drop = (self.best_silhouette - score) / self.best_silhouette
            if drop > SILHOUETTE_DROP_THRESHOLD:
                # Log rejection
                self._log_rejection(score, self.best_silhouette, self.k, prev_k)

                # Revert: re-cluster with previous k if different
                if prev_k != self.k and prev_centroids:
                    self.k = prev_k
                    centroids, assignments = self._run_kmeans(features, self.k, max_iter)
                    self.centroids = centroids
                    self._compute_cluster_metrics(
                        features, assignments, rewards, weights_used
                    )
                else:
                    # Restore previous state entirely
                    self.centroids = prev_centroids
                    self.cluster_weights = prev_cluster_weights
                    self.cluster_sizes = prev_cluster_sizes
                    self.cluster_avg_rewards = prev_cluster_avg_rewards
                self.best_silhouette = prev_best_silhouette

                return {
                    "rejected": True,
                    "reason": f"silhouette drop {drop:.1%} > {SILHOUETTE_DROP_THRESHOLD:.0%} threshold",
                    "attempted_k": self.k if prev_k == self.k else prev_k,
                    "reverted_k": self.k,
                    "score": score,
                    "bestSilhouette": self.best_silhouette,
                }

        # Accept: update state
        self.centroids = centroids
        self._compute_cluster_metrics(features, assignments, rewards, weights_used)

        # Update best silhouette if new score is higher (or first run)
        if self.best_silhouette is None or score > self.best_silhouette:
            self.best_silhouette = score

        self._loaded = True
        summary = self._summary()
        summary["silhouette"] = score
        return summary

    def _run_kmeans(
        self, features: list[list[float]], k: int, max_iter: int
    ) -> tuple[list[list[float]], list[int]]:
        """Run k-means and return (centroids, assignments)."""
        centroids = self._kmeans_pp_init_with_k(features, k)
        assignments = [0] * len(features)
        for _ in range(max_iter):
            new_assignments = [
                min(range(len(centroids)), key=lambda c: _euclidean(f, centroids[c]))
                for f in features
            ]
            if new_assignments == assignments:
                break
            assignments = new_assignments
            for c in range(k):
                members = [features[i] for i in range(len(features)) if assignments[i] == c]
                if members:
                    centroids[c] = _mean_vector(members)
        return centroids, assignments

    def _compute_cluster_metrics(
        self,
        features: list[list[float]],
        assignments: list[int],
        rewards: list[float],
        weights_used: list[dict],
    ) -> None:
        """Compute per-cluster sizes, avg rewards, and best weights."""
        self.cluster_sizes = [0] * self.k
        self.cluster_avg_rewards = [0.0] * self.k
        cluster_best_weights: list[list[tuple[float, dict]]] = [[] for _ in range(self.k)]

        for i, c in enumerate(assignments):
            self.cluster_sizes[c] += 1
            cluster_best_weights[c].append((rewards[i], weights_used[i]))

        self.cluster_weights = []
        for c in range(self.k):
            entries = cluster_best_weights[c]
            if entries:
                self.cluster_avg_rewards[c] = sum(r for r, _ in entries) / len(entries)
                entries.sort(key=lambda x: x[0], reverse=True)
                top_n = max(1, len(entries) // 5)
                top_weights = [w for _, w in entries[:top_n] if w]
                if top_weights:
                    avg_weights: dict[str, list[float]] = {}
                    for tw in top_weights:
                        for pid, val in tw.items():
                            avg_weights.setdefault(pid, []).append(val)
                    self.cluster_weights.append(
                        {pid: sum(vals) / len(vals) for pid, vals in avg_weights.items()}
                    )
                else:
                    self.cluster_weights.append({})
            else:
                self.cluster_avg_rewards[c] = 0.0
                self.cluster_weights.append({})

    def _log_rejection(
        self, score: float, best: float, attempted_k: int, prev_k: int
    ) -> None:
        """Log a silhouette guard rejection to data/lrf-reports/."""
        LRF_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        report = {
            "event": "silhouette_guard_rejection",
            "timestamp": datetime.now().isoformat(),
            "attempted_k": attempted_k,
            "reverted_k": prev_k,
            "silhouette_score": round(score, 6),
            "best_silhouette": round(best, 6),
            "drop_pct": round((best - score) / best * 100, 2),
            "threshold_pct": SILHOUETTE_DROP_THRESHOLD * 100,
        }
        report_path = LRF_REPORTS_DIR / f"rejection-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        report_path.write_text(json.dumps(report, indent=2))

    def _kmeans_pp_init(self, features: list[list[float]]) -> list[list[float]]:
        """K-means++ initialization using self.k."""
        return self._kmeans_pp_init_with_k(features, self.k)

    def _kmeans_pp_init_with_k(self, features: list[list[float]], k: int) -> list[list[float]]:
        """K-means++ initialization for a given k."""
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

    def _nearest(self, feature: list[float]) -> int:
        """Find nearest centroid index."""
        return min(range(len(self.centroids)), key=lambda c: _euclidean(feature, self.centroids[c]))

    def classify(self, decision: dict) -> int:
        """Classify a single decision into a cluster.

        Returns cluster index, or -1 if no clusters loaded.
        """
        if not self._loaded or not self.centroids:
            return -1
        features = extract_features(decision)
        return self._nearest(features)

    def get_cluster_weights(self, cluster_idx: int) -> dict[str, float]:
        """Get optimal weight bias for a cluster.

        Returns empty dict if cluster not found or no weights available.
        """
        if 0 <= cluster_idx < len(self.cluster_weights):
            return dict(self.cluster_weights[cluster_idx])
        return {}

    @staticmethod
    def _compute_cluster_exploration_rate(decision_count: int, global_floor: float = 0.05) -> float:
        """Compute per-cluster exploration rate from decision count.

        Matches the tier rules in bandit-engine.js getExplorationRate():
          <50 decisions  → max(0.15, globalFloor)  (forced exploration)
          50–200         → max(0.08, globalFloor)   (moderate)
          >200           → globalFloor              (mature, exploit)
        """
        if decision_count < 50:
            return max(0.15, global_floor)
        elif decision_count <= 200:
            return max(0.08, global_floor)
        else:
            return global_floor

    def _get_global_floor(self) -> float:
        """Load explorationFloorGlobal from param registry."""
        try:
            params_path = BASE_DIR / "config" / "learnable-params.json"
            data = json.loads(params_path.read_text())
            for p in data.get("parameters", []):
                if p.get("id") == "explorationFloorGlobal":
                    return float(p["value"])
        except Exception:
            pass
        return 0.05

    def save(self) -> None:
        """Save clusters to disk, including per-cluster exploration metadata."""
        self.clusters_path.parent.mkdir(parents=True, exist_ok=True)

        global_floor = self._get_global_floor()

        # Build per-cluster entries with decisionCount and exploration rate
        clusters = []
        for i in range(len(self.centroids)):
            dc = self.cluster_sizes[i] if i < len(self.cluster_sizes) else 0
            clusters.append({
                "decisionCount": dc,
                "clusterExplorationRate": round(
                    self._compute_cluster_exploration_rate(dc, global_floor), 4
                ),
            })

        data = {
            "version": "1.2.0",
            "k": self.k,
            "centroids": self.centroids,
            "cluster_weights": self.cluster_weights,
            "cluster_sizes": self.cluster_sizes,
            "cluster_avg_rewards": self.cluster_avg_rewards,
            "clusters": clusters,
            "bestSilhouette": self.best_silhouette,
            "updated": datetime.now().isoformat(),
            "feature_schema": [
                "graphComplexity",
                *[f"sessionType_{t}" for t in SESSION_TYPES],
                *[f"timeMode_{m}" for m in TIME_MODES],
            ],
        }
        self.clusters_path.write_text(json.dumps(data, indent=2))

    def _summary(self) -> dict[str, Any]:
        return {
            "k": self.k,
            "cluster_sizes": self.cluster_sizes,
            "cluster_avg_rewards": self.cluster_avg_rewards,
            "total_decisions": sum(self.cluster_sizes),
        }
